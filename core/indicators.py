"""
core/indicators.py — Mean Reversion Indicators
================================================
Pure calculation module for short-term mean reversion signals.
Used to score option-selling timing based on underlying price movement.

Components (research-backed weighting):
  1. RSI(5)              — 40%  — momentum oscillator, best for 30-45 DTE
  2. Z-Score(20)         — 40%  — displacement from mean, vol-normalized
  3. ROC %Rank(100)      — 20%  — surge magnitude ranking (Connors method)

Trend Guard:
  Caps the mean reversion score when price is >N% from SMA(200),
  preventing false signals in strong trends (the #1 failure mode).

References:
  - Connors & Alvarez (2008), "Short Term Trading Strategies That Work"
  - DeMiguel et al. (2009), Review of Financial Studies (equal-weight robustness)
  - Jegadeesh (1990), short-term reversal factor
  - Gatev, Goetzmann & Rouwenhorst (2006), mean reversion convergence rates
"""
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

import logging
import math
from dataclasses import dataclass
from typing import List, Optional

log = logging.getLogger(__name__)


@dataclass
class MeanReversionResult:
    """Result of mean reversion analysis for one ticker + direction."""
    score: float            # 0.0–1.0 composite (direction-aware)
    rsi: float              # raw RSI(5) value (0–100)
    z_score: float          # raw Z-Score (typically -3 to +3)
    roc_pct_rank: float     # ROC percentile rank (0–100)
    trend_guard_active: bool  # True if score was capped by trend guard
    sma200_distance_pct: float  # % distance from SMA(200)


# ── Component Calculators ────────────────────────────────────────────────


def compute_rsi(prices: List[float], period: int = 5) -> float:
    """
    Relative Strength Index.

    RSI(5) is optimal for 30-45 DTE mean reversion (Connors research):
    - RSI(2) is too noisy for 30+ day horizons
    - RSI(14) is too slow — misses short-term surges
    - RSI(5) is the sweet spot

    Returns 0–100. Needs at least period+1 prices.
    """
    if len(prices) < period + 1:
        log.debug("RSI: insufficient data (%d prices, need %d)", len(prices), period + 1)
        return 50.0  # neutral fallback

    # Use the most recent period+1 prices for current RSI
    changes = [prices[i] - prices[i - 1] for i in range(1, len(prices))]

    # Wilder's smoothed averages (exponential moving average style)
    gains = [max(0, c) for c in changes]
    losses = [max(0, -c) for c in changes]

    # Seed with simple average of first `period` values
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    # Smooth through remaining values
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def compute_z_score(prices: List[float], period: int = 20) -> float:
    """
    Z-Score: (price - SMA) / StdDev over `period` bars.

    Measures how many standard deviations price is from its short-term mean.
    |Z| > 2.0 → statistically extreme, ~70-80% reversion within 30 days.

    Mathematically equivalent to Bollinger %B (rescaled), so using both
    would be redundant. Z-Score is preferred for algorithmic systems.

    Returns raw Z value (typically -3 to +3). Needs at least `period` prices.
    """
    if len(prices) < period:
        log.debug("Z-Score: insufficient data (%d prices, need %d)", len(prices), period)
        return 0.0  # neutral fallback

    recent = prices[-period:]
    mean = sum(recent) / len(recent)
    variance = sum((p - mean) ** 2 for p in recent) / len(recent)
    std = math.sqrt(variance) if variance > 0 else 0.0

    if std == 0:
        return 0.0
    return (prices[-1] - mean) / std


def compute_roc_percentile_rank(prices: List[float], period: int = 100) -> float:
    """
    Rate of Change Percentile Rank (Connors method).

    Ranks today's 1-day price change as a percentile against the past
    `period` days. This is more robust than raw ROC because:
    - A 2% move means different things for AAPL vs TSLA
    - Percentile ranking auto-normalizes across volatility regimes

    Used in Connors RSI (CRSI) as the third component.

    Returns 0–100. Needs at least period+2 prices.
    """
    if len(prices) < period + 2:
        log.debug("ROC %%Rank: insufficient data (%d prices, need %d)", len(prices), period + 2)
        return 50.0  # neutral fallback

    # Today's 1-day ROC
    today_roc = (prices[-1] - prices[-2]) / prices[-2] if prices[-2] != 0 else 0.0

    # Past `period` days' 1-day ROCs (excluding today)
    count_below = 0
    total = 0
    for i in range(-2, -(period + 2), -1):
        idx = len(prices) + i
        if idx < 1:
            break
        past_roc = (prices[idx] - prices[idx - 1]) / prices[idx - 1] if prices[idx - 1] != 0 else 0.0
        if today_roc > past_roc:
            count_below += 1
        total += 1

    if total == 0:
        return 50.0
    return (count_below / total) * 100.0


def compute_sma(prices: List[float], period: int = 200) -> Optional[float]:
    """Simple Moving Average. Returns None if insufficient data."""
    if len(prices) < period:
        return None
    return sum(prices[-period:]) / period


# ── Composite Mean Reversion Score ───────────────────────────────────────


def compute_mean_reversion_score(
    prices: List[float],
    strategy: str,
    rsi_period: int = 5,
    z_period: int = 20,
    roc_period: int = 100,
    w_rsi: float = 0.40,
    w_z: float = 0.40,
    w_roc: float = 0.20,
    trend_guard: bool = True,
    trend_pct: float = 15.0,
) -> MeanReversionResult:
    """
    Compute direction-aware mean reversion composite score for option selling.

    For COVERED CALLS (strategy contains "cc" or is "C"):
      High score when price is overbought → likely to revert DOWN → good to sell call.
      RSI high + Z positive + ROC high → score boosted.

    For CASH-SECURED PUTS (strategy contains "csp" or is "P"):
      High score when price is oversold → likely to revert UP → good to sell put.
      RSI low + Z negative + ROC low → score boosted.

    The direction flip is the key innovation: same indicators, opposite interpretation.

    Parameters
    ----------
    prices : list of float
        Daily close prices, oldest first. Need at least 200 for trend guard.
    strategy : str
        "cc", "C", "COVERED_CALL" for calls; "csp", "P", "CASH_SECURED_PUT" for puts.
    rsi_period, z_period, roc_period : int
        Lookback periods for each indicator.
    w_rsi, w_z, w_roc : float
        Weights (should sum to 1.0).
    trend_guard : bool
        If True, cap score when price is far from SMA(200).
    trend_pct : float
        Threshold for trend guard (default 15%).

    Returns
    -------
    MeanReversionResult
    """
    # Determine direction: selling calls benefits from overbought, puts from oversold
    is_call = strategy.upper() in ("CC", "C", "COVERED_CALL")

    # Compute raw indicators
    rsi = compute_rsi(prices, rsi_period)
    z = compute_z_score(prices, z_period)
    roc_rank = compute_roc_percentile_rank(prices, roc_period)

    # Normalise each to 0–1
    rsi_norm = rsi / 100.0                                          # already 0–100
    z_norm = max(0.0, min(1.0, (z + 3.0) / 6.0))                   # Z ∈ [-3,+3] → [0,1]
    roc_norm = roc_rank / 100.0                                     # already 0–100

    # Weighted composite (0–1), where 1.0 = maximally overbought
    total_w = w_rsi + w_z + w_roc
    if total_w == 0:
        total_w = 1.0
    overbought_score = (rsi_norm * w_rsi + z_norm * w_z + roc_norm * w_roc) / total_w

    # Direction flip:
    # For calls: overbought = high score (good to sell call)
    # For puts:  oversold = high score → flip: 1 - overbought_score
    if is_call:
        score = overbought_score
    else:
        score = 1.0 - overbought_score

    # ── Trend Guard ──────────────────────────────────────────────────────
    # Mean reversion fails in strong trends. Cap the score to prevent
    # false signals when price is extended far from SMA(200).
    sma200 = compute_sma(prices, 200)
    sma200_dist_pct = 0.0
    tg_active = False

    if sma200 is not None and sma200 > 0:
        sma200_dist_pct = ((prices[-1] - sma200) / sma200) * 100.0

        if trend_guard:
            # Strong uptrend: price >N% above SMA(200)
            # → cap CALL score at 0.5 (overbought may persist)
            if sma200_dist_pct > trend_pct and is_call and score > 0.5:
                log.debug("Trend guard: capping call MR score (%.1f%% above SMA200)", sma200_dist_pct)
                score = 0.5
                tg_active = True

            # Strong downtrend: price >N% below SMA(200)
            # → cap PUT score at 0.5 (oversold may persist)
            if sma200_dist_pct < -trend_pct and not is_call and score > 0.5:
                log.debug("Trend guard: capping put MR score (%.1f%% below SMA200)", sma200_dist_pct)
                score = 0.5
                tg_active = True

    return MeanReversionResult(
        score=round(score, 4),
        rsi=round(rsi, 1),
        z_score=round(z, 2),
        roc_pct_rank=round(roc_rank, 1),
        trend_guard_active=tg_active,
        sma200_distance_pct=round(sma200_dist_pct, 1),
    )
