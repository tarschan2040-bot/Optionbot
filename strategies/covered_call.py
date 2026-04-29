"""
strategies/covered_call.py — Covered Call Filter
==================================================
A Covered Call is sold when you OWN 100 shares and sell a call above
the current price to collect premium.

Ideal setup:
  - Mildly bullish to neutral underlying
  - Sell 0.25–0.35 delta calls (OTM, 2–5% above current price)
  - 21–45 DTE for maximum theta decay
  - High IV Rank (selling expensive premium)
  - Exit at 50% profit or 21 DTE (standard wheel/CC management)

IV FILTERING — two independent layers
  1. iv_rank  : relative filter — where IV sits in 52-week range
  2. min_iv   : absolute floor  — raw IV must be high enough regardless
  Both can be active simultaneously, or either can be disabled (set to 0).
"""
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))


import logging
from typing import Optional

from core.config import ScannerConfig
from core.models import OptionContract, GreeksResult, ScanOpportunity

log = logging.getLogger(__name__)


class CoveredCallFilter:
    STRATEGY_NAME = "COVERED_CALL"

    def __init__(self, config: ScannerConfig):
        self.cfg = config

    def applies_to(self, contract: OptionContract) -> bool:
        """Only evaluate CALL options for covered calls."""
        return contract.is_call

    def evaluate(
        self,
        contract: OptionContract,
        greeks: GreeksResult,
        iv_rank: float,
        ann_return: float,
    ) -> Optional[ScanOpportunity]:
        """
        Apply all covered call filters.
        Returns ScanOpportunity if it passes, None if it fails.
        """
        cfg = self.cfg
        reason = self._check_filters(contract, greeks, iv_rank, ann_return)

        if reason:
            log.debug("CC REJECT %s $%.2f: %s", contract.ticker, contract.strike, reason)
            return None

        theta_yield = greeks.theta / contract.mid if contract.mid > 0 else 0

        return ScanOpportunity(
            contract=contract,
            greeks=greeks,
            strategy=self.STRATEGY_NAME,
            iv_rank=iv_rank,
            annualised_return=ann_return,
            theta_yield=theta_yield,
        )

    def _check_filters(self, contract, greeks, iv_rank, ann_return) -> Optional[str]:
        cfg = self.cfg

        # Delta range: sell OTM calls with moderate delta
        if not (cfg.cc_delta_min <= greeks.delta <= cfg.cc_delta_max):
            return (f"delta {greeks.delta:.3f} outside "
                    f"[{cfg.cc_delta_min}, {cfg.cc_delta_max}]")

        # Theta: must earn meaningful daily decay
        if greeks.theta < cfg.min_theta:
            return f"theta ${greeks.theta:.3f} below min ${cfg.min_theta}"

        # IV Rank filter (relative): only active when min_iv_rank > 0
        # Requires IBKR historical data. Set min_iv_rank=0 to disable.
        if cfg.min_iv_rank > 0 and iv_rank < cfg.min_iv_rank:
            return f"IV Rank {iv_rank:.0f} below min {cfg.min_iv_rank:.0f}"

        # Absolute IV floor (raw IV): active when min_iv > 0
        # Works independently of IV Rank — reads directly from option quote.
        # Use this when min_iv_rank=0 (no IBKR history) to still gate on premium quality.
        if cfg.min_iv > 0 and contract.implied_vol < cfg.min_iv:
            return (f"IV {contract.implied_vol*100:.1f}% below min "
                    f"{cfg.min_iv*100:.1f}% — premium too cheap")

        # Vega: avoid too much IV sensitivity
        if greeks.vega > cfg.max_vega:
            return f"vega {greeks.vega:.3f} above max {cfg.max_vega}"

        # Minimum premium: avoid pennies
        if contract.mid < cfg.min_premium:
            return f"premium ${contract.mid:.2f} below min ${cfg.min_premium}"

        # Strike must be ABOVE underlying (OTM call)
        if contract.strike <= contract.underlying_price:
            return f"strike ${contract.strike} not above underlying ${contract.underlying_price}"

        # Annualised return check
        if ann_return < cfg.min_annualised_return:
            return f"ann return {ann_return*100:.1f}% below min {cfg.min_annualised_return*100:.0f}%"

        return None  # all filters passed
