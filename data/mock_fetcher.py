"""
data/mock_fetcher.py — Mock Data Fetcher for Dry-Run / Testing
===============================================================
Generates realistic synthetic option chain data so you can:
  1. Test the scanner logic without an IBKR connection
  2. Develop and debug strategies
  3. Run unit tests in CI/CD

The mock data is built from realistic assumptions about option pricing
using approximate Black-Scholes values for common stocks.
"""
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))


import math
import random
import logging
from datetime import date, timedelta
from typing import List, Dict

from core.config import ScannerConfig
from core.models import OptionContract

log = logging.getLogger(__name__)

# Realistic mock prices and IVs for common tickers
MOCK_UNDERLYINGS = {
    "SPY":  {"price": 510.00, "iv": 0.18, "iv_low": 0.12, "iv_high": 0.35},
    "QQQ":  {"price": 430.00, "iv": 0.22, "iv_low": 0.15, "iv_high": 0.40},
    "AAPL": {"price": 190.00, "iv": 0.28, "iv_low": 0.18, "iv_high": 0.55},
    "MSFT": {"price": 415.00, "iv": 0.25, "iv_low": 0.16, "iv_high": 0.50},
    "NVDA": {"price": 820.00, "iv": 0.55, "iv_low": 0.35, "iv_high": 0.90},
    "TSLA": {"price": 195.00, "iv": 0.65, "iv_low": 0.40, "iv_high": 1.10},
    "AMZN": {"price": 185.00, "iv": 0.30, "iv_low": 0.20, "iv_high": 0.55},
    "META": {"price": 490.00, "iv": 0.35, "iv_low": 0.22, "iv_high": 0.70},
    "GOOGL":{"price": 172.00, "iv": 0.27, "iv_low": 0.18, "iv_high": 0.50},
    "AMD":  {"price": 165.00, "iv": 0.48, "iv_low": 0.30, "iv_high": 0.80},
}

DEFAULT_MOCK = {"price": 100.00, "iv": 0.30, "iv_low": 0.20, "iv_high": 0.55}


class MockFetcher:
    """Generates synthetic but realistic option chain data for testing."""

    def __init__(self, config: ScannerConfig):
        self.config = config
        random.seed(42)  # reproducible results
        log.info("MockFetcher: Using synthetic data (dry-run mode)")

    def fetch_option_chain(self, ticker: str, progress_cb=None) -> List[OptionContract]:
        """Generate a synthetic option chain for the ticker."""
        mock = MOCK_UNDERLYINGS.get(ticker, DEFAULT_MOCK)
        underlying_price = mock["price"] * (1 + random.uniform(-0.02, 0.02))
        base_iv = mock["iv"] * (1 + random.uniform(-0.10, 0.15))

        contracts = []
        today = date.today()

        # Generate 3 expirations within DTE window
        dtes = self._get_sample_dtes()

        # Generate strikes from -25% to +25% ATM in 2.5% steps
        strike_offsets = [-0.20, -0.15, -0.10, -0.075, -0.05, -0.025,
                           0.025, 0.05, 0.075, 0.10, 0.15, 0.20]

        for dte in dtes:
            exp_date = today + timedelta(days=dte)
            for offset in strike_offsets:
                strike = round(underlying_price * (1 + offset), 1)
                iv = base_iv * (1 + abs(offset) * 0.5)  # IV smile

                for opt_type in ["C", "P"]:
                    # Skip calls far below ATM and puts far above ATM
                    if opt_type == "C" and offset < -0.05:
                        continue
                    if opt_type == "P" and offset > 0.05:
                        continue

                    contract = self._make_contract(
                        ticker, underlying_price, strike,
                        exp_date, dte, opt_type, iv
                    )
                    if contract:
                        contracts.append(contract)

        log.debug("MockFetcher: Generated %d contracts for %s", len(contracts), ticker)
        return contracts

    def fetch_iv_history(self, ticker: str) -> Dict:
        mock = MOCK_UNDERLYINGS.get(ticker, DEFAULT_MOCK)
        # Generate synthetic price history for mean reversion indicators
        import random
        base = mock["price"]
        prices = [base]
        for _ in range(251):  # ~1 year of daily bars
            prices.append(prices[-1] * (1 + random.gauss(0, 0.02)))
        return {
            "iv_52w_low":  mock["iv_low"],
            "iv_52w_high": mock["iv_high"],
            "prices": prices,
        }

    def _get_sample_dtes(self) -> List[int]:
        """Return realistic DTE values within the configured window."""
        cfg = self.config
        mid = (cfg.min_dte + cfg.max_dte) // 2
        dtes = [
            max(cfg.min_dte, mid - 10),
            mid,
            min(cfg.max_dte, mid + 10),
        ]
        return sorted(set(dtes))

    def _make_contract(
        self, ticker: str, underlying_price: float, strike: float,
        exp_date: date, dte: int, opt_type: str, iv: float
    ) -> OptionContract:
        """Build a single synthetic contract with approximate pricing."""
        # Approximate premium using simplified BS
        T = dte / 365
        moneyness = underlying_price / strike if opt_type == "C" else strike / underlying_price
        atm_premium = underlying_price * iv * math.sqrt(T) * 0.4  # rough ATM approx
        otm_factor = max(0.05, 1.0 - max(0, moneyness - 1.0) * 5)
        mid_price = max(0.05, atm_premium * otm_factor * random.uniform(0.85, 1.15))

        bid = round(mid_price * 0.95, 2)
        ask = round(mid_price * 1.05, 2)

        # Volume and OI scale with liquidity of the ticker
        base_oi = {"SPY": 5000, "QQQ": 3000}.get(ticker, 500)
        open_interest = int(base_oi * otm_factor * random.uniform(0.5, 2.0))
        volume = int(open_interest * random.uniform(0.05, 0.30))

        return OptionContract(
            ticker=ticker,
            underlying_price=round(underlying_price, 2),
            strike=strike,
            expiry=exp_date,
            dte=dte,
            option_type=opt_type,
            bid=bid,
            ask=ask,
            last=round(mid_price * random.uniform(0.97, 1.03), 2),
            volume=max(1, volume),
            open_interest=max(10, open_interest),
            implied_vol=round(iv, 4),
        )
