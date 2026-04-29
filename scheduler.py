"""
scheduler.py — Scan Scheduler + Optional Telegram Bot
=====================================================
Runs the option scanner at three fixed daily time slots. Optionally sends
results to Telegram and starts the Telegram bot listener.

Auto-scan fires at exactly THREE fixed times each trading day (Mon-Fri ET):
  Slot 1 — 09:35  Market Open   (5 min after open, quotes settled)
  Slot 2 — 12:45  Midday        (session midpoint)
  Slot 3 — 15:00  Pre-Close     (1 hour before close, theta fully priced)

Usage:
    py -3.11 scheduler.py                     — run on schedule (3 slots per day)
    py -3.11 scheduler.py --once              — run a single scan now and exit
    py -3.11 scheduler.py --dry-run --once    — test with mock data, no IBKR needed
    py -3.11 scheduler.py --once --no-telegram — scan and print results, no Telegram needed

Telegram commands supported (when Telegram is enabled):
    scan / scan TSLA / scan TSLA AAPL NVDA
    stopscan / cancelscan / lastscan
    results / results 2 / result 5
    score / config / set <param> <value> / set reset
    price SPY / movers / ask <question> / help
"""
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))

import argparse
import logging
import signal
import threading
import time
from datetime import datetime
from typing import List, Optional

from dotenv import load_dotenv
load_dotenv()

from core.scanner import OptionScanner
from core.config import ScannerConfig
from core.models import ScanOpportunity
from output.reporter import Reporter
from data.supabase_client import SupabaseClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("scheduler")

# ── Default watchlist (canonical source — telegram_bot also uses this) ────
DEFAULT_WATCHLIST = ["TSLA", "NVDA"]

# ── Watchlist & strategy defaults ─────────────────────────────────────────
WATCHLIST = list(DEFAULT_WATCHLIST)
STRATEGY  = "both"


# ─────────────────────────────────────────────────────────────────────────
# NullNotifier — drop-in replacement when Telegram is disabled
# ─────────────────────────────────────────────────────────────────────────

class NullNotifier:
    """
    Silent notifier that logs messages instead of sending to Telegram.
    Implements the same public API as TelegramNotifier so run_scan()
    works without any Telegram credentials.
    """
    def send_message(self, text: str) -> bool:
        # Strip Markdown formatting for cleaner log output
        clean = text.replace("*", "").replace("`", "").replace("_", "")
        for line in clean.strip().split("\n"):
            if line.strip():
                log.info("[notifier] %s", line.strip())
        return True

    def send_error(self, text: str) -> bool:
        log.error("[notifier] %s", text)
        return True

    def send_scan_results(self, *args, **kwargs) -> bool:
        return True

    def send_scan_config(self, *args, **kwargs) -> bool:
        return True

# ── Auto-scan schedule (ET, 24h format) ───────────────────────────────────
#   Each slot fires ONCE per trading day.
#   (hour, minute, display_label)
SCAN_SLOTS = [
    ( 9, 35, "Open"),       # 5 min after open — first settled quotes
    (12, 45, "Midday"),     # session midpoint
    (15,  0, "Pre-Close"),  # 1 hour before close
]

# ── Market hours (ET) ─────────────────────────────────────────────────────
MARKET_OPEN_H,  MARKET_OPEN_M  = 9,  30
MARKET_CLOSE_H, MARKET_CLOSE_M = 16,  0


# ─────────────────────────────────────────────────────────────────────────
# Timezone helpers
# ─────────────────────────────────────────────────────────────────────────

def _et_now():
    """Return current datetime in US/Eastern, DST-aware.
    Uses pytz if installed (accurate), falls back to month-based offset."""
    try:
        import pytz
        from datetime import datetime as _dt
        return _dt.now(pytz.timezone("America/New_York"))
    except ImportError:
        from datetime import datetime as _dt, timezone, timedelta
        now_utc = _dt.now(timezone.utc)
        # Approximate DST: EDT (UTC-4) Mar-Oct, EST (UTC-5) Nov-Feb
        offset  = -4 if 3 <= now_utc.month <= 10 else -5
        return now_utc + timedelta(hours=offset)


def _is_market_hours() -> bool:
    """True if current ET time is within regular market hours Mon-Fri."""
    now = _et_now()
    if now.weekday() >= 5:      # Sat=5, Sun=6
        return False
    t      = now.hour * 60 + now.minute
    open_  = MARKET_OPEN_H  * 60 + MARKET_OPEN_M
    close_ = MARKET_CLOSE_H * 60 + MARKET_CLOSE_M
    return open_ <= t < close_


def _is_trading_day() -> bool:
    """True on Mon-Fri (does not account for public holidays)."""
    return _et_now().weekday() < 5


# ─────────────────────────────────────────────────────────────────────────
# Scan cancel exception — raised inside progress_cb to abort mid-scan
# ─────────────────────────────────────────────────────────────────────────

class ScanCancelledError(Exception):
    """Raised when a cancelscan command is received mid-scan."""
    pass


# ─────────────────────────────────────────────────────────────────────────
# Shared scan state — thread-safe, passed between scheduler and bot
# ─────────────────────────────────────────────────────────────────────────

class ScanState:
    """
    Thread-safe shared state between the scheduler loop and Telegram bot.

    Uses threading.Event for cancel (same as original) so that the
    progress_cb can read it efficiently without holding the main lock.
    """
    def __init__(self):
        self._lock                  = threading.Lock()
        self._running               = False
        self._scan_requested        = False
        self._requested_tickers     = None
        self._requested_strategy    = None   # None = use default / config override
        self._scheduler_enabled     = True

        # threading.Event for cancel — efficient, same pattern as original
        self.cancel_event: threading.Event = threading.Event()

        # Last scan results cache
        self._last_results          = None
        self._last_scan_time        = None
        self._last_count            = 0
        self._last_tickers          = []

        # Dynamic watchlist and scan slots — adjustable via Telegram at runtime
        self._watchlist  = list(DEFAULT_WATCHLIST)
        self._scan_slots = list(SCAN_SLOTS)   # [(h, m, label), ...]

    # ── scan running ──────────────────────────────────────────────────
    def is_running(self) -> bool:
        with self._lock:
            return self._running

    def set_running(self, val: bool):
        with self._lock:
            self._running = val
            # Clear cancel flag on both start (discard stale) and stop (reset)
            self.cancel_event.clear()

    # ── manual scan request ───────────────────────────────────────────
    def request_scan(self, tickers=None, strategy=None):
        with self._lock:
            self._scan_requested     = True
            self._requested_tickers  = tickers
            self._requested_strategy = strategy   # None = use default
            # Clear any stale cancel from the previous scan
            self.cancel_event.clear()

    def consume_scan_request(self):
        """Returns (requested, tickers, strategy) and clears the flag atomically."""
        with self._lock:
            if self._scan_requested:
                self._scan_requested     = False
                tickers                  = self._requested_tickers
                strategy                 = self._requested_strategy
                self._requested_tickers  = None
                self._requested_strategy = None
                return True, tickers, strategy
            return False, None, None

    # ── cancel (threading.Event — readable without holding the lock) ──
    def request_cancel(self):
        """Signal the running scan to stop at the next batch boundary."""
        self.cancel_event.set()

    def is_cancel_requested(self) -> bool:
        return self.cancel_event.is_set()

    def force_reset(self):
        """
        Emergency reset when a scan is stuck and not responding to cancel.
        Forces _running=False and clears the cancel event so a new scan can start.
        The stuck daemon thread will eventually be cleaned up by the OS.
        """
        with self._lock:
            self._running = False
        self.cancel_event.clear()
        log.warning("ScanState force_reset: state cleared by user.")

    # ── scheduler on/off ──────────────────────────────────────────────
    def is_enabled(self) -> bool:
        with self._lock:
            return self._scheduler_enabled

    def disable_scheduler(self):
        with self._lock:
            self._scheduler_enabled = False

    def enable_scheduler(self):
        with self._lock:
            self._scheduler_enabled = True

    # ── last results cache ────────────────────────────────────────────
    def store_results(self, results, scan_time, tickers):
        with self._lock:
            self._last_results   = results
            self._last_scan_time = scan_time
            self._last_count     = len(results) if results else 0
            self._last_tickers   = list(tickers or [])

    def get_last_results(self):
        """Returns (results, scan_time, count, tickers)."""
        with self._lock:
            return (
                self._last_results,
                self._last_scan_time,
                self._last_count,
                list(self._last_tickers),
            )

    # ── dynamic watchlist ─────────────────────────────────────────────
    def get_watchlist(self) -> list:
        with self._lock:
            return list(self._watchlist)

    def set_watchlist(self, tickers: list):
        with self._lock:
            self._watchlist = list(tickers)

    # ── dynamic scan slots ────────────────────────────────────────────
    def get_scan_slots(self) -> list:
        with self._lock:
            return list(self._scan_slots)

    def set_scan_slots(self, slots: list):
        """slots: list of (hour, minute, label) tuples."""
        with self._lock:
            self._scan_slots = list(slots)


# ─────────────────────────────────────────────────────────────────────────
# Scan runner
# ─────────────────────────────────────────────────────────────────────────

def run_scan(
    notifier,
    state: ScanState,
    tickers: Optional[List[str]] = None,
    bot=None,
    slot_label: str = "Manual",
    strategy: Optional[str] = None,
    dry_run: bool = False,
) -> int:
    """
    Run a full option scan, cache results, send notifications.
    Returns the number of opportunities found.

    notifier: any object with send_message(str) and send_error(str) methods.
              TelegramNotifier when Telegram is enabled, NullNotifier otherwise.

    Argument order matches the original scheduler so existing threading.Thread
    calls with positional args continue to work unchanged.
    """
    if state.is_running():
        log.warning("Scan already in progress - skipped.")
        return 0

    state.set_running(True)
    scan_tickers = tickers or state.get_watchlist()
    start        = time.time()
    log.info("=== Scan START [%s] tickers=%s ===", slot_label, ", ".join(scan_tickers))

    try:
        # ── build config with live Telegram overrides ──────────────────
        config = ScannerConfig(tickers=scan_tickers, strategy=STRATEGY, dry_run=dry_run)
        if bot is not None:
            overrides = bot.get_config_overrides()
            for attr, value in overrides.items():
                if hasattr(config, attr):
                    setattr(config, attr, value)
                    log.info("Override applied: %s = %s", attr, value)
        # Per-scan strategy takes priority over global config override
        if strategy:
            config.strategy = strategy
            log.info("Per-scan strategy override: %s", strategy)

        cfg_hash = config.config_hash()
        log.info("Config hash: %s", cfg_hash)

        scanner = OptionScanner(config)

        # ── progress callback: sends updates AND checks for cancel ─────
        # This is the key mechanism: ScanCancelledError propagates up
        # through scanner.run() → caught below → sends cancel message.
        def progress_cb(msg: str):
            if state.is_cancel_requested():
                raise ScanCancelledError("Scan cancelled by user.")
            if msg:   # empty string = silent cancel-check only, no Telegram message
                notifier.send_message(msg)
                # Small delay to avoid Telegram flood control when Yahoo Finance
                # scans fire many messages in rapid succession (vs ~2min for IBKR).
                # NullNotifier is local-only — no delay needed.
                if not isinstance(notifier, NullNotifier):
                    import time as _time
                    _time.sleep(0.3)

        try:
            results = scanner.run(progress_cb=progress_cb)
        except ScanCancelledError:
            elapsed = time.time() - start
            log.info("Scan cancelled after %.0fs.", elapsed)
            notifier.send_message(
                f"Scan cancelled after {elapsed:.0f}s.\n"
                f"Send `scan` to start a new scan."
            )
            return 0
        finally:
            # Always disconnect IBKR — prevents connection leaks
            try:
                scanner.fetcher.disconnect()
            except Exception:
                pass    # fetcher may already be disconnected; ignore

        # ── one final cancel check (race: cancel arrived at last batch) ─
        if state.is_cancel_requested():
            elapsed = time.time() - start
            notifier.send_message(
                f"Scan cancelled after {elapsed:.0f}s.\n"
                f"Send `scan` to start a new scan."
            )
            return 0

        # ── cache results ─────────────────────────────────────────────
        scan_time = datetime.now()
        state.store_results(results, scan_time, scan_tickers)

        # ── write top candidates to Supabase ──────────────────────────
        # Runs only when results exist. Errors are caught inside
        # write_candidates — will never crash or affect Telegram output.
        if results:
            try:
                supabase = SupabaseClient()
                if supabase.is_enabled():
                    # Pass autostar threshold from live config overrides if set
                    autostar_threshold = 80.0
                    if bot is not None:
                        overrides = bot.get_config_overrides()
                        autostar_threshold = float(
                            overrides.get("autostar_threshold", 80.0)
                        )
                    saved, auto_starred = supabase.write_candidates(
                        results, scan_time, top_n=10,
                        autostar_threshold=autostar_threshold,
                    )
                    log.info(
                        "Supabase: %d candidate(s) saved (%d auto-starred).",
                        saved, auto_starred,
                    )
                    # Save full scan record (config + weights + all results)
                    supabase.save_scan_history(
                        scan_time=scan_time,
                        slot_label=slot_label,
                        tickers=scan_tickers,
                        strategy=config.strategy,
                        result_count=len(results),
                        elapsed_secs=int(time.time() - start),
                        config=config,
                        results=results,
                        config_hash=cfg_hash,
                    )
                    if saved > 0:
                        msg = f"💾 {saved} candidate(s) saved to TOS."
                        if auto_starred > 0:
                            msg += (
                                f"\n⭐ {auto_starred} auto-starred "
                                f"(score ≥ {autostar_threshold:.0f}). "
                                f"Send `starredlist` to review."
                            )
                        else:
                            msg += " Send `starredlist` or `star <n>` to shortlist."
                        notifier.send_message(msg)
                else:
                    log.info("Supabase not enabled — candidates not saved.")
            except Exception as e:
                # Never let a Supabase failure affect scan results delivery
                log.error("Supabase write failed (non-fatal): %s", e)

        # ── terminal output ───────────────────────────────────────────
        reporter = Reporter(results, top_n=10)
        reporter.print_table()

        elapsed = time.time() - start
        count   = len(results)
        log.info("=== Scan END [%s] %d results in %.0fs ===", slot_label, count, elapsed)

        # ── Telegram completion message ───────────────────────────────
        if count == 0:
            notifier.send_message(
                f"Scan complete [{slot_label}] - 0 opportunities found. "
                f"({elapsed:.0f}s)\n\n"
                f"Check rejection summary above. "
                f"Send `config` to review filters or `set` to adjust."
            )
        else:
            # Top-5 inline table (no dependency on notifier.send_scan_results)
            top   = results[:5]
            lines = [
                f"Scan complete [{slot_label}] - *{count} opportunities* ({elapsed:.0f}s)\n",
                "```",
                f"{'#':<3} {'Ticker':<6} {'T':<4} {'Strike':>7} {'DTE':>4} {'Exp':>6} {'Dlt':>5} {'IV%':>5} {'Prem':>6} {'Scr':>5}",
                "-" * 58,
            ]
            for i, o in enumerate(top, 1):
                t_label = "CC" if o.strategy == "COVERED_CALL" else "SCP"
                iv_pct  = f"{o.contract.implied_vol * 100:.0f}%"
                exp_str = o.contract.expiry.strftime("%d/%m") if hasattr(o.contract.expiry, 'strftime') else "?"
                delta_s = f"{o.greeks.delta:+.2f}"
                lines.append(
                    f"{i:<3} {o.contract.ticker:<6} {t_label:<4} "
                    f"${o.contract.strike:>6.1f} "
                    f"{o.contract.dte:>4} "
                    f"{exp_str:>6} "
                    f"{delta_s:>5} "
                    f"{iv_pct:>5} "
                    f"${o.contract.mid:>5.2f} "
                    f"{o.score:>5.1f}"
                )
            lines.append("```")
            if count > 5:
                lines.append(f"_{count - 5} more — send_ `result` _to browse all_")
            lines.append(f"_Detail:_ `detail 1`  _Star:_ `star 1`")
            lines.append("_Workflow:_ `star <#>` → `approve <#>` → `placed <#>`")
            notifier.send_message("\n".join(lines))

            # Auto-show Results menu for quick next-action selection
            if bot is not None:
                try:
                    bot.send_results_menu()
                except Exception:
                    pass   # menu is a convenience; never block scan flow

        return count

    except ScanCancelledError:
        # Belt-and-suspenders: catch any cancel that escaped the inner try
        elapsed = time.time() - start
        log.info("Scan cancelled after %.0fs.", elapsed)
        notifier.send_message(
            f"Scan cancelled after {elapsed:.0f}s.\n"
            f"Send `scan` to start a new scan."
        )
        return 0

    except Exception as e:
        log.error("Scan error: %s", e, exc_info=True)
        try:
            notifier.send_error(str(e))
        except Exception:
            notifier.send_message(f"Scan error [{slot_label}]: `{e}`")
        return 0

    finally:
        state.set_running(False)


# ─────────────────────────────────────────────────────────────────────────
# Scheduler loop — checks every 10 seconds (matches original main loop cadence)
# ─────────────────────────────────────────────────────────────────────────

def _scheduler_loop(
    notifier,
    state: ScanState,
    bot,
):
    """
    Background thread. Every 10 seconds:
      1. Check for a manual scan request from Telegram → fire immediately.
      2. Check if any scheduled slot time has arrived → fire once per day.

    Slot logic:
      - Each slot (index) fires at most once per calendar day (ET).
      - A scan already in progress blocks scheduled firing (not manual).
      - stopscan disables scheduled firing; manual scan still works.
    """
    log.info(
        "Scheduler loop started. Slots (ET): %s",
        "  ".join(f"{h:02d}:{m:02d} [{lbl}]" for h, m, lbl in state.get_scan_slots()),
    )

    fired_today: dict = {}      # { date_str: set_of_slot_indices_fired }
    CHECK_INTERVAL    = 10      # seconds — same as original main loop sleep

    while True:
        time.sleep(CHECK_INTERVAL)

        now    = _et_now()
        today  = now.strftime("%Y-%m-%d")
        t_mins = now.hour * 60 + now.minute

        # ── 1. Manual scan request ─────────────────────────────────────
        requested, req_tickers, req_strategy = state.consume_scan_request()
        if requested and not state.is_running():
            log.info("Manual scan requested. Tickers: %s  Strategy: %s",
                     req_tickers or "full watchlist", req_strategy or "default")
            threading.Thread(
                target=run_scan,
                args=(notifier, state, req_tickers),
                kwargs={"bot": bot, "slot_label": "Manual", "strategy": req_strategy},
                daemon=True,
            ).start()
            continue    # skip slot check this tick

        # ── 2. Scheduled slot check ────────────────────────────────────
        if not state.is_enabled():
            continue
        if not _is_trading_day():
            continue
        if state.is_running():
            continue

        if today not in fired_today:
            fired_today[today] = set()
            # Prune entries older than today
            fired_today = {k: v for k, v in fired_today.items() if k >= today}

        for idx, (slot_h, slot_m, slot_label) in enumerate(state.get_scan_slots()):
            if idx in fired_today[today]:
                continue    # already fired today

            slot_mins = slot_h * 60 + slot_m
            # Fire if we are within CHECK_INTERVAL seconds past the slot time
            # and market is currently open (guards against bot starting late)
            in_window = slot_mins <= t_mins < slot_mins + (CHECK_INTERVAL // 60 + 2)
            if in_window and _is_market_hours():
                fired_today[today].add(idx)
                log.info("Firing slot [%s] at %02d:%02d ET", slot_label, slot_h, slot_m)
                notifier.send_message(
                    f"Auto-scan starting - *{slot_label}* slot "
                    f"({slot_h:02d}:{slot_m:02d} ET)"
                )
                threading.Thread(
                    target=run_scan,
                    args=(notifier, state, None),
                    kwargs={"bot": bot, "slot_label": slot_label},
                    daemon=True,
                ).start()
                break   # only one slot per tick


# ─────────────────────────────────────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Sell Option Scanner Bot")
    parser.add_argument("--once",    action="store_true",
                        help="Run a single scan immediately then exit")
    parser.add_argument("--dry-run", action="store_true",
                        help="Use mock data instead of IBKR (no TWS needed)")
    parser.add_argument("--no-telegram", action="store_true",
                        help="Run without Telegram (results printed to terminal only)")
    args = parser.parse_args()

    state = ScanState()
    bot   = None  # None when Telegram is disabled

    # ── Choose notifier: Telegram or NullNotifier ──────────────────────
    use_telegram = not args.no_telegram
    if use_telegram:
        try:
            from output.telegram_notifier import TelegramNotifier
            from output.telegram_bot import TelegramBotListener
            notifier = TelegramNotifier()
            bot = TelegramBotListener(scan_state=state, notifier=notifier)
            bot.start()
            log.info("Telegram bot listener started.")
        except (ImportError, ValueError) as e:
            log.warning("Telegram unavailable (%s). Falling back to terminal output.", e)
            use_telegram = False
            notifier = NullNotifier()
            bot = None
    else:
        log.info("--no-telegram: Telegram disabled. Results will print to terminal.")
        notifier = NullNotifier()

    # ── OS signal handlers (Ctrl+C / SIGTERM) ─────────────────────────
    def shutdown(sig, frame):
        log.info("Shutdown signal received. Stopping...")
        if bot is not None:
            bot.stop()
        try:
            notifier.send_message("Bot stopped.")
        except Exception:
            pass
        raise SystemExit(0)

    signal.signal(signal.SIGINT,  shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # ── Startup notification ───────────────────────────────────────────
    slots_str = "  ".join(
        f"{h:02d}:{m:02d} [{lbl}]" for h, m, lbl in state.get_scan_slots()
    )
    if use_telegram:
        notifier.send_message(
            f"Bot started.\n\n"
            f"Auto-scan slots (ET):\n"
            f"`{slots_str}`\n\n"
            f"Send `scan` for a manual scan, `m` for menu."
        )
        bot.send_main_menu()
    else:
        log.info("Auto-scan slots (ET): %s", slots_str)

    # ── --once mode ────────────────────────────────────────────────────
    if args.once:
        log.info("--once mode: running single scan.%s%s",
                 " (dry-run)" if args.dry_run else "",
                 " (no-telegram)" if not use_telegram else "")
        run_scan(notifier, state, tickers=state.get_watchlist(), bot=bot,
                 slot_label="Test", dry_run=args.dry_run)
        log.info("--once scan complete. Exiting.")
        if bot is not None:
            bot.stop()
        return

    # ── Start scheduler loop in background thread ──────────────────────
    sched_thread = threading.Thread(
        target=_scheduler_loop,
        args=(notifier, state, bot),
        daemon=True,
        name="scheduler-loop",
    )
    sched_thread.start()
    log.info(
        "Scheduler running. Slots (ET): %s",
        "  ".join(f"{h:02d}:{m:02d}" for h, m, _ in SCAN_SLOTS),
    )

    # ── Main thread: keep alive ────────────────────────────────────────
    try:
        while True:
            time.sleep(10)
    except KeyboardInterrupt:
        log.info("Shutting down...")
        if bot is not None:
            bot.stop()
        try:
            notifier.send_message("Bot stopped (manual shutdown).")
        except Exception:
            pass


if __name__ == "__main__":
    main()
