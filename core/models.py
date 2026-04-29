"""
core/models.py — Data models for options and scan results.
Using dataclasses for clean, typed, IDE-friendly structures.
"""
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))


from dataclasses import dataclass, field
from typing import Optional
from datetime import date


@dataclass
class OptionContract:
    """Raw option contract data fetched from IBKR."""
    ticker: str
    underlying_price: float
    strike: float
    expiry: date
    dte: int                        # days to expiration
    option_type: str                # "C" or "P"
    bid: float
    ask: float
    last: float
    volume: int
    open_interest: int
    implied_vol: float              # annualised IV (e.g. 0.35 = 35%)

    @property
    def mid(self) -> float:
        return (self.bid + self.ask) / 2

    @property
    def spread_pct(self) -> float:
        if self.mid == 0:
            return 1.0
        return (self.ask - self.bid) / self.mid

    @property
    def is_call(self) -> bool:
        return self.option_type == "C"

    @property
    def is_put(self) -> bool:
        return self.option_type == "P"

    def __repr__(self):
        return (f"<Option {self.ticker} {self.option_type} "
                f"${self.strike} exp={self.expiry} DTE={self.dte}>")


@dataclass
class GreeksResult:
    """Black-Scholes Greeks for a contract."""
    delta: float
    gamma: float
    theta: float        # daily theta (negative for buyer, positive view for seller)
    vega: float         # per 1% IV move
    rho: float
    iv: float           # implied vol used
    theoretical_price: float


@dataclass
class ScanOpportunity:
    """A fully evaluated sell option opportunity."""
    contract: OptionContract
    greeks: GreeksResult
    strategy: str               # "COVERED_CALL" or "CASH_SECURED_PUT"

    # Computed metrics
    iv_rank: float              # 0–100
    annualised_return: float    # e.g. 0.25 = 25%
    theta_yield: float          # daily theta / premium received
    score: float = 0.0          # composite ranking score (0–100)

    # Mean reversion indicators (populated by indicators.py)
    mean_rev_score: float = 0.0         # 0–1 composite (direction-aware)
    rsi_5: float = 50.0                 # raw RSI(5) value (0–100)
    z_score_20: float = 0.0             # raw Z-Score(20) (typically -3 to +3)
    roc_pct_rank: float = 50.0          # ROC percentile rank (0–100)
    trend_guard_active: bool = False     # True if score was capped
    sma200_distance_pct: float = 0.0    # % distance from SMA(200)

    # Filter flags (for debugging)
    passed_filters: bool = True
    filter_reason: Optional[str] = None

    @property
    def premium(self) -> float:
        return self.contract.mid

    @property
    def ticker(self) -> str:
        return self.contract.ticker

    @property
    def strike(self) -> float:
        return self.contract.strike

    @property
    def expiry(self) -> date:
        return self.contract.expiry

    @property
    def dte(self) -> int:
        return self.contract.dte

    @property
    def delta(self) -> float:
        return self.greeks.delta

    @property
    def theta(self) -> float:
        return self.greeks.theta

    @property
    def iv(self) -> float:
        return self.greeks.iv

    def summary_dict(self) -> dict:
        d = {
            "Ticker":       self.ticker,
            "Strategy":     self.strategy,
            "Strike":       f"${self.strike:.2f}",
            "Expiry":       str(self.expiry),
            "DTE":          self.dte,
            "Premium":      f"${self.premium:.2f}",
            "Delta":        f"{self.delta:+.3f}",
            "Theta":        f"${self.theta:.3f}",
            "IV":           f"{self.iv*100:.1f}%",
            "IV Rank":      f"{self.iv_rank:.0f}",
            "Ann. Return":  f"{self.annualised_return*100:.1f}%",
            "Score":        f"{self.score:.1f}",
        }
        # Mean reversion fields (only if populated / non-default)
        if self.mean_rev_score > 0:
            tg_flag = " ⚠TG" if self.trend_guard_active else ""
            d["MR Score"] = f"{self.mean_rev_score:.2f}{tg_flag}"
            d["RSI(5)"] = f"{self.rsi_5:.0f}"
            d["Z-Score"] = f"{self.z_score_20:+.2f}"
            d["ROC %Rank"] = f"{self.roc_pct_rank:.0f}"
        return d
