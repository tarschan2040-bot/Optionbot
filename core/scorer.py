"""
core/scorer.py — Composite Opportunity Scorer
===============================================
Scores each opportunity 0–100 using weighted factors.
All sub-scores are normalised to 0–1 before weighting.

Score Components (6-factor with mean reversion enabled):
  1. IV             → Raw annualised IV — higher = richer premium = better to sell
  2. Theta Yield    → Theta earned as % of premium per day
  3. Delta Safety   → How far OTM (lower |delta| = safer)
  4. Liquidity      → Open interest + tight bid/ask
  5. Ann. Return    → Annualised return on capital
  6. Mean Reversion → Price momentum/displacement timing (direction-aware)

When use_mean_reversion=False, falls back to original 5-factor scoring
with weights automatically redistributed to maintain sum=1.0.
"""
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))


import logging
from core.config import ScannerConfig
from core.models import ScanOpportunity

log = logging.getLogger(__name__)


class OpportunityScorer:
    def __init__(self, config: ScannerConfig):
        self.cfg = config

    def score(self, opp: ScanOpportunity) -> float:
        """Return composite score 0–100. Higher = better sell opportunity."""
        scores = {
            "iv":           self._score_iv(opp.iv),
            "theta_yield":  self._score_theta_yield(opp),
            "delta_safety": self._score_delta_safety(opp),
            "liquidity":    self._score_liquidity(opp),
            "ann_return":   self._score_ann_return(opp.annualised_return),
        }

        weights = {
            "iv":           self.cfg.weight_iv,
            "theta_yield":  self.cfg.weight_theta_yield,
            "delta_safety": self.cfg.weight_delta_safety,
            "liquidity":    self.cfg.weight_liquidity,
            "ann_return":   self.cfg.weight_ann_return,
        }

        # ── 6th component: Mean Reversion ────────────────────────
        if self.cfg.use_mean_reversion:
            # mean_rev_score is already 0–1, direction-aware, computed by indicators.py
            scores["mean_reversion"] = opp.mean_rev_score
            weights["mean_reversion"] = self.cfg.weight_mean_reversion
        else:
            # When MR is disabled, redistribute its weight proportionally
            # across the original 5 factors so composite scale stays the same.
            # The config still stores the 6-factor weights, but we ignore MR
            # and re-normalise the remaining 5 to sum to 1.0.
            total_5 = sum(weights.values())
            if total_5 > 0:
                for k in weights:
                    weights[k] /= total_5

        composite = sum(scores[k] * weights[k] for k in scores) * 100
        return round(composite, 2)

    # ── Sub-scorers (each returns 0.0–1.0) ───────────────────

    def _score_iv(self, iv: float) -> float:
        """
        Absolute IV score — linear normalisation, no step jumps.
        Formula: (iv - 0.45) / 0.55, clamped 0.0–1.0.

        Anchor points:
          iv = 0.45  →  0.00  (floor — don't sell cheap premium)
          iv = 0.60  →  0.27  (marginal)
          iv = 0.70  →  0.45  (decent)
          iv = 0.80  →  0.64  (good)
          iv = 0.95  →  0.91  (excellent)
          iv = 1.00  →  1.00  (max)

        TSLA typical range 0.50–0.85 → score 0.09–0.73.
        No artificial cap at high IV — rewards genuinely expensive premium.
        """
        return max(0.0, min(1.0, (iv - 0.45) / 0.55))

    def _score_theta_yield(self, opp: ScanOpportunity) -> float:
        """
        Theta yield = daily theta / premium.
        Higher % = faster decay relative to what you sold for.
        Target: 1–3% daily theta yield is excellent.
        """
        if opp.premium <= 0:
            return 0.0
        yield_pct = opp.theta / opp.premium
        if yield_pct < 0.005:   return 0.1
        if yield_pct < 0.010:   return 0.3
        if yield_pct < 0.015:   return 0.6
        if yield_pct < 0.025:   return 0.85
        return 1.0

    def _score_delta_safety(self, opp: ScanOpportunity) -> float:
        """
        Lower absolute delta = more OTM = safer = higher score.
        Sweet spot for sellers: |delta| between 0.20 and 0.35.
        """
        abs_delta = abs(opp.delta)
        if abs_delta > 0.50:    return 0.0   # ITM — never sell
        if abs_delta > 0.40:    return 0.2
        if abs_delta > 0.35:    return 0.5
        if abs_delta > 0.25:    return 0.9   # sweet spot
        if abs_delta > 0.15:    return 0.8
        return 0.5  # very OTM — safe but low premium

    def _score_liquidity(self, opp: ScanOpportunity) -> float:
        """Score based on OI and bid/ask spread."""
        c = opp.contract
        # OI score
        if c.open_interest >= 5000:   oi_score = 1.0
        elif c.open_interest >= 1000: oi_score = 0.8
        elif c.open_interest >= 500:  oi_score = 0.6
        elif c.open_interest >= 100:  oi_score = 0.4
        else:                         oi_score = 0.1

        # Spread score (tighter is better)
        spread = c.spread_pct
        if spread <= 0.03:    spread_score = 1.0
        elif spread <= 0.05:  spread_score = 0.8
        elif spread <= 0.08:  spread_score = 0.6
        elif spread <= 0.12:  spread_score = 0.4
        else:                 spread_score = 0.2

        return (oi_score * 0.6) + (spread_score * 0.4)

    def _score_ann_return(self, ann_return: float) -> float:
        """
        Annualised return on capital.
        Target: 10–30% is realistic for consistent income selling.
        """
        if ann_return < 0.05:   return 0.1
        if ann_return < 0.10:   return 0.3
        if ann_return < 0.15:   return 0.6
        if ann_return < 0.25:   return 0.85
        if ann_return < 0.40:   return 1.0
        return 0.8  # very high return usually means high risk
