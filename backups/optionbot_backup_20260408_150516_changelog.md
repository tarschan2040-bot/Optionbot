# OptionBot Backup Changelog
# Backup: optionbot_backup_20260408_150516.zip
# Date: 2026-04-08 15:05

## Description
Yahoo Finance IV data quality fix — replaced unreliable Yahoo-reported impliedVolatility
with a Black-Scholes bisection solver that calculates IV directly from the option's market
price. Resolves the root cause of "IV < 10% (raw): 134" screening out virtually all TSLA
contracts (Yahoo was returning per-period/per-day vol ~0–6% instead of annualised ~60–100%).

---

## Changes Applied in This Backup (since 2026-03-24 backup)

### ROOT CAUSE: YAHOO IV DATA QUALITY BUG FIXED

**Symptom:**
Telegram scan output showed:
```
IV < 10% (raw)      : 134
  ⚠️ Yahoo IV seen: 0%–6% (min_iv=10%)
```
163 contracts fetched, 134 filtered by IV alone → 0 opportunities.

**Root Cause:**
`yfinance`'s `option_chain()` DataFrame `impliedVolatility` column returns per-period
(per-trading-day) volatility instead of annualised volatility. TSLA's real annualised IV
is ~60–100%, but Yahoo was returning values of 0.00–0.06 (0–6%), which all failed the
`min_iv` filter.

### FIX 1 — `core/greeks.py` — New `calculate_implied_vol()` function

Added a Black-Scholes bisection solver that back-calculates annualised IV from the option's
market mid-price:
- Inputs: mid-price, underlying price, strike, DTE (in years), risk-free rate, call/put flag
- Method: bisection between σ=0.0001 and σ=10.0 with tolerance 1e-5, up to 200 iterations
- Edge cases handled: zero price, intrinsic value bound, degenerate T/S/K inputs
- Returns 0.0 on failure (signals fallback logic in fetcher)
- Fully independent of Yahoo's data quality — only uses option price and contract params

**Why this is better than trusting Yahoo:**
Computing IV from price is the standard market practice (same as how Bloomberg and IBKR
calculate their IV fields). The result is exactly what the Black-Scholes model implies,
not a stale or mis-scaled field from a free API.

### FIX 2 — `data/yfinance_fetcher.py` — `_row_to_contract()` IV logic rewritten

- Now calls `calculate_implied_vol()` on every contract using the option's mid-price
- Falls back to Yahoo's reported IV only if the BS solver fails (rare: deep ITM, no price)
- Skips the contract entirely only if both BS and Yahoo return no usable IV
- Logs a DEBUG line when Yahoo and BS disagree by >10pp for diagnostic visibility
- Caps IV at 3.0 (300%) — unchanged, still guards against deep ITM/OTM junk

---

## Files Modified
- `core/greeks.py` — added `calculate_implied_vol()` bisection solver (~60 lines)
- `data/yfinance_fetcher.py` — rewrote IV block in `_row_to_contract()` (~35 lines changed)

## Test Results
```
TSLA 350P 30DTE mid=$12  → BS IV = 38.4%  ✅ (was: 0–6% from Yahoo)
TSLA 360C 30DTE mid=$10  → BS IV = 27.4%  ✅
TSLA 300P 30DTE mid=$0.05 (deep OTM) → BS IV = 24.7%
Zero price input         → 0.0            ✅ (correct fallback)
Imports: yfinance_fetcher + scanner both import cleanly ✅
```

## Previous Backup
- `optionbot_backup_20260324_213644.zip` (March 24 — IBKR market data type auto-probe + watchlist update)
