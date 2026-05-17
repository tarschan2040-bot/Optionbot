"""
backend/routers/candidates.py — Simplified candidate + portfolio workflow
==========================================================================
Flow: Star (from scan) → Candidates list → Confirm → Portfolio (active trades)

Candidates page:  GET  /candidates           — list starred candidates
                  POST /candidates/star       — star from scan results
                  POST /candidates/{id}/confirm — move to portfolio (active trade)
                  DELETE /candidates/{id}      — remove candidate

Portfolio page:   GET  /candidates/portfolio       — active trades with live market data
                  GET  /candidates/portfolio/summary — P&L summary and stats
                  POST /candidates/{id}/close       — close a trade (record exit)
"""
import logging
import math
import json
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from backend.auth import get_current_user
from data.supabase_client import SupabaseClient

log = logging.getLogger(__name__)
router = APIRouter()
_OPTION_CHART_CACHE: dict[tuple[str, str, str], List["OptionChartPoint"]] = {}


# ── Pydantic models ──────────────────────────────────────────────────────

class CandidateItem(BaseModel):
    id: str
    ticker: str
    strategy: str
    strike: float
    expiry: str
    dte: int
    delta: float
    premium: float
    score: float
    iv_rank: Optional[float] = None
    ann_return: Optional[float] = None
    status: str
    scan_time: Optional[str] = None


class StarRequest(BaseModel):
    ticker: str
    strategy: str
    strike: float
    expiry: str
    dte: int
    delta: float
    theta: float
    premium: float
    score: float
    iv: float
    iv_rank: Optional[float] = 0
    ann_return: Optional[float] = 0


class CloseRequest(BaseModel):
    exit_price: Optional[float] = None  # option price at close; None = expired worthless ($0)


class UpdateTradeRequest(BaseModel):
    trade_date: Optional[str] = None
    entry_price: Optional[float] = None
    contracts: Optional[int] = None


class RollRequest(BaseModel):
    buyback_price: float
    ticker: str
    strategy: str
    strike: float
    expiry: str
    entry_price: float
    contracts: int = 1
    entry_delta: Optional[float] = None


class OptionChartPoint(BaseModel):
    timestamp: str
    close: float
    volume: Optional[int] = None


class OptionChartResponse(BaseModel):
    symbol: str
    interval: str
    range: str
    delayed: bool = True
    stale: bool = False
    points: List[OptionChartPoint] = []
    error: Optional[str] = None


class ActionResponse(BaseModel):
    success: bool
    message: str


class PortfolioPosition(BaseModel):
    id: str
    ticker: str
    strategy: str
    strike: float
    expiry: str = ""
    dte_at_entry: int = 0
    dte_now: int = 0
    entry_premium: float = 0
    entry_delta: float = 0
    # Live market data
    current_stock_price: Optional[float] = None
    current_option_price: Optional[float] = None
    current_delta: Optional[float] = None
    current_iv: Optional[float] = None
    current_theta: Optional[float] = None
    stock_day_change_pct: Optional[float] = None
    # P&L
    pnl_dollars: Optional[float] = None
    pnl_percent: Optional[float] = None
    realized_pnl: Optional[float] = None
    cost_basis: float = 0
    average_price: float = 0
    market_value: Optional[float] = None
    portfolio_percent: Optional[float] = None
    today_change_pct: Optional[float] = None
    # Metadata
    opened_at: Optional[str] = None
    contracts: int = 1
    same_contracts: int = 1
    option_type: str = "Call"
    option_label: str = ""
    exit_date: Optional[str] = None
    exit_price: Optional[float] = None
    status: str = "open"
    is_expired: bool = False


class PortfolioSummary(BaseModel):
    total_open_trades: int
    total_trades_all_time: int
    total_closed_trades: int
    # P&L
    total_pnl: Optional[float] = None
    total_premium_collected: float
    # Performance
    win_count: int
    loss_count: int
    win_rate: Optional[float] = None
    avg_return_pct: Optional[float] = None
    best_trade_pnl: Optional[float] = None
    worst_trade_pnl: Optional[float] = None


# ── Helpers ───────────────────────────────────────────────────────────────

def _get_supabase() -> SupabaseClient:
    client = SupabaseClient()
    if not client.is_enabled():
        raise HTTPException(status_code=503, detail="Database not available.")
    return client


def _fetch_live_data(positions: list) -> dict:
    """
    Fetch current stock prices, option data for portfolio positions.
    Returns dict keyed by ticker with market data.
    Uses yfinance — same as the scanner.
    """
    if not positions:
        return {}

    tickers = list(set(p["ticker"] for p in positions))
    result = {}

    try:
        import yfinance as yf

        for ticker_sym in tickers:
            try:
                tk = yf.Ticker(ticker_sym)
                # Current stock price + daily change
                hist = tk.history(period="2d")
                if len(hist) >= 1:
                    current_price = float(hist["Close"].iloc[-1])
                    prev_close = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else current_price
                    day_change_pct = ((current_price - prev_close) / prev_close * 100) if prev_close else 0
                else:
                    current_price = None
                    day_change_pct = None

                # Get option chain for matching strikes
                option_data = {}
                try:
                    expiry_dates = tk.options  # list of 'YYYY-MM-DD' strings
                    ticker_positions = [p for p in positions if p["ticker"] == ticker_sym]

                    for pos in ticker_positions:
                        pos_key = f"{pos['strike']}-{pos['expiry']}"
                        target_expiry = str(pos["expiry"]).strip()

                        # Find matching expiry in available chains
                        matched_exp = None
                        for exp_date in expiry_dates:
                            # Match various formats: 'YYYY-MM-DD' vs 'YYYY-MM-DD'
                            if exp_date == target_expiry:
                                matched_exp = exp_date
                                break
                            # Also try without dashes
                            if exp_date.replace("-", "") == target_expiry.replace("-", ""):
                                matched_exp = exp_date
                                break

                        if not matched_exp:
                            log.debug("No matching expiry for %s %s in available: %s",
                                      ticker_sym, target_expiry, expiry_dates[:5])
                            continue

                        chain = tk.option_chain(matched_exp)
                        is_call = pos["strategy"] == "COVERED_CALL"
                        opts = chain.calls if is_call else chain.puts

                        # Match strike within $0.50 tolerance
                        strike_diff = abs(opts["strike"] - pos["strike"])
                        strike_match = opts[strike_diff < 0.50]
                        if not strike_match.empty:
                            # Pick closest strike
                            closest_idx = (abs(strike_match["strike"] - pos["strike"])).idxmin()
                            row = strike_match.loc[closest_idx]

                            bid = float(row.get("bid", 0) or 0)
                            ask = float(row.get("ask", 0) or 0)
                            last = float(row.get("lastPrice", 0) or 0)

                            # Use mid if available, fall back to lastPrice
                            if bid > 0 and ask > 0:
                                price = (bid + ask) / 2
                            elif last > 0:
                                price = last
                            else:
                                price = 0

                            option_data[pos_key] = {
                                "mid": round(price, 4),
                                "iv": float(row.get("impliedVolatility", 0) or 0),
                                "delta": None,
                                "theta": None,
                            }
                            log.info("Option price for %s $%.2f %s: bid=%.2f ask=%.2f last=%.2f → $%.4f",
                                     ticker_sym, pos["strike"], matched_exp, bid, ask, last, price)

                except Exception as e:
                    log.warning("Option chain fetch failed for %s: %s", ticker_sym, e)

                result[ticker_sym] = {
                    "price": current_price,
                    "day_change_pct": round(day_change_pct, 2) if day_change_pct is not None else None,
                    "options": option_data,
                }
            except Exception as e:
                log.warning("Live data fetch failed for %s: %s", ticker_sym, e)
                result[ticker_sym] = {"price": None, "day_change_pct": None, "options": {}}

    except ImportError:
        log.error("yfinance not installed — cannot fetch live data")

    return result


def _option_type_for_strategy(strategy: str) -> str:
    return "Call" if strategy == "COVERED_CALL" else "Put"


def _contract_key(ticker: str, strategy: str, strike: float, expiry: str) -> tuple:
    return (ticker.upper(), strategy, round(float(strike or 0), 4), str(expiry or ""))


def _format_strike(strike: float) -> str:
    if float(strike).is_integer():
        return str(int(strike))
    return f"{strike:.2f}".rstrip("0").rstrip(".")


def _format_option_label(ticker: str, expiry: str, strike: float, strategy: str) -> str:
    try:
        exp_date = datetime.fromisoformat(str(expiry)).date()
        expiry_label = exp_date.strftime("%b %d '%y").upper()
    except Exception:
        expiry_label = str(expiry)
    return f"{ticker.upper()} {expiry_label} {_format_strike(strike)} {_option_type_for_strategy(strategy)}"


def _dte_now(expiry_str: str) -> int:
    if not expiry_str:
        return 0
    try:
        from datetime import date
        exp_date = date.fromisoformat(str(expiry_str))
        return max(0, (exp_date - datetime.now().date()).days)
    except Exception:
        return 0


def _expiry_date(expiry_str: str):
    try:
        from datetime import date
        return date.fromisoformat(str(expiry_str))
    except Exception:
        return None


def _is_expired(expiry_str: str) -> bool:
    exp_date = _expiry_date(expiry_str)
    return bool(exp_date and exp_date < datetime.now().date())


def _yahoo_option_symbol(ticker: str, expiry: str, strike: float, strategy: str) -> str:
    exp_date = _expiry_date(expiry)
    if not exp_date:
        raise ValueError("Invalid expiry date.")
    option_code = "C" if _option_type_for_strategy(strategy) == "Call" else "P"
    strike_code = int(round(float(strike) * 1000))
    return f"{ticker.upper().strip()}{exp_date.strftime('%y%m%d')}{option_code}{strike_code:08d}"


def _fetch_option_chart(symbol: str, interval: str, range_value: str) -> List[OptionChartPoint]:
    url = (
        "https://query1.finance.yahoo.com/v8/finance/chart/"
        f"{urllib.parse.quote(symbol)}?interval={urllib.parse.quote(interval)}&range={urllib.parse.quote(range_value)}"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read())

    chart = data.get("chart", {})
    if chart.get("error"):
        raise ValueError(chart["error"].get("description") or "Option chart unavailable.")

    result = (chart.get("result") or [None])[0]
    if not result:
        return []

    timestamps = result.get("timestamp") or []
    quote = ((result.get("indicators") or {}).get("quote") or [{}])[0]
    closes = quote.get("close") or []
    volumes = quote.get("volume") or []

    points: List[OptionChartPoint] = []
    for idx, ts in enumerate(timestamps):
        if idx >= len(closes) or closes[idx] is None:
            continue
        volume = volumes[idx] if idx < len(volumes) else None
        points.append(OptionChartPoint(
            timestamp=datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat(),
            close=round(float(closes[idx]), 4),
            volume=int(volume) if volume is not None else None,
        ))

    return points


def _same_contract_counts(trades: list) -> dict:
    counts = {}
    for t in trades:
        key = _contract_key(
            t.get("ticker") or "",
            t.get("strategy") or "",
            float(t.get("strike") or 0),
            t.get("expiry") or "",
        )
        counts[key] = counts.get(key, 0) + int(t.get("contracts") or 1)
    return counts


def _total_cost_basis(trades: list) -> float:
    return sum(
        float(t.get("entry_price") or 0) * 100 * int(t.get("contracts") or 1)
        for t in trades
    )


def _position_from_trade(
    trade: dict,
    same_contracts: dict,
    total_cost_basis: float,
    live_data: Optional[dict] = None,
) -> PortfolioPosition:
    ticker = trade.get("ticker") or ""
    strike = float(trade.get("strike") or 0)
    expiry_str = trade.get("expiry") or ""
    strategy = trade.get("strategy") or ""
    contracts = int(trade.get("contracts") or 1)
    entry_premium = float(trade.get("entry_price") or 0)
    cost_basis = round(entry_premium * 100 * contracts, 2)
    is_closed = bool(trade.get("exit_date"))

    ticker_data = (live_data or {}).get(ticker, {})
    stock_price = ticker_data.get("price")
    day_change = ticker_data.get("day_change_pct")
    opt_data = ticker_data.get("options", {}).get(f"{strike}-{expiry_str}", {})

    current_option_price = opt_data.get("mid")
    current_iv = opt_data.get("iv")
    current_delta = opt_data.get("delta")
    current_theta = opt_data.get("theta")

    exit_price = trade.get("exit_price")
    exit_price_value = float(exit_price) if exit_price is not None else None
    realized_pnl = float(trade["pnl"]) if trade.get("pnl") is not None else None
    is_expired = (not is_closed) and _is_expired(expiry_str)

    if is_closed:
        market_value = round(exit_price_value * 100 * contracts, 2) if exit_price_value is not None else None
        pnl_dollars = round(realized_pnl, 2) if realized_pnl is not None else None
        pnl_percent = round(realized_pnl / cost_basis * 100, 2) if realized_pnl is not None and cost_basis > 0 else None
    else:
        market_value = round(current_option_price * 100 * contracts, 2) if current_option_price is not None else None
        pnl_dollars = None
        pnl_percent = None
        if current_option_price is not None and entry_premium > 0:
            pnl_dollars = round((entry_premium - current_option_price) * 100 * contracts, 2)
            pnl_percent = round((entry_premium - current_option_price) / entry_premium * 100, 2)

    return PortfolioPosition(
        id=trade["id"],
        ticker=ticker,
        strategy=strategy,
        strike=strike,
        expiry=expiry_str,
        dte_at_entry=int(trade.get("dte_at_entry") or 0),
        dte_now=0 if is_closed else _dte_now(expiry_str),
        entry_premium=entry_premium,
        entry_delta=float(trade.get("entry_delta") or 0),
        current_stock_price=stock_price,
        current_option_price=current_option_price,
        current_delta=current_delta,
        current_iv=current_iv,
        current_theta=current_theta,
        stock_day_change_pct=day_change,
        pnl_dollars=pnl_dollars,
        pnl_percent=pnl_percent,
        realized_pnl=round(realized_pnl, 2) if realized_pnl is not None else None,
        cost_basis=cost_basis,
        average_price=entry_premium,
        market_value=market_value,
        portfolio_percent=round(cost_basis / total_cost_basis * 100, 2) if total_cost_basis > 0 else None,
        today_change_pct=day_change,
        opened_at=trade.get("trade_date"),
        contracts=contracts,
        same_contracts=same_contracts.get(_contract_key(ticker, strategy, strike, expiry_str), contracts),
        option_type=_option_type_for_strategy(strategy),
        option_label=_format_option_label(ticker, expiry_str, strike, strategy),
        exit_date=trade.get("exit_date"),
        exit_price=exit_price_value,
        status="closed" if is_closed else "open",
        is_expired=is_expired,
    )


# ── Candidates endpoints ──────────────────────────────────────────────────

@router.get("", response_model=List[CandidateItem])
async def list_candidates(
    user_id: str = Depends(get_current_user),
):
    """List all starred (unconfirmed) candidates."""
    supabase = _get_supabase()
    try:
        resp = (
            supabase._client.table("trade_candidates")
            .select("id, ticker, strategy, strike, expiry, dte, delta, premium, score, iv_rank, ann_return, status, scan_time")
            .eq("user_id", user_id)
            .eq("status", "starred")
            .order("scan_time", desc=True)
            .execute()
        )
        return [CandidateItem(**row) for row in (resp.data or [])]
    except Exception as e:
        log.error("list_candidates failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to fetch candidates.")


@router.post("/star", response_model=ActionResponse)
async def star_candidate(
    body: StarRequest,
    user_id: str = Depends(get_current_user),
):
    """Star a scan result — saves it to candidates."""
    supabase = _get_supabase()
    try:
        row = {
            "user_id":       user_id,
            "ticker":        body.ticker,
            "strategy":      body.strategy,
            "strike":        body.strike,
            "expiry":        body.expiry,
            "dte":           body.dte,
            "delta":         round(body.delta, 4),
            "theta":         round(body.theta, 4),
            "premium":       round(body.premium, 4),
            "total_premium": round(body.premium * 100, 2),
            "contracts":     1,
            "score":         round(body.score, 2),
            "iv_rank":       round(body.iv_rank or 0, 2),
            "ann_return":    round(body.ann_return or 0, 4),
            "scan_time":     datetime.now().isoformat(),
            "status":        "starred",
        }
        supabase._client.table("trade_candidates").insert(row).execute()
        return ActionResponse(success=True, message=f"Starred {body.ticker} ${body.strike:.2f}")
    except Exception as e:
        log.error("star_candidate failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to star candidate.")


@router.post("/{candidate_id}/confirm", response_model=ActionResponse)
async def confirm_candidate(
    candidate_id: str,
    user_id: str = Depends(get_current_user),
):
    """Confirm a candidate — moves to portfolio as an active trade."""
    supabase = _get_supabase()
    inserted_trade_id = None
    try:
        # Fetch and validate before writing anything. This avoids marking a
        # candidate as placed if the portfolio insert fails.
        resp = (
            supabase._client.table("trade_candidates")
            .select("*")
            .eq("id", candidate_id)
            .eq("user_id", user_id)
            .single()
            .execute()
        )
        c = resp.data
        if not c:
            raise HTTPException(status_code=404, detail="Candidate not found.")
        if c.get("status") != "starred":
            raise HTTPException(status_code=409, detail="Only starred candidates can be confirmed.")

        trade_row = {
            "user_id":       user_id,
            "trade_date":    datetime.now().strftime("%Y-%m-%d"),
            "ticker":        c["ticker"],
            "strategy":      c["strategy"],
            "strike":        c["strike"],
            "expiry":        c["expiry"],
            "dte_at_entry":  c["dte"],
            "entry_price":   c.get("premium"),
            "contracts":     int(c.get("contracts") or 1),
            "entry_delta":   c.get("delta"),
            "iv_percentile": c.get("iv_rank"),
            "net_premium":   round(float(c.get("premium", 0)) * 100 * int(c.get("contracts") or 1), 2),
            "candidate_id":  candidate_id,
        }

        insert_resp = supabase._client.table("trade_log").insert(trade_row).execute()
        inserted_rows = insert_resp.data or []
        if inserted_rows:
            inserted_trade_id = inserted_rows[0].get("id")

        try:
            supabase._client.table("trade_candidates").update({
                "status": "placed",
                "approved_at": datetime.now().isoformat(),
                "notes": f"Confirmed {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            }).eq("id", candidate_id).eq("user_id", user_id).execute()
        except Exception:
            rollback = (
                supabase._client.table("trade_log")
                .delete()
                .eq("candidate_id", candidate_id)
                .eq("user_id", user_id)
            )
            if inserted_trade_id:
                rollback = rollback.eq("id", inserted_trade_id)
            rollback.execute()
            raise

        return ActionResponse(success=True, message="Trade confirmed and added to portfolio.")
    except HTTPException:
        raise
    except Exception as e:
        log.error("confirm_candidate failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to confirm.")


@router.delete("/{candidate_id}", response_model=ActionResponse)
async def remove_candidate(
    candidate_id: str,
    user_id: str = Depends(get_current_user),
):
    """Remove a starred candidate."""
    supabase = _get_supabase()
    try:
        supabase._client.table("trade_candidates").update(
            {"status": "rejected"}
        ).eq("id", candidate_id).eq("user_id", user_id).execute()
        return ActionResponse(success=True, message="Candidate removed.")
    except Exception as e:
        log.error("remove_candidate failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to remove.")


# ── Portfolio endpoints ───────────────────────────────────────────────────

@router.get("/portfolio", response_model=List[PortfolioPosition])
async def get_portfolio(
    user_id: str = Depends(get_current_user),
):
    """
    Get active (open) trades with live market data.
    Fetches current stock price, option price, daily change, and P&L.
    """
    supabase = _get_supabase()
    try:
        resp = (
            supabase._client.table("trade_log")
            .select("*")
            .eq("user_id", user_id)
            .is_("exit_date", "null")
            .order("trade_date", desc=True)
            .execute()
        )
        trades = resp.data or []
        if not trades:
            return []

        # Build position list for live data fetch
        positions = []
        for t in trades:
            if t.get("ticker") and t.get("expiry"):
                positions.append({
                    "ticker": t["ticker"],
                    "strategy": t.get("strategy") or "",
                    "strike": float(t.get("strike") or 0),
                    "expiry": t["expiry"],
                })

        # Fetch live market data
        live_data = _fetch_live_data(positions)
        same_contracts = _same_contract_counts(trades)
        total_cost_basis = _total_cost_basis(trades)

        return [
            _position_from_trade(t, same_contracts, total_cost_basis, live_data=live_data)
            for t in trades
        ]

    except Exception as e:
        log.error("get_portfolio failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to fetch portfolio.")


@router.get("/portfolio/closed", response_model=List[PortfolioPosition])
async def get_closed_portfolio(
    user_id: str = Depends(get_current_user),
):
    """Get closed trades including expired-worthless or assigned positions once recorded."""
    supabase = _get_supabase()
    try:
        resp = (
            supabase._client.table("trade_log")
            .select("*")
            .eq("user_id", user_id)
            .order("exit_date", desc=True)
            .execute()
        )
        trades = [t for t in (resp.data or []) if t.get("exit_date")]
        if not trades:
            return []

        same_contracts = _same_contract_counts(trades)
        total_cost_basis = _total_cost_basis(trades)
        return [
            _position_from_trade(t, same_contracts, total_cost_basis)
            for t in trades
        ]
    except Exception as e:
        log.error("get_closed_portfolio failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to fetch closed portfolio.")


@router.get("/portfolio/summary", response_model=PortfolioSummary)
async def get_portfolio_summary(
    user_id: str = Depends(get_current_user),
):
    """Portfolio summary: total P&L, trade counts, win rate, performance stats."""
    supabase = _get_supabase()
    try:
        # Open trades
        open_resp = (
            supabase._client.table("trade_log")
            .select("entry_price, contracts, net_premium")
            .eq("user_id", user_id)
            .is_("exit_date", "null")
            .execute()
        )
        open_trades = open_resp.data or []

        # All trades (including closed)
        all_resp = (
            supabase._client.table("trade_log")
            .select("entry_price, exit_price, contracts, net_premium, pnl, exit_date")
            .eq("user_id", user_id)
            .execute()
        )
        all_trades = all_resp.data or []

        closed_trades = [t for t in all_trades if t.get("exit_date")]

        # Calculate stats
        total_premium = sum(float(t.get("net_premium") or 0) for t in all_trades)

        # P&L from closed trades
        total_pnl = None
        win_count = 0
        loss_count = 0
        pnls = []

        for t in closed_trades:
            pnl = t.get("pnl")
            if pnl is not None:
                pnl_val = float(pnl)
                pnls.append(pnl_val)
                if pnl_val >= 0:
                    win_count += 1
                else:
                    loss_count += 1

        if pnls:
            total_pnl = round(sum(pnls), 2)

        total_closed = len(closed_trades)
        win_rate = round(win_count / total_closed * 100, 1) if total_closed > 0 else None

        # Average return as % of premium collected
        avg_return_pct = None
        if pnls and total_premium > 0:
            avg_return_pct = round(sum(pnls) / len(pnls) / (total_premium / len(all_trades)) * 100, 1) if all_trades else None

        return PortfolioSummary(
            total_open_trades=len(open_trades),
            total_trades_all_time=len(all_trades),
            total_closed_trades=total_closed,
            total_pnl=total_pnl,
            total_premium_collected=round(total_premium, 2),
            win_count=win_count,
            loss_count=loss_count,
            win_rate=win_rate,
            avg_return_pct=avg_return_pct,
            best_trade_pnl=round(max(pnls), 2) if pnls else None,
            worst_trade_pnl=round(min(pnls), 2) if pnls else None,
        )

    except Exception as e:
        log.error("get_portfolio_summary failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to fetch summary.")


@router.get("/portfolio/{trade_id}", response_model=PortfolioPosition)
async def get_portfolio_position(
    trade_id: str,
    user_id: str = Depends(get_current_user),
):
    """Get one position with live market data for open trades."""
    supabase = _get_supabase()
    try:
        resp = (
            supabase._client.table("trade_log")
            .select("*")
            .eq("id", trade_id)
            .eq("user_id", user_id)
            .single()
            .execute()
        )
        trade = resp.data
        if not trade:
            raise HTTPException(status_code=404, detail="Trade not found.")

        all_resp = (
            supabase._client.table("trade_log")
            .select("*")
            .eq("user_id", user_id)
            .execute()
        )
        user_trades = all_resp.data or [trade]
        same_contracts = _same_contract_counts(user_trades)
        total_cost_basis = _total_cost_basis(user_trades)

        live_data = {}
        if not trade.get("exit_date") and trade.get("ticker") and trade.get("expiry"):
            live_data = _fetch_live_data([{
                "ticker": trade["ticker"],
                "strategy": trade.get("strategy") or "",
                "strike": float(trade.get("strike") or 0),
                "expiry": trade["expiry"],
            }])

        return _position_from_trade(trade, same_contracts, total_cost_basis, live_data=live_data)
    except HTTPException:
        raise
    except Exception as e:
        log.error("get_portfolio_position failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to fetch position.")


@router.get("/portfolio/{trade_id}/option-chart", response_model=OptionChartResponse)
async def get_portfolio_option_chart(
    trade_id: str,
    interval: str = Query("15m"),
    range: str = Query("5d"),
    user_id: str = Depends(get_current_user),
):
    """
    Best-effort delayed option price chart for the exact contract.

    Yahoo option chart availability varies by contract and market hours. Return
    an empty point list with an error string instead of failing the edit page.
    """
    allowed_intervals = {"5m", "15m", "30m", "1h", "1d"}
    allowed_ranges = {"1d", "5d", "1mo", "3mo", "6mo", "1y"}
    if interval not in allowed_intervals:
        raise HTTPException(status_code=422, detail="Unsupported chart interval.")
    if range not in allowed_ranges:
        raise HTTPException(status_code=422, detail="Unsupported chart range.")

    supabase = _get_supabase()
    resp = (
        supabase._client.table("trade_log")
        .select("ticker, strategy, strike, expiry")
        .eq("id", trade_id)
        .eq("user_id", user_id)
        .single()
        .execute()
    )
    trade = resp.data
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found.")

    try:
        symbol = _yahoo_option_symbol(
            trade.get("ticker") or "",
            trade.get("expiry") or "",
            float(trade.get("strike") or 0),
            trade.get("strategy") or "",
        )
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))

    try:
        points = _fetch_option_chart(symbol, interval, range)
        cache_key = (symbol, interval, range)
        if points:
            _OPTION_CHART_CACHE[cache_key] = points
        else:
            cached = _OPTION_CHART_CACHE.get(cache_key)
            if cached:
                return OptionChartResponse(
                    symbol=symbol,
                    interval=interval,
                    range=range,
                    points=cached,
                    stale=True,
                    error="Using the last available chart because Yahoo returned no new bars.",
                )
        return OptionChartResponse(
            symbol=symbol,
            interval=interval,
            range=range,
            points=points,
            error=None if points else "No option chart bars returned for this contract.",
        )
    except Exception as e:
        log.warning("option chart fetch failed for %s: %s", symbol, e)
        cached = _OPTION_CHART_CACHE.get((symbol, interval, range))
        if cached:
            return OptionChartResponse(
                symbol=symbol,
                interval=interval,
                range=range,
                points=cached,
                stale=True,
                error="Using the last available chart because Yahoo is unavailable right now.",
            )
        return OptionChartResponse(
            symbol=symbol,
            interval=interval,
            range=range,
            points=[],
            error="Option chart is unavailable for this contract right now.",
        )


@router.patch("/portfolio/{trade_id}", response_model=ActionResponse)
async def update_portfolio_position(
    trade_id: str,
    body: UpdateTradeRequest,
    user_id: str = Depends(get_current_user),
):
    """Edit mutable trade fields for an open position."""
    updates = {}
    if body.trade_date is not None:
        try:
            datetime.fromisoformat(str(body.trade_date)).date()
        except Exception:
            raise HTTPException(status_code=422, detail="Entry date must be a valid date.")
        updates["trade_date"] = str(body.trade_date)
    if body.entry_price is not None:
        if not math.isfinite(float(body.entry_price)) or body.entry_price < 0:
            raise HTTPException(status_code=422, detail="Entry price must be zero or greater.")
        updates["entry_price"] = float(body.entry_price)
    if body.contracts is not None:
        if body.contracts < 1:
            raise HTTPException(status_code=422, detail="Contracts must be at least 1.")
        updates["contracts"] = int(body.contracts)

    if not updates:
        raise HTTPException(status_code=422, detail="No editable fields supplied.")

    if "entry_price" in updates or "contracts" in updates:
        resp = (
            _get_supabase()._client.table("trade_log")
            .select("entry_price, contracts")
            .eq("id", trade_id)
            .eq("user_id", user_id)
            .is_("exit_date", "null")
            .single()
            .execute()
        )
        trade = resp.data
        if not trade:
            raise HTTPException(status_code=404, detail="Open trade not found.")
        entry_price = updates.get("entry_price", float(trade.get("entry_price") or 0))
        contracts = updates.get("contracts", int(trade.get("contracts") or 1))
        updates["net_premium"] = round(float(entry_price) * 100 * int(contracts), 2)

    try:
        _get_supabase()._client.table("trade_log").update(updates).eq("id", trade_id).eq(
            "user_id", user_id
        ).is_("exit_date", "null").execute()
        return ActionResponse(success=True, message="Position updated.")
    except Exception as e:
        log.error("update_portfolio_position failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to update position.")


@router.delete("/portfolio/{trade_id}", response_model=ActionResponse)
async def delete_portfolio_position(
    trade_id: str,
    user_id: str = Depends(get_current_user),
):
    """Delete an open trade that was added by mistake."""
    try:
        _get_supabase()._client.table("trade_log").delete().eq("id", trade_id).eq(
            "user_id", user_id
        ).is_("exit_date", "null").execute()
        return ActionResponse(success=True, message="Position deleted.")
    except Exception as e:
        log.error("delete_portfolio_position failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to delete position.")


@router.post("/portfolio/{trade_id}/roll", response_model=ActionResponse)
async def roll_portfolio_position(
    trade_id: str,
    body: RollRequest,
    user_id: str = Depends(get_current_user),
):
    """Close an open position and create the rolled replacement contract."""
    if not math.isfinite(float(body.buyback_price)) or body.buyback_price < 0:
        raise HTTPException(status_code=422, detail="Buyback price must be zero or greater.")
    if not math.isfinite(float(body.entry_price)) or body.entry_price < 0:
        raise HTTPException(status_code=422, detail="New entry price must be zero or greater.")
    if body.contracts < 1:
        raise HTTPException(status_code=422, detail="Contracts must be at least 1.")

    supabase = _get_supabase()
    inserted_trade_id = None
    try:
        resp = (
            supabase._client.table("trade_log")
            .select("*")
            .eq("id", trade_id)
            .eq("user_id", user_id)
            .is_("exit_date", "null")
            .single()
            .execute()
        )
        old_trade = resp.data
        if not old_trade:
            raise HTTPException(status_code=404, detail="Open trade not found.")

        old_entry = float(old_trade.get("entry_price") or 0)
        old_contracts = int(old_trade.get("contracts") or 1)
        pnl = round((old_entry - body.buyback_price) * 100 * old_contracts, 2)

        new_row = {
            "user_id": user_id,
            "trade_date": datetime.now().strftime("%Y-%m-%d"),
            "ticker": body.ticker.upper().strip(),
            "strategy": body.strategy,
            "strike": body.strike,
            "expiry": body.expiry,
            "dte_at_entry": 0,
            "entry_price": body.entry_price,
            "contracts": int(body.contracts),
            "entry_delta": body.entry_delta,
            "net_premium": round(float(body.entry_price) * 100 * int(body.contracts), 2),
            "candidate_id": old_trade.get("candidate_id"),
        }
        insert_resp = supabase._client.table("trade_log").insert(new_row).execute()
        inserted_rows = insert_resp.data or []
        if inserted_rows:
            inserted_trade_id = inserted_rows[0].get("id")

        try:
            supabase._client.table("trade_log").update({
                "exit_date": datetime.now().strftime("%Y-%m-%d"),
                "exit_price": body.buyback_price,
                "pnl": pnl,
            }).eq("id", trade_id).eq("user_id", user_id).is_("exit_date", "null").execute()
        except Exception:
            rollback = supabase._client.table("trade_log").delete().eq("user_id", user_id)
            if inserted_trade_id:
                rollback = rollback.eq("id", inserted_trade_id)
            rollback.execute()
            raise

        return ActionResponse(success=True, message=f"Position rolled. Closed P&L: ${pnl:+.2f}")
    except HTTPException:
        raise
    except Exception as e:
        log.error("roll_portfolio_position failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to roll position.")


@router.post("/{trade_id}/close", response_model=ActionResponse)
async def close_trade(
    trade_id: str,
    body: CloseRequest = CloseRequest(),
    user_id: str = Depends(get_current_user),
):
    """Close an active trade — record exit price and P&L."""
    supabase = _get_supabase()
    try:
        # Fetch the trade
        resp = (
            supabase._client.table("trade_log")
            .select("*")
            .eq("id", trade_id)
            .eq("user_id", user_id)
            .is_("exit_date", "null")
            .single()
            .execute()
        )
        trade = resp.data
        if not trade:
            raise HTTPException(status_code=404, detail="Open trade not found.")

        entry_price = float(trade.get("entry_price") or 0)
        contracts = int(trade.get("contracts") or 1)
        exit_price = body.exit_price if body.exit_price is not None else 0.0
        if not math.isfinite(float(exit_price)) or exit_price < 0:
            raise HTTPException(status_code=422, detail="Exit price must be zero or greater.")

        # P&L for short options: (entry - exit) * 100 * contracts
        pnl = round((entry_price - exit_price) * 100 * contracts, 2)

        supabase._client.table("trade_log").update({
            "exit_date": datetime.now().strftime("%Y-%m-%d"),
            "exit_price": exit_price,
            "pnl": pnl,
        }).eq("id", trade_id).eq("user_id", user_id).execute()

        return ActionResponse(
            success=True,
            message=f"Trade closed. P&L: ${pnl:+.2f}",
        )
    except HTTPException:
        raise
    except Exception as e:
        log.error("close_trade failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to close trade.")
