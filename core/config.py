"""
core/config.py — All tunable parameters in one place.
Adjust thresholds here without touching strategy logic.

TWO-LAYER IV FILTERING
─────────────────────────────────────────────────────────────────────────────
  min_iv_rank  : WHERE current IV sits vs its own 52-week range (0–100).
                 Requires IBKR historical data. Falls back to a synthetic
                 estimate when history is unavailable.
                 Set to 0 to disable (e.g. when IBKR history is unavailable).

  min_iv       : ABSOLUTE raw implied volatility floor (annualised, 0–1.0).
                 0.40 = 40% IV. Works even when iv_rank history is missing
                 because it reads directly from the option quote.
                 Set to 0.0 to disable.

RECOMMENDED USAGE
  Normal scan  : min_iv_rank=30,  min_iv=0.35   (both layers active)
  IBKR no hist : min_iv_rank=0,   min_iv=0.40   (use raw IV as sole gate)
  TSLA / beta  : min_iv_rank=30,  min_iv=0.50   (only take high-vol trades)
  Wide scan    : min_iv_rank=0,   min_iv=0.0    (no IV filter at all)

OPEN INTEREST (OI) EXPLAINED
─────────────────────────────────────────────────────────────────────────────
  OI = total open contracts for a given strike+expiry.
  High OI → tight spreads, easy exits.  Low OI → wide spreads, hard exits.

  WHY DEFAULT IS 0 (DISABLED):
    IBKR 15-min delayed data returns OI=0 for almost all contracts.
    Setting min_open_interest=100 would reject virtually everything.
    Keep at 0 until you have a live data subscription.
    With live data, restore to 100–500 depending on stock liquidity.
"""
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import List


@dataclass
class ScannerConfig:

    # ── Watchlist ──────────────────────────────────────────────
    tickers: List[str] = field(default_factory=list)
    strategy: str = "both"          # "cc" | "csp" | "both"
    dry_run: bool = False

    # ── Data Source ───────────────────────────────────────────
    # "yahoo"  — Yahoo Finance via yfinance. FREE. No login. No IBKR session.
    #            Works 24/7. 15-min delayed data. Recommended default.
    # "ibkr"   — IB Gateway / TWS. Requires IBKR desktop running + logged in.
    #            Phone login kicks the session — bot dies. Live data when open.
    #
    #   Telegram: set data_source yahoo   (switch to Yahoo — no IBKR needed)
    #             set data_source ibkr    (switch back to IBKR)
    data_source: str = "yahoo"      # default: Yahoo Finance (free, no login)

    # ── Expiry Window ─────────────────────────────────────────
    # 21–42 DTE is the professional sweet spot for theta selling.
    # Under 21 DTE gamma risk spikes — avoid.
    min_dte: int = 21
    max_dte: int = 42

    # ── Strike Range ──────────────────────────────────────────
    # Wider scan to catch more OTM candidates.
    strike_range_pct: float = 0.2  # ±20% of current price

    # ── Delta Range ───────────────────────────────────────────
    # 0.20–0.35 delta = ~65–80% probability of keeping full premium.
    # Below 0.20: too little premium. Above 0.35: too close to money.
    cc_delta_min: float = 0.20
    cc_delta_max: float = 0.35
    csp_delta_min: float = -0.35
    csp_delta_max: float = -0.20

    # ── Theta ─────────────────────────────────────────────────
    # Minimum daily time decay earned per contract.
    min_theta: float = 0.08         # $8/day minimum per contract

    # ── IV Rank ───────────────────────────────────────────────
    # WHERE current IV sits in its own 52-week history (0–100).
    # MOST IMPORTANT filter when historical data is available.
    # Selling low IV = selling cheap premium = bad risk/reward.
    # Set to 0 when IBKR history is unavailable; pair with min_iv instead.
    min_iv_rank: float = 0.0
    max_iv_rank: float = 100.0

    # ── Absolute IV Floor (raw implied volatility) ────────────
    # Independent of IV Rank — reads directly from the option quote.
    # Ensures you never sell cheap premium even when iv_rank = 0.
    #
    #   Telegram command : set min_iv 0.40
    #
    #   0.30 = 30% IV  → baseline for any options trading
    #   0.35 = 35% IV  → sensible floor for mid-vol stocks (SPY, QQQ)
    #   0.40 = 40% IV  → recommended for TSLA / high-beta names
    #   0.50 = 50% IV  → only take very high-vol trades
    #   0.00           → disabled (no raw IV check)
    min_iv: float = 0.40            # 40% absolute IV minimum — real premium floor for TSLA

    # ── Vega ──────────────────────────────────────────────────
    # Limits exposure to IV expansion (vega risk).
    # Higher-priced stocks will have naturally larger vega values.
    max_vega: float = 0.50

    # ── Return / Premium Filters ──────────────────────────────
    # Under $0.25 premium the trade isn't worth commissions + risk.
    # Target 15%+ annualised — the Wheel Strategy benchmark.
    min_annualised_return: float = 0.15  # 15% annualised minimum
    min_premium: float = 2.00            # $2.00 minimum credit — removes micro-premium noise

    # ── Liquidity Filters ─────────────────────────────────────
    # OI explanation: OI = total open contracts for this strike+expiry.
    #   High OI (500+) = liquid, tight spreads, easy to exit at 50% profit.
    #   Low OI (<100)  = illiquid, wide spreads, hard to close position.
    #
    # DEFAULT = 0 because IBKR delayed data returns OI=0 for almost all
    # contracts. This is a data limitation, not real zero liquidity.
    # Only raise min_open_interest when you have a live data subscription.
    #
    # Spread > 10% means you give up 5% of premium to the market maker
    # on entry — this filter is always active and still protects you.
    min_open_interest: int = 0      # 0 = disabled (IBKR delayed data limitation)
    min_volume: int = 0             # 0 = disabled (normal on delayed data)
    max_bid_ask_spread_pct: float = 1.0

    # ── Scoring Weights (must sum to 1.0) ─────────────────────
    # With mean reversion enabled:  IV 15 + θ 15 + δ 20 + liq 10 + ret 25 + MR 15 = 100
    # With mean reversion disabled: IV 20 + θ 20 + δ 20 + liq 10 + ret 30         = 100
    weight_iv: float = 0.15
    weight_theta_yield: float = 0.15
    weight_delta_safety: float = 0.20
    weight_liquidity: float = 0.10
    weight_ann_return: float = 0.25
    weight_mean_reversion: float = 0.15  # 6th component — price mean reversion timing

    # ── Mean Reversion Settings ───────────────────────────────
    # Toggle: set to False to disable entirely (reverts to original 5-factor scoring).
    #   Telegram: set use_mean_reversion false
    use_mean_reversion: bool = True

    # Indicator periods (match the TradingView indicator defaults)
    mr_rsi_period: int = 5              # RSI lookback (research: 5 optimal for 30-45 DTE)
    mr_z_period: int = 20               # Z-Score lookback (standard Bollinger period)
    mr_roc_period: int = 100            # ROC percentile rank lookback (Connors method)

    # Sub-indicator weights within the MR composite (must sum to 1.0)
    mr_w_rsi: float = 0.40             # momentum oscillator
    mr_w_z: float = 0.40               # displacement from mean
    mr_w_roc: float = 0.20             # surge magnitude ranking

    # Trend Guard — prevents false signals in strong trends
    mr_trend_guard: bool = True
    mr_trend_pct: float = 15.0          # % distance from SMA(200) to trigger guard

    def validate(self):
        # All 6 weights must always sum to 1.0.
        # When MR is off, the scorer re-normalises the remaining 5 at runtime,
        # but the config stores the full 6-weight split regardless of MR state.
        weights = [
            self.weight_iv, self.weight_theta_yield,
            self.weight_delta_safety, self.weight_liquidity,
            self.weight_ann_return, self.weight_mean_reversion,
        ]
        assert abs(sum(weights) - 1.0) < 0.001, (
            f"Scoring weights must sum to 1.0 (got {sum(weights):.3f})"
        )
        assert 0.0 <= self.min_iv <= 2.0, "min_iv should be 0.0–2.0 (e.g. 0.40 = 40% IV)"

        # DTE bounds
        assert self.min_dte >= 0, f"min_dte must be >= 0 (got {self.min_dte})"
        assert self.max_dte >= self.min_dte, (
            f"max_dte ({self.max_dte}) must be >= min_dte ({self.min_dte})"
        )

        # MR sub-weights
        mr_w = self.mr_w_rsi + self.mr_w_z + self.mr_w_roc
        assert abs(mr_w - 1.0) < 0.001, (
            f"MR sub-weights must sum to 1.0 (got {mr_w:.3f})"
        )
        return self

    def config_hash(self) -> str:
        """
        SHA-256 hash of this config's fields (sorted keys, deterministic).

        Purpose: audit trail. Store alongside scan results so you can
        reproduce the exact config that generated a given ranking.
        Two configs with identical parameters produce the same hash.

        Excludes `dry_run` — it doesn't affect scoring/ranking.
        """
        d = asdict(self)
        d.pop("dry_run", None)  # runtime flag, not a scoring parameter
        serialized = json.dumps(d, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
