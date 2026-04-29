import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

"""
data/yfinance_fetcher.py
==========================
FREE option chain data from Yahoo Finance — no IBKR, no login, no session conflicts.

WHY THIS EXISTS
---------------
IB Gateway requires a logged-in IBKR session to serve data.
If Ken logs in via phone, the desktop Gateway session is kicked — bot dies.
This fetcher solves that: runs 24/7 with no login required.

DATA QUALITY
------------
  Option chain   : 15-min delayed during market hours
  Underlying     : Real-time price from Yahoo
  Greeks         : NOT from Yahoo — calculated by our Black-Scholes engine
  IV (implied)   : Provided per-contract by Yahoo (annualised, e.g. 0.65 = 65%)
  IV Rank        : Approximated from 1-year realized volatility range (see note)
  Open Interest  : Available (delayed, but more reliable than IBKR delayed which returns 0)

IV RANK NOTE
------------
  Yahoo does not provide 52-week IV history. We approximate IV Rank by calculating
  the 30-day rolling annualised historical volatility over the past year, then finding
  where today's option IV sits in that range.
  Result: not identical to IBKR's IV Rank, but directionally correct and sufficient
  for the go/no-go decision on premium-selling trades.

SPEED
-----
  yfinance: ~5-30 seconds per ticker (one API call per expiry)
  IBKR: ~2 min per ticker (batch-polling 30 contracts at a time)
  This means faster scan cycles and real-time scan results.

LIMITATIONS
-----------
  - Data is ~15 min delayed during market hours
  - For 30-45 DTE options selling this delay is operationally irrelevant
  - Yahoo rate-limits heavy usage — scanning many tickers rapidly may slow down
  - IV Rank is approximate (historical vol proxy), not exact IBKR iv_history_rank
"""

import logging
import math
import urllib.request
import json
import time
from datetime import date, datetime
from typing import List, Dict, Optional, Callable

from core.config import ScannerConfig
from core.models import OptionContract
from core.greeks import calculate_implied_vol, RISK_FREE_RATE

log = logging.getLogger(__name__)

try:
    import yfinance as yf
    YF_AVAILABLE = True
except ImportError:
    YF_AVAILABLE = False
    log.warning("yfinance not installed. Run: pip3 install yfinance")

try:
    import pandas as pd
    PD_AVAILABLE = True
except ImportError:
    PD_AVAILABLE = False


def _safe_float(val, default=0.0) -> float:
    """Convert value to float, returning default on NaN/None/error."""
    try:
        f = float(val)
        return f if not math.isnan(f) else default
    except Exception:
        return default


def _safe_int(val, default=0) -> int:
    try:
        return int(val)
    except Exception:
        return default


def get_price_yahoo(ticker: str) -> float:
    """Fetch current stock price from Yahoo Finance JSON API (no yfinance needed)."""
    try:
        url = (f"https://query1.finance.yahoo.com/v8/finance/chart/"
               f"{ticker}?interval=1d&range=1d")
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        result = data["chart"]["result"][0]
        price = (result["meta"].get("regularMarketPrice")
                 or result["meta"].get("previousClose"))
        if price and price > 0:
            log.info("%s price from Yahoo: $%.2f", ticker, price)
            return float(price)
    except Exception as e:
        log.warning("%s: Yahoo price failed: %s", ticker, e)
    return 0.0


class YFinanceFetcher:
    """
    Drop-in replacement for IBKRFetcher using Yahoo Finance option chain data.
    Implements the same interface: fetch_option_chain(), fetch_iv_history(), disconnect().
    """

    def __init__(self, config: ScannerConfig):
        self.config = config
        if not YF_AVAILABLE:
            raise RuntimeError(
                "yfinance not installed. Run: pip3 install yfinance"
            )
        log.info("YFinanceFetcher initialised — no IBKR connection needed.")

    def disconnect(self):
        """No-op: yfinance has no persistent connection to close."""
        pass

    # ── IV History (for IV Rank calculation) ────────────────────────────

    def fetch_iv_history(self, ticker: str) -> Dict:
        """
        Approximate 52-week IV range using historical realized volatility,
        AND return the close prices for mean reversion indicator calculation.

        Method:
          1. Download 1-year daily price history via yfinance
          2. Calculate rolling 30-day annualised realized vol (HV30)
          3. Return min/max of HV30 as proxy for 52w IV low/high
          4. Return close prices list for RSI/Z-Score/ROC computation

        This is a proxy — realized vol ≠ implied vol, but they are strongly
        correlated. Good enough to determine if IV is elevated or depressed
        for premium-selling decisions.

        Returns dict with keys:
          iv_52w_low, iv_52w_high : float
          prices : List[float]  — daily closes, oldest first (up to ~252 bars)
        """
        default = {"iv_52w_low": 0.20, "iv_52w_high": 0.80, "prices": []}
        if not YF_AVAILABLE or not PD_AVAILABLE:
            log.warning("%s: yfinance/pandas unavailable — using default IV range", ticker)
            return default

        try:
            hist = yf.Ticker(ticker).history(period="1y")
            if hist.empty or len(hist) < 30:
                log.warning("%s: insufficient price history for IV proxy", ticker)
                return default

            # Extract close prices for mean reversion indicators (oldest first)
            prices = hist["Close"].dropna().tolist()

            returns = hist["Close"].pct_change().dropna()
            # 30-day rolling annualised realised volatility
            hv30 = returns.rolling(30).std() * (252 ** 0.5)
            hv30 = hv30.dropna()
            if hv30.empty:
                return {**default, "prices": prices}

            iv_low = float(hv30.min())
            iv_high = float(hv30.max())
            log.info("%s: HV proxy — 52w low=%.1f%% high=%.1f%% (%d price bars)",
                     ticker, iv_low * 100, iv_high * 100, len(prices))
            return {"iv_52w_low": iv_low, "iv_52w_high": iv_high, "prices": prices}

        except Exception as e:
            log.warning("%s: IV history error: %s — using defaults", ticker, e)
            return default

    # ── Main option chain fetch ──────────────────────────────────────────

    def fetch_option_chain(
        self,
        ticker: str,
        progress_cb: Optional[Callable[[str], None]] = None,
    ) -> List[OptionContract]:
        """
        Fetch all option contracts for a ticker via Yahoo Finance.

        Flow:
          1. Get underlying price from Yahoo
          2. Get available expiry dates from yfinance
          3. Filter expiries to DTE range
          4. For each valid expiry: fetch option chain, filter strikes
          5. Return list of OptionContract objects (same as IBKRFetcher)
        """
        cfg = self.config

        # 1. Underlying price
        underlying_price = get_price_yahoo(ticker)
        if underlying_price <= 0:
            # Fallback: try yfinance fast_info
            try:
                underlying_price = _safe_float(
                    yf.Ticker(ticker).fast_info.get("lastPrice", 0)
                )
            except Exception:
                pass
        if underlying_price <= 0:
            log.warning("%s: Could not get underlying price", ticker)
            return []

        # 2. Available expiry dates
        try:
            tkr = yf.Ticker(ticker)
            available_expiries = tkr.options  # tuple of "YYYY-MM-DD" strings
        except Exception as e:
            log.warning("%s: Could not fetch option expiries: %s", ticker, e)
            return []

        if not available_expiries:
            log.warning("%s: No option expiries returned by Yahoo", ticker)
            return []

        # 3. Filter expiries by DTE range
        today = date.today()
        valid_expiries = []
        for exp_str in available_expiries:
            try:
                exp_date = datetime.strptime(exp_str, "%Y-%m-%d").date()
                dte = (exp_date - today).days
                if cfg.min_dte <= dte <= cfg.max_dte:
                    valid_expiries.append((exp_str, exp_date, dte))
            except ValueError:
                continue

        if not valid_expiries:
            log.warning(
                "%s: No expiries in DTE range %d-%d. Available: %s",
                ticker, cfg.min_dte, cfg.max_dte,
                [e for e in available_expiries[:6]]
            )
            return []

        # 4. Determine which option types to fetch
        fetch_calls = cfg.strategy in ("cc", "both")
        fetch_puts  = cfg.strategy in ("csp", "both")

        # Strike filter bounds
        strike_lo = underlying_price * (1 - cfg.strike_range_pct)
        strike_hi = underlying_price * (1 + cfg.strike_range_pct)

        # Progress header
        if progress_cb:
            exp_lines = "  " + " · ".join(
                f"`{exp_date.strftime('%b %d')}` ({dte}d)"
                for (_, exp_date, dte) in valid_expiries
            )
            progress_cb(
                f"📡 *{ticker}* @ ${underlying_price:.2f}  _(Yahoo Finance — 15min delay)_\n"
                f"\n"
                f"📅 *Expiries ({len(valid_expiries)}):*\n{exp_lines}\n"
                f"\n"
                f"⚙️ Fetching option chains... (no IBKR needed)"
            )

        # 5. Fetch each expiry and collect contracts
        contracts: List[OptionContract] = []

        for i, (exp_str, exp_date, dte) in enumerate(valid_expiries, 1):
            try:
                chain = tkr.option_chain(exp_str)
            except Exception as e:
                log.warning("%s: option_chain(%s) failed: %s", ticker, exp_str, e)
                continue

            # Small pause to be polite to Yahoo — avoid rate limiting
            if i > 1:
                time.sleep(0.5)

            # Process calls
            if fetch_calls and chain.calls is not None and not chain.calls.empty:
                calls_filtered = chain.calls[
                    (chain.calls["strike"] >= strike_lo) &
                    (chain.calls["strike"] <= strike_hi)
                ]
                for _, row in calls_filtered.iterrows():
                    c = self._row_to_contract(
                        row, ticker, underlying_price, exp_date, dte, "C"
                    )
                    if c:
                        contracts.append(c)

            # Process puts
            if fetch_puts and chain.puts is not None and not chain.puts.empty:
                puts_filtered = chain.puts[
                    (chain.puts["strike"] >= strike_lo) &
                    (chain.puts["strike"] <= strike_hi)
                ]
                for _, row in puts_filtered.iterrows():
                    c = self._row_to_contract(
                        row, ticker, underlying_price, exp_date, dte, "P"
                    )
                    if c:
                        contracts.append(c)

            log.info(
                "%s %s (DTE=%d): %d contracts in strike range",
                ticker, exp_str, dte,
                sum(1 for c in contracts if c.expiry == exp_date)
            )

        if progress_cb:
            progress_cb(
                f"✅ *{ticker}*: {len(contracts)} contracts fetched "
                f"across {len(valid_expiries)} expir{'y' if len(valid_expiries)==1 else 'ies'}"
            )

        log.info("%s: YFinanceFetcher returned %d contracts", ticker, len(contracts))
        return contracts

    # ── Row parser ───────────────────────────────────────────────────────

    def _row_to_contract(
        self, row, ticker: str, underlying_price: float,
        exp_date: date, dte: int, opt_type: str
    ) -> Optional[OptionContract]:
        """Parse one row from yfinance option_chain DataFrame → OptionContract."""

        strike = _safe_float(row.get("strike", 0))
        if strike <= 0:
            return None

        bid       = _safe_float(row.get("bid", 0))
        ask       = _safe_float(row.get("ask", 0))
        last      = _safe_float(row.get("lastPrice", 0))
        volume    = _safe_int(row.get("volume", 0))
        oi        = _safe_int(row.get("openInterest", 0))
        iv        = _safe_float(row.get("impliedVolatility", 0))

        # Must have SOME price data
        if bid <= 0 and ask <= 0 and last <= 0:
            return None

        # If bid/ask missing but we have last price, synthesise a spread
        if bid <= 0 and ask <= 0 and last > 0:
            bid = last * 0.95
            ask = last * 1.05

        # ── Implied Volatility — compute from price, don't trust Yahoo ──────
        #
        # Yahoo Finance's impliedVolatility column has a persistent data-quality
        # bug: it returns a per-period (often per-day) vol instead of annualised,
        # giving values like 0–6% for TSLA where true IV is 60–100%.
        #
        # Fix: always back-solve IV from the option's mid price using our own
        # Black-Scholes solver. Fall back to Yahoo's figure only if the solver
        # fails (e.g., deep ITM options where BS is numerically unstable).
        # ─────────────────────────────────────────────────────────────────────
        mid = (bid + ask) / 2.0 if (bid > 0 and ask > 0) else last
        T_years = dte / 365.0

        bs_iv = 0.0
        if mid > 0 and T_years > 0:
            bs_iv = calculate_implied_vol(
                market_price=mid,
                S=underlying_price,
                K=strike,
                T=T_years,
                r=RISK_FREE_RATE,
                is_call=(opt_type == "C"),
            )

        if bs_iv > 0:
            if iv > 0 and abs(bs_iv - iv) > 0.10:
                # Yahoo and BS disagree by >10pp — log for diagnostics
                log.debug(
                    "%s $%.0f %s: Yahoo IV=%.1f%% vs BS IV=%.1f%% — using BS",
                    ticker, strike, opt_type,
                    iv * 100, bs_iv * 100,
                )
            iv = bs_iv
        elif iv <= 0.0:
            # Both Yahoo and BS solver failed — no usable IV, skip contract
            return None
        # (else: BS failed but Yahoo has something — use Yahoo as last resort)

        # Cap extreme values (>3.0 = 300%+) which occur on deep ITM/OTM junk.
        if iv > 3.0:
            iv = 3.0

        return OptionContract(
            ticker=ticker,
            underlying_price=underlying_price,
            strike=strike,
            expiry=exp_date,
            dte=dte,
            option_type=opt_type,
            bid=bid,
            ask=ask,
            last=last,
            volume=volume,
            open_interest=oi,
            implied_vol=iv,
        )
