# OptionBot Backup Changelog
# Backup: optionbot_backup_20260427_114600.zip
# Date: 2026-04-27 11:46

## Description
Mean Reversion scoring engine — added a 6th scoring component that times option-selling
entries based on short-term price displacement (RSI, Z-Score, ROC Percentile Rank).
Includes a matching TradingView Pine Script indicator for visual confirmation on charts.

---

## Changes Applied in This Backup (since 2026-04-08 backup)

### FEATURE: MEAN REVERSION SCORING (6TH COMPONENT)

**What it does:**
Scores the *timing* of option-selling entries by detecting when the underlying price
is stretched away from its mean — oversold (good for selling puts) or overbought
(good for selling covered calls). This is a direction-aware signal layered on top
of the existing 5-factor scoring engine.

**Research basis:**
- Connors & Alvarez (2008), "Short Term Trading Strategies That Work"
- RSI(5) optimal for 30-45 DTE mean reversion
- Z-Score(20) for vol-normalised displacement
- ROC Percentile Rank(100) for surge magnitude (Connors method)

### NEW FILE 1 — `core/indicators.py` (260 lines)

Pure calculation module for mean reversion signals:
- `compute_rsi()` — RSI with Wilder's smoothing, configurable period (default 5)
- `compute_z_score()` — Standard Z-Score over rolling window (default 20)
- `compute_roc_pct_rank()` — Rate of Change percentile rank (default 100-day lookback)
- `compute_mean_reversion_score()` — Master function combining all three into a
  direction-aware 0–1 composite score
- Trend Guard: caps the score when price is >N% from SMA(200) to prevent false
  signals in strong trends (the #1 failure mode of mean reversion strategies)

**Weighting (configurable via Telegram):**
- RSI(5): 40%
- Z-Score(20): 40%
- ROC %Rank(100): 20%

### NEW FILE 2 — `tradingview/mean_reversion_scanner.pine` (273 lines)

TradingView Pine Script v5 indicator that mirrors the Python scoring logic:
- Same 3 components with same default weights
- Background colours: RED = overbought (sell CC), GREEN = oversold (sell CSP)
- Trend Guard overlay with SMA(200) distance
- All parameters configurable via TradingView inputs panel
- Allows Ken to visually confirm scanner signals on the chart

### MODIFIED — `core/config.py` (143 → 181 lines)

- Added 6th scoring weight: `weight_mean_reversion` (default 0.15)
- Rebalanced existing weights: IV 20→15%, Theta 20→15%, Ann Return 30→25%
- Delta Safety (20%) and Liquidity (10%) unchanged
- Added `use_mean_reversion` toggle (default: True)
- Added MR indicator period settings: `mr_rsi_period`, `mr_z_period`, `mr_roc_period`
- Added MR sub-weights: `mr_w_rsi`, `mr_w_z`, `mr_w_roc`
- Added Trend Guard settings: `mr_trend_guard`, `mr_trend_pct`
- Updated `validate()` to check 6-factor weight sum when MR enabled

### MODIFIED — `core/scorer.py` (128 → 147 lines)

- Added 6th scoring component: mean reversion score
- When `use_mean_reversion=True`: uses all 6 weights as configured
- When `use_mean_reversion=False`: redistributes MR weight proportionally across
  the remaining 5 factors so the composite scale stays 0–100
- No change to the 5 existing sub-scorers (IV, theta, delta, liquidity, ann return)

### MODIFIED — `core/models.py` (128 → 144 lines)

- Added mean reversion fields to `ScanOpportunity`:
  `mean_rev_score`, `rsi_5`, `z_score_20`, `roc_pct_rank`,
  `trend_guard_active`, `sma200_distance_pct`
- Updated `to_dict()` to include MR fields when populated

### MODIFIED — `core/scanner.py` (289 → 335 lines)

- Imports `compute_mean_reversion_score` from indicators
- Computes MR once per ticker (reuses existing price history — no extra API call)
- Direction-aware: computes separately for calls (overbought) and puts (oversold)
- Populates MR fields on each `ScanOpportunity` before scoring
- Scan config summary now includes MR status, weights, and Trend Guard state
- Logs MR indicators once per ticker at INFO level for debugging

### MODIFIED — `output/telegram_bot.py` (2703 → 2752 lines)

- Added 10 new settable parameters for MR configuration via Telegram:
  `use_mean_reversion`, `weight_mr`, `mr_rsi_period`, `mr_z_period`,
  `mr_roc_period`, `mr_w_rsi`, `mr_w_z`, `mr_w_roc`, `mr_trend_guard`, `mr_trend_pct`
- Result table now shows MR score column
- Detail card includes Mean Reversion section with RSI(5), Z-Score(20),
  ROC %Rank, and Trend Guard status
- `/config` output includes MR settings summary

### MODIFIED — `data/ibkr_fetcher.py` (535 → 553 lines)
### MODIFIED — `data/mock_fetcher.py` (142 → 149 lines)
### MODIFIED — `data/yfinance_fetcher.py` (395 → 404 lines)

Minor adjustments to support the new MR fields and price history passthrough.

---

## Files Modified
- `core/indicators.py` — **NEW** — mean reversion calculation engine (260 lines)
- `tradingview/mean_reversion_scanner.pine` — **NEW** — TradingView visual indicator (273 lines)
- `core/config.py` — MR weights, toggles, and indicator settings (+38 lines)
- `core/scorer.py` — 6th scoring component with fallback redistribution (+19 lines)
- `core/models.py` — MR fields on ScanOpportunity (+16 lines)
- `core/scanner.py` — MR computation per ticker, scan summary update (+46 lines)
- `output/telegram_bot.py` — 10 new settable params, MR in results/detail (+49 lines)
- `data/ibkr_fetcher.py` — minor MR support (+18 lines)
- `data/mock_fetcher.py` — minor MR support (+7 lines)
- `data/yfinance_fetcher.py` — minor MR support (+9 lines)

## Previous Backup
- `optionbot_backup_20260408_150516.zip` (April 8 — Yahoo Finance IV data quality fix with BS bisection solver)
