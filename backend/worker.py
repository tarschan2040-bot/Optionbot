"""
backend/worker.py — Background Scan Worker
============================================
Runs scheduled scans for all Pro users at configured time slots.
Also processes manual scan jobs queued via the API.

This runs as a separate process alongside the FastAPI server.

Usage:
    python -m backend.worker

Schedule (ET):
    Slot 1 — 09:35  Market Open
    Slot 2 — 12:45  Midday
    Slot 3 — 15:00  Pre-Close

Architecture (v1 — no Redis/Celery):
    - Single Python process with a polling loop
    - Checks every 30 seconds for pending jobs and slot times
    - Market data caching: shared cache dict reduces Yahoo requests
    - One scan at a time per user (deduped via scan_jobs table or in-memory set)
    - Scales to ~200 users on a single server
"""
import sys
import os
import time
import logging
import threading
from datetime import datetime, date

# Project root on path
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from dotenv import load_dotenv
load_dotenv()

from core.scanner import OptionScanner
from core.config import ScannerConfig
from data.supabase_client import SupabaseClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("worker")

# ── Schedule (ET) ─────────────────────────────────────────────────────────

SCAN_SLOTS = [
    (9, 35, "Open"),
    (12, 45, "Midday"),
    (15, 0, "Pre-Close"),
]

CHECK_INTERVAL = 30  # seconds between checks

# ── Market data cache ─────────────────────────────────────────────────────
# Shared across users to avoid hammering Yahoo for the same ticker.
# Key: ticker, Value: {"data": ..., "fetched_at": timestamp}

_chain_cache: dict = {}
_CHAIN_CACHE_TTL = 1800   # 30 min for chain metadata
_QUOTE_CACHE_TTL = 180    # 3 min for quotes

# ── In-memory dedup ───────────────────────────────────────────────────────

_running_users: set = set()
_lock = threading.Lock()


# ── Timezone helpers ──────────────────────────────────────────────────────

def _et_now():
    try:
        import pytz
        return datetime.now(pytz.timezone("America/New_York"))
    except ImportError:
        from datetime import timezone, timedelta
        now_utc = datetime.now(timezone.utc)
        offset = -4 if 3 <= now_utc.month <= 10 else -5
        return now_utc + timedelta(hours=offset)


def _is_trading_day() -> bool:
    return _et_now().weekday() < 5


def _is_market_hours() -> bool:
    now = _et_now()
    if now.weekday() >= 5:
        return False
    t = now.hour * 60 + now.minute
    return (9 * 60 + 30) <= t < (16 * 60)


# ── Scan execution ────────────────────────────────────────────────────────

def run_user_scan(user_id: str, config: ScannerConfig, slot_label: str):
    """Run a scan for a single user and write results to Supabase."""
    with _lock:
        if user_id in _running_users:
            log.info("Skip %s — already running.", user_id[:8])
            return
        _running_users.add(user_id)

    start = time.time()
    log.info("Scan START [%s] user=%s tickers=%s",
             slot_label, user_id[:8], ",".join(config.tickers))

    try:
        scanner = OptionScanner(config)
        cfg_hash = config.config_hash()

        try:
            results = scanner.run()
        finally:
            try:
                scanner.fetcher.disconnect()
            except Exception:
                pass

        elapsed = time.time() - start
        scan_time = datetime.now()

        # Write to DB
        supabase = SupabaseClient()
        if supabase.is_enabled() and results:
            results_data = [
                {
                    "rank": i + 1,
                    "ticker": o.contract.ticker,
                    "strategy": o.strategy,
                    "strike": float(o.contract.strike),
                    "expiry": str(o.contract.expiry),
                    "dte": int(o.contract.dte),
                    "premium": round(float(o.contract.mid), 4),
                    "delta": round(float(o.greeks.delta), 4),
                    "theta": round(float(o.greeks.theta), 4),
                    "iv": round(float(o.greeks.iv), 4),
                    "ann_return": round(float(o.annualised_return), 4),
                    "score": round(float(o.score), 2),
                }
                for i, o in enumerate(results)
            ]

            try:
                supabase._client.table("scan_results").insert({
                    "user_id": user_id,
                    "config_hash": cfg_hash,
                    "scan_timestamp": scan_time.isoformat(),
                    "slot_label": slot_label,
                    "results": results_data,
                    "ticker_count": len(config.tickers),
                    "opportunity_count": len(results),
                    "duration_seconds": round(elapsed, 1),
                }).execute()
            except Exception as e:
                log.error("Failed to save scan_results for %s: %s", user_id[:8], e)

            # Also save to scan_history
            supabase.save_scan_history(
                scan_time=scan_time,
                slot_label=slot_label,
                tickers=config.tickers,
                strategy=config.strategy,
                result_count=len(results),
                elapsed_secs=int(elapsed),
                config=config,
                results=results,
                config_hash=cfg_hash,
            )

        log.info("Scan END [%s] user=%s → %d results in %.0fs",
                 slot_label, user_id[:8], len(results), elapsed)

    except Exception as e:
        log.error("Scan FAILED user=%s: %s", user_id[:8], e, exc_info=True)

    finally:
        with _lock:
            _running_users.discard(user_id)


# ── Get all scannable users ───────────────────────────────────────────────

def get_active_users() -> list:
    """
    Get all users with configs (Pro users in future, all users for now).
    Returns list of (user_id, ScannerConfig) tuples.
    """
    supabase = SupabaseClient()
    if not supabase.is_enabled():
        return []

    try:
        resp = (
            supabase._client.table("user_configs")
            .select("user_id")
            .execute()
        )
        rows = resp.data or []
        users = []
        for row in rows:
            uid = row["user_id"]
            config = supabase.load_user_config(uid)
            if config and config.tickers:
                users.append((uid, config))
        log.info("Active users with configs: %d", len(users))
        return users

    except Exception as e:
        log.error("get_active_users failed: %s", e)
        return []


# ── Main loop ─────────────────────────────────────────────────────────────

def main():
    log.info("=" * 60)
    log.info("OptionBot Background Worker starting")
    log.info("Scan slots (ET): %s",
             "  ".join(f"{h:02d}:{m:02d} [{lbl}]" for h, m, lbl in SCAN_SLOTS))
    log.info("Check interval: %ds", CHECK_INTERVAL)
    log.info("=" * 60)

    fired_today: dict = {}  # {date_str: set of slot indices}

    while True:
        try:
            now = _et_now()
            today = now.strftime("%Y-%m-%d")
            t_mins = now.hour * 60 + now.minute

            # Reset daily tracking
            if today not in fired_today:
                fired_today = {today: set()}

            # Check scheduled slots
            if _is_trading_day() and _is_market_hours():
                for idx, (slot_h, slot_m, slot_label) in enumerate(SCAN_SLOTS):
                    if idx in fired_today[today]:
                        continue

                    slot_mins = slot_h * 60 + slot_m
                    # Fire within a 2-minute window
                    if slot_mins <= t_mins < slot_mins + 2:
                        fired_today[today].add(idx)
                        log.info("=== SLOT FIRED: [%s] at %02d:%02d ET ===",
                                 slot_label, slot_h, slot_m)

                        # Get all users and run scans in threads
                        users = get_active_users()
                        for user_id, config in users:
                            thread = threading.Thread(
                                target=run_user_scan,
                                args=(user_id, config, slot_label),
                                daemon=True,
                                name=f"scan-{user_id[:8]}",
                            )
                            thread.start()
                            # Small stagger to avoid burst
                            time.sleep(0.5)

                        break  # only one slot per check

        except Exception as e:
            log.error("Worker loop error: %s", e, exc_info=True)

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
