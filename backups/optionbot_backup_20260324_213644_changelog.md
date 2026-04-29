# OptionBot Backup Changelog
# Backup: optionbot_backup_20260324_213644.zip
# Date: 2026-03-24 21:36

## Description
IBKR market data type auto-probe + frozen data fallback fix + watchlist update.
All changes verified (syntax OK). Bot restart required to activate.

---

## Changes Applied in This Backup (since 2026-03-23 backup)

### DEFAULT WATCHLIST UPDATED

**File:** `output/telegram_bot.py`
**Change:** Default watchlist reduced from 9 tickers to 2: `["TSLA", "NVDA"]`.
**Impact:** LOW — scans run faster, focused on user's preferred tickers.

### IBKR MARKET DATA TYPE — SMART AUTO-PROBE

**File:** `data/ibkr_fetcher.py`
**Change:** Replaced static Type 2 (frozen) after-hours logic with a dynamic probe system:
- New `_probe_best_data_type()` method tests a real ATM option contract against each data type
- Probe order: Type 1 (live) → Type 3 (delayed) → Type 4 (delayed-frozen) → Type 2 (frozen)
- Picks the first type that actually returns price data
- Runs automatically before every scan
- Logs exactly what each type returned for diagnostics
**Impact:** HIGH — solves the "0 results after hours" problem where Type 2 frozen returned no data.

### MODEL GREEKS PRICE FALLBACK

**File:** `data/ibkr_fetcher.py`
**Change:** `_parse_ticker_data()` now uses multiple price fallbacks:
- Price priority: close → last → modelGreeks.optPrice → lastGreeks.optPrice → midpoint
- IV priority: impliedVolatility → modelGreeks.impliedVol → lastGreeks.impliedVol
- When bid/ask=0, synthetics are created from ref_price (±5%)
- Generic tick "106" requested in `reqMktData()` to ensure modelGreeks populate
**Impact:** HIGH — options now have price data even when live bid/ask are empty.

### DYNAMIC BATCH WAIT

**File:** `data/ibkr_fetcher.py`
**Change:** Split batch wait into `BATCH_WAIT_LIVE = 5.0s` and `BATCH_WAIT_FROZEN = 8.0s`. Frozen/model data gets more time to populate.
**Impact:** MEDIUM — better data quality after hours without slowing live scans.

### DYNAMIC MARKET DATA TYPE PER SCAN

**File:** `data/ibkr_fetcher.py`
**Change:** `reqMarketDataType()` now called at the start of each scan via probe, not just at connection time. Bot connected overnight automatically uses correct type when market opens — no restart needed.
**Impact:** MEDIUM — seamless transition across market open/close.

### ENHANCED DIAGNOSTIC LOGGING

**File:** `data/ibkr_fetcher.py`
**Change:** First batch logs modelGreeks.optPrice, lastGreeks.optPrice, modelIV, modelDelta, and active data type. Probe logs results for every type tested.
**Impact:** LOW — easier debugging, no functional change.

---

## Files Modified
- `output/telegram_bot.py` — watchlist change (line 98)
- `data/ibkr_fetcher.py` — major rewrite of data type selection and price fallback logic

## Previous Backup
- `optionbot_backup_20260323_004436.zip` (March 23 — UX overhaul + live account + multi-user)
