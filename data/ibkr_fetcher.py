import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

"""
data/ibkr_fetcher.py
Uses Yahoo Finance for underlying prices (free, no subscription needed).
Uses IBKR only for option chain data (strikes, expirations, quotes).

Speed optimisation: batch reqMktData calls instead of one-by-one with sleep.

Market data type logic:
  IBKR accounts without a live options data subscription get Error 354/10091
  when requesting Type 1 (live).  IBKR itself says "Delayed market data is
  available" — meaning Type 3 (delayed 15-min) works.
  We probe once per scan: try each type on a real ATM option, use the first
  type that returns data.  Order: 3 → 1 → 4 → 2
  (delayed preferred because most accounts have it; live tried next in case
  the user upgrades subscription; then delayed-frozen, then frozen).
"""

import asyncio
import logging
import math
import random
import time
import urllib.request
import json
from datetime import date, datetime
from typing import List, Dict, Optional, Callable

from core.config import ScannerConfig
from core.models import OptionContract

log = logging.getLogger(__name__)

try:
    from ib_insync import IB, Stock, Option, util
    IB_AVAILABLE = True
except (ImportError, RuntimeError):
    IB_AVAILABLE = False
    log.warning("ib_insync not available.")

BATCH_SIZE = 30       # request this many contracts at once
BATCH_WAIT_LIVE   = 5.0    # seconds to wait per batch when market is open
BATCH_WAIT_FROZEN = 8.0    # seconds to wait per batch for frozen/delayed data

TYPE_NAMES = {1: "live streaming", 2: "frozen", 3: "delayed 15-min", 4: "delayed-frozen"}


def _is_market_open() -> bool:
    """Returns True if US market is currently open (Mon-Fri 9:30-16:00 ET)."""
    from datetime import timezone, timedelta
    try:
        import pytz
        et = pytz.timezone("America/New_York")
        now = datetime.now(et)
    except ImportError:
        month = datetime.utcnow().month
        if 3 <= month <= 10:
            offset = -4  # EDT
        else:
            offset = -5  # EST
        et = timezone(timedelta(hours=offset))
        now = datetime.now(et)
    if now.weekday() >= 5:
        return False
    market_open  = now.replace(hour=9,  minute=30, second=0, microsecond=0)
    market_close = now.replace(hour=16, minute=0,  second=0, microsecond=0)
    return market_open <= now <= market_close


def _ensure_event_loop():
    """ib_insync needs an asyncio event loop — background threads don't have one."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError("closed")
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop


def get_price_yahoo(ticker: str) -> float:
    """Fetch current price from Yahoo Finance — free, no subscription needed."""
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=1d"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        result = data["chart"]["result"][0]
        price = result["meta"].get("regularMarketPrice") or result["meta"].get("previousClose")
        if price and price > 0:
            log.info("%s price from Yahoo: $%.2f", ticker, price)
            return float(price)
    except Exception as e:
        log.warning("%s: Yahoo price failed: %s", ticker, e)
    return 0.0


class IBKRFetcher:
    def __init__(self, config: ScannerConfig):
        self.config = config
        self.ib: Optional["IB"] = None
        self._active_data_type: int = 3  # default to delayed (most widely available)
        _ensure_event_loop()
        self._connect()

    def _connect(self):
        if not IB_AVAILABLE:
            raise RuntimeError("ib_insync not installed. Run: pip3 install ib_insync")

        ports = [7497, 4002, 7496, 4001]
        last_error = None
        for port in ports:
            client_id = random.randint(20, 99)
            try:
                log.info("Trying IBKR connection on port %d with clientId=%d...", port, client_id)
                self.ib = IB()
                self.ib.connect("127.0.0.1", port, clientId=client_id, timeout=10)
                log.info("Connected to IBKR on port %d (clientId=%d)", port, client_id)
                # Default to Type 3 (delayed) — safest for accounts without
                # live options data subscription.  Will be probed at scan time.
                self.ib.reqMarketDataType(3)
                self._active_data_type = 3
                log.info("Initial data type: 3 (delayed) — will probe at scan time")
                return
            except Exception as e:
                last_error = e
                log.warning("Port %d failed: %s", port, e)
                try:
                    self.ib.disconnect()
                except Exception:
                    pass

        raise ConnectionError(
            f"Could not connect to TWS/IB Gateway on any port. "
            f"Make sure TWS is running and API is enabled. Last error: {last_error}"
        )

    def disconnect(self):
        if self.ib and self.ib.isConnected():
            try:
                self.ib.disconnect()
                log.info("Disconnected from IBKR.")
            except Exception as e:
                log.debug("Disconnect error: %s", e)

    # ── Data type probing ─────────────────────────────────────────────────

    def _has_price(self, td) -> bool:
        """Check if a ticker data object has ANY usable price."""
        def _ok(v):
            try:
                f = float(v)
                return not math.isnan(f) and f > 0
            except Exception:
                return False

        for field in ("bid", "ask", "last", "close"):
            if _ok(getattr(td, field, None)):
                return True
        mg = getattr(td, "modelGreeks", None)
        if mg and _ok(getattr(mg, "optPrice", None)):
            return True
        lg = getattr(td, "lastGreeks", None)
        if lg and _ok(getattr(lg, "optPrice", None)):
            return True
        return False

    def _probe_best_data_type(self, ticker: str, probe_exp: str,
                               atm_strike: float, opt_type: str) -> int:
        """Try data types on a fresh contract per attempt.
        Order: 3 (delayed) → 1 (live) → 4 (delayed-frozen) → 2 (frozen)
        Delayed is tried first because most IBKR accounts have it for free.
        """
        type_order = [3, 1, 4, 2]

        for dtype in type_order:
            try:
                # Create a FRESH contract for each attempt to avoid stale state
                probe = Option(ticker, probe_exp, atm_strike, opt_type,
                               "SMART", multiplier="100")
                probe.tradingClass = ticker
                qualified = self.ib.qualifyContracts(probe)
                if not qualified:
                    log.debug("Probe Type %d: contract did not qualify", dtype)
                    continue

                self.ib.reqMarketDataType(dtype)
                td = self.ib.reqMktData(probe, "106", False, False)
                self.ib.sleep(5.0)  # give it time to populate

                has_data = self._has_price(td)

                # Log what we got
                mg = getattr(td, "modelGreeks", None)
                lg = getattr(td, "lastGreeks", None)
                log.info(
                    "PROBE Type %d (%s): bid=%.3f ask=%.3f last=%.3f close=%.3f "
                    "modelPrice=%.3f lastGreeksPrice=%.3f → %s",
                    dtype, TYPE_NAMES.get(dtype, "?"),
                    float(getattr(td, "bid", 0) or 0),
                    float(getattr(td, "ask", 0) or 0),
                    float(getattr(td, "last", 0) or 0),
                    float(getattr(td, "close", 0) or 0),
                    float(getattr(mg, "optPrice", 0) or 0) if mg else 0,
                    float(getattr(lg, "optPrice", 0) or 0) if lg else 0,
                    "HAS DATA" if has_data else "empty",
                )

                try:
                    self.ib.cancelMktData(probe)
                except Exception:
                    pass

                if has_data:
                    self._active_data_type = dtype
                    log.info("==> Selected data Type %d (%s)",
                             dtype, TYPE_NAMES.get(dtype, "?"))
                    return dtype

            except Exception as e:
                log.debug("Probe Type %d error: %s", dtype, e)

        # Nothing worked — default to Type 3 (delayed) and proceed
        log.warning("No data type returned prices in probe. "
                    "Defaulting to Type 3 (delayed).")
        self.ib.reqMarketDataType(3)
        self._active_data_type = 3
        return 3

    # ── Main fetch ────────────────────────────────────────────────────────

    def fetch_option_chain(
        self,
        ticker: str,
        progress_cb: Optional[Callable[[str], None]] = None,
    ) -> List[OptionContract]:
        """
        Fetch all option contracts for a ticker.
        progress_cb(msg) is called periodically so the caller can relay
        progress to Telegram.
        """
        cfg = self.config

        # 1. Yahoo price
        underlying_price = get_price_yahoo(ticker)
        if underlying_price <= 0:
            log.warning("%s: Could not get price from Yahoo", ticker)
            return []

        # 2. Qualify stock
        stock = Stock(ticker, "SMART", "USD")
        try:
            qualified = self.ib.qualifyContracts(stock)
        except Exception as e:
            log.warning("%s: qualifyContracts failed: %s", ticker, e)
            return []
        if not qualified:
            log.warning("%s: Could not qualify stock contract", ticker)
            return []

        # 3. Option chain definition
        try:
            chains = self.ib.reqSecDefOptParams(ticker, "", stock.secType, stock.conId)
        except Exception as e:
            log.warning("%s: reqSecDefOptParams failed: %s", ticker, e)
            return []
        if not chains:
            log.warning("%s: No option chain found", ticker)
            return []

        smart_chains = [c for c in chains if c.exchange == "SMART"]
        chain = smart_chains[0] if smart_chains else chains[0]

        # 4. Filter expirations by DTE
        today = date.today()
        valid_expirations = []
        for exp_str in sorted(chain.expirations):
            exp_date = datetime.strptime(exp_str, "%Y%m%d").date()
            dte = (exp_date - today).days
            if cfg.min_dte <= dte <= cfg.max_dte:
                valid_expirations.append((exp_str, exp_date, dte))

        if not valid_expirations:
            log.warning("%s: No expirations in DTE range %d-%d",
                        ticker, cfg.min_dte, cfg.max_dte)
            return []

        # 5. Filter strikes within ±strike_range_pct of price
        valid_strikes = sorted([
            s for s in chain.strikes
            if underlying_price * (1 - cfg.strike_range_pct)
               <= s <=
               underlying_price * (1 + cfg.strike_range_pct)
        ])
        if not valid_strikes:
            log.warning("%s: No strikes near $%.2f", ticker, underlying_price)
            return []

        # 6. Option types
        option_types = []
        if cfg.strategy in ("cc", "both"):
            option_types.append("C")
        if cfg.strategy in ("csp", "both"):
            option_types.append("P")

        # 7. Build full list of contracts to fetch
        combos = [
            (exp_str, exp_date, dte, strike, opt_type)
            for (exp_str, exp_date, dte) in valid_expirations
            for strike in valid_strikes
            for opt_type in option_types
        ]

        total = len(combos)
        batches = [combos[i:i + BATCH_SIZE] for i in range(0, total, BATCH_SIZE)]
        log.info("%s: $%.2f | %d expirations | %d strikes | %d contracts",
                 ticker, underlying_price, len(valid_expirations),
                 len(valid_strikes), total)

        # 7b. Probe best data type using ATM option from nearest expiry
        probe_exp = valid_expirations[0][0]
        atm_strike = min(valid_strikes, key=lambda s: abs(s - underlying_price))
        probe_opt_type = option_types[0]
        best_type = self._probe_best_data_type(
            ticker, probe_exp, atm_strike, probe_opt_type
        )

        is_live = (best_type == 1)
        batch_wait = BATCH_WAIT_LIVE if is_live else BATCH_WAIT_FROZEN

        if progress_cb:
            exp_lines = "  " + " · ".join(
                f"`{exp_date.strftime('%b %d')}` ({dte}d)"
                for (_, exp_date, dte) in valid_expirations
            )
            strike_min = valid_strikes[0]
            strike_max = valid_strikes[-1]
            est_mins_low  = max(1, len(batches) * int(batch_wait) // 60)
            est_mins_high = est_mins_low + 1
            if is_live and _is_market_open():
                market_status = "🟢 Market OPEN — live streaming data"
            elif is_live:
                market_status = "🟡 Market CLOSED — live data (extended hours)"
            else:
                market_status = (
                    f"🔴 Using {TYPE_NAMES.get(best_type, '?')} data (Type {best_type})"
                )
            progress_cb(
                f"📡 *{ticker}* @ ${underlying_price:.2f}\n"
                f"{market_status}\n"
                f"\n"
                f"📅 *Expiries ({len(valid_expirations)}):*\n{exp_lines}\n"
                f"\n"
                f"🎯 *Strikes:* `${strike_min:.0f}` → `${strike_max:.0f}` "
                f"({len(valid_strikes)} strikes)\n"
                f"\n"
                f"⚙️ Fetching *{total} contracts* in batches of {BATCH_SIZE}...\n"
                f"_Est. time: ~{est_mins_low}–{est_mins_high} min_"
            )

        # 8. Batch fetch
        contracts: List[OptionContract] = []

        for batch_num, batch in enumerate(batches, 1):
            ticker_data_pairs = []

            for (exp_str, exp_date, dte, strike, opt_type) in batch:
                try:
                    opt = Option(ticker, exp_str, strike, opt_type,
                                 "SMART", multiplier="100")
                    opt.tradingClass = ticker
                    qualified_opt = self.ib.qualifyContracts(opt)
                    if not qualified_opt:
                        continue
                    # Generic tick 106 = modelGreeks (theoretical option price)
                    td = self.ib.reqMktData(opt, "106", False, False)
                    ticker_data_pairs.append(
                        (td, opt, exp_date, dte, strike, opt_type)
                    )
                except Exception as e:
                    log.debug("reqMktData failed %s %s %s: %s",
                              exp_str, strike, opt_type, e)

            # Wait once for the whole batch
            self.ib.sleep(batch_wait)

            # On first batch: log raw field values for diagnostics
            if batch_num == 1 and ticker_data_pairs:
                td0, opt0, *_ = ticker_data_pairs[0]
                mg0 = getattr(td0, "modelGreeks", None)
                lg0 = getattr(td0, "lastGreeks", None)
                log.info(
                    "BATCH1 sample — bid:%.3f ask:%.3f last:%.3f close:%.3f "
                    "modelPrice:%.3f lgPrice:%.3f modelIV:%.4f (Type %d)",
                    float(getattr(td0, "bid", 0) or 0),
                    float(getattr(td0, "ask", 0) or 0),
                    float(getattr(td0, "last", 0) or 0),
                    float(getattr(td0, "close", 0) or 0),
                    float(getattr(mg0, "optPrice", 0) or 0) if mg0 else 0,
                    float(getattr(lg0, "optPrice", 0) or 0) if lg0 else 0,
                    float(getattr(mg0, "impliedVol", 0) or 0) if mg0 else 0,
                    best_type,
                )

            # Read results
            for (td, opt, exp_date, dte, strike, opt_type) in ticker_data_pairs:
                try:
                    contract = self._parse_ticker_data(
                        td, opt, ticker, exp_date, dte,
                        strike, opt_type, underlying_price
                    )
                    if contract:
                        contracts.append(contract)
                    self.ib.cancelMktData(opt)
                except Exception as e:
                    log.debug("Parse failed %s %s %s: %s",
                              strike, opt_type, dte, e)

            # Progress update every 5 batches
            done = min(batch_num * BATCH_SIZE, total)
            if progress_cb:
                if batch_num % 5 == 0:
                    pct = int(done / total * 100)
                    progress_cb(
                        f"⏳ *{ticker}* scan progress: {pct}%\n"
                        f"({done}/{total} contracts fetched, "
                        f"{len(contracts)} valid so far)"
                    )
                else:
                    progress_cb("")  # silent cancel check
            log.info("%s: batch %d/%d — %d valid so far",
                     ticker, batch_num, len(batches), len(contracts))

        log.info("%s: fetched %d valid option contracts", ticker, len(contracts))
        return contracts

    def _parse_ticker_data(self, td, opt, ticker, exp_date, dte,
                           strike, opt_type, underlying_price
                           ) -> Optional[OptionContract]:
        def safe_float(v, default=0.0):
            try:
                f = float(v)
                return f if not math.isnan(f) and f >= 0 else default
            except Exception:
                return default

        bid  = safe_float(td.bid)
        ask  = safe_float(td.ask)
        last = safe_float(td.last)
        volume = int(safe_float(td.volume))

        # Price fallback chain for after-hours / delayed data:
        # close > last > modelGreeks.optPrice > lastGreeks.optPrice > midpoint
        close_price = safe_float(getattr(td, "close", 0))
        mid_price   = safe_float(getattr(td, "midpoint", 0))

        model_price = 0.0
        mg = getattr(td, "modelGreeks", None)
        if mg:
            model_price = safe_float(getattr(mg, "optPrice", 0))

        lg_price = 0.0
        lg = getattr(td, "lastGreeks", None)
        if lg:
            lg_price = safe_float(getattr(lg, "optPrice", 0))

        ref_price = close_price or last or model_price or lg_price or mid_price

        # IV: try direct field, then modelGreeks, then lastGreeks
        iv = 0.30
        if hasattr(td, "impliedVolatility"):
            iv_val = safe_float(td.impliedVolatility, 0)
            if iv_val > 0:
                iv = iv_val
        if iv == 0.30 and mg:
            iv_val = safe_float(getattr(mg, "impliedVol", 0))
            if iv_val > 0:
                iv = iv_val
        if iv == 0.30 and lg:
            iv_val = safe_float(getattr(lg, "impliedVol", 0))
            if iv_val > 0:
                iv = iv_val

        # Accept contract if ANY price field has data
        if bid <= 0 and ask <= 0:
            if ref_price > 0:
                bid = ref_price * 0.95
                ask = ref_price * 1.05
                log.debug("Price fallback %s %.0f%s: ref=%.3f "
                          "(close=%.3f last=%.3f model=%.3f lg=%.3f mid=%.3f)",
                          ticker, strike, opt_type, ref_price,
                          close_price, last, model_price, lg_price, mid_price)
            else:
                return None  # truly no price data at all

        if last <= 0 and ref_price > 0:
            last = ref_price

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
            open_interest=0,
            implied_vol=iv,
        )

    def fetch_iv_history(self, ticker: str) -> Dict:
        result = {"iv_52w_low": 0.15, "iv_52w_high": 0.60, "prices": []}
        try:
            stock = Stock(ticker, "SMART", "USD")
            self.ib.qualifyContracts(stock)

            # Fetch IV history
            bars = self.ib.reqHistoricalData(
                stock,
                endDateTime="",
                durationStr="1 Y",
                barSizeSetting="1 day",
                whatToShow="OPTION_IMPLIED_VOLATILITY",
                useRTH=True,
            )
            if bars:
                ivs = [bar.close for bar in bars if bar.close > 0]
                if ivs:
                    result["iv_52w_low"] = min(ivs)
                    result["iv_52w_high"] = max(ivs)

            # Fetch price history for mean reversion indicators
            price_bars = self.ib.reqHistoricalData(
                stock,
                endDateTime="",
                durationStr="1 Y",
                barSizeSetting="1 day",
                whatToShow="TRADES",
                useRTH=True,
            )
            if price_bars:
                result["prices"] = [bar.close for bar in price_bars if bar.close > 0]
                log.info("%s: fetched %d price bars for MR indicators", ticker, len(result["prices"]))

        except Exception as e:
            log.debug("%s: IV history error: %s", ticker, e)
        return result
