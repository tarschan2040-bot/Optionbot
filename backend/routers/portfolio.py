"""
backend/routers/portfolio.py — Portfolio + Candidates endpoints
================================================================
Simplified flow: Star (from dashboard) → Candidates → Confirm → Portfolio

Candidates:
  GET    /portfolio/candidates         — list starred candidates
  POST   /portfolio/candidates/confirm/{id} — confirm → moves to portfolio (placed)
  DELETE /portfolio/candidates/{id}    — remove a starred candidate

Portfolio (live positions):
  GET    /portfolio/positions          — open trades with live market data
  GET    /portfolio/summary            — aggregate P&L, trade counts, performance
"""
import logging
import time
from datetime import datetime, date
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


class PositionItem(BaseModel):
    id: str
    ticker: str
    strategy: str
    strike: float
    expiry: str
    dte_at_entry: int
    dte_now: int
    entry_premium: float
    entry_delta: float
    placed_at: str
    # Live market data
    current_stock_price: Optional[float] = None
    current_option_price: Optional[float] = None
    current_delta: Optional[float] = None
    current_iv: Optional[float] = None
    current_theta: Optional[float] = None
    day_change_pct: Optional[float] = None
    # P&L
    pnl_dollar: Optional[float] = None
    pnl_pct: Optional[float] = None


class PortfolioSummary(BaseModel):
    total_open_trades: int
    total_trades_all_time: int
    total_pnl: float
    total_premium_collected: float
    win_rate: Optional[float] = None
    avg_days_held: Optional[float] = None
    best_trade_pnl: Optional[float] = None
    worst_trade_pnl: Optional[float] = None


class ActionResponse(BaseModel):
    success: bool
    message: str


# ── Helpers ───────────────────────────────────────────────────────────────

def _get_supabase() -> SupabaseClient:
    client = SupabaseClient()
    if not client.is_enabled():
        raise HTTPException(status_code=503, detail="Database not available.")
    return client


def _fetch_live_data(ticker: str, strike: float, expiry: str, is_call: bool):
    """
    Fetch current stock price, option price, and Greeks for a position.
    Uses yfinance. Returns dict with live data or empty values on failure.
    """
    result = {
        "current_stock_price": None,
        "current_option_price": None,
        "current_delta": None,
        "current_iv": None,
        "current_theta": None,
        "day_change_pct": None,
    }
    try:
        import yfinance as yf

        stock = yf.Ticker(ticker)
        info = stock.fast_info if hasattr(stock, "fast_info") else {}

        # Current stock price + day change
        current_price = getattr(info, "last_price", None)
        prev_close = getattr(info, "previous_close", None)
        if current_price:
            result["current_stock_price"] = round(float(current_price), 2)
            if prev_close and prev_close > 0:
                result["day_change_pct"] = round(
                    ((float(current_price) - float(prev_close)) / float(prev_close)) * 100, 2
                )

        # Try to get current option data
        try:
            # Find the matching expiry in available dates
            exp_dates = stock.options
            target_exp = expiry  # format: YYYY-MM-DD
            if target_exp in exp_dates:
                chain = stock.option_chain(target_exp)
                options_df = chain.calls if is_call else chain.puts
                # Find the closest strike
                match = options_df.iloc[(options_df["strike"] - strike).abs().argsort()[:1]]
                if not match.empty:
                    row = match.iloc[0]
                    mid = (float(row.get("bid", 0)) + float(row.get("ask", 0))) / 2
                    if mid > 0:
                        result["current_option_price"] = round(mid, 4)
                    iv = row.get("impliedVolatility")
                    if iv is not None:
                        result["current_iv"] = round(float(iv), 4)
        except Exception as e:
            log.debug("Option chain fetch failed for %s: %s", ticker, e)

        # Compute approximate current Greeks using Black-Scholes
        if result["current_stock_price"] and result["current_iv"]:
            try:
                from core.greeks import calculate_greeks
                from core.models import OptionContract
                from datetime import datetime as dt

                exp_date = dt.strptime(expiry, "%Y-%m-%d").date()
                dte_now = max((exp_date - date.today()).days, 1)

                contract = OptionContract(
                    ticker=ticker,
                    strike=strike,
                    expiry=exp_date,
                    dte=dte_now,
                    is_call=is_call,
                    bid=result.get("current_option_price") or 0,
                    ask=result.get("current_option_price") or 0,
                    mid=result.get("current_option_price") or 0,
                    underlying_price=result["current_stock_price"],
                    implied_vol=result["current_iv"],
                    volume=0,
                    open_interest=0,
                    spread_pct=0,
                )
                greeks = calculate_greeks(contract)
                result["current_delta"] = round(float(greeks.delta), 4)
                result["current_theta"] = round(float(greeks.theta), 4)
            except Exception as e:
                log.debug("Greeks calc failed for %s: %s", ticker, e)

    except Exception as e:
        log.warning("Live data fetch failed for %s: %s", ticker, e)

    return result


# ── Candidate endpoints ───────────────────────────────────────────────────

@router.get("/candidates", response_model=List[CandidateItem])
async def list_candidates(user_id: str = Depends(get_current_user)):
    """List all starred candidates (not yet confirmed)."""
    supabase = _get_supabase()
    try:
        resp = (
            supabase._client.table("trade_candidates")
            .select("id, ticker, strategy, strike, expiry, dte, delta, premium, score, scan_time")
            .eq("status", "starred")
            .order("scan_time", desc=True)
            .execute()
        )
        return [CandidateItem(**row) for row in (resp.data or [])]
    except Exception as e:
        log.error("list_candidates failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to fetch candidates.")


@router.post("/candidates/star", response_model=ActionResponse)
async def star_candidate(
    body: StarRequest,
    user_id: str = Depends(get_current_user),
):
    """Star a scan result — saves it to candidates."""
    supabase = _get_supabase()
    try:
        row = {
            "ticker": body.ticker,
            "strategy": body.strategy,
            "strike": body.strike,
            "expiry": body.expiry,
            "dte": body.dte,
            "delta": round(body.delta, 4),
            "theta": round(body.theta, 4),
            "premium": round(body.premium, 4),
            "total_premium": round(body.premium * 100, 2),
            "contracts": 1,
            "score": round(body.score, 2),
            "iv_rank": round(body.iv_rank or 0, 2),
            "ann_return": round(body.ann_return or 0, 4),
            "scan_time": datetime.now().isoformat(),
            "status": "starred",
        }
        supabase._client.table("trade_candidates").insert(row).execute()
        return ActionResponse(success=True, message=f"Starred {body.ticker} ${body.strike:.2f}")
    except Exception as e:
        log.error("star_candidate failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to star.")


@router.post("/candidates/confirm/{candidate_id}", response_model=ActionResponse)
async def confirm_candidate(
    candidate_id: str,
    user_id: str = Depends(get_current_user),
):
    """
    Confirm a starred candidate → moves to portfolio as a placed trade.
    Writes to trade_log and updates candidate status.
    """
    supabase = _get_supabase()
    ok = supabase.place_candidate(candidate_id, entry_price=None)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to confirm.")
    return ActionResponse(success=True, message="Trade confirmed and added to portfolio.")


@router.delete("/candidates/{candidate_id}", response_model=ActionResponse)
async def remove_candidate(
    candidate_id: str,
    user_id: str = Depends(get_current_user),
):
    """Remove (reject) a starred candidate."""
    supabase = _get_supabase()
    ok = supabase.reject_candidate(candidate_id)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to remove.")
    return ActionResponse(success=True, message="Candidate removed.")


# ── Portfolio endpoints ───────────────────────────────────────────────────

@router.get("/positions", response_model=List[PositionItem])
async def get_positions(user_id: str = Depends(get_current_user)):
    """
    Get all open (non-closed) trades with live market data.
    Fetches current stock price, option price, Greeks, and P&L for each position.
    """
    supabase = _get_supabase()

    try:
        resp = (
            supabase._client.table("trade_log")
            .select("*")
            .is_("exit_date", "null")
            .order("trade_date", desc=True)
            .execute()
        )
        trades = resp.data or []

        positions = []
        for t in trades:
            ticker = t["ticker"]
            strike = float(t["strike"])
            expiry = t["expiry"]
            is_call = t["strategy"] == "COVERED_CALL"
            entry_premium = float(t.get("entry_price") or t.get("net_premium") or 0)

            # Calculate current DTE
            try:
                exp_date = datetime.strptime(expiry, "%Y-%m-%d").date()
                dte_now = max((exp_date - date.today()).days, 0)
            except Exception:
                dte_now = 0

            # Fetch live data (stock price, option price, Greeks)
            live = _fetch_live_data(ticker, strike, expiry, is_call)

            # Calculate P&L (for option sellers: profit = entry - current)
            pnl_dollar = None
            pnl_pct = None
            current_opt = live.get("current_option_price")
            if current_opt is not None and entry_premium > 0:
                pnl_dollar = round((entry_premium - current_opt) * 100, 2)  # per contract
                pnl_pct = round(((entry_premium - current_opt) / entry_premium) * 100, 2)

            positions.append(PositionItem(
                id=t["id"],
                ticker=ticker,
                strategy=t["strategy"],
                strike=strike,
                expiry=expiry,
                dte_at_entry=int(t.get("dte_at_entry") or 0),
                dte_now=dte_now,
                entry_premium=entry_premium,
                entry_delta=float(t.get("entry_delta") or 0),
                placed_at=t.get("trade_date", ""),
                current_stock_price=live.get("current_stock_price"),
                current_option_price=current_opt,
                current_delta=live.get("current_delta"),
                current_iv=live.get("current_iv"),
                current_theta=live.get("current_theta"),
                day_change_pct=live.get("day_change_pct"),
                pnl_dollar=pnl_dollar,
                pnl_pct=pnl_pct,
            ))

        return positions

    except Exception as e:
        log.error("get_positions failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to fetch positions.")


@router.get("/summary", response_model=PortfolioSummary)
async def get_portfolio_summary(user_id: str = Depends(get_current_user)):
    """
    Aggregate portfolio stats: total P&L, trade counts, win rate, etc.
    Combines open positions (from trade_log) and closed history.
    """
    supabase = _get_supabase()

    try:
        # All trades (open + closed)
        resp = (
            supabase._client.table("trade_log")
            .select("*")
            .order("trade_date", desc=True)
            .execute()
        )
        all_trades = resp.data or []

        open_trades = [t for t in all_trades if not t.get("exit_date")]
        closed_trades = [t for t in all_trades if t.get("exit_date")]

        # Total premium collected
        total_premium = sum(float(t.get("net_premium") or 0) for t in all_trades)

        # Closed trade stats
        total_pnl = sum(float(t.get("pnl") or 0) for t in closed_trades)
        wins = [t for t in closed_trades if (t.get("pnl") or 0) > 0]
        win_rate = (len(wins) / len(closed_trades) * 100) if closed_trades else None

        # Average days held
        days_held = []
        for t in closed_trades:
            try:
                entry = datetime.strptime(t["trade_date"], "%Y-%m-%d")
                exit_d = datetime.strptime(t["exit_date"], "%Y-%m-%d")
                days_held.append((exit_d - entry).days)
            except Exception:
                pass
        avg_days = sum(days_held) / len(days_held) if days_held else None

        # Best/worst
        pnls = [float(t.get("pnl") or 0) for t in closed_trades]
        best = max(pnls) if pnls else None
        worst = min(pnls) if pnls else None

        return PortfolioSummary(
            total_open_trades=len(open_trades),
            total_trades_all_time=len(all_trades),
            total_pnl=round(total_pnl, 2),
            total_premium_collected=round(total_premium, 2),
            win_rate=round(win_rate, 1) if win_rate is not None else None,
            avg_days_held=round(avg_days, 1) if avg_days is not None else None,
            best_trade_pnl=round(best, 2) if best is not None else None,
            worst_trade_pnl=round(worst, 2) if worst is not None else None,
        )

    except Exception as e:
        log.error("get_portfolio_summary failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to fetch summary.")
