"""
core/scanner.py — Main Scanner Orchestrator
"""
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

import logging
from datetime import date, datetime
from typing import List, Optional, Callable

from core.config import ScannerConfig
from core.models import OptionContract, ScanOpportunity
from core.greeks import calculate_greeks, calculate_iv_rank, calculate_annualised_return
from data.ibkr_fetcher import IBKRFetcher
from data.mock_fetcher import MockFetcher
from data.yfinance_fetcher import YFinanceFetcher
from strategies.covered_call import CoveredCallFilter
from strategies.cash_secured_put import CashSecuredPutFilter
from core.scorer import OpportunityScorer
from core.indicators import compute_mean_reversion_score

log = logging.getLogger(__name__)


def _build_fetcher(config: ScannerConfig):
    """Select and instantiate the correct data fetcher based on config.data_source."""
    if config.dry_run:
        log.info("Data source: MockFetcher (dry_run=True)")
        return MockFetcher(config)
    source = (config.data_source or "yahoo").strip().lower()
    if source == "ibkr":
        log.info("Data source: IBKR (IB Gateway — requires login)")
        return IBKRFetcher(config)
    else:
        log.info("Data source: Yahoo Finance (free, no login required)")
        return YFinanceFetcher(config)


class OptionScanner:
    def __init__(self, config: ScannerConfig):
        self.config = config.validate()
        self.fetcher = _build_fetcher(config)
        self.scorer = OpportunityScorer(config)

        self.filters = []
        if config.strategy in ("cc", "both"):
            self.filters.append(CoveredCallFilter(config))
        if config.strategy in ("csp", "both"):
            self.filters.append(CashSecuredPutFilter(config))

    def run(
        self,
        progress_cb: Optional[Callable[[str], None]] = None,
    ) -> List[ScanOpportunity]:
        all_opportunities: List[ScanOpportunity] = []
        total_tickers = len(self.config.tickers)
        cfg = self.config

        # ── Send scan config summary to Telegram at start ────────────────
        if progress_cb:
            strategy_label = {
                "cc": "Covered Calls only",
                "csp": "Cash-Secured Puts only",
                "both": "CC + CSP",
            }.get(cfg.strategy, cfg.strategy)

            # IV filter status labels
            iv_rank_label = (
                f"{cfg.min_iv_rank:.0f}"
                if cfg.min_iv_rank > 0 else "OFF (no history)"
            )
            iv_abs_label = (
                f"{cfg.min_iv*100:.0f}%"
                if cfg.min_iv > 0 else "OFF"
            )
            # OI status label — remind user it's a data limitation
            oi_label = (
                f"{cfg.min_open_interest}"
                if cfg.min_open_interest > 0
                else "OFF (delayed data returns OI=0)"
            )

            # Data source label
            data_source = getattr(cfg, "data_source", "yahoo").lower()
            if data_source == "ibkr":
                data_source_label = "IBKR (IB Gateway — live/delayed)"
            else:
                data_source_label = "Yahoo Finance (free — 15min delay)"

            progress_cb(
                f"\u2699\ufe0f *Scan Configuration*\n"
                f"```\n"
                f"Data source : {data_source_label}\n"
                f"Tickers   : {', '.join(cfg.tickers)}\n"
                f"Strategy  : {strategy_label}\n"
                f"DTE range : {cfg.min_dte}-{cfg.max_dte} days\n"
                f"Strike +/- : {cfg.strike_range_pct*100:.0f}% of price\n"
                f"----------------------\n"
                f"Min premium : ${cfg.min_premium:.2f}\n"
                f"Min theta   : ${cfg.min_theta:.3f}/day\n"
                f"Min ann ret : {cfg.min_annualised_return*100:.0f}%\n"
                f"----------------------\n"
                f"IV Rank     : {iv_rank_label}\n"
                f"IV (raw)    : {iv_abs_label}\n"
                f"----------------------\n"
                f"CC delta  : {cfg.cc_delta_min:.2f} to {cfg.cc_delta_max:.2f}\n"
                f"CSP delta : {cfg.csp_delta_min:.2f} to {cfg.csp_delta_max:.2f}\n"
                f"----------------------\n"
                f"Min OI    : {oi_label}\n"
                f"Min vol   : {cfg.min_volume}\n"
                f"Max spread: {cfg.max_bid_ask_spread_pct*100:.0f}% of mid\n"
                f"----------------------\n"
                f"Mean Rev  : {'ON (w={:.0f}%)'.format(cfg.weight_mean_reversion*100) if cfg.use_mean_reversion else 'OFF'}\n"
                f"  RSI({cfg.mr_rsi_period}) {cfg.mr_w_rsi:.0%} | Z({cfg.mr_z_period}) {cfg.mr_w_z:.0%} | ROC({cfg.mr_roc_period}) {cfg.mr_w_roc:.0%}\n"
                f"  Trend Guard: {'ON (>{:.0f}% from SMA200)'.format(cfg.mr_trend_pct) if cfg.mr_trend_guard else 'OFF'}\n"
                f"```"
            )

        for idx, ticker in enumerate(cfg.tickers, 1):
            log.info("Scanning %s...", ticker)
            if progress_cb:
                progress_cb(f"\U0001f50d Scanning *{ticker}* ({idx}/{total_tickers})...")
            try:
                opportunities, reject_summary = self._scan_ticker(ticker, progress_cb=progress_cb)
                all_opportunities.extend(opportunities)
                log.info("  %s -> %d opportunities found", ticker, len(opportunities))

                if progress_cb:
                    if opportunities:
                        progress_cb(f"OK *{ticker}* done - {len(opportunities)} opportunities found")
                    else:
                        progress_cb(
                            f"\u26a0\ufe0f *{ticker}* - 0 opportunities found\n\n"
                            f"{reject_summary}\n\n"
                            f"_Send_ `config` _to review thresholds, or_ `set` _to adjust live._"
                        )
            except Exception as e:
                log.error("  %s -> ERROR: %s", ticker, e)
                if progress_cb:
                    progress_cb(f"\u274c *{ticker}* error: `{e}`")

        for opp in all_opportunities:
            opp.score = self.scorer.score(opp)

        ranked = sorted(all_opportunities, key=lambda x: x.score, reverse=True)
        log.info("-" * 50)
        log.info("Total opportunities: %d across %d tickers", len(ranked), total_tickers)

        return ranked

    def _scan_ticker(
        self,
        ticker: str,
        progress_cb: Optional[Callable[[str], None]] = None,
    ):
        """Returns (opportunities, reject_summary_string)."""
        cfg = self.config

        chain = self.fetcher.fetch_option_chain(ticker, progress_cb=progress_cb)
        iv_history = self.fetcher.fetch_iv_history(ticker)

        # ── Mean Reversion: compute once per ticker ──────────────
        # prices come from the same yf.history() call as IV proxy — no extra API call
        prices = iv_history.get("prices", [])
        mr_results = {}  # keyed by strategy direction: "C" and/or "P"
        if cfg.use_mean_reversion and len(prices) >= 30:
            for direction in ("C", "P"):
                mr_results[direction] = compute_mean_reversion_score(
                    prices=prices,
                    strategy=direction,
                    rsi_period=cfg.mr_rsi_period,
                    z_period=cfg.mr_z_period,
                    roc_period=cfg.mr_roc_period,
                    w_rsi=cfg.mr_w_rsi,
                    w_z=cfg.mr_w_z,
                    w_roc=cfg.mr_w_roc,
                    trend_guard=cfg.mr_trend_guard,
                    trend_pct=cfg.mr_trend_pct,
                )
            # Log once per ticker
            mr_c = mr_results.get("C")
            if mr_c:
                log.info(
                    "%s MR indicators: RSI(5)=%.0f  Z(20)=%+.2f  ROC%%Rank=%.0f  "
                    "SMA200 dist=%.1f%%  TrendGuard=%s",
                    ticker, mr_c.rsi, mr_c.z_score, mr_c.roc_pct_rank,
                    mr_c.sma200_distance_pct,
                    "ACTIVE" if mr_c.trend_guard_active else "off",
                )
        elif cfg.use_mean_reversion and len(prices) < 30:
            log.warning("%s: insufficient price history (%d bars) — MR score disabled", ticker, len(prices))

        # Rejection counters
        r_dte = r_liq = r_bid = r_spread = r_oi = r_vol = r_strategy = r_iv = 0
        passed_liq = 0
        opportunities = []
        iv_rejected_vals = []        # track IVs of contracts rejected by IV filter
        strategy_reject_counts = {}  # e.g. {"delta": 80, "premium": 50, "theta": 36}

        if not chain:
            # Chain empty = all contracts had bid=0 (frozen data outside market hours)
            r_bid = -1  # signal: unknown count, fetcher filtered them

        for contract in chain:
            # DTE filter
            if not (cfg.min_dte <= contract.dte <= cfg.max_dte):
                r_dte += 1
                continue

            # Liquidity filters — tracked individually
            if contract.open_interest < cfg.min_open_interest:
                r_oi += 1
                continue
            if contract.volume < cfg.min_volume:
                r_vol += 1
                continue
            if contract.spread_pct > cfg.max_bid_ask_spread_pct:
                r_spread += 1
                continue
            if contract.bid <= 0:
                r_bid += 1
                continue

            passed_liq += 1

            # ── Absolute IV pre-filter ────────────────────────────────────
            # Applied before Greeks calculation as a fast early-exit.
            # Rejects contracts where the raw IV is below the configured floor.
            # This is independent of IV Rank — it reads directly from the quote.
            if cfg.min_iv > 0 and contract.implied_vol < cfg.min_iv:
                r_iv += 1
                iv_rejected_vals.append(contract.implied_vol)
                log.debug(
                    "IV REJECT %s $%.2f: IV %.1f%% < min %.1f%%",
                    ticker, contract.strike,
                    contract.implied_vol * 100, cfg.min_iv * 100,
                )
                continue

            greeks = calculate_greeks(contract)
            iv_rank = calculate_iv_rank(
                contract.implied_vol,
                iv_history.get("iv_52w_low", contract.implied_vol * 0.7),
                iv_history.get("iv_52w_high", contract.implied_vol * 1.5),
            )
            ann_return = calculate_annualised_return(
                contract.mid, contract.underlying_price, contract.dte,
                "cc" if contract.is_call else "csp",
                strike=contract.strike,
            )

            found = False
            for strategy_filter in self.filters:
                if strategy_filter.applies_to(contract):
                    opp = strategy_filter.evaluate(contract, greeks, iv_rank, ann_return)
                    if opp is not None:
                        # Attach mean reversion data (direction-aware)
                        direction = "C" if contract.is_call else "P"
                        mr = mr_results.get(direction)
                        if mr is not None:
                            opp.mean_rev_score = mr.score
                            opp.rsi_5 = mr.rsi
                            opp.z_score_20 = mr.z_score
                            opp.roc_pct_rank = mr.roc_pct_rank
                            opp.trend_guard_active = mr.trend_guard_active
                            opp.sma200_distance_pct = mr.sma200_distance_pct
                        opportunities.append(opp)
                        found = True
                    else:
                        r_strategy += 1
                        # Capture first rejection reason per sub-filter type
                        reason = strategy_filter._check_filters(
                            contract, greeks, iv_rank, ann_return
                        )
                        if reason:
                            # Extract the leading keyword (e.g. "delta", "theta", "premium")
                            key = reason.split()[0].lower()
                            strategy_reject_counts[key] = (
                                strategy_reject_counts.get(key, 0) + 1
                            )

        total = len(chain)
        bid_zero_str = (
            f"ALL ({total}) - frozen data had no bid/ask"
            if r_bid == -1 else str(r_bid)
        )
        scanned_str = "0 (all filtered by fetcher)" if r_bid == -1 else str(total)

        # OI filter label: show as "disabled" if min_oi=0 so user understands
        oi_filter_label = (
            f"OI < {cfg.min_open_interest}"
            if cfg.min_open_interest > 0
            else "OI filter (disabled)"
        )
        iv_label = (
            f"IV < {cfg.min_iv*100:.0f}% (raw)"
            if cfg.min_iv > 0 else "IV (raw) filter (disabled)"
        )

        # If IV filter blocked everything, show the actual IV range seen
        iv_debug_line = ""
        if r_iv > 0 and iv_rejected_vals:
            iv_lo = min(iv_rejected_vals) * 100
            iv_hi = max(iv_rejected_vals) * 100
            iv_debug_line = f"\n  ⚠️ Yahoo IV seen: {iv_lo:.0f}%–{iv_hi:.0f}% (min_iv={cfg.min_iv*100:.0f}%)"

        # Strategy rejection breakdown string
        if strategy_reject_counts:
            breakdown = "  ".join(
                f"{k}:{v}" for k, v in sorted(
                    strategy_reject_counts.items(), key=lambda x: -x[1]
                )
            )
            strategy_line = f"Failed strategy     : {r_strategy}\n  ↳ {breakdown}\n"
        else:
            strategy_line = f"Failed strategy     : {r_strategy}  (delta/IVRank/premium/theta)\n"

        reject_summary = (
            f"Scanned          : {scanned_str}\n"
            f"Passed liquidity : {passed_liq}\n"
            f"---------------------\n"
            f"Bid=0 (no mkt data) : {bid_zero_str}\n"
            f"Spread too wide     : {r_spread}\n"
            f"{oi_filter_label:<20}: {r_oi}\n"
            f"Volume < {cfg.min_volume:<3}         : {r_vol}\n"
            f"DTE out of range    : {r_dte}\n"
            f"{iv_label:<20}: {r_iv}{iv_debug_line}\n"
            f"{strategy_line}"
            f"---------------------\n"
            f"Opportunities       : {len(opportunities)}"
        )
        log.info("%s reject summary:\n%s", ticker, reject_summary)
        return opportunities, reject_summary

    # NOTE: Liquidity checks are inline in _scan_ticker() for
    # per-field rejection counters. No separate method needed.
