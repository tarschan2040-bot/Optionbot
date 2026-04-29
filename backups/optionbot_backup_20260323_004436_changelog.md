# OptionBot Backup Changelog
# Backup: optionbot_backup_20260323_004436.zip
# Date: 2026-03-23 00:44

## Description
Major Telegram UX overhaul + IBKR live account connection + multi-user access.
All changes verified (syntax OK). Bot restart required to activate.

---

## Changes Applied in This Backup

### IBKR LIVE ACCOUNT CONNECTION

**File:** `data/ibkr_fetcher.py`
**Change:** Market data type switched from Type 3 (delayed) to Type 1 (live streaming) when market is open. Type 3 used when market closed. Previously used Type 3/4 for paper account.
**Impact:** HIGH — real-time prices, accurate OI, better IV data with live account + data subscription.

### TELEGRAM NAVIGATION OVERHAUL

**File:** `output/telegram_bot.py`, `scheduler.py`
**Changes:**
- `result` — shows full result list (page 1). Replaces `fullresult`.
- `page <n>` — jump to any results page. Replaces `next`/`previous`.
- `detail <n>` — full detail card for result #n. Replaces `result <n>`.
- Removed `next`, `previous`, `fullresult` commands entirely.
- Removed Prev/Next Page buttons from Results inline keyboard menu.
**Impact:** HIGH — cleaner, more intuitive navigation.

### SLASH PREFIX REMOVED

**File:** `output/telegram_bot.py`
**Change:** Removed the slash gate (`if not text.startswith("/"): return`). Commands now work with or without `/`. Plain text commands are processed directly.
**Impact:** HIGH — users just type `scan`, `config`, `m` etc. No `/` needed.

### MENU SHORTCUT

**File:** `output/telegram_bot.py`
**Change:** `m` now opens the interactive menu (in addition to `menu`).
**Impact:** LOW — convenience shortcut.

### RESULT TABLE IMPROVEMENTS

**Files:** `output/telegram_bot.py`, `scheduler.py`
**Changes:**
- `CP` label changed to `SCP` (Cash-Secured Put) everywhere.
- Added `Exp` column showing exact expiry date in DD/MM format.
- Added `Dlt` (Delta) column for each result.
- Table width increased from 44 to 58 chars.
- Applied to: scan completion table, full results page, last scan summary.
**Impact:** MEDIUM — more useful information at a glance.

### INTERACTIVE INLINE KEYBOARD MENUS

**File:** `output/telegram_bot.py`
**Changes:**
- `send_results_menu()` — new public method, called automatically after each scan.
- Auto Results menu: after scan results pop out, the Results category menu appears automatically.
- All menu wording updated to remove `/` prefix from command references.
**Impact:** MEDIUM — faster workflow after scan.

### PORTFOLIO & CLEAR COMMANDS

**File:** `output/telegram_bot.py`, `data/supabase_client.py`
**Changes:**
- `portfolio` — shows open trades from trade_log WHERE exit_date IS NULL.
- `trade <n>` — full detail card for open trade #n.
- `clearstarred`, `clearapproved`, `clearplaced` — bulk-clear workflow lists.
- `clear_by_status()` in supabase_client.py — updates trade_candidates only, never touches trade_log or scan_history.
- Portfolio date format changed to DD-Mon (e.g. `16-Mar`) matching placed list.
**Impact:** MEDIUM — new commands for portfolio management.

### DYNAMIC WATCHLIST & SCHEDULE

**File:** `output/telegram_bot.py`, `scheduler.py`
**Changes:**
- `setwatchlist AAPL TSLA NVDA` — change default scan tickers at runtime.
- `setscantime 09:35 13:00 15:00` — change auto-scan schedule at runtime.
- Thread-safe via `ScanState._lock` in scheduler.py.
**Impact:** MEDIUM — no restart needed to change watchlist or schedule.

### HELP BUTTON FIX

**File:** `output/telegram_bot.py`
**Change:** Added `_send_long()` method that splits messages exceeding Telegram's 4096-char limit at line boundaries while correctly pairing ``` code block fences. Applied to /help and cb_help.
**Impact:** MEDIUM — Help button was silently failing (4257 chars > 4096 limit).

### CONFIG WITH PARAMETER GUIDE

**File:** `output/telegram_bot.py`
**Change:** `_build_config_reply()` now includes a full PARAMETER GUIDE section explaining what each of the 16 settable parameters does, with practical notes.
**Impact:** LOW — better user experience for config review.

### MULTI-USER ACCESS CONTROL

**File:** `output/telegram_bot.py`, `.env`
**Changes:**
- New env var: `TELEGRAM_VIEWER_IDS` (comma-separated chat IDs).
- Admin (TELEGRAM_CHAT_ID) = full access.
- Viewers = read-only: can view results, portfolio, prices, health. Cannot modify config, clear lists, place trades, use AI chat, or stop bot.
- `ADMIN_ONLY_COMMANDS` set guards text commands; `ADMIN_CALLBACKS` set guards inline buttons.
- Viewer 788460876 added to .env.
**Impact:** HIGH — safe multi-user access without exposing IBKR or admin functions.

### STARTUP MESSAGE UPDATE

**File:** `scheduler.py`
**Change:** Startup message now says `scan` and `m` instead of `/scan` and `/menu`.
**Impact:** LOW — consistency with new no-slash convention.

---

## Architecture Notes

- **Three independent Supabase tables:** scan_history (permanent, never modified), trade_candidates (workflow status lifecycle), trade_log (portfolio — written once when placed, never deleted by bot).
- **clearplaced** sets trade_candidates status='archived' only. trade_log completely untouched.
- **IBKR connection:** Live account via IB Gateway port 4001. Bot is read-only by code (no placeOrder calls). Read-Only API disabled in Gateway to allow reqMktData/reqHistoricalData.
- **Multi-user:** Admin identified by TELEGRAM_CHAT_ID. Viewers by TELEGRAM_VIEWER_IDS. Unknown chat IDs silently ignored.
- **Message splitting:** `_send_long()` splits at ~4000 chars (safety margin below 4096), closes/reopens ``` fences across chunks.
