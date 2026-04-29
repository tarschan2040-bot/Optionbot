"""
output/telegram_notifier.py — Telegram Bot Notifier
=====================================================
Sends scan results to your Telegram bot using the Bot API.
"""
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

import os
import logging
import time
import urllib.request
import json
from datetime import datetime
from typing import List, Optional

from core.models import ScanOpportunity
from core.config import ScannerConfig

log = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"


class TelegramNotifier:
    def __init__(
        self,
        token: Optional[str] = None,
        chat_id: Optional[str] = None,
    ):
        self.token = token or os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID", "")

        if not self.token or not self.chat_id:
            raise ValueError(
                "Missing Telegram credentials.\n"
                "Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in your .env file."
            )

    # ── Public API ────────────────────────────────────────────

    def send_message(self, text: str) -> bool:
        """Send any plain message to Telegram. Used for progress updates."""
        return self._send(text)

    def send_scan_config(self, config: ScannerConfig, tickers: List[str]):
        """Send active scan thresholds at the start of a scan."""
        strategy_label = {
            "cc": "Covered Calls only",
            "csp": "Cash-Secured Puts only",
            "both": "Covered Calls + Cash-Secured Puts",
        }.get(config.strategy, config.strategy)

        tickers_str = ", ".join(f"`{t}`" for t in tickers)
        now = datetime.now().strftime("%Y-%m-%d %H:%M")

        msg = (
            f"🔎 *Scan Starting* — `{now}`\n"
            f"Tickers: {tickers_str}\n"
            f"Strategy: _{strategy_label}_\n"
            f"\n"
            f"*Active Filters:*\n"
            f"```\n"
            f"DTE range       {config.min_dte} – {config.max_dte} days\n"
            f"Strike range    ±{config.strike_range_pct*100:.0f}% of price\n"
            f"─────────────────────────────\n"
            f"CC delta        {config.cc_delta_min:.2f} to {config.cc_delta_max:.2f}\n"
            f"CSP delta       {config.csp_delta_min:.2f} to {config.csp_delta_max:.2f}\n"
            f"Min theta       ${config.min_theta:.2f}/day\n"
            f"IV Rank         {config.min_iv_rank:.0f} – {config.max_iv_rank:.0f}\n"
            f"Max vega        {config.max_vega:.2f}\n"
            f"─────────────────────────────\n"
            f"Min premium     ${config.min_premium:.2f}\n"
            f"Min ann. return {config.min_annualised_return*100:.0f}%\n"
            f"─────────────────────────────\n"
            f"Min OI          {config.min_open_interest}\n"
            f"Min volume      {config.min_volume}\n"
            f"Max spread      {config.max_bid_ask_spread_pct*100:.0f}% of mid\n"
            f"```\n"
            f"_Edit thresholds in_ `core/config.py`"
        )
        self._send(msg)

    def send_scan_results(self, opportunities: List[ScanOpportunity], top_n: int = 5):
        """Send full scan report to Telegram."""
        if not opportunities:
            return  # scheduler already sends the 0-result summary message

        summary_msg = self._build_summary_message(opportunities, top_n)
        self._send(summary_msg)

        for opp in opportunities[:3]:
            card = self._build_opportunity_card(opp)
            self._send(card)

        log.info("Telegram: Sent %d opportunities to chat %s", len(opportunities[:top_n]), self.chat_id)

    def send_error(self, message: str):
        """Send an error alert to Telegram."""
        self._send(f"🚨 *Scanner Error*\n\n`{message}`")

    def send_startup(self):
        """Send a startup notification."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        self._send(
            f"🤖 *Sell Option Scanner Started*\n"
            f"⏰ `{now}`\n"
            f"📡 Connected to IBKR\n"
            f"✅ Scanning every scheduled interval...\n\n"
            f"Send `help` for available commands."
        )

    # ── Message Builders ──────────────────────────────────────

    def _build_summary_message(self, opps: List[ScanOpportunity], top_n: int) -> str:
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        top = opps[:top_n]

        cc_count  = sum(1 for o in opps if o.strategy == "COVERED_CALL")
        csp_count = sum(1 for o in opps if o.strategy == "CASH_SECURED_PUT")

        lines = [
            f"📊 *Sell Option Scanner* — `{now}`",
            f"Found *{len(opps)}* opportunities "
            f"({cc_count} CC · {csp_count} CSP)\n",
            "```",
            f"{'#':<2} {'Ticker':<6} {'Type':<4} {'Strike':>7} {'DTE':>4} {'Prem':>6} {'Δ':>6} {'IVR':>4} {'Ann%':>6} {'Score':>6}",
            "─" * 58,
        ]

        for i, o in enumerate(top, 1):
            t = "CC" if o.strategy == "COVERED_CALL" else "CSP"
            lines.append(
                f"{i:<2} {o.ticker:<6} {t:<4} "
                f"${o.strike:>6.1f} "
                f"{o.dte:>4} "
                f"${o.premium:>5.2f} "
                f"{o.delta:>+6.2f} "
                f"{o.iv_rank:>4.0f} "
                f"{o.annualised_return*100:>5.0f}% "
                f"{o.score:>5.1f}"
            )

        lines.append("```")
        lines.append("\n_Tap reply to see full details_")
        return "\n".join(lines)

    def _build_opportunity_card(self, opp: ScanOpportunity) -> str:
        emoji = "📞" if opp.strategy == "COVERED_CALL" else "💰"
        strategy_label = "Covered Call" if opp.strategy == "COVERED_CALL" else "Cash-Secured Put"
        score_emoji = "🟢" if opp.score >= 70 else "🟡" if opp.score >= 50 else "🔴"

        filled = int(opp.score / 10)
        bar = "█" * filled + "░" * (10 - filled)

        return (
            f"{emoji} *{opp.ticker}* — {strategy_label}\n"
            f"\n"
            f"*Strike:* `${opp.strike:.2f}`   *Expiry:* `{opp.expiry}` ({opp.dte} DTE)\n"
            f"*Premium:* `${opp.premium:.2f}` per share  (`${opp.premium*100:.0f}` per contract)\n"
            f"\n"
            f"*Greeks*\n"
            f"  Delta: `{opp.delta:+.3f}`   Theta: `${opp.theta:.3f}/day`\n"
            f"  IV: `{opp.iv*100:.1f}%`   IV Rank: `{opp.iv_rank:.0f}/100`\n"
            f"\n"
            f"*Returns*\n"
            f"  Annualised: `{opp.annualised_return*100:.1f}%`\n"
            f"  Break-even: `${opp.strike - opp.premium:.2f}`\n"
            f"\n"
            f"{score_emoji} *Score: {opp.score:.1f}/100*\n"
            f"`{bar}`"
        )

    # ── HTTP Layer ────────────────────────────────────────────

    def _send(self, text: str, parse_mode: str = "Markdown") -> bool:
        """
        Send a Telegram message with automatic retry for:
          - 429 flood control: waits retry_after seconds then resends
          - 400 Markdown error: retries as plain text so message always arrives
        """
        url = TELEGRAM_API.format(token=self.token, method="sendMessage")

        def _do_send(mode):
            body = {
                "chat_id": self.chat_id,
                "text": text,
                "disable_web_page_preview": True,
            }
            if mode:
                body["parse_mode"] = mode
            payload = json.dumps(body).encode("utf-8")
            req = urllib.request.Request(
                url, data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read())

        try:
            result = _do_send(parse_mode)
            if result.get("ok"):
                return True
            log.error("Telegram API error: %s", result)
            return False

        except urllib.error.HTTPError as e:
            # ── 429 flood control: Telegram says slow down ────────────────
            if e.code == 429:
                try:
                    body = json.loads(e.read())
                    retry_after = body.get("parameters", {}).get("retry_after", 2)
                except Exception:
                    retry_after = 2
                log.warning("Telegram flood control — waiting %ss then retrying", retry_after)
                time.sleep(retry_after + 0.5)
                try:
                    result = _do_send(parse_mode)
                    return result.get("ok", False)
                except Exception as e2:
                    log.error("Send error after flood retry: %s", e2)
                    return False

            # ── 400 Markdown parse error: retry as plain text ─────────────
            if e.code == 400 and parse_mode:
                log.warning("Markdown parse error (400) — retrying as plain text")
                try:
                    result = _do_send(None)
                    return result.get("ok", False)
                except Exception as e2:
                    log.error("Send error (plain text retry): %s", e2)
                    return False

            log.error("Failed to send Telegram message (HTTP %s): %s", e.code, e)
            return False

        except Exception as e:
            log.error("Failed to send Telegram message: %s", e)
            return False

    def test_connection(self) -> bool:
        ok = self._send(
            "✅ *Connection test successful!*\n"
            "Your Sell Option Scanner is connected to Telegram."
        )
        if ok:
            log.info("Telegram connection test: PASSED")
        else:
            log.error("Telegram connection test: FAILED")
        return ok
