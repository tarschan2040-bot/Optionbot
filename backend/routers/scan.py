"""
backend/routers/scan.py — Scan endpoints
==========================================
GET  /scan/results     — latest scan results for authenticated user
GET  /scan/results/:index — single opportunity detail
POST /scan/trigger     — queue a manual scan for authenticated user
GET  /scan/status      — check if a scan is running for this user
GET  /scan/history     — list of past scans with metadata
"""
import logging
import threading
import time
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from backend.auth import get_current_user
from backend.tier import get_tier_info
from core.config import ScannerConfig
from core.scanner import OptionScanner
from data.supabase_client import SupabaseClient

log = logging.getLogger(__name__)
router = APIRouter()


# ── In-memory job tracker (v1 — no Redis/Celery) ─────────────────────────
# Tracks running scans per user to prevent duplicates.
# Phase 3 replaces this with a proper task queue.

_running_scans: dict = {}  # { user_id: True }
_scan_lock = threading.Lock()


# ── Pydantic models ──────────────────────────────────────────────────────

class ScanTriggerRequest(BaseModel):
    """Optional overrides for a manual scan."""
    tickers: Optional[List[str]] = None   # None = use user's configured watchlist
    strategy: Optional[str] = None        # None = use user's configured strategy


class ScanTriggerResponse(BaseModel):
    status: str       # "started" | "already_running" | "error"
    message: str


class ScanResultItem(BaseModel):
    rank: int
    ticker: str
    strategy: str
    strike: float
    expiry: str
    dte: int
    premium: float
    delta: float
    theta: float
    iv: float
    ann_return: float
    score: float


class ScanResultsResponse(BaseModel):
    scan_time: Optional[str]
    slot_label: Optional[str]
    config_hash: Optional[str]
    result_count: int
    results: List[ScanResultItem]
    # Tier info for frontend
    tier: Optional[str] = None
    visible_results: Optional[int] = None   # None = all visible
    scans_remaining: Optional[int] = None
    scans_per_day: Optional[int] = None
    can_scan: bool = True


class ScanHistoryItem(BaseModel):
    scan_time: str
    slot_label: str
    result_count: int
    elapsed_secs: int
    config_hash: Optional[str]
    strategy: str
    tickers: List[str]


# ── Helpers ───────────────────────────────────────────────────────────────

def _get_supabase() -> SupabaseClient:
    client = SupabaseClient()
    if not client.is_enabled():
        raise HTTPException(status_code=503, detail="Database not available.")
    return client


def _run_scan_background(user_id: str, config: ScannerConfig):
    """
    Run a scan in a background thread.
    Writes results to scan_results and scan_history in Supabase.
    """
    start = time.time()
    try:
        scanner = OptionScanner(config)
        cfg_hash = config.config_hash()
        log.info("Scan started for user %s (hash=%s)", user_id, cfg_hash[:12])

        try:
            results = scanner.run()
        finally:
            try:
                scanner.fetcher.disconnect()
            except Exception:
                pass

        elapsed = time.time() - start
        scan_time = datetime.now()

        # Write results to DB
        supabase = SupabaseClient()
        if supabase.is_enabled() and results:
            # Save to scan_results table (per-user results)
            results_data = [
                {
                    "rank":       i + 1,
                    "ticker":     o.contract.ticker,
                    "strategy":   o.strategy,
                    "strike":     float(o.contract.strike),
                    "expiry":     str(o.contract.expiry),
                    "dte":        int(o.contract.dte),
                    "premium":    round(float(o.contract.mid), 4),
                    "delta":      round(float(o.greeks.delta), 4),
                    "theta":      round(float(o.greeks.theta), 4),
                    "iv":         round(float(o.greeks.iv), 4),
                    "ann_return": round(float(o.annualised_return), 4),
                    "score":      round(float(o.score), 2),
                }
                for i, o in enumerate(results)
            ]

            try:
                supabase._client.table("scan_results").insert({
                    "user_id":           user_id,
                    "config_hash":       cfg_hash,
                    "scan_timestamp":    scan_time.isoformat(),
                    "slot_label":        "Manual",
                    "results":           results_data,
                    "ticker_count":      len(config.tickers),
                    "opportunity_count": len(results),
                    "duration_seconds":  round(elapsed, 1),
                }).execute()
                log.info(
                    "Scan results saved: user=%s, %d results in %.0fs",
                    user_id, len(results), elapsed,
                )
            except Exception as e:
                log.error("Failed to save scan_results: %s", e)

            # Also save to scan_history (full audit trail)
            supabase.save_scan_history(
                scan_time=scan_time,
                slot_label="Manual",
                tickers=config.tickers,
                strategy=config.strategy,
                result_count=len(results),
                elapsed_secs=int(elapsed),
                config=config,
                results=results,
                config_hash=cfg_hash,
            )

        log.info(
            "Scan complete for user %s: %d results in %.0fs",
            user_id, len(results), elapsed,
        )

    except Exception as e:
        log.error("Scan failed for user %s: %s", user_id, e, exc_info=True)

    finally:
        with _scan_lock:
            _running_scans.pop(user_id, None)


# ── Endpoints ─────────────────────────────────────────────────────────────

@router.get("/results", response_model=ScanResultsResponse)
async def get_scan_results(tier_info: dict = Depends(get_tier_info)):
    """
    Get the most recent scan results for the authenticated user.
    Returns all results but marks how many are visible based on tier.
    """
    user_id = tier_info["user_id"]
    visible_limit = tier_info["visible_results"]  # None = all, 3 for free
    supabase = _get_supabase()

    try:
        resp = (
            supabase._client.table("scan_results")
            .select("*")
            .eq("user_id", user_id)
            .order("scan_timestamp", desc=True)
            .limit(1)
            .execute()
        )
        rows = resp.data or []
        if not rows:
            return ScanResultsResponse(
                scan_time=None, slot_label=None, config_hash=None,
                result_count=0, results=[],
                tier=tier_info["tier"],
                visible_results=visible_limit,
                scans_remaining=tier_info["scans_remaining"],
                scans_per_day=tier_info["scans_per_day"],
                can_scan=tier_info["can_scan"],
            )

        row = rows[0]
        raw_results = row.get("results", [])
        total_count = row.get("opportunity_count", len(raw_results))

        # Return ALL results — frontend handles blurring
        return ScanResultsResponse(
            scan_time=row.get("scan_timestamp"),
            slot_label=row.get("slot_label"),
            config_hash=row.get("config_hash"),
            result_count=total_count,
            results=[ScanResultItem(**r) for r in raw_results],
            tier=tier_info["tier"],
            visible_results=visible_limit,
            scans_remaining=tier_info["scans_remaining"],
            scans_per_day=tier_info["scans_per_day"],
            can_scan=tier_info["can_scan"],
        )

    except Exception as e:
        log.error("get_scan_results failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to fetch results.")


@router.post("/trigger", response_model=ScanTriggerResponse)
async def trigger_scan(
    body: ScanTriggerRequest = ScanTriggerRequest(),
    tier_info: dict = Depends(get_tier_info),
):
    """
    Trigger a manual scan. All tiers can scan, with daily limits.
    Free: 3/day, Pro: 30/day, Max: unlimited.
    """
    user_id = tier_info["user_id"]

    if not tier_info["can_scan"]:
        limit = tier_info["scans_per_day"]
        raise HTTPException(
            status_code=429,
            detail=f"Daily scan limit reached ({limit}/{limit}). Upgrade for more scans.",
        )

    # Check for duplicate
    with _scan_lock:
        if user_id in _running_scans:
            return ScanTriggerResponse(
                status="already_running",
                message="A scan is already running. Check back shortly.",
            )
        _running_scans[user_id] = True

    # Load user config
    supabase = _get_supabase()
    config = supabase.ensure_user_config(user_id)

    # Apply request overrides
    if body.tickers:
        config.tickers = body.tickers
    if body.strategy:
        config.strategy = body.strategy

    # Start scan in background thread
    thread = threading.Thread(
        target=_run_scan_background,
        args=(user_id, config),
        daemon=True,
        name=f"scan-{user_id[:8]}",
    )
    thread.start()

    return ScanTriggerResponse(
        status="started",
        message=f"Scan started for {len(config.tickers)} ticker(s). Results will appear shortly.",
    )


class ScanStatusResponse(BaseModel):
    running: bool
    message: str


@router.get("/status", response_model=ScanStatusResponse)
async def get_scan_status(user_id: str = Depends(get_current_user)):
    """Check if a scan is currently running for this user."""
    with _scan_lock:
        running = user_id in _running_scans
    return ScanStatusResponse(
        running=running,
        message="Scan in progress..." if running else "No scan running.",
    )


@router.get("/results/{index}", response_model=ScanResultItem)
async def get_scan_result_detail(
    index: int,
    user_id: str = Depends(get_current_user),
):
    """
    Get a single opportunity by its rank index (1-based).
    Returns full detail for the opportunity card view.
    """
    supabase = _get_supabase()

    try:
        resp = (
            supabase._client.table("scan_results")
            .select("results")
            .eq("user_id", user_id)
            .order("scan_timestamp", desc=True)
            .limit(1)
            .execute()
        )
        rows = resp.data or []
        if not rows:
            raise HTTPException(status_code=404, detail="No scan results found.")

        results = rows[0].get("results", [])
        # index is 1-based rank
        if index < 1 or index > len(results):
            raise HTTPException(
                status_code=404,
                detail=f"Opportunity #{index} not found. {len(results)} results available.",
            )

        return ScanResultItem(**results[index - 1])

    except HTTPException:
        raise
    except Exception as e:
        log.error("get_scan_result_detail failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to fetch detail.")


@router.get("/history", response_model=List[ScanHistoryItem])
async def get_scan_history(
    limit: int = Query(default=10, le=50),
    user_id: str = Depends(get_current_user),
):
    """
    List recent scan history for the authenticated user.
    Returns metadata only (not full results) — use /scan/results for detailed data.
    """
    supabase = _get_supabase()

    try:
        resp = (
            supabase._client.table("scan_results")
            .select("scan_timestamp, slot_label, opportunity_count, duration_seconds, config_hash, ticker_count")
            .eq("user_id", user_id)
            .order("scan_timestamp", desc=True)
            .limit(limit)
            .execute()
        )
        rows = resp.data or []
        return [
            ScanHistoryItem(
                scan_time=r.get("scan_timestamp", ""),
                slot_label=r.get("slot_label", ""),
                result_count=r.get("opportunity_count", 0),
                elapsed_secs=int(r.get("duration_seconds", 0)),
                config_hash=r.get("config_hash"),
                strategy="",     # not stored in scan_results, lightweight endpoint
                tickers=[],      # same — full details in /scan/results
            )
            for r in rows
        ]

    except Exception as e:
        log.error("get_scan_history failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to fetch history.")
