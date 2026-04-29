# OptionBot Backup Changelog
# Backup: optionbot_post_review_20260316_230557.zip
# Date: 2026-03-16 23:05

## Description
Post-review — all bug fixes applied, syntax verified across all 14 Python files.

---

## Changes Applied in This Backup

### CRITICAL BUG FIX: `scheduler.py` — NameError on `count`

**File:** `scheduler.py` line 339
**Issue:** `result_count=count` was passed to `supabase.save_scan_history()` but `count = len(results)` was not defined until line 366 (after the Supabase block). This caused a `NameError` crash every time a scan completed with results and Supabase was enabled.
**Fix:** Changed `result_count=count` to `result_count=len(results)`.
**Impact:** HIGH — would crash every successful scan with Supabase enabled. Supabase's own try/except caught it, so the scan still delivered results to Telegram, but scan history was never saved to Supabase.

### BUG FIX: `data/mock_fetcher.py` — Missing `progress_cb` parameter

**File:** `data/mock_fetcher.py` line 52
**Issue:** `fetch_option_chain(self, ticker)` did not accept `progress_cb` keyword argument, but `scanner.py` line 131 calls `self.fetcher.fetch_option_chain(ticker, progress_cb=progress_cb)`. Running `--dry-run` mode would crash with `TypeError: unexpected keyword argument 'progress_cb'`.
**Fix:** Added `progress_cb=None` parameter to match `IBKRFetcher` interface.
**Impact:** MEDIUM — `--dry-run` / test mode was broken.

### CLEANUP: `core/scanner.py` — Dead code removed

**File:** `core/scanner.py` lines 234–243
**Issue:** `_passes_liquidity()` method was defined but never called. The same logic was implemented inline in `_scan_ticker()` with individual rejection counters.
**Fix:** Replaced with a comment explaining liquidity checks are inline.
**Impact:** LOW — no runtime effect, code hygiene only.

### CLEANUP: `output/telegram_bot.py` — Outdated docstring

**File:** `output/telegram_bot.py` lines 4–5
**Issue:** Docstring said "All commands work both with and without a leading slash" but the slash gate on line 987 requires `/` prefix for all commands.
**Fix:** Updated to "All commands require a leading / (slash gate active for security)".
**Impact:** LOW — documentation accuracy only.

### NOTED: `data/cd` — Accidental file

**File:** `data/cd`
**Issue:** Duplicate of `mock_fetcher.py` content, likely created by a mistyped terminal command.
**Action needed:** Manually delete `data/cd` on the Mac Mini.

---

## Architecture Notes for Future Reference

- **IV filtering is two-layer:** `min_iv_rank` (relative, needs IBKR 52-week history) + `min_iv` (absolute floor, always available from option quote). The absolute IV check runs twice: once in `scanner.py` as a pre-filter before Greeks, and again in each strategy filter. This is intentional belt-and-suspenders.
- **IBKR delayed data quirk:** OI always returns 0. `min_open_interest` must stay at 0. The spread filter handles liquidity.
- **Config overrides are permanent** until `set reset` is explicitly sent via Telegram. They survive across scans but not across bot restarts.
- **Supabase errors are always non-fatal.** Every Supabase call is wrapped in try/except so IBKR data and Telegram delivery are never blocked.
- **Risk-free rate** (`greeks.py` line 27): Currently hardcoded at 5.3%. Should be reviewed periodically against the 3-month T-bill rate.
