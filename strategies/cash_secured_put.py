"""
strategies/cash_secured_put.py — Cash-Secured Put Filter
==========================================================
A Cash-Secured Put is sold when you want to BUY a stock at a lower price
(or just collect premium). You sell an OTM put and set aside cash = strike × 100.

Ideal setup:
  - Bullish to neutral underlying (you'd be OK owning it at the strike)
  - Sell -0.20 to -0.35 delta puts (OTM, 2–5% below current price)
  - 21–45 DTE for maximum theta decay
  - High IV Rank (selling expensive premium)
  - Part of "The Wheel" strategy: CSP → assignment → Covered Call

Risk management:
  - If assigned: you buy 100 shares at strike (your cost basis = strike - premium)
  - Only sell CSPs on stocks you are WILLING to own!

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


class CashSecuredPutFilter:
    STRATEGY_NAME = "CASH_SECURED_PUT"

    def __init__(self, config: ScannerConfig):
        self.cfg = config

    def applies_to(self, contract: OptionContract) -> bool:
        """Only evaluate PUT options for CSPs."""
        return contract.is_put

    def evaluate(
        self,
        contract: OptionContract,
        greeks: GreeksResult,
        iv_rank: float,
        ann_return: float,
    ) -> Optional[ScanOpportunity]:
        """
        Apply all cash-secured put filters.
        Returns ScanOpportunity if it passes, None if it fails.
        """
        reason = self._check_filters(contract, greeks, iv_rank, ann_return)

        if reason:
            log.debug("CSP REJECT %s $%.2f: %s", contract.ticker, contract.strike, reason)
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

        # Delta range: put delta is negative; we want -0.35 to -0.20
        if not (cfg.csp_delta_min <= greeks.delta <= cfg.csp_delta_max):
            return (f"delta {greeks.delta:.3f} outside "
                    f"[{cfg.csp_delta_min}, {cfg.csp_delta_max}]")

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

        # Minimum premium
        if contract.mid < cfg.min_premium:
            return f"premium ${contract.mid:.2f} below min ${cfg.min_premium}"

        # Strike must be BELOW underlying (OTM put)
        if contract.strike >= contract.underlying_price:
            return f"strike ${contract.strike} not below underlying ${contract.underlying_price}"

        # Annualised return check (use strike as capital at risk for CSP)
        if contract.dte <= 0 or contract.strike <= 0:
            return "invalid dte or strike for annualised return calculation"
        csp_return = (contract.mid / contract.strike) * (365 / contract.dte)
        if csp_return < cfg.min_annualised_return:
            return f"ann return {csp_return*100:.1f}% below min {cfg.min_annualised_return*100:.0f}%"

        return None  # all filters passed
