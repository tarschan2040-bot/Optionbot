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
from datetime import datetime, timedelta
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from backend.auth import get_current_user
from data.supabase_client import SupabaseClient

log = logging.getLogger(__name__)
router = APIRouter()


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
    # Metadata
    opened_at: Optional[str] = None
    contracts: int = 1


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
    try:
        # Update status to placed
        supabase._client.table("trade_candidates").update({
            "status": "placed",
            "approved_at": datetime.now().isoformat(),
            "notes": f"Confirmed {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        }).eq("id", candidate_id).eq("user_id", user_id).execute()

        # Fetch the candidate to write to trade_log
        resp = (
            supabase._client.table("trade_candidates")
            .select("*")
            .eq("id", candidate_id)
            .eq("user_id", user_id)
            .single()
            .execute()
        )
        c = resp.data
        if c:
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
            supabase._client.table("trade_log").insert(trade_row).execute()

        return ActionResponse(success=True, message="Trade confirmed and added to portfolio.")
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

        # Build response
        result = []
        today = datetime.now().date()
        for t in trades:
            ticker = t.get("ticker") or ""
            strike = float(t.get("strike") or 0)
            expiry_str = t.get("expiry") or ""
            strategy = t.get("strategy") or ""

            # Calculate current DTE
            dte_now = 0
            if expiry_str:
                try:
                    from datetime import date
                    exp_date = date.fromisoformat(expiry_str)
                    dte_now = max(0, (exp_date - today).days)
                except Exception:
                    dte_now = 0

            # Live data
            ticker_data = live_data.get(ticker, {})
            stock_price = ticker_data.get("price")
            day_change = ticker_data.get("day_change_pct")

            pos_key = f"{strike}-{expiry_str}"
            opt_data = ticker_data.get("options", {}).get(pos_key, {})
            current_option_price = opt_data.get("mid")
            current_iv = opt_data.get("iv")
            current_delta = opt_data.get("delta")
            current_theta = opt_data.get("theta")

            # P&L calculation (for short options: profit = entry - current)
            entry_premium = float(t.get("entry_price") or 0)
            contracts = int(t.get("contracts") or 1)
            pnl_dollars = None
            pnl_percent = None
            if current_option_price is not None and entry_premium > 0:
                pnl_dollars = round((entry_premium - current_option_price) * 100 * contracts, 2)
                pnl_percent = round((entry_premium - current_option_price) / entry_premium * 100, 2)

            result.append(PortfolioPosition(
                id=t["id"],
                ticker=ticker,
                strategy=strategy,
                strike=strike,
                expiry=expiry_str,
                dte_at_entry=int(t.get("dte_at_entry") or 0),
                dte_now=dte_now,
                entry_premium=entry_premium,
                entry_delta=float(t.get("entry_delta") or 0),
                current_stock_price=stock_price,
                current_option_price=current_option_price,
                current_delta=current_delta,
                current_iv=current_iv,
                current_theta=current_theta,
                stock_day_change_pct=day_change,
                pnl_dollars=pnl_dollars,
                pnl_percent=pnl_percent,
                opened_at=t.get("trade_date"),
                contracts=contracts,
            ))

        return result

    except Exception as e:
        log.error("get_portfolio failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to fetch portfolio.")


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
            .single()
            .execute()
        )
        trade = resp.data
        if not trade:
            raise HTTPException(status_code=404, detail="Trade not found.")

        entry_price = float(trade.get("entry_price") or 0)
        contracts = int(trade.get("contracts") or 1)
        exit_price = body.exit_price if body.exit_price is not None else 0.0

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
