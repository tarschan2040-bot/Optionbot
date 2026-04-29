"""
output/reporter.py — Results Reporter
=======================================
Formats scan results as:
  1. Rich terminal table (colour-coded by score)
  2. CSV export for Excel/Google Sheets analysis
"""
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))


import csv
import logging
from datetime import datetime
from typing import List

from core.models import ScanOpportunity

log = logging.getLogger(__name__)

# ANSI colour codes for terminal output
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"
DIM    = "\033[2m"


def _score_colour(score: float) -> str:
    if score >= 70:  return GREEN
    if score >= 50:  return YELLOW
    return RED


class Reporter:
    def __init__(self, opportunities: List[ScanOpportunity], top_n: int = 10):
        self.opportunities = opportunities
        self.top_n = top_n
        self.top = opportunities[:top_n]

    def print_table(self):
        """Print a formatted table to the terminal."""
        if not self.opportunities:
            print(f"\n{RED}No opportunities found matching your filters.{RESET}")
            print("Try relaxing thresholds in core/config.py (min_iv_rank, min_theta, etc.)\n")
            return

        # Header
        print(f"\n{BOLD}{CYAN}{'─'*100}{RESET}")
        print(f"{BOLD}{CYAN}  TOP {self.top_n} SELL OPTION OPPORTUNITIES{RESET}")
        print(f"{BOLD}{CYAN}{'─'*100}{RESET}")
        print(f"{BOLD}"
              f"{'#':>3}  {'Ticker':<6} {'Strategy':<16} {'Strike':>8} {'Expiry':<12} "
              f"{'DTE':>4} {'Premium':>8} {'Delta':>7} {'Theta':>7} "
              f"{'IV':>6} {'IVR':>5} {'Ann%':>7} {'Score':>7}"
              f"{RESET}")
        print(f"{'─'*100}")

        for i, opp in enumerate(self.top, 1):
            col = _score_colour(opp.score)
            strategy_label = "📞 COV CALL" if opp.strategy == "COVERED_CALL" else "💰 CSP"

            print(
                f"{col}{i:>3}{RESET}  "
                f"{BOLD}{opp.ticker:<6}{RESET} "
                f"{strategy_label:<16} "
                f"${opp.strike:>7.2f} "
                f"{str(opp.expiry):<12} "
                f"{opp.dte:>4} "
                f"${opp.premium:>7.2f} "
                f"{opp.delta:>+7.3f} "
                f"${opp.theta:>6.3f} "
                f"{opp.iv*100:>5.1f}% "
                f"{opp.iv_rank:>5.0f} "
                f"{opp.annualised_return*100:>6.1f}% "
                f"{col}{opp.score:>7.1f}{RESET}"
            )

        print(f"{'─'*100}")
        self._print_legend()
        self._print_summary()

    def _print_legend(self):
        print(f"\n{DIM}Score: {GREEN}●{RESET}{DIM} ≥70 Excellent  "
              f"{YELLOW}●{RESET}{DIM} ≥50 Good  "
              f"{RED}●{RESET}{DIM} <50 Marginal{RESET}")
        print(f"{DIM}IVR = IV Rank (0-100) | Ann% = Annualised Return | "
              f"Delta: puts are negative{RESET}\n")

    def _print_summary(self):
        total = len(self.opportunities)
        cc_count = sum(1 for o in self.opportunities if o.strategy == "COVERED_CALL")
        csp_count = sum(1 for o in self.opportunities if o.strategy == "CASH_SECURED_PUT")
        avg_score = sum(o.score for o in self.opportunities) / total if total > 0 else 0

        print(f"{BOLD}Summary:{RESET} {total} total opportunities "
              f"({cc_count} Covered Calls, {csp_count} Cash-Secured Puts) "
              f"| Avg Score: {avg_score:.1f}\n")

    def export_csv(self) -> str:
        """Export all opportunities to a timestamped CSV file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"scan_results_{timestamp}.csv"

        if not self.opportunities:
            log.warning("No opportunities to export.")
            return filename

        fieldnames = list(self.opportunities[0].summary_dict().keys())

        with open(filename, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for opp in self.opportunities:
                writer.writerow(opp.summary_dict())

        log.info("Exported %d rows to %s", len(self.opportunities), filename)
        return filename
