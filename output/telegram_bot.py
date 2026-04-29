"""
output/telegram_bot.py — Telegram Bot Listener
================================================
Commands (no / needed — just type the command):
  scan / scan TSLA / scan TSLA AAPL
  stopscan
  cancelscan      — cancel a scan currently running
  lastscan        — summary table of last scan (top 10)
  result          — page 1 of full ranked results (10 per page)
  page 2          — page 2, etc.
  detail 5        — full detail card for opportunity #5
  score           — explain how the 0-100 score is calculated
  price SPY
  movers
  config          — show current scan config
  set <param> <value>  — change a config parameter live
  set reset       — clear ALL overrides and restore defaults
  askclaude <question>  — ask Claude AI (Anthropic)
  askllama <question>   — ask Llama AI (OpenRouter)
  health          — full system health check (IBKR, Supabase, Claude API, OpenRouter)
  stopbot         — gracefully stop the bot (password required: killbot)
  help
  m               — interactive menu
"""
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

import os
import json
import logging
import signal
import threading
import time
import urllib.request
import urllib.parse
from datetime import datetime
from typing import Optional, List

log = logging.getLogger(__name__)

TELEGRAM_API      = "https://api.telegram.org/bot{token}/{method}"
ANTHROPIC_API     = "https://api.anthropic.com/v1/messages"
CLAUDE_MODEL      = "claude-sonnet-4-6"
OPENROUTER_API    = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL  = "meta-llama/llama-3.3-70b-instruct"

# ── Results paging ────────────────────────────────────────────────────────
RESULTS_PAGE_SIZE = 10
LASTSCAN_PREVIEW  = 10

# ── stopbot password ──────────────────────────────────────────────────────
STOPBOT_PASSWORD        = "killbot"   # password required to stop bot via Telegram
STOPBOT_TIMEOUT_SECS    = 60         # auto-cancel pending stopbot after this many seconds

# ── Multi-user access control ────────────────────────────────────────────
# Admin  = full access (you). Set via TELEGRAM_CHAT_ID env var.
# Viewer = read-only commands only. Set via TELEGRAM_VIEWER_IDS env var
#          (comma-separated chat IDs, e.g. "123456,789012").
# Commands restricted to admin only:
ADMIN_ONLY_COMMANDS = {
    "stopbot", "stopscan", "cancelscan",
    "set", "setwatchlist", "setscantime",
    "clearstarred", "clearapproved", "clearplaced",
    "placed", "approve", "reject", "unstar",
    "askclaude", "askllama",
}

PRESET_SYMBOLS = {
    "SPY":    ("SPY",     "S&P 500 ETF",       "stock"),
    "QQQ":    ("QQQ",     "Nasdaq 100 ETF",    "stock"),
    "DIA":    ("DIA",     "Dow Jones ETF",     "stock"),
    "VIX":    ("^VIX",    "VIX Fear Index",    "index"),
    "DJI":    ("^DJI",    "Dow Jones",         "index"),
    "SPX":    ("^GSPC",   "S&P 500 Index",     "index"),
    "NDX":    ("^NDX",    "Nasdaq 100 Index",  "index"),
    "BTC":    ("BTC-USD", "Bitcoin",           "crypto"),
    "ETH":    ("ETH-USD", "Ethereum",          "crypto"),
    "SOL":    ("SOL-USD", "Solana",            "crypto"),
    "BNB":    ("BNB-USD", "BNB",               "crypto"),
    "GOLD":   ("GC=F",    "Gold Futures",      "commodity"),
    "OIL":    ("CL=F",    "Crude Oil Futures", "commodity"),
    "SILVER": ("SI=F",    "Silver Futures",    "commodity"),
    "AAPL":   ("AAPL",    "Apple",             "stock"),
    "MSFT":   ("MSFT",    "Microsoft",         "stock"),
    "NVDA":   ("NVDA",    "NVIDIA",            "stock"),
    "TSLA":   ("TSLA",    "Tesla",             "stock"),
    "AMZN":   ("AMZN",    "Amazon",            "stock"),
    "META":   ("META",    "Meta",              "stock"),
    "GOOGL":  ("GOOGL",   "Alphabet",          "stock"),
    "AMD":    ("AMD",     "AMD",               "stock"),
}

MOVERS_STOCKS  = ["AAPL", "MSFT", "NVDA", "TSLA", "AMZN", "META", "GOOGL", "AMD",
                   "SPY", "QQQ", "NFLX", "BABA", "INTC", "PYPL", "CRM", "UBER"]
MOVERS_CRYPTO  = ["BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "XRP-USD", "DOGE-USD"]
MOVERS_INDICES = ["^GSPC", "^NDX", "^DJI", "^VIX", "^RUT"]

DEFAULT_WATCHLIST = ["TSLA", "NVDA"]

# ── Settable config parameters ────────────────────────────────────────────
SETTABLE_PARAMS = {
    "min_dte":        ("min_dte",               int,   "Min days to expiry"),
    "max_dte":        ("max_dte",               int,   "Max days to expiry"),
    "strike_pct":     ("strike_range_pct",      float, "Strike range +/-% (e.g. 0.10 = 10%)"),
    "min_premium":    ("min_premium",           float, "Min option premium $"),
    "min_theta":      ("min_theta",             float, "Min daily theta $"),
    "min_iv_rank":    ("min_iv_rank",           float, "Min IV rank 0-100 (0 = disabled)"),
    "min_iv":         ("min_iv",                float, "Min raw IV floor (e.g. 0.40 = 40%, 0 = disabled)"),
    "min_ann_return": ("min_annualised_return", float, "Min annualised return (e.g. 0.05 = 5%)"),
    "cc_delta_min":   ("cc_delta_min",          float, "CC min delta"),
    "cc_delta_max":   ("cc_delta_max",          float, "CC max delta"),
    "csp_delta_min":  ("csp_delta_min",         float, "CSP min delta"),
    "csp_delta_max":  ("csp_delta_max",         float, "CSP max delta"),
    "min_oi":         ("min_open_interest",     int,   "Min open interest (0 = disabled)"),
    "max_spread":     ("max_bid_ask_spread_pct",float, "Max bid/ask spread % (e.g. 0.30 = 30%)"),
    "strategy":       ("strategy",              str,   "Strategy: cc / csp / both"),
    "autostar":       ("autostar_threshold",    float, "Auto-star score threshold (0 = disabled, e.g. 80 = auto-star score >= 80)"),
    "data_source":    ("data_source",           str,   "Data source: yahoo (free, no login) or ibkr (requires IB Gateway)"),

    # ── Mean Reversion ────────────────────────────────────────
    "use_mean_reversion": ("use_mean_reversion",   bool,  "Enable/disable MR scoring (true/false)"),
    "weight_mr":          ("weight_mean_reversion", float, "MR weight in composite score (e.g. 0.15)"),
    "mr_rsi_period":      ("mr_rsi_period",         int,   "RSI lookback period (default 5)"),
    "mr_z_period":        ("mr_z_period",           int,   "Z-Score lookback period (default 20)"),
    "mr_roc_period":      ("mr_roc_period",         int,   "ROC %Rank lookback period (default 100)"),
    "mr_w_rsi":           ("mr_w_rsi",              float, "RSI sub-weight within MR (default 0.40)"),
    "mr_w_z":             ("mr_w_z",                float, "Z-Score sub-weight within MR (default 0.40)"),
    "mr_w_roc":           ("mr_w_roc",              float, "ROC sub-weight within MR (default 0.20)"),
    "mr_trend_guard":     ("mr_trend_guard",        bool,  "Enable trend guard (true/false)"),
    "mr_trend_pct":       ("mr_trend_pct",          float, "Trend guard threshold % from SMA200 (default 15)"),
}

# ── Claude AI system prompt ───────────────────────────────────────────────
CLAUDE_SYSTEM_PROMPT = """You are an expert options trader and financial advisor assistant
embedded in a Telegram trading bot. The user runs a Wheel Strategy scanner (Covered Calls
and Cash-Secured Puts) on US stocks using IBKR TWS and Python.

Answer any question the user asks — options trading, Greeks, strategy, market concepts,
finance, or anything else. Be concise and direct. Use plain text only — no markdown
headers, no bullet symbols, no asterisks. Keep responses under 800 characters so they
fit cleanly in a Telegram message. If the answer genuinely needs more detail, give the
most important 2-3 points and offer to elaborate."""


# ── Yahoo Finance helpers ─────────────────────────────────────────────────

def _yahoo_fetch(symbol: str) -> Optional[dict]:
    try:
        url = (f"https://query1.finance.yahoo.com/v8/finance/chart/"
               f"{urllib.parse.quote(symbol)}?interval=1d&range=2d")
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        meta       = data["chart"]["result"][0]["meta"]
        price      = meta.get("regularMarketPrice") or meta.get("previousClose", 0)
        prev_close = meta.get("chartPreviousClose") or meta.get("previousClose", price)
        change     = price - prev_close
        change_pct = (change / prev_close * 100) if prev_close else 0
        return {
            "symbol":       symbol,
            "price":        price,
            "prev_close":   prev_close,
            "change":       change,
            "change_pct":   change_pct,
            "name":         meta.get("longName") or meta.get("shortName", symbol),
            "market_state": meta.get("marketState", "CLOSED"),
        }
    except Exception as e:
        log.debug("Yahoo fetch failed for %s: %s", symbol, e)
        return None


def get_price_quote(user_input: str) -> str:
    key = user_input.upper().strip()
    yahoo_sym, label = (PRESET_SYMBOLS[key][0], PRESET_SYMBOLS[key][1]) \
                       if key in PRESET_SYMBOLS else (key, key)

    data = _yahoo_fetch(yahoo_sym)
    if not data:
        return f"Could not find price for *{key}*.\nTry: `price AAPL`, `price BTC`, `price GOLD`"

    arrow     = "up" if data["change"] >= 0 else "down"
    sign      = "+" if data["change"] >= 0 else ""
    state     = data["market_state"]
    state_lbl = ("Market Open" if state == "REGULAR"
                 else "Market Closed" if state == "CLOSED"
                 else state)
    price     = data["price"]
    price_str = f"{price:,.2f}" if price >= 1 else f"{price:.6f}"

    return (
        f"*{label}* (`{yahoo_sym}`)\n\n"
        f"Price:  `${price_str}`\n"
        f"Change: `{sign}{data['change']:.2f}` ({sign}{data['change_pct']:.2f}%) [{arrow}]\n"
        f"Prev Close: `${data['prev_close']:.2f}`\n\n"
        f"{state_lbl}\n"
        f"_as of {datetime.now().strftime('%Y-%m-%d %H:%M')}_"
    )


def get_top_movers() -> str:
    lines = [f"*Top Movers* -- `{datetime.now().strftime('%Y-%m-%d %H:%M')}`\n"]

    lines.append("*Indices*")
    for sym in MOVERS_INDICES:
        d = _yahoo_fetch(sym)
        if d:
            arrow = "^" if d["change"] >= 0 else "v"
            sign  = "+" if d["change"] >= 0 else ""
            lines.append(f"  {arrow} `{sym:<6}` ${d['price']:>10,.2f}  {sign}{d['change_pct']:.2f}%")

    stock_data = []
    for sym in MOVERS_STOCKS:
        d = _yahoo_fetch(sym)
        if d:
            stock_data.append(d)
        time.sleep(0.05)

    if stock_data:
        sorted_stocks = sorted(stock_data, key=lambda x: x["change_pct"], reverse=True)
        lines.append("\n*Top 5 Gainers*")
        for d in sorted_stocks[:5]:
            lines.append(f"  ^ `{d['symbol']:<6}` ${d['price']:>8.2f}  +{d['change_pct']:.2f}%")
        lines.append("\n*Top 5 Losers*")
        for d in sorted_stocks[-5:][::-1]:
            lines.append(f"  v `{d['symbol']:<6}` ${d['price']:>8.2f}  {d['change_pct']:.2f}%")
        most_active = sorted(stock_data, key=lambda x: abs(x["change_pct"]), reverse=True)[:5]
        lines.append("\n*Most Active*")
        for d in most_active:
            arrow = "^" if d["change"] >= 0 else "v"
            sign  = "+" if d["change"] >= 0 else ""
            lines.append(f"  {arrow} `{d['symbol']:<6}` ${d['price']:>8.2f}  {sign}{d['change_pct']:.2f}%")

    lines.append("\n*Crypto Movers*")
    crypto_data = []
    for sym in MOVERS_CRYPTO:
        d = _yahoo_fetch(sym)
        if d:
            crypto_data.append(d)
        time.sleep(0.05)

    if crypto_data:
        for d in sorted(crypto_data, key=lambda x: x["change_pct"], reverse=True):
            arrow     = "^" if d["change"] >= 0 else "v"
            sign      = "+" if d["change"] >= 0 else ""
            price_str = f"{d['price']:,.2f}" if d['price'] >= 1 else f"{d['price']:.6f}"
            lines.append(f"  {arrow} `{d['symbol']:<10}` ${price_str:>12}  {sign}{d['change_pct']:.2f}%")

    lines.append("\n_Data from Yahoo Finance_")
    return "\n".join(lines)


# ── Score explanation ─────────────────────────────────────────────────────

def get_score_explanation() -> str:
    # Score table uses plain text inside the code block.
    # The surrounding bold headings are safe (no underscores in parameter names).
    return (
        "*How the Score (0-100) Works*\n\n"
        "Every opportunity that passes all filters is scored on 5 factors.\n"
        "The score ranks results so the best trade is always number 1.\n\n"
        "```\n"
        "Factor          Weight  What it measures\n"
        "--------------- ------  ----------------------------------\n"
        "Ann. Return       30%   Annualised return on capital\n"
        "                        Premium / capital x 365 / DTE\n"
        "\n"
        "IV Score          20%   Absolute IV (linear: 45-100% range)\n"
        "                        Higher IV = richer premium to sell\n"
        "\n"
        "Theta Yield       20%   Daily theta divided by premium\n"
        "                        More decay per dollar = higher score\n"
        "\n"
        "Delta Safety      20%   How far OTM the strike is\n"
        "                        Lower delta = further OTM = safer\n"
        "\n"
        "Liquidity         10%   Bid/ask spread tightness\n"
        "                        Tighter = better fill price\n"
        "```\n\n"
        "*Score quality guide:*\n"
        "```\n"
        "80-100   Excellent  strong across all 5 factors\n"
        "60-79    Good       solid trade, minor weaknesses\n"
        "40-59    Fair       passes filters but not ideal\n"
        "below 40 Marginal   use caution, check detail card\n"
        "```\n\n"
        "*Important:* Score is relative to the current scan only.\n"
        "A score of 75 today vs 75 yesterday are not comparable.\n"
        "Always check the detail card (type: result 1) before trading.\n\n"
        "_To adjust scoring weights: edit_ `core/config.py` _weights section._"
    )


# ── Claude AI helper ──────────────────────────────────────────────────────

def ask_claude(question: str) -> str:
    """
    Send a question to Claude Sonnet via the Anthropic API.
    Returns the reply as a plain string suitable for Telegram.
    Requires ANTHROPIC_API_KEY in .env
    """
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        return (
            "ANTHROPIC_API_KEY not found in .env\n\n"
            "To enable Claude AI chat:\n"
            "1. Get your key at console.anthropic.com\n"
            "2. Add to .env: ANTHROPIC_API_KEY=sk-ant-...\n"
            "3. Restart the bot"
        )

    payload = json.dumps({
        "model":      CLAUDE_MODEL,
        "max_tokens": 1024,
        "system":     CLAUDE_SYSTEM_PROMPT,
        "messages":   [{"role": "user", "content": question}],
    }).encode("utf-8")

    try:
        req = urllib.request.Request(
            ANTHROPIC_API,
            data=payload,
            headers={
                "Content-Type":      "application/json",
                "x-api-key":         api_key,
                "anthropic-version": "2023-06-01",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())

        # Extract text from response
        content = data.get("content", [])
        text_blocks = [b["text"] for b in content if b.get("type") == "text"]
        return "\n".join(text_blocks).strip() if text_blocks else "No response received."

    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        log.error("Claude API HTTP error %s: %s", e.code, body)
        if e.code == 401:
            return "Invalid ANTHROPIC_API_KEY. Check your .env file."
        if e.code == 429:
            return "Claude API rate limit hit. Please wait a moment and try again."
        if e.code == 400 and "credit balance is too low" in body:
            return (
                "Anthropic account has no credits.\n\n"
                "Add credits at: console.anthropic.com\n"
                "Go to Plans & Billing -> Add credits\n"
                "Minimum top-up is $5 (~1,600 questions).\n"
                "No restart needed once credits are added."
            )
        return f"Claude API error {e.code}. Try again shortly."
    except Exception as e:
        log.error("Claude API error: %s", e)
        return f"Could not reach Claude API: {e}"


# ── OpenRouter (Llama) AI helper ──────────────────────────────────────────

def ask_openrouter(question: str) -> str:
    """
    Send a question to Llama via OpenRouter API.
    Returns the reply as a plain string suitable for Telegram.
    Requires OPENROUTER_API_KEY in .env.
    OpenRouter uses OpenAI-compatible format.
    """
    api_key = os.getenv("OPENROUTER_API_KEY", "")
    if not api_key:
        return (
            "OPENROUTER_API_KEY not found in .env\n\n"
            "To enable Llama AI chat:\n"
            "1. Get your key at openrouter.ai/settings/keys\n"
            "2. Add to .env: OPENROUTER_API_KEY=sk-or-...\n"
            "3. Restart the bot"
        )

    payload = json.dumps({
        "model":    OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": CLAUDE_SYSTEM_PROMPT},
            {"role": "user",   "content": question},
        ],
        "max_tokens": 1024,
    }).encode("utf-8")

    try:
        req = urllib.request.Request(
            OPENROUTER_API,
            data=payload,
            headers={
                "Content-Type":  "application/json",
                "Authorization": f"Bearer {api_key}",
                "X-Title":       "OptionBot",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())

        # OpenAI-compatible response: choices[0].message.content
        choices = data.get("choices", [])
        if choices:
            content = choices[0].get("message", {}).get("content", "")
            if content:
                return content.strip()
        return "No response received from Llama."

    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        log.error("OpenRouter HTTP error %s: %s", e.code, body)
        if e.code == 401:
            return "Invalid OPENROUTER_API_KEY. Check your .env file."
        if e.code == 429:
            return "OpenRouter rate limit hit. Please wait a moment and try again."
        if e.code == 402:
            return (
                "OpenRouter account has insufficient credits.\n\n"
                "Top up at: openrouter.ai/settings/credits"
            )
        return f"OpenRouter API error {e.code}. Try again shortly."
    except Exception as e:
        log.error("OpenRouter error: %s", e)
        return f"Could not reach OpenRouter API: {e}"


# ── Health check helpers ──────────────────────────────────────────────────

def _health_check_ibkr() -> tuple:
    """
    Try a TCP socket connection to known IBKR ports.
    Returns (connected: bool, port: int or None, latency_ms: float or None).
    Fast (~1-3 sec) — does not use ib_insync, no data subscription started.
    """
    import socket
    ports = [7497, 4002, 7496, 4001]
    for port in ports:
        try:
            t0 = time.time()
            s  = socket.create_connection(("127.0.0.1", port), timeout=3)
            ms = (time.time() - t0) * 1000
            s.close()
            return True, port, ms
        except Exception:
            pass
    return False, None, None


def _health_check_yahoo() -> tuple:
    """
    TCP-level reachability check to Yahoo Finance.
    Returns (reachable: bool, latency_ms: float or None).
    """
    import socket
    try:
        t0 = time.time()
        s  = socket.create_connection(("query1.finance.yahoo.com", 443), timeout=8)
        ms = (time.time() - t0) * 1000
        s.close()
        return True, ms
    except Exception as e:
        log.debug("Yahoo Finance TCP check failed: %s", e)
        return False, None


def _health_check_claude_api() -> tuple:
    """
    TCP-level reachability check to api.anthropic.com:443.
    Returns (reachable: bool, latency_ms: float or None).
    No API key used, no tokens spent.
    """
    import socket
    try:
        t0 = time.time()
        s  = socket.create_connection(("api.anthropic.com", 443), timeout=8)
        ms = (time.time() - t0) * 1000
        s.close()
        return True, ms
    except Exception as e:
        log.debug("Claude API TCP check failed: %s", e)
        return False, None


def _health_check_openrouter() -> tuple:
    """
    TCP-level reachability check to openrouter.ai:443.
    Returns (reachable: bool, latency_ms: float or None).
    No API key used, no tokens spent.
    """
    import socket
    try:
        t0 = time.time()
        s  = socket.create_connection(("openrouter.ai", 443), timeout=8)
        ms = (time.time() - t0) * 1000
        s.close()
        return True, ms
    except Exception as e:
        log.debug("OpenRouter TCP check failed: %s", e)
        return False, None


def _health_check_supabase() -> tuple:
    """
    Try a lightweight Supabase query (select count from trade_candidates).
    Returns (ok: bool, detail: str).
    """
    try:
        from data.supabase_client import SupabaseClient
        sb = SupabaseClient()
        if not sb.is_enabled():
            return False, "Not configured (missing SUPABASE_URL / SUPABASE_KEY)"
        # Lightweight query — just fetch 1 row to confirm connection
        result = sb._client.table(SupabaseClient.TABLE_CANDIDATES).select("id").limit(1).execute()
        return True, "Connected"
    except Exception as e:
        log.debug("Supabase health check error: %s", e)
        return False, str(e)[:60]


def _health_market_status() -> str:
    """Return a short market open/closed status string."""
    try:
        import pytz
        et  = pytz.timezone("America/New_York")
        now = datetime.now(et)
    except ImportError:
        from datetime import timezone, timedelta
        month  = datetime.utcnow().month
        offset = -4 if 3 <= month <= 10 else -5
        now    = datetime.now(timezone(timedelta(hours=offset)))

    weekday = now.weekday()
    t_mins  = now.hour * 60 + now.minute
    open_   = 9 * 60 + 30
    close_  = 16 * 60

    if weekday >= 5:
        days_to_mon = 7 - weekday
        return f"CLOSED (weekend — opens Mon)"
    if t_mins < open_:
        opens_in = open_ - t_mins
        return f"CLOSED (opens in {opens_in}min at 09:30 ET)"
    if t_mins >= close_:
        return "CLOSED (after hours)"
    return f"OPEN ({now.strftime('%H:%M')} ET)"


# ── Help text ─────────────────────────────────────────────────────────────

def get_help() -> str:
    # Everything inside one ``` code block so Telegram renders it in
    # monospace font with correct column alignment. No Markdown symbols
    # outside the fences = no parse errors from underscores in param names.
    return (
        "```\n"
        "OptionBot — Commands\n"
        "Just type the command (no / needed)\n"
        "\n"
        "SCAN\n"
        "  scan               scan full watchlist (CC + SCP)\n"
        "  scan CC            covered calls only\n"
        "  scan CSP           cash-secured puts only\n"
        "  scan TSLA          scan TSLA (CC + SCP)\n"
        "  scan TSLA CC       TSLA covered calls only\n"
        "  scan TSLA CSP      TSLA cash-secured puts only\n"
        "\n"
        "RESULTS\n"
        "  result             full result list (page 1)\n"
        "  page 2             go to page 2, 3, etc.\n"
        "  detail 5           full detail for result #5\n"
        "  lastscan           last scan summary (top 10)\n"
        "  score              how the 0-100 score works\n"
        "\n"
        "TRADE WORKFLOW\n"
        "  star <n>           star result #n for review\n"
        "  approve <n>        approve starred #n\n"
        "  placed <n>         confirm order placed\n"
        "  placed <n> 14:35   placed at specific time\n"
        "  unstar <n>         remove from starred\n"
        "  reject <n>         reject from starred/approved\n"
        "  starredlist        show starred candidates\n"
        "  approvedlist       show approved candidates\n"
        "  placedlist         show placed trades\n"
        "\n"
        "PORTFOLIO\n"
        "  portfolio          show open trades\n"
        "  trade 1            full detail for trade #1\n"
        "\n"
        "CLEAR LISTS (scan history & portfolio kept)\n"
        "  clearstarred       clear starred list\n"
        "  clearapproved      clear approved list\n"
        "  clearplaced        clear placed list\n"
        "\n"
        "WATCHLIST & SCHEDULE\n"
        "  watchlist           show current watchlist\n"
        "  setwatchlist AAPL TSLA NVDA\n"
        "  setwatchlist reset\n"
        "  scanschedule        show scan times (ET)\n"
        "  setscantime 09:35 13:00 15:00\n"
        "  setscantime reset\n"
        "\n"
        "CONFIG\n"
        "  config             show settings + overrides\n"
        "  set <param> <val>  change a filter\n"
        "  set reset          clear all overrides\n"
        "\n"
        "ASK AI (text only, no photos)\n"
        "  askclaude <question>   Claude AI\n"
        "  askllama <question>    Llama AI\n"
        "\n"
        "MARKET DATA\n"
        "  price TSLA / price BTC / price GOLD\n"
        "  movers             top movers\n"
        "\n"
        "SYSTEM\n"
        "  health             health check\n"
        "  stopscan           pause auto-scan\n"
        "  cancelscan         cancel running scan\n"
        "  stopbot            stop bot (password)\n"
        "\n"
        "QUICK ACCESS\n"
        "  m                  interactive menu\n"
        "\n"
        "TIPS\n"
        "  After scan: result -> browse, page 2 -> next\n"
        "              detail 1 -> top pick full detail\n"
        "  Workflow: star -> approve -> placed\n"
        "  0 results? set min_iv_rank 0, set min_iv 0.40\n"
        "  score to understand the ranking system\n"
        "```"
    )

# ── Results formatting helpers ────────────────────────────────────────────

def _format_results_page(results: list, page: int, scan_time, scanned_tickers: list) -> str:
    total       = len(results)
    total_pages = (total + RESULTS_PAGE_SIZE - 1) // RESULTS_PAGE_SIZE
    page        = max(1, min(page, total_pages))
    start       = (page - 1) * RESULTS_PAGE_SIZE
    end         = min(start + RESULTS_PAGE_SIZE, total)
    time_str    = scan_time.strftime("%Y-%m-%d %H:%M") if scan_time else "unknown"
    tickers_str = ", ".join(scanned_tickers) if scanned_tickers else "default watchlist"

    lines = [
        f"*Scan Results* -- Page {page}/{total_pages}  _({total} total)_",
        f"_{tickers_str} -- {time_str}_\n",
        "```",
        f"{'#':<3} {'Ticker':<6} {'T':<4} {'Strike':>7} {'DTE':>4} {'Exp':>6} {'Dlt':>5} {'IV%':>5} {'Prem':>6} {'Scr':>5} {'MR':>4}",
        "-" * 63,
    ]
    for rank in range(start + 1, end + 1):
        o       = results[rank - 1]
        t_label = "CC" if o.strategy == "COVERED_CALL" else "SCP"
        iv_pct  = f"{o.contract.implied_vol * 100:.0f}%"
        exp_str = o.contract.expiry.strftime("%d/%m") if hasattr(o.contract.expiry, 'strftime') else "?"
        delta_s = f"{o.greeks.delta:+.2f}"
        mr_str  = f"{o.mean_rev_score:.2f}" if getattr(o, "mean_rev_score", 0) > 0 else "  --"
        lines.append(
            f"{rank:<3} {o.contract.ticker:<6} {t_label:<4} "
            f"${o.contract.strike:>6.1f} "
            f"{o.contract.dte:>4} "
            f"{exp_str:>6} "
            f"{delta_s:>5} "
            f"{iv_pct:>5} "
            f"${o.contract.mid:>5.2f} "
            f"{o.score:>5.1f} "
            f"{mr_str:>4}"
        )
    lines.append("```")

    nav = []
    if page > 1:
        nav.append(f"`page {page - 1}` prev")
    if page < total_pages:
        nav.append(f"next `page {page + 1}`")
    if nav:
        lines.append("  |  ".join(nav))
    lines.append(f"\n_Detail:_ `detail {start + 1}`  _Star:_ `star {start + 1}`")
    lines.append(f"_Workflow:_ `star <#>` → `approve <#>` → `placed <#>`")
    return "\n".join(lines)


def _format_result_detail(results: list, rank: int, scan_time, scanned_tickers: list) -> str:
    total = len(results)
    if rank < 1 or rank > total:
        return (
            f"Rank {rank} is out of range.\n"
            f"Valid range: `detail 1` to `detail {total}`\n\n"
            f"Send `result` to see the full list."
        )

    o              = results[rank - 1]
    c              = o.contract
    g              = o.greeks
    strategy_label = "Covered Call" if o.strategy == "COVERED_CALL" else "Cash-Secured Put"
    otm_pct        = abs(c.strike - c.underlying_price) / c.underlying_price * 100
    otm_dir        = "above" if o.strategy == "COVERED_CALL" else "below"
    spread_pct     = getattr(c, "spread_pct", 0) * 100
    spread_flag    = " [wide]" if spread_pct > 8 else ""
    iv_rank_str    = f"{o.iv_rank:.0f}" if o.iv_rank > 0 else "N/A"
    ann_ret_str    = f"{o.annualised_return * 100:.1f}%"
    theta_y_str    = f"{o.theta_yield * 100:.2f}%/day" if getattr(o, "theta_yield", None) else "--"

    if o.strategy == "COVERED_CALL":
        capital_str = f"${c.underlying_price * 100:,.0f}  (100 shares at ${c.underlying_price:.2f})"
        action_str  = f"Sell {c.ticker} ${c.strike:.1f} CALL  |  {c.dte}d to expiry"
    else:
        capital_str = f"${c.strike * 100:,.0f}  (cash reserve)"
        action_str  = f"Sell {c.ticker} ${c.strike:.1f} PUT   |  {c.dte}d to expiry"
        cost_basis  = c.strike - c.mid

    lines = [
        f"*#{rank} / {total} -- {strategy_label}*\n",
        f"`{action_str}`",
        f"_Underlying: ${c.underlying_price:.2f}  |  {otm_pct:.1f}% OTM {otm_dir}_",
        f"_Score: {o.score:.1f} / 100_\n",
        "```",
        f"-- Contract ------------------",
        f"Strike      : ${c.strike:.2f}",
        f"DTE         : {c.dte} days",
        f"",
        f"-- Premium -------------------",
        f"Bid / Ask   : ${c.bid:.2f} / ${c.ask:.2f}",
        f"Mid (credit): ${c.mid:.2f}",
        f"Spread      : {spread_pct:.1f}%{spread_flag}",
        f"",
        f"-- Greeks --------------------",
        f"Delta       : {g.delta:+.3f}",
        f"Theta       : ${g.theta:.3f}/day",
        f"Vega        : {g.vega:.3f}",
        f"Gamma       : {g.gamma:.4f}",
        f"",
        f"-- IV & Return ---------------",
        f"Implied Vol : {c.implied_vol * 100:.1f}%",
        f"IV Rank     : {iv_rank_str}",
        f"Ann. Return : {ann_ret_str}",
        f"Theta Yield : {theta_y_str}",
        f"",
        f"-- Liquidity -----------------",
        f"Open Int    : {c.open_interest}",
        f"Volume      : {c.volume}",
        f"",
        f"-- Capital -------------------",
        f"Required    : {capital_str}",
    ]

    # Mean Reversion section (only if populated)
    if getattr(o, "mean_rev_score", 0) > 0:
        tg_str = " ⚠TREND GUARD" if getattr(o, "trend_guard_active", False) else ""
        lines.extend([
            f"",
            f"-- Mean Reversion ------------",
            f"MR Score    : {o.mean_rev_score:.2f}{tg_str}",
            f"RSI(5)      : {o.rsi_5:.0f}",
            f"Z-Score(20) : {o.z_score_20:+.2f}",
            f"ROC %Rank   : {o.roc_pct_rank:.0f}",
            f"SMA200 Dist : {o.sma200_distance_pct:+.1f}%",
        ])

    lines.append("```")
    lines = lines  # close the code block after MR section

    if o.strategy == "COVERED_CALL":
        lines.append(
            f"\n_Sell if you own 100 shares of {c.ticker}._\n"
            f"_Target: close at 50% profit (${c.mid * 0.5:.2f}) or {max(c.dte - 21, 1)}d DTE._"
        )
    else:
        lines.append(
            f"\n_Sell only if willing to own {c.ticker} at ${c.strike:.2f}._\n"
            f"_If assigned: cost basis = ${cost_basis:.2f} (strike - premium)._\n"
            f"_Target: close at 50% profit (${c.mid * 0.5:.2f}) or {max(c.dte - 21, 1)}d DTE._"
        )

    nav_parts = []
    if rank > 1:
        nav_parts.append(f"`detail {rank - 1}` prev")
    if rank < total:
        nav_parts.append(f"next `detail {rank + 1}`")
    if nav_parts:
        lines.append("\n" + "  |  ".join(nav_parts))
    lines.append(f"\n_⭐ Star this pick:_ `star {rank}`")
    lines.append(f"_Workflow:_ `star {rank}` → `approve {rank}` → `placed {rank}`")
    lines.append(f"_Back to list:_ `result`")
    return "\n".join(lines)


# ── Workflow list formatter ───────────────────────────────────────────────

def _format_candidate_list(rows: list, title: str, hint: str) -> str:
    """Format starredlist / approvedlist / placedlist for Telegram."""
    if not rows:
        return f"*{title}*\n\n_Nothing here yet._\n\n_{hint}_"

    lines = [f"*{title}* -- {len(rows)} item(s)\n", "```"]
    lines.append(
        f"{'#':<3} {'Date':<7} {'Ticker':<6} {'T':<3} "
        f"{'Strike':>7} {'Expiry':<10} {'Prem':>6} {'Scr':>5}"
    )
    lines.append("-" * 54)

    for i, row in enumerate(rows, 1):
        try:
            dt       = datetime.fromisoformat(str(row["scan_time"]).replace("Z", ""))
            date_str = dt.strftime("%d-%b")
        except Exception:
            date_str = "?"

        ticker  = str(row.get("ticker", "?"))[:6]
        strat   = row.get("strategy", "")
        t_label = "CC" if "CALL" in strat.upper() else "CP"
        strike  = float(row.get("strike", 0))
        expiry  = str(row.get("expiry", "?"))
        premium = float(row.get("premium", 0))
        score   = float(row.get("score", 0))

        lines.append(
            f"{i:<3} {date_str:<7} {ticker:<6} {t_label:<3} "
            f"${strike:>6.1f} {expiry:<10} "
            f"${premium:>5.2f} {score:>5.1f}"
        )

    lines.append("```")
    lines.append(f"\n_{hint}_")
    return "\n".join(lines)


def _try_fetch_price(ticker: str):
    """Fetch current Yahoo Finance price. Returns float or None."""
    try:
        data = _yahoo_fetch(ticker)
        if data and data.get("price", 0) > 0:
            return float(data["price"])
    except Exception as e:
        log.debug("_try_fetch_price %s failed: %s", ticker, e)
    return None


# ── Ticker validation ─────────────────────────────────────────────────────

def _validate_tickers(raw_tickers: List[str]):
    valid, invalid = [], []
    for t in raw_tickers:
        t = t.upper().strip()
        if not t:
            continue
        data = _yahoo_fetch(t)
        if data and data["price"] > 0:
            valid.append(t)
        else:
            invalid.append(t)
    return valid, invalid


# ── Bot Listener ──────────────────────────────────────────────────────────

class TelegramBotListener:
    def __init__(
        self,
        token: Optional[str] = None,
        chat_id: Optional[str] = None,
        scan_state=None,
        notifier=None,
    ):
        self.token    = token    or os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.chat_id  = chat_id  or os.getenv("TELEGRAM_CHAT_ID", "")  # admin
        self.state    = scan_state
        self.notifier = notifier
        self._offset  = 0
        self._running = False

        # Load viewer IDs (comma-separated in env)
        viewer_str = os.getenv("TELEGRAM_VIEWER_IDS", "")
        self._viewer_ids: set = {
            v.strip() for v in viewer_str.split(",") if v.strip()
        }
        # All allowed chat IDs = admin + viewers
        self._allowed_ids: set = set()
        if self.chat_id:
            self._allowed_ids.add(self.chat_id)
        self._allowed_ids.update(self._viewer_ids)
        if self._viewer_ids:
            log.info("Viewer IDs loaded: %s", ", ".join(self._viewer_ids))

        # Live config overrides — persist until `set reset` is sent.
        # Never cleared automatically by scans or bot restarts.
        self._config_overrides: dict = {}

        # Results pagination state — tracks current page for next/previous
        self._results_current_page: int = 1

        # Bot uptime tracking
        self._start_time: datetime = datetime.now()

        # stopbot password flow state
        self._stopbot_pending: bool      = False
        self._stopbot_pending_time: float = 0.0

        if not self.token:
            raise ValueError("Missing TELEGRAM_BOT_TOKEN in .env")

    def get_config_overrides(self) -> dict:
        """Called by scheduler to apply any live overrides set via Telegram."""
        return dict(self._config_overrides)

    def send_main_menu(self):
        """Send the top-level interactive menu to the configured chat.
        Called by scheduler.py after the startup notification."""
        if self.chat_id:
            self._send_category_menu(self.chat_id)

    def send_results_menu(self):
        """Send the Results category menu to the configured chat.
        Called by scheduler.py automatically after each scan completes."""
        if self.chat_id:
            self._send_category_menu(self.chat_id, "results")

    def start(self):
        self._running = True
        # Register slash commands with Telegram so they show in autocomplete menu
        self._register_commands()
        # Drain any messages queued before this startup — prevents stale
        # commands (e.g. /stopbot) from firing the moment the bot starts.
        self._drain_queue()
        t = threading.Thread(target=self._poll_loop, daemon=True)
        t.start()
        log.info("Telegram bot listener started (polling)")
        return t

    def stop(self):
        self._running = False

    def _drain_queue(self):
        """
        Advance the offset past all messages currently in the Telegram queue.
        Called once at startup so stale commands queued while the bot was
        offline are silently skipped — they are never processed.
        """
        try:
            url    = TELEGRAM_API.format(token=self.token, method="getUpdates")
            params = urllib.parse.urlencode({"offset": -1, "timeout": 0})
            req    = urllib.request.Request(f"{url}?{params}", headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read())
            updates = data.get("result", [])
            if updates:
                self._offset = updates[-1]["update_id"] + 1
                log.info("Startup drain: skipped %d pending message(s).", len(updates))
        except Exception as e:
            log.warning("Startup drain failed (non-fatal): %s", e)

    def _poll_loop(self):
        while self._running:
            try:
                updates = self._get_updates()
                for update in updates:
                    self._handle_update(update)
            except Exception as e:
                log.error("Poll error: %s", e)
            time.sleep(2)

    def _get_updates(self) -> list:
        url    = TELEGRAM_API.format(token=self.token, method="getUpdates")
        # allowed_updates ensures Telegram sends both messages AND button presses
        params = urllib.parse.urlencode({
            "offset":          self._offset,
            "timeout":         10,
            "allowed_updates": '["message","callback_query"]',
        })
        req = urllib.request.Request(f"{url}?{params}", headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        updates = data.get("result", [])
        if updates:
            self._offset = updates[-1]["update_id"] + 1
        return updates

    def _register_commands(self):
        """
        Register slash commands with Telegram so they appear in the autocomplete
        menu when the user types / in the chat. Safe to call on every start.
        """
        commands = [
            ("m",              "Interactive menu — browse all commands by category"),
            ("scan",           "Run option scan (full or custom tickers)"),
            ("result",         "Full ranked results list (page 1)"),
            ("detail",         "Detail for result #n  e.g. detail 5"),
            ("page",           "Jump to results page  e.g. page 2"),
            ("lastscan",       "Show last scan summary (top 10)"),
            ("score",          "Explain the 0-100 scoring system"),
            ("starredlist",    "Show all starred candidates"),
            ("approvedlist",   "Show all approved candidates"),
            ("placedlist",     "Show all placed trades (workflow view)"),
            ("clearstarred",   "Remove all candidates from starred list"),
            ("clearapproved",  "Remove all candidates from approved list"),
            ("clearplaced",    "Clear placed list (portfolio/trade records kept)"),
            ("portfolio",      "Show all open trades in portfolio"),
            ("trade",          "Full detail for open trade #n  e.g. trade 1"),
            ("config",         "Show current scan config and overrides"),
            ("watchlist",      "Show current scan watchlist"),
            ("setwatchlist",   "Set scan watchlist (e.g. AAPL TSLA NVDA / reset)"),
            ("scanschedule",   "Show current auto-scan schedule"),
            ("setscantime",    "Set scan times in ET (e.g. 09:35 13:00 15:00 / reset)"),
            ("stopscan",       "Pause auto-scheduled scans"),
            ("cancelscan",     "Cancel a scan currently in progress"),
            ("movers",         "Top market movers (stocks, crypto, indices)"),
            ("askclaude",      "Ask Claude AI a question (Anthropic)"),
            ("askllama",       "Ask Llama AI a question (OpenRouter)"),
            ("health",         "System health check (IBKR, Supabase, Claude, OpenRouter)"),
            ("stopbot",        "Gracefully stop the bot (password required)"),
            ("help",           "Show all commands and usage guide"),
        ]
        try:
            url     = TELEGRAM_API.format(token=self.token, method="setMyCommands")
            payload = json.dumps(
                {"commands": [{"command": cmd, "description": desc} for cmd, desc in commands]}
            ).encode("utf-8")
            req = urllib.request.Request(
                url, data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read())
            if result.get("ok"):
                log.info("Telegram slash commands registered (%d commands).", len(commands))
            else:
                log.warning("setMyCommands returned not-ok: %s", result)
        except Exception as e:
            log.warning("Could not register Telegram slash commands: %s", e)

    def _handle_update(self, update: dict):
        # ── Inline keyboard button press ──────────────────────────────────
        cb = update.get("callback_query", {})
        if cb:
            self._handle_callback(cb)
            return

        msg     = update.get("message", {})
        text    = msg.get("text", "").strip()
        chat_id = str(msg.get("chat", {}).get("id", ""))

        if not text:
            return
        # Multi-user access: admin + viewers allowed; all others ignored
        if self._allowed_ids and chat_id not in self._allowed_ids:
            log.warning("Message from unknown chat %s ignored", chat_id)
            return
        is_admin = (chat_id == self.chat_id) if self.chat_id else True

        # ── stopbot password confirmation — checked BEFORE slash gate ────────
        # When waiting for a password, accept the reply regardless of whether
        # it starts with / (the password is plain text, not a slash command).
        if self._stopbot_pending:
            # Auto-cancel if too much time has passed
            if time.time() - self._stopbot_pending_time > STOPBOT_TIMEOUT_SECS:
                self._stopbot_pending = False
                self._send(chat_id,
                    "Stopbot request timed out (60s). Send `stopbot` to try again.")
                return
            # Check password
            self._stopbot_pending = False
            if text.strip() == STOPBOT_PASSWORD:
                self._send(chat_id,
                    "🛑 *Bot shutting down...*\n\n"
                    "Password accepted. Goodbye!\n"
                    "_Restart with: `bash START_BOT.sh` or `bash START_BOT_BACKGROUND.sh`_"
                )
                time.sleep(1)   # give Telegram time to deliver the message
                log.info("stopbot command received — sending SIGTERM to self.")
                os.kill(os.getpid(), signal.SIGTERM)
            else:
                self._send(chat_id,
                    "❌ *Incorrect password.*\n\nBot is still running.\n"
                    "Send `stopbot` again to retry.")
            return

        # Strip optional leading / and any @botname suffix
        if text.startswith("/"):
            text = text[1:]
        if text and "@" in text.split()[0]:
            first = text.split()[0]
            text = first.split("@")[0] + text[len(first):]
        if not text:
            return

        log.info("Received command: %s (admin=%s)", text, is_admin)
        lower = text.lower()
        parts = text.split()

        # ── Admin-only gate for restricted commands ──────────────────────
        cmd_word = parts[0].lower() if parts else ""
        if cmd_word in ADMIN_ONLY_COMMANDS and not is_admin:
            self._send(chat_id, "🔒 This command is admin-only.")
            return

        # ── scan ─────────────────────────────────────────────────────────
        if lower == "scan" or (lower.startswith("scan ") and len(parts) >= 2
                               and parts[1].upper() != "CONFIG"):
            if self.state is None:
                reply = "Scanner not available."
            elif self.state.is_running():
                reply = (
                    "A scan is *already in progress*.\n\n"
                    "Send `cancelscan` to stop it."
                )
            else:
                raw_parts = [p.upper() for p in parts[1:]] if len(parts) > 1 else []

                # Extract optional strategy token (CC / CSP / BOTH) from any position
                STRATEGY_TOKENS = {"CC": "cc", "CSP": "csp", "BOTH": "both"}
                scan_strategy = None
                ticker_parts  = []
                for p in raw_parts:
                    if p in STRATEGY_TOKENS:
                        scan_strategy = STRATEGY_TOKENS[p]
                    else:
                        ticker_parts.append(p)

                strategy_label = f" [{scan_strategy.upper()}]" if scan_strategy else ""

                if ticker_parts:
                    self._send(chat_id, f"Validating {len(ticker_parts)} ticker(s)...")
                    valid, invalid = _validate_tickers(ticker_parts)
                    if invalid:
                        invalid_str = ", ".join(f"`{t}`" for t in invalid)
                        if not valid:
                            self._send(chat_id, f"Unknown tickers: {invalid_str}")
                            return
                        self._send(chat_id, f"Skipping unknown: {invalid_str}")
                    tickers_to_scan = valid
                    ticker_str      = ", ".join(f"`{t}`" for t in tickers_to_scan)
                    self.state.request_scan(tickers=tickers_to_scan, strategy=scan_strategy)
                    reply = f"*Custom scan requested!*{strategy_label}\nScanning: {ticker_str}"
                else:
                    wl = self.state.get_watchlist()
                    wl_preview = " ".join(wl[:5]) + ("…" if len(wl) > 5 else "")
                    if scan_strategy:
                        # Strategy already specified — start scan immediately
                        self.state.request_scan(tickers=None, strategy=scan_strategy)
                        watchlist_str = ", ".join(f"`{t}`" for t in wl)
                        reply = f"*Full scan requested!*{strategy_label}\nScanning: {watchlist_str}"
                    else:
                        # No args — show quick-action buttons
                        self._send_with_keyboard(
                            chat_id,
                            f"*📊 Scan Options*\nWatchlist: `{wl_preview}`\n\nChoose scan type:",
                            [
                                [{"text": "🔍 Full Scan (CC + CSP)", "callback_data": "cb_scan_full"}],
                                [
                                    {"text": "📈 Covered Calls",    "callback_data": "cb_scan_cc"},
                                    {"text": "📉 Cash-Sec Puts",    "callback_data": "cb_scan_csp"},
                                ],
                                [
                                    {"text": "📋 Watchlist",        "callback_data": "cb_watchlist"},
                                    {"text": "🕐 Schedule",         "callback_data": "cb_schedule"},
                                ],
                            ],
                        )
                        return

        # ── cancelscan ───────────────────────────────────────────────────
        elif lower == "cancelscan":
            if self.state is None:
                reply = "Scanner not available."
            elif not self.state.is_running():
                reply = "No scan is currently running."
            elif self.state.is_cancel_requested():
                # Cancel was already set but scan hasn't responded — scan is stuck.
                # Force-reset state so a new scan can start without restarting the bot.
                self.state.force_reset()
                reply = (
                    "*Force reset applied.*\n"
                    "Stuck scan cleared — send `scan` to start a fresh scan."
                )
            else:
                self.state.request_cancel()
                reply = "*Cancel requested.*\nStopping at next batch (~5-10 sec)."

        # ── stopscan ─────────────────────────────────────────────────────
        elif lower == "stopscan":
            if self.state is None:
                reply = "Scanner not available."
            elif not self.state.is_enabled():
                reply = "Scheduler is *already paused.*"
            else:
                self.state.disable_scheduler()
                reply = (
                    "*Scheduled scanner paused.*\n"
                    "Manual `scan` commands still work.\n\n"
                    "_Restart the bot to re-enable auto-scan._"
                )

        # ── lastscan ─────────────────────────────────────────────────────
        elif lower == "lastscan":
            reply = self._build_lastscan_reply()

        # ── result / results / fullresult — full result list (page 1) ─────
        elif lower in ("result", "results", "fullresult") or lower.startswith("fullresult "):
            page = 1
            if lower.startswith("fullresult ") and len(parts) >= 2:
                try:
                    page = int(parts[1])
                except ValueError:
                    self._send(chat_id, "Usage: `result` or `page 2`")
                    return
            self._results_current_page = page
            reply = self._build_results_page_reply(page)

        # ── page <#> — jump to specific results page ─────────────────────
        elif lower.startswith("page ") and len(parts) == 2:
            try:
                page = int(parts[1])
            except ValueError:
                self._send(chat_id, "Usage: `page 2`  (page number)")
                return
            self._results_current_page = page
            reply = self._build_results_page_reply(page)

        # ── detail <rank> — individual result detail ─────────────────────
        elif lower.startswith("detail ") and len(parts) == 2:
            try:
                rank = int(parts[1])
            except ValueError:
                self._send(chat_id, "Usage: `detail 5`  (rank number from `result`)")
                return
            reply = self._build_result_detail_reply(rank)

        # ── star <n> ──────────────────────────────────────────────────────
        elif lower.startswith("star ") and len(parts) == 2:
            reply = self._handle_star(chat_id, parts)

        # ── unstar <n> ────────────────────────────────────────────────────
        elif lower.startswith("unstar ") and len(parts) == 2:
            reply = self._handle_unstar(chat_id, parts)

        # ── approve <n> ───────────────────────────────────────────────────
        elif lower.startswith("approve ") and len(parts) == 2:
            reply = self._handle_approve(chat_id, parts)

        # ── placed <n> [HH:MM] ────────────────────────────────────────────
        elif lower.startswith("placed ") and len(parts) in (2, 3):
            reply = self._handle_placed(chat_id, parts)

        # ── reject <n> ────────────────────────────────────────────────────
        elif lower.startswith("reject ") and len(parts) == 2:
            reply = self._handle_reject(chat_id, parts)

        # ── starredlist ───────────────────────────────────────────────────
        elif lower == "starredlist":
            reply = self._handle_list("starred")

        # ── approvedlist ──────────────────────────────────────────────────
        elif lower == "approvedlist":
            reply = self._handle_list("approved")

        # ── placedlist ────────────────────────────────────────────────────
        elif lower == "placedlist":
            reply = self._handle_list("placed")

        # ── clearstarred / clearapproved / clearplaced ────────────────────
        elif lower == "clearstarred":
            reply = self._handle_clear_list("starred")
        elif lower == "clearapproved":
            reply = self._handle_clear_list("approved")
        elif lower == "clearplaced":
            reply = self._handle_clear_list("placed")

        # ── portfolio ─────────────────────────────────────────────────────
        elif lower == "portfolio":
            reply = self._handle_portfolio()

        # ── trade <n> — open trade detail card ───────────────────────────
        elif lower.startswith("trade ") and len(parts) == 2:
            try:
                rank = int(parts[1])
                reply = self._handle_trade_detail(rank)
            except ValueError:
                reply = "Usage: `trade <n>`  e.g. `trade 1`"

        # ── score ─────────────────────────────────────────────────────────
        elif lower == "score":
            reply = get_score_explanation()

        # ── askclaude <question> ──────────────────────────────────────────
        elif lower.startswith("askclaude ") and len(text) > 10:
            question = text[10:].strip()
            if not question:
                self._send(chat_id, "Usage: askclaude <your question>", use_markdown=False)
                return
            self._send(chat_id, "🤖 Claude thinking...", use_markdown=False)
            answer = ask_claude(question)
            self._send(chat_id, answer, use_markdown=False)
            return

        # ── askllama <question> ───────────────────────────────────────────
        elif lower.startswith("askllama ") and len(text) > 9:
            question = text[9:].strip()
            if not question:
                self._send(chat_id, "Usage: askllama <your question>", use_markdown=False)
                return
            self._send(chat_id, "🦙 Llama thinking...", use_markdown=False)
            answer = ask_openrouter(question)
            self._send(chat_id, answer, use_markdown=False)
            return

        # ── config ───────────────────────────────────────────────────────
        elif lower == "config":
            # Sent with Markdown ON so the ``` fences render as a code block.
            # Safe because ALL content is inside the code block — no Markdown
            # symbols outside it means nothing for the parser to misinterpret.
            reply = self._build_config_reply()

        # ── setwatchlist ─────────────────────────────────────────────────
        # NOTE: must come BEFORE the `set` branch to avoid partial matching
        elif lower == "setwatchlist" or lower.startswith("setwatchlist "):
            reply = self._handle_setwatchlist(parts)

        # ── watchlist ─────────────────────────────────────────────────────
        elif lower == "watchlist":
            reply = self._handle_watchlist()

        # ── setscantime ───────────────────────────────────────────────────
        # NOTE: must come BEFORE the `set` branch to avoid partial matching
        elif lower == "setscantime" or lower.startswith("setscantime "):
            reply = self._handle_setscantime(parts)

        # ── scanschedule ──────────────────────────────────────────────────
        elif lower == "scanschedule":
            reply = self._handle_scanschedule()

        # ── set <param> <value> — single or multi-line ───────────────────
        # Handles both formats:
        #   set min_iv_rank 0 min_iv 0.40          (single line, multiple pairs)
        #   set min_iv_rank 0\nset min_iv 0.40      (multiple lines, each with set)
        elif lower.startswith("set ") or all(
            ln.strip().lower().startswith("set ") or ln.strip() == ""
            for ln in text.splitlines() if ln.strip()
        ):
            reply = self._handle_set(parts, raw_text=text)

        # ── price ─────────────────────────────────────────────────────────
        elif lower.startswith("price "):
            ticker = text[6:].strip()
            reply  = get_price_quote(ticker)

        # ── movers ───────────────────────────────────────────────────────
        elif lower == "movers":
            self._send(chat_id, "Fetching top movers...")
            reply = get_top_movers()

        # ── health ────────────────────────────────────────────────────────
        elif lower == "health":
            self._send(chat_id, "Running health checks...")
            reply = self._handle_health()

        # ── stopbot ───────────────────────────────────────────────────────
        elif lower == "stopbot":
            self._stopbot_pending      = True
            self._stopbot_pending_time = time.time()
            reply = (
                "🛑 *Stop Bot Requested*\n\n"
                "Enter the password to confirm shutdown:\n"
                "_Wrong password or no reply in 60s = bot stays running._"
            )

        # ── m / menu — interactive menu ──────────────────────────────────
        elif lower in ("m", "menu") or lower.startswith("menu "):
            self._send_category_menu(chat_id)
            return

        # ── help ──────────────────────────────────────────────────────────
        elif lower == "help":
            # Help text exceeds Telegram's 4096-char limit — must use _send_long()
            # which splits into chunks while keeping ``` fences correctly paired.
            self._send_long(chat_id, get_help())
            return

        else:
            reply = (
                "Unknown command: `" + text + "`\n\n"
                "Send `help` for all commands.\n"
                "Or: `askclaude <question>` for Claude AI\n"
                "Or: `askllama <question>` for Llama AI"
            )

        self._send(chat_id, reply)

    # ── Results paging ────────────────────────────────────────────────────

    def _get_cached_results(self):
        if self.state is None:
            return None, None, 0, []
        results, scan_time, count, scanned_tickers = self.state.get_last_results()
        return results, scan_time, count, scanned_tickers

    def _build_results_page_reply(self, page: int) -> str:
        results, scan_time, count, scanned_tickers = self._get_cached_results()
        if results is None:
            return "*No scan results yet.*\n\nSend `scan` to run a scan now."
        if count == 0:
            return "*Last scan found 0 opportunities.*\n\n_Send `config` to review thresholds._"
        total_pages = (count + RESULTS_PAGE_SIZE - 1) // RESULTS_PAGE_SIZE
        if page < 1 or page > total_pages:
            return f"Page {page} does not exist. Valid: 1 to {total_pages}.\n\nSend `results` for page 1."
        return _format_results_page(results, page, scan_time, scanned_tickers)

    def _build_result_detail_reply(self, rank: int) -> str:
        results, scan_time, count, scanned_tickers = self._get_cached_results()
        if results is None:
            return "*No scan results yet.*\n\nSend `scan` to run a scan now."
        if count == 0:
            return "*Last scan found 0 opportunities.*"
        return _format_result_detail(results, rank, scan_time, scanned_tickers)

    def _build_lastscan_reply(self) -> str:
        results, scan_time, count, scanned_tickers = self._get_cached_results()
        if results is None:
            return "*No scan results yet.*\n\nSend `scan` to run a scan now."

        time_str    = scan_time.strftime("%Y-%m-%d %H:%M") if scan_time else "Unknown"
        tickers_str = ", ".join(scanned_tickers) if scanned_tickers else "default watchlist"

        if count == 0:
            return (
                f"*Last Scan* -- `{time_str}`\n"
                f"Tickers: `{tickers_str}`\n\n"
                "No opportunities found.\n"
                "_Send `config` to review thresholds._"
            )

        preview_count = min(LASTSCAN_PREVIEW, count)
        lines = [
            f"*Last Scan* -- `{time_str}`",
            f"_Tickers: {tickers_str}_",
            f"_Showing top {preview_count} of {count} total_\n",
            "```",
            f"{'#':<3} {'Ticker':<6} {'T':<4} {'Strike':>7} {'DTE':>4} {'Exp':>6} {'Dlt':>5} {'IV%':>5} {'Prem':>6} {'Scr':>5}",
            "-" * 58,
        ]
        for i, o in enumerate(results[:preview_count], 1):
            t_label = "CC" if o.strategy == "COVERED_CALL" else "SCP"
            iv_pct  = f"{o.contract.implied_vol * 100:.0f}%"
            exp_str = o.contract.expiry.strftime("%d/%m") if hasattr(o.contract.expiry, 'strftime') else "?"
            delta_s = f"{o.greeks.delta:+.2f}"
            lines.append(
                f"{i:<3} {o.contract.ticker:<6} {t_label:<4} "
                f"${o.contract.strike:>6.1f} "
                f"{o.contract.dte:>4} "
                f"{exp_str:>6} "
                f"{delta_s:>5} "
                f"{iv_pct:>5} "
                f"${o.contract.mid:>5.2f} "
                f"{o.score:>5.1f}"
            )
        lines.append("```")

        if count > LASTSCAN_PREVIEW:
            remaining   = count - LASTSCAN_PREVIEW
            total_pages = (count + RESULTS_PAGE_SIZE - 1) // RESULTS_PAGE_SIZE
            lines.append(
                f"\n_{remaining} more not shown._\n"
                f"`result` — all {count} results ({total_pages} pages)\n"
                f"`detail 1` — full detail on top pick"
            )
        else:
            lines.append("\n_Send `detail 1` for full detail on the top pick._")

        return "\n".join(lines)

    # ── Health check ──────────────────────────────────────────────────────

    def _handle_health(self) -> str:
        """
        Run live checks on all system components and return a formatted
        status card for Telegram. Each check is independent — one failure
        does not block the others.
        """
        lines = ["*System Health Check*\n"]

        # ── 1. Telegram (trivially OK — we received the command) ──────────
        lines.append("✅ Telegram        Connected")

        # ── 2. Data source (Yahoo Finance or IBKR) ────────────────────────
        data_source = self._config_overrides.get("data_source", "yahoo").lower()
        if data_source == "ibkr":
            ibkr_ok, ibkr_port, ibkr_ms = _health_check_ibkr()
            if ibkr_ok:
                lines.append(f"✅ IBKR            Port {ibkr_port} ({ibkr_ms:.0f}ms)  [data source]")
            else:
                lines.append(
                    "❌ IBKR            Not reachable  [data source]\n"
                    "   Check: TWS or IB Gateway running?\n"
                    "   Tip: `set data_source yahoo` to scan without IBKR"
                )
        else:
            # Yahoo Finance is the data source
            yf_ok, yf_ms = _health_check_yahoo()
            if yf_ok:
                lines.append(f"✅ Yahoo Finance   Reachable ({yf_ms:.0f}ms)  [data source — 15min delay]")
            else:
                lines.append("❌ Yahoo Finance   Not reachable — check internet connection")
            # Show IBKR as informational (needed for placing trades, not scanning)
            ibkr_ok, ibkr_port, ibkr_ms = _health_check_ibkr()
            if ibkr_ok:
                lines.append(f"✅ IBKR            Port {ibkr_port} ({ibkr_ms:.0f}ms)  [trade execution]")
            else:
                lines.append("⚪ IBKR            Not running  [not needed for scanning]")

        # ── 3. Supabase ───────────────────────────────────────────────────
        sb_ok, sb_detail = _health_check_supabase()
        if sb_ok:
            lines.append(f"✅ Supabase        {sb_detail}")
        else:
            lines.append(f"❌ Supabase        {sb_detail}")

        # ── 4. Claude API (TCP to api.anthropic.com:443) ──────────────────
        claude_ok, claude_ms = _health_check_claude_api()
        claude_key_ok = bool(os.getenv("ANTHROPIC_API_KEY", ""))
        if claude_ok:
            key_note = "" if claude_key_ok else " (⚠️ no API key)"
            lines.append(f"✅ Claude API      Reachable ({claude_ms:.0f}ms){key_note}")
        else:
            lines.append("❌ Claude API      Not reachable (check internet)")

        # ── 5. OpenRouter / Llama ─────────────────────────────────────────
        or_ok, or_ms = _health_check_openrouter()
        or_key_ok    = bool(os.getenv("OPENROUTER_API_KEY", ""))
        if or_ok:
            key_note = "" if or_key_ok else " (⚠️ no API key)"
            lines.append(f"✅ OpenRouter      Reachable ({or_ms:.0f}ms){key_note}")
        else:
            lines.append("❌ OpenRouter      Not reachable (check internet)")

        # ── 6. Market status ──────────────────────────────────────────────
        market_str = _health_market_status()
        lines.append(f"\n📊 *Market:* {market_str}")

        # ── 7. Next auto-scan slots ───────────────────────────────────────
        # Import SCAN_SLOTS from scheduler context if available
        try:
            from scheduler import SCAN_SLOTS
            slots_str = "  ".join(
                f"{h:02d}:{m:02d} [{lbl}]" for h, m, lbl in SCAN_SLOTS
            )
        except ImportError:
            slots_str = "09:35 [Open]  12:45 [Midday]  15:00 [Pre-Close]"
        lines.append(f"📅 *Auto-scan slots (ET):*\n`{slots_str}`")

        # ── 8. Scanner running status ─────────────────────────────────────
        if self.state is not None:
            if self.state.is_running():
                lines.append("⏳ *Scanner:* Scan in progress...")
            elif not self.state.is_enabled():
                lines.append("⏸ *Scanner:* Auto-scan paused (send `scan` for manual scan)")
            else:
                lines.append("💤 *Scanner:* Idle (waiting for next slot)")

        # ── 9. Bot uptime ─────────────────────────────────────────────────
        uptime_secs = int((datetime.now() - self._start_time).total_seconds())
        hours, rem  = divmod(uptime_secs, 3600)
        mins, secs  = divmod(rem, 60)
        if hours > 0:
            uptime_str = f"{hours}h {mins}m"
        elif mins > 0:
            uptime_str = f"{mins}m {secs}s"
        else:
            uptime_str = f"{secs}s"
        lines.append(f"⏱ *Bot uptime:* {uptime_str}")

        # ── 10. Active config overrides ───────────────────────────────────
        if self._config_overrides:
            ov_parts = [f"{k}={v}" for k, v in self._config_overrides.items()]
            lines.append(f"⚙️ *Overrides:* `{', '.join(ov_parts)}`")
        else:
            lines.append("⚙️ *Overrides:* none (all defaults)")

        lines.append(f"\n_Checked at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_")
        return "\n".join(lines)

    # ── Workflow handlers — star / approve / placed / reject / lists ──────

    def _get_supabase(self):
        """Lazy-init Supabase client. Returns None if unavailable."""
        try:
            from dotenv import load_dotenv
            load_dotenv()
            from data.supabase_client import SupabaseClient
            client = SupabaseClient()
            if client.is_enabled():
                return client
        except Exception as e:
            log.error("Supabase init error: %s", e)
        return None

    def _handle_star(self, chat_id: str, parts: list) -> str:
        """star <n> — star result #n from the last scan (in-memory list)."""
        try:
            rank = int(parts[1])
        except ValueError:
            return "Usage: `star <n>`  e.g. `star 3`"

        results, scan_time, count, _ = self._get_cached_results()
        if not results or count == 0:
            return "*No scan results to star.*\n\nRun `scan` first."
        if rank < 1 or rank > count:
            return f"Rank {rank} out of range. Valid: 1 to {count}."

        o = results[rank - 1]
        sb = self._get_supabase()
        if not sb:
            return "Supabase not available — cannot star candidates."

        # Find existing pending row and update to starred.
        # Falls back to insert if no existing row found.
        result = sb.find_and_star(o, scan_time)
        if result == "error":
            return "Failed to star candidate. Try again."

        t_label = "CC" if o.strategy == "COVERED_CALL" else "CSP"
        note    = "" if result == "updated" else "\n_No existing record found — new entry created._"
        return (
            f"⭐ *Starred #{rank}*\n\n"
            f"`{o.contract.ticker} {t_label} ${o.contract.strike:.1f}` "
            f"exp {o.contract.expiry}  score {o.score:.1f}\n\n"
            f"_Send `starredlist` to review all starred candidates._"
            f"{note}"
        )

    def _handle_unstar(self, chat_id: str, parts: list) -> str:
        """unstar <n> — remove item #n from starredlist."""
        try:
            rank = int(parts[1])
        except ValueError:
            return "Usage: `unstar <n>`  e.g. `unstar 2`"

        sb = self._get_supabase()
        if not sb:
            return "Supabase not available."

        rows = sb.get_starred()
        if not rows:
            return "*Starred list is empty.*"
        if rank < 1 or rank > len(rows):
            return f"#{rank} not found. Send `starredlist` to see current items."

        candidate_id = rows[rank - 1]["id"]
        if sb.unstar_candidate(candidate_id):
            row = rows[rank - 1]
            return (
                f"↩ *Unstarred #{rank}*\n"
                f"`{row.get('ticker')} ${row.get('strike')} {row.get('expiry')}`\n\n"
                f"_Moved back to pending._"
            )
        return "Failed to unstar. Try again."

    def _handle_approve(self, chat_id: str, parts: list) -> str:
        """approve <n> — approve item #n from starredlist."""
        try:
            rank = int(parts[1])
        except ValueError:
            return "Usage: `approve <n>`  e.g. `approve 2`"

        sb = self._get_supabase()
        if not sb:
            return "Supabase not available."

        rows = sb.get_starred()
        if not rows:
            return "*Starred list is empty.*\n\nSend `starredlist` to check."
        if rank < 1 or rank > len(rows):
            return f"#{rank} not found in starred list. Send `starredlist` to see current items."

        candidate_id = rows[rank - 1]["id"]
        row          = rows[rank - 1]

        if sb.approve_candidate(candidate_id):
            t_label = "CC" if "CALL" in str(row.get("strategy", "")).upper() else "CSP"
            return (
                f"✅ *Approved #{rank}*\n\n"
                f"`{row.get('ticker')} {t_label} ${row.get('strike')} "
                f"exp {row.get('expiry')}`\n\n"
                f"_Decision made. Place order in IBKR when ready._\n"
                f"_Then send `placed <n>` from `approvedlist`._"
            )
        return "Failed to approve. Try again."

    def _handle_placed(self, chat_id: str, parts: list) -> str:
        """placed <n> [HH:MM] — confirm order placed for item #n from approvedlist."""
        try:
            rank = int(parts[1])
        except ValueError:
            return "Usage: `placed <n>`  or  `placed <n> 14:35`"

        # Optional time argument
        placed_at = None
        if len(parts) == 3:
            try:
                h, m     = parts[2].split(":")
                now      = datetime.now()
                placed_at = now.replace(hour=int(h), minute=int(m), second=0, microsecond=0)
            except Exception:
                return "Invalid time format. Use HH:MM e.g. `placed 1 14:35`"

        sb = self._get_supabase()
        if not sb:
            return "Supabase not available."

        rows = sb.get_approved()
        if not rows:
            return "*Approved list is empty.*\n\nSend `approvedlist` to check."
        if rank < 1 or rank > len(rows):
            return f"#{rank} not found in approved list. Send `approvedlist` to see current items."

        row          = rows[rank - 1]
        candidate_id = row["id"]
        ticker       = row.get("ticker", "")
        scan_premium = row.get("premium")   # option premium from scan (per share)

        # entry_price for options = the OPTION premium fill (per share, e.g. $1.25)
        # We cannot fetch live option prices from Yahoo — pass None so
        # place_candidate() uses the scan premium as the best estimate.
        # Ken updates the actual fill manually in TOS if it differs.
        ok = sb.place_candidate(candidate_id, entry_price=None, placed_at=placed_at)
        if ok:
            t_label      = "CC" if "CALL" in str(row.get("strategy", "")).upper() else "CSP"
            contracts    = int(row.get("contracts") or 1)
            scan_prem    = float(scan_premium) if scan_premium else None
            net_est      = round(scan_prem * 100 * contracts, 2) if scan_prem else None
            prem_str     = f"${scan_prem:.4f}/share  (~${net_est:.2f} total)" if scan_prem else "unknown — update manually"
            time_str     = (placed_at or datetime.now()).strftime("%H:%M")
            return (
                f"🚀 *Placed #{rank}*\n\n"
                f"`{ticker} {t_label} ${row.get('strike')} exp {row.get('expiry')}`\n\n"
                f"Scan premium : {prem_str}\n"
                f"Time logged  : {time_str}\n\n"
                f"_Entry price = scan estimate. Update actual fill in TOS if different._\n"
                f"_Send `placedlist` to see all open trades._"
            )
        return "Failed to log placed trade. Try again."

    def _handle_reject(self, chat_id: str, parts: list) -> str:
        """reject <n> — reject item #n from starredlist or approvedlist (starred first)."""
        try:
            rank = int(parts[1])
        except ValueError:
            return "Usage: `reject <n>`  e.g. `reject 2`"

        sb = self._get_supabase()
        if not sb:
            return "Supabase not available."

        # Try starred first, then approved
        rows   = sb.get_starred()
        source = "starred"
        if rank > len(rows):
            rows   = sb.get_approved()
            source = "approved"

        if not rows:
            return "*No starred or approved candidates to reject.*"
        if rank < 1 or rank > len(rows):
            return f"#{rank} not found. Send `starredlist` or `approvedlist` to check."

        row          = rows[rank - 1]
        candidate_id = row["id"]

        if sb.reject_candidate(candidate_id):
            t_label = "CC" if "CALL" in str(row.get("strategy", "")).upper() else "CSP"
            return (
                f"❌ *Rejected #{rank}* (from {source} list)\n\n"
                f"`{row.get('ticker')} {t_label} ${row.get('strike')} "
                f"exp {row.get('expiry')}`\n\n"
                f"_Removed from workflow._"
            )
        return "Failed to reject. Try again."

    def _handle_list(self, status: str) -> str:
        """Build starredlist / approvedlist / placedlist reply."""
        sb = self._get_supabase()
        if not sb:
            return "Supabase not available — cannot fetch list."

        if status == "starred":
            rows       = sb.get_starred()
            title      = "Starred Candidates"
            hint       = "approve <n> to approve  |  unstar <n> to remove  |  reject <n> to reject"
        elif status == "approved":
            rows       = sb.get_approved()
            title      = "Approved Candidates"
            hint       = "placed <n> to confirm order placed  |  reject <n> to reject"
        else:
            rows       = sb.get_placed()
            title      = "Placed Trades"
            hint       = "Trades logged to TOS. Update entry price manually if needed."

        return _format_candidate_list(rows, title, hint)

    # ── Bulk-clear commands ───────────────────────────────────────────────

    def _handle_clear_list(self, which: str) -> str:
        """
        /clearstarred  → rejected   (candidate didn't make it to a trade)
        /clearapproved → rejected   (same)
        /clearplaced   → archived   (trade already in portfolio; just clear workflow view)

        NEVER touches scan_history or trade_log.
        """
        sb = self._get_supabase()
        if not sb:
            return "Supabase not available."

        if which == "starred":
            from_status = "starred"
            to_status   = "rejected"
            label       = "Starred"
            note        = "All starred candidates rejected — removed from starred list.\n_Scan history and portfolio unchanged._"
        elif which == "approved":
            from_status = "approved"
            to_status   = "rejected"
            label       = "Approved"
            note        = "All approved candidates rejected — removed from approved list.\n_Scan history and portfolio unchanged._"
        elif which == "placed":
            from_status = "placed"
            to_status   = "archived"
            label       = "Placed"
            note        = (
                "Placed list cleared — entries archived in candidate DB.\n"
                "_All trade records in your Portfolio (trade\\_log) are fully preserved._"
            )
        else:
            return "Unknown list. Use `clearstarred`, `clearapproved`, or `clearplaced`."

        count = sb.clear_by_status(from_status, to_status)
        if count < 0:
            return f"Failed to clear {label} list. Try again."
        if count == 0:
            return f"*{label} list is already empty.* Nothing to clear."
        return f"🗑 *{label} list cleared ({count} item(s)).*\n\n{note}"

    # ── Portfolio commands ────────────────────────────────────────────────

    def _handle_portfolio(self) -> str:
        """Show all open (not yet closed) trades from trade_log."""
        sb = self._get_supabase()
        if not sb:
            return "Supabase not available."

        trades = sb.get_portfolio()
        if not trades:
            return (
                "*📌 Portfolio — Open Trades*\n\n"
                "_No open trades yet._\n\n"
                "Use `placed <n>` after approving a candidate to log a new trade."
            )

        lines = [f"*📌 Portfolio — {len(trades)} Open Trade(s)*\n", "```"]
        lines.append(
            f"{'#':<3} {'Date':<7} {'Ticker':<6} {'T':<3} "
            f"{'Strike':>7} {'Expiry':<10} {'Fill':>6} {'Net$':>7}"
        )
        lines.append("-" * 58)
        for i, t in enumerate(trades, 1):
            try:
                date_str = datetime.fromisoformat(
                    str(t.get("trade_date", "")).replace("Z", "")
                ).strftime("%d-%b")
            except Exception:
                date_str = str(t.get("trade_date", "?"))[:6]

            ticker = str(t.get("ticker", "?"))[:6]
            strat  = t.get("strategy", "")
            t_lbl  = "CC" if "CALL" in strat.upper() else "CP"
            strike = float(t.get("strike") or 0)
            expiry = str(t.get("expiry") or "?")
            fill   = t.get("entry_price")
            net    = t.get("net_premium")
            fill_s = f"${float(fill):.2f}" if fill is not None else "  ?"
            net_s  = f"${float(net):.0f}"  if net  is not None else "    ?"

            lines.append(
                f"{i:<3} {date_str:<7} {ticker:<6} {t_lbl:<3} "
                f"${strike:>6.1f} {expiry:<10} "
                f"{fill_s:>6} {net_s:>7}"
            )
        lines.append("```")
        lines.append("\n`trade <n>` for full detail on any trade")
        return "\n".join(lines)

    def _handle_trade_detail(self, rank: int) -> str:
        """Show full detail card for open trade #rank from portfolio."""
        sb = self._get_supabase()
        if not sb:
            return "Supabase not available."

        trades = sb.get_portfolio()
        if not trades:
            return "*No open trades in portfolio.*"
        if rank < 1 or rank > len(trades):
            return f"Trade #{rank} not found. Send `portfolio` to see current trades ({len(trades)} total)."

        t = trades[rank - 1]
        strat   = t.get("strategy", "")
        t_full  = "Covered Call"   if "CALL" in strat.upper() else "Cash-Secured Put"
        t_short = "CC"             if "CALL" in strat.upper() else "CSP"
        ticker  = t.get("ticker", "?")
        strike  = float(t.get("strike") or 0)
        expiry  = str(t.get("expiry") or "?")
        dte_e   = t.get("dte_at_entry")
        fill    = t.get("entry_price")
        contr   = int(t.get("contracts") or 1)
        net     = t.get("net_premium")
        delta   = t.get("entry_delta")
        iv_p    = t.get("iv_percentile")
        t_date  = str(t.get("trade_date", "?"))
        trade_id = str(t.get("id", ""))[:8]

        fill_s = f"${float(fill):.4f}/share"   if fill is not None else "not recorded"
        net_s  = f"${float(net):.2f} total"    if net  is not None else "not recorded"
        dte_s  = str(dte_e)                    if dte_e is not None else "?"
        dlt_s  = f"{float(delta):.3f}"         if delta is not None else "?"
        iv_s   = f"{float(iv_p):.0f}%"         if iv_p  is not None else "?"

        lines = [
            f"*📌 Trade #{rank} — {ticker} {t_short}*\n",
            f"Ticker     : `{ticker}`  ({t_full})",
            f"Strike     : `${strike:.2f}`",
            f"Expiry     : `{expiry}` ({dte_s} DTE at entry)",
            f"Trade date : `{t_date}`",
            f"",
            f"Option fill: `{fill_s}`",
            f"Contracts  : `{contr}`",
            f"Net premium: `{net_s}`   _(total credit received)_",
            f"",
            f"Delta      : `{dlt_s}`",
            f"IV%tile    : `{iv_s}`",
            f"",
            f"Status     : Open _(exit\\_date not set)_",
            f"Trade ID   : `{trade_id}...`",
            f"",
            f"_To close: update exit\\_date, exit\\_price, pnl directly in Supabase or TOS._",
        ]
        return "\n".join(lines)

    # ── Config helpers ────────────────────────────────────────────────────

    # ── Inline keyboard callback handler ──────────────────────────────────

    def _handle_callback(self, cb: dict):
        """Handle inline keyboard button presses."""
        cb_id   = cb.get("id", "")
        data    = cb.get("data", "")
        chat_id = str(cb.get("message", {}).get("chat", {}).get("id", ""))

        # Must always answer the callback to dismiss the button spinner
        self._answer_callback(cb_id)

        if not chat_id or (self._allowed_ids and chat_id not in self._allowed_ids):
            return
        is_admin = (chat_id == self.chat_id) if self.chat_id else True

        # Admin-only callback buttons
        ADMIN_CALLBACKS = {
            "cb_stopscan", "cb_cancelscan", "cb_stopbot",
            "cb_clearstarred", "cb_clearapproved", "cb_clearplaced",
        }
        if data in ADMIN_CALLBACKS and not is_admin:
            self._send(chat_id, "🔒 This action is admin-only.")
            return

        def _scan_with_strategy(strategy):
            if self.state and self.state.is_running():
                self._send(chat_id,
                    "A scan is *already in progress.*\n\nSend `cancelscan` to stop it.")
                return
            if self.state:
                self.state.request_scan(tickers=None, strategy=strategy)
            wl = self.state.get_watchlist() if self.state else DEFAULT_WATCHLIST
            wl_str = ", ".join(f"`{t}`" for t in wl)
            label = {"cc": "Covered Calls", "csp": "Cash-Secured Puts"}.get(
                strategy or "", "Full (CC + CSP)"
            )
            self._send(chat_id, f"*{label} scan requested!*\nScanning: {wl_str}")

        # ── Scan actions ──────────────────────────────────────────────────
        if data == "cb_scan_full":
            _scan_with_strategy(None)
        elif data == "cb_scan_cc":
            _scan_with_strategy("cc")
        elif data == "cb_scan_csp":
            _scan_with_strategy("csp")
        elif data == "cb_scan_other":
            self._send(chat_id,
                "*Custom Ticker Scan*\n\n"
                "Type one of these commands:\n"
                "`scan TSLA NVDA AMD` — CC + SCP\n"
                "`scan TSLA CC` — covered calls only\n"
                "`scan TSLA NVDA CSP` — cash-secured puts only\n\n"
                "_You can mix any US stock tickers._"
            )

        # ── Watchlist / Schedule ──────────────────────────────────────────
        elif data == "cb_watchlist":
            self._send(chat_id, self._handle_watchlist())
        elif data == "cb_schedule":
            self._send(chat_id, self._handle_scanschedule())

        # ── Results ───────────────────────────────────────────────────────
        elif data == "cb_lastscan":
            self._send(chat_id, self._build_lastscan_reply())
        elif data == "cb_fullresult":
            self._results_current_page = 1
            self._send(chat_id, self._build_results_page_reply(1))
        elif data == "cb_starred":
            self._send(chat_id, self._handle_list("starred"))
        elif data == "cb_approved":
            self._send(chat_id, self._handle_list("approved"))
        elif data == "cb_placed":
            self._send(chat_id, self._handle_list("placed"))
        elif data == "cb_portfolio":
            self._send(chat_id, self._handle_portfolio())
        elif data == "cb_clearstarred":
            self._send(chat_id, self._handle_clear_list("starred"))
        elif data == "cb_clearapproved":
            self._send(chat_id, self._handle_clear_list("approved"))
        elif data == "cb_clearplaced":
            self._send(chat_id, self._handle_clear_list("placed"))

        # ── Config / Score ────────────────────────────────────────────────
        elif data == "cb_config":
            self._send(chat_id, self._build_config_reply())
        elif data == "cb_score":
            self._send(chat_id, get_score_explanation())

        # ── Market ────────────────────────────────────────────────────────
        elif data == "cb_health":
            self._send(chat_id, "Running health checks...")
            self._send(chat_id, self._handle_health())
        elif data == "cb_movers":
            self._send(chat_id, "Fetching top movers...")
            self._send(chat_id, get_top_movers())

        # ── System controls ───────────────────────────────────────────────
        elif data == "cb_stopscan":
            if self.state is None:
                self._send(chat_id, "Scanner not available.")
            elif not self.state.is_enabled():
                self._send(chat_id, "Scheduler is *already paused.*")
            else:
                self.state.disable_scheduler()
                self._send(chat_id,
                    "*Scheduled scanner paused.*\n"
                    "Manual `scan` commands still work.\n"
                    "_Restart the bot to re-enable auto-scan._"
                )
        elif data == "cb_cancelscan":
            if self.state is None:
                self._send(chat_id, "Scanner not available.")
            elif not self.state.is_running():
                self._send(chat_id, "No scan is currently running.")
            elif self.state.is_cancel_requested():
                self.state.force_reset()
                self._send(chat_id,
                    "*Force reset applied.*\n"
                    "Stuck scan cleared — send `scan` to start a fresh scan."
                )
            else:
                self.state.request_cancel()
                self._send(chat_id, "*Cancel requested.*\nStopping at next batch (~5-10 sec).")
        elif data == "cb_stopbot":
            self._stopbot_pending      = True
            self._stopbot_pending_time = time.time()
            self._send(chat_id,
                "🛑 *Stop Bot Requested*\n\n"
                "Type the password to confirm shutdown:\n"
                "_Wrong password or no reply in 60s = bot stays running._"
            )

        # ── Help ─────────────────────────────────────────────────────────────
        elif data == "cb_help":
            # Help text exceeds Telegram's 4096 limit — use _send_long()
            self._send_long(chat_id, get_help())

        # ── Menu navigation ───────────────────────────────────────────────
        elif data.startswith("cb_menu_"):
            self._send_category_menu(chat_id, data[8:])
        elif data == "cb_menu":
            self._send_category_menu(chat_id)
        elif data == "cb_noop":
            pass   # separator button — do nothing
        else:
            log.debug("Unknown callback data: %s", data)

    def _send_category_menu(self, chat_id: str, category: str = ""):
        """Send the interactive inline keyboard for a given category.
        Empty category = top-level main menu."""

        # ── Top-level main menu ───────────────────────────────────────────
        if not category:
            self._send_with_keyboard(
                chat_id,
                "*OptionBot Menu* — tap a category:",
                [
                    [
                        {"text": "📊 Scan",     "callback_data": "cb_menu_scan"},
                        {"text": "📈 Results",  "callback_data": "cb_menu_results"},
                    ],
                    [
                        {"text": "⚙️ Config",   "callback_data": "cb_menu_config"},
                        {"text": "🤖 AI Chat",  "callback_data": "cb_menu_ai"},
                    ],
                    [
                        {"text": "🌐 Market",   "callback_data": "cb_menu_market"},
                        {"text": "🔧 System",   "callback_data": "cb_menu_system"},
                    ],
                    [
                        {"text": "❓ Help — all commands & usage guide", "callback_data": "cb_help"},
                    ],
                ],
            )
            return

        # ── 📊 Scan ───────────────────────────────────────────────────────
        if category == "scan":
            wl = self.state.get_watchlist() if self.state else DEFAULT_WATCHLIST
            wl_str = " ".join(wl[:5]) + ("…" if len(wl) > 5 else "")
            self._send_with_keyboard(
                chat_id,
                f"*📊 Scan*\nWatchlist: `{wl_str}`\n\nChoose scan type:",
                [
                    [{"text": "🔍 Full Scan (CC + CSP)",  "callback_data": "cb_scan_full"}],
                    [
                        {"text": "📈 Covered Calls Only", "callback_data": "cb_scan_cc"},
                        {"text": "📉 Cash-Sec Puts Only", "callback_data": "cb_scan_csp"},
                    ],
                    [{"text": "🔎 Other Tickers...",       "callback_data": "cb_scan_other"}],
                    [
                        {"text": "📋 Watchlist",          "callback_data": "cb_watchlist"},
                        {"text": "🕐 Schedule",           "callback_data": "cb_schedule"},
                    ],
                    [{"text": "« Back to Menu",            "callback_data": "cb_menu"}],
                ],
            )

        # ── 📈 Results ────────────────────────────────────────────────────
        elif category == "results":
            self._send_with_keyboard(
                chat_id,
                "*📈 Results*\nBrowse scan results and manage trade workflow:",
                [
                    [{"text": "📊 Last Scan Summary",          "callback_data": "cb_lastscan"}],
                    [{"text": "📃 Full Results",                "callback_data": "cb_fullresult"}],
                    [{"text": "─── Workflow Lists ───",        "callback_data": "cb_noop"}],
                    [
                        {"text": "⭐ Starred",                 "callback_data": "cb_starred"},
                        {"text": "✅ Approved",                "callback_data": "cb_approved"},
                    ],
                    [
                        {"text": "🗑 Clear Starred",           "callback_data": "cb_clearstarred"},
                        {"text": "🗑 Clear Approved",          "callback_data": "cb_clearapproved"},
                    ],
                    [{"text": "─── Portfolio ───",             "callback_data": "cb_noop"}],
                    [{"text": "📌 Open Portfolio",             "callback_data": "cb_portfolio"}],
                    [
                        {"text": "📋 Placed List",             "callback_data": "cb_placed"},
                        {"text": "🗑 Clear Placed List",       "callback_data": "cb_clearplaced"},
                    ],
                    [{"text": "« Back to Menu",                "callback_data": "cb_menu"}],
                ],
            )
            self._send(chat_id,
                "Workflow: `star 1` → `approve 1` → `placed 1`\n"
                "Detail: `detail 5` (scan result)  `trade 2` (portfolio trade)\n"
                "Pages: `page 2`, `page 3` ...  Clear = list view only, scan history & portfolio kept."
            )

        # ── ⚙️ Config ─────────────────────────────────────────────────────
        elif category == "config":
            self._send_with_keyboard(
                chat_id,
                "*⚙️ Config*\nView settings and scoring:",
                [
                    [{"text": "⚙️ Show Config & Filters", "callback_data": "cb_config"}],
                    [{"text": "📊 Score Explained",        "callback_data": "cb_score"}],
                    [
                        {"text": "📋 View Watchlist",     "callback_data": "cb_watchlist"},
                        {"text": "🕐 View Schedule",      "callback_data": "cb_schedule"},
                    ],
                    [{"text": "« Back to Menu",            "callback_data": "cb_menu"}],
                ],
            )
            self._send(chat_id,
                "To change settings, type:\n"
                "`setwatchlist AAPL TSLA NVDA` — update watchlist\n"
                "`setscantime 09:35 13:00 15:00` — update scan times\n"
                "`set min_iv 0.40` — adjust any scan filter\n"
                "`set reset` — clear all overrides"
            )

        # ── 🤖 AI Chat ────────────────────────────────────────────────────
        elif category == "ai":
            self._send(
                chat_id,
                "*🤖 AI Chat*\n\n"
                "Ask any options or finance question:\n\n"
                "`askclaude <question>` — Claude AI (Anthropic)\n"
                "`askllama <question>` — Llama AI (OpenRouter)\n\n"
                "Examples:\n"
                "  `askclaude when should I roll a covered call`\n"
                "  `askclaude what is theta decay`\n"
                "  `askllama explain the wheel strategy`\n"
                "  `askllama what does IV rank 80 mean`\n\n"
                "_Note: text only — photo/document upload is not supported in AI chat._",
            )

        # ── 🌐 Market ─────────────────────────────────────────────────────
        elif category == "market":
            self._send_with_keyboard(
                chat_id,
                "*🌐 Market Data*\nLive prices and movers:",
                [
                    [{"text": "📊 Top Movers (stocks, crypto, indices)", "callback_data": "cb_movers"}],
                    [{"text": "« Back to Menu", "callback_data": "cb_menu"}],
                ],
            )
            self._send(chat_id,
                "For a specific price quote, type:\n"
                "`price SPY`  `price TSLA`  `price BTC`  `price GOLD`"
            )

        # ── 🔧 System ─────────────────────────────────────────────────────
        elif category == "system":
            self._send_with_keyboard(
                chat_id,
                "*🔧 System*\nBot controls and health:",
                [
                    [{"text": "❤️ Health Check",          "callback_data": "cb_health"}],
                    [
                        {"text": "⏸ Pause Auto-Scan",    "callback_data": "cb_stopscan"},
                        {"text": "❌ Cancel Running Scan","callback_data": "cb_cancelscan"},
                    ],
                    [{"text": "🛑 Stop Bot (password)",   "callback_data": "cb_stopbot"}],
                    [{"text": "« Back to Menu",            "callback_data": "cb_menu"}],
                ],
            )

    # ── Watchlist management ───────────────────────────────────────────────

    def _handle_setwatchlist(self, parts: list) -> str:
        if self.state is None:
            return "Scanner not available."
        if len(parts) == 1:
            # No args — show current watchlist
            return self._handle_watchlist()
        if len(parts) == 2 and parts[1].lower() == "reset":
            self.state.set_watchlist(list(DEFAULT_WATCHLIST))
            wl_str = " ".join(DEFAULT_WATCHLIST)
            return (
                "*Watchlist reset to defaults.*\n\n"
                f"`{wl_str}`"
            )
        tickers = [p.upper() for p in parts[1:]]
        valid, invalid = _validate_tickers(tickers)
        if not valid:
            inv_str = ", ".join(f"`{t}`" for t in invalid)
            return f"No valid tickers found.\nUnknown: {inv_str}"
        self.state.set_watchlist(valid)
        msg = f"*Watchlist updated! ({len(valid)} tickers)*\n`{' '.join(valid)}`"
        if invalid:
            msg += f"\nSkipped unknown: {', '.join(f'`{t}`' for t in invalid)}"
        return msg

    def _handle_watchlist(self) -> str:
        if self.state is None:
            return "Scanner not available."
        wl = self.state.get_watchlist()
        return (
            f"*Current watchlist ({len(wl)} tickers):*\n"
            f"`{' '.join(wl)}`\n\n"
            "To change: `setwatchlist AAPL TSLA NVDA`\n"
            "To reset:  `setwatchlist reset`"
        )

    # ── Scan schedule management ───────────────────────────────────────────

    _DEFAULT_SLOTS = [( 9, 35, "Open"), (12, 45, "Midday"), (15,  0, "Pre-Close")]

    def _handle_setscantime(self, parts: list) -> str:
        if self.state is None:
            return "Scanner not available."
        if len(parts) == 1:
            # No args — show current schedule
            return self._handle_scanschedule()
        if len(parts) == 2 and parts[1].lower() == "reset":
            self.state.set_scan_slots(list(self._DEFAULT_SLOTS))
            slots_str = "  ".join(
                f"{h:02d}:{m:02d} [{lbl}]" for h, m, lbl in self._DEFAULT_SLOTS
            )
            return (
                "*Scan schedule reset to defaults.*\n\n"
                f"`{slots_str}`"
            )
        LABELS = ["Open", "Midday", "Pre-Close", "Slot4", "Slot5", "Slot6"]
        new_slots = []
        errors    = []
        for i, ts in enumerate(parts[1:]):
            try:
                h_str, m_str = ts.split(":")
                h, m = int(h_str), int(m_str)
                if not (0 <= h <= 23 and 0 <= m <= 59):
                    raise ValueError
                label = LABELS[i] if i < len(LABELS) else f"Slot{i + 1}"
                new_slots.append((h, m, label))
            except (ValueError, AttributeError):
                errors.append(f"`{ts}`")
        if errors:
            return (
                f"Invalid time(s): {', '.join(errors)}\n"
                "Format: `setscantime 09:35 13:00 15:00` (24h HH:MM, ET)"
            )
        if not new_slots:
            return "No valid times.\nFormat: `setscantime 09:35 13:00 15:00`"
        self.state.set_scan_slots(new_slots)
        slots_str = "  ".join(f"{h:02d}:{m:02d} [{lbl}]" for h, m, lbl in new_slots)
        return (
            f"*Scan schedule updated! ({len(new_slots)} slot(s), ET)*\n"
            f"`{slots_str}`\n\n"
            "_New schedule takes effect immediately._"
        )

    def _handle_scanschedule(self) -> str:
        if self.state is None:
            return "Scanner not available."
        slots = self.state.get_scan_slots()
        if not slots:
            return (
                "*No scan slots configured.*\n"
                "Send `setscantime 09:35 13:00 15:00` to add slots."
            )
        lines = [f"*Auto-scan schedule ({len(slots)} slot(s), ET):*\n"]
        for h, m, lbl in slots:
            lines.append(f"  `{h:02d}:{m:02d}` — {lbl}")
        lines.append("\nTo change: `setscantime 09:35 13:00 15:00`")
        lines.append("To reset:  `setscantime reset`")
        return "\n".join(lines)

    def _build_config_reply(self) -> str:
        from core.config import ScannerConfig
        defaults = ScannerConfig()

        # Bot-level params that live in overrides only (not in ScannerConfig).
        BOT_PARAMS = {
            "autostar_threshold": 75.0,
        }

        lines = ["```"]
        lines.append("Current Scan Config")
        lines.append("")
        lines.append("%-18s %10s %10s" % ("Parameter", "Default", "Override"))
        lines.append("-" * 42)

        for param, (attr, typ, desc) in SETTABLE_PARAMS.items():
            if attr in BOT_PARAMS:
                default_val = BOT_PARAMS[attr]
            else:
                default_val = getattr(defaults, attr)
            override_val = self._config_overrides.get(attr, "-")
            lines.append("%-18s %10s %10s" % (param, str(default_val), str(override_val)))

        lines.append("")
        lines.append("-" * 42)
        lines.append("PARAMETER GUIDE")
        lines.append("")
        lines.append("min_dte        min days to expiry (too short = high gamma risk)")
        lines.append("max_dte        max days to expiry (too long = capital locked)")
        lines.append("strike_pct     strike range +/-% from price (0.20 = 20%)")
        lines.append("min_premium    min credit $ per contract to qualify")
        lines.append("min_ann_return min annualised return (0.05 = 5%)")
        lines.append("min_theta      min daily theta $ (time decay income)")
        lines.append("min_iv_rank    IV rank 0-100 (needs IBKR history, 0=off)")
        lines.append("min_iv         raw IV floor (0.40=40%, always works, 0=off)")
        lines.append("cc_delta_min   CC min delta (higher = more premium, more risk)")
        lines.append("cc_delta_max   CC max delta (0.30 = ~30% chance ITM)")
        lines.append("csp_delta_min  CSP min delta (e.g. -0.35)")
        lines.append("csp_delta_max  CSP max delta (e.g. -0.20)")
        lines.append("min_oi         min open interest (keep 0, delayed data = 0)")
        lines.append("max_spread     max bid/ask spread % (1.0 = 100%)")
        lines.append("strategy       both / cc / csp")
        lines.append("autostar       auto-star score threshold (0=off, 80=auto)")
        lines.append("data_source    yahoo (free/no login) or ibkr (needs Gateway)")
        lines.append("")
        lines.append("MEAN REVERSION")
        lines.append("use_mean_reversion  true/false (enable 6th scoring factor)")
        lines.append("weight_mr      MR weight in composite (default 0.15)")
        lines.append("mr_rsi_period  RSI lookback (default 5, research optimal)")
        lines.append("mr_z_period    Z-Score lookback (default 20)")
        lines.append("mr_roc_period  ROC %Rank lookback (default 100)")
        lines.append("mr_w_rsi       RSI sub-weight (default 0.40)")
        lines.append("mr_w_z         Z-Score sub-weight (default 0.40)")
        lines.append("mr_w_roc       ROC sub-weight (default 0.20)")
        lines.append("mr_trend_guard true/false (cap score in strong trends)")
        lines.append("mr_trend_pct   trend guard % from SMA200 (default 15)")
        lines.append("")
        lines.append("-" * 42)
        lines.append("To change: set <param> <value>")
        lines.append("Multiple:  set min_iv_rank 0 min_iv 0.40")
        lines.append("set reset  clear all overrides")
        lines.append("Overrides are permanent until set reset is sent")

        # Show current watchlist and scan schedule
        if self.state is not None:
            lines.append("")
            lines.append("-" * 42)
            wl = self.state.get_watchlist()
            lines.append(f"Watchlist ({len(wl)}):  {' '.join(wl)}")
            lines.append("  setwatchlist AAPL TSLA ...  to change")
            slots = self.state.get_scan_slots()
            slots_str = "  ".join(f"{h:02d}:{m:02d}[{lbl}]" for h, m, lbl in slots)
            lines.append(f"Auto-scan (ET):  {slots_str}")
            lines.append("  setscantime 09:35 13:00 15:00  to change")

        lines.append("```")

        return "\n".join(lines)

    def _handle_set(self, parts: list, raw_text: str = "") -> str:
        # ── Special redirects: /set watchlist and /set scantime ───────────
        # User may type /set watchlist AAPL TSLA instead of /setwatchlist
        if len(parts) >= 2 and parts[1].lower() in ("watchlist", "setwatchlist"):
            return self._handle_setwatchlist(["setwatchlist"] + parts[2:])
        if len(parts) >= 2 and parts[1].lower() in ("scantime", "setscantime", "schedule"):
            return self._handle_setscantime(["setscantime"] + parts[2:])

        # ── set reset ─────────────────────────────────────────────────────
        if len(parts) == 2 and parts[1].lower() == "reset":
            self._config_overrides.clear()
            return (
                "*All config overrides cleared.*\n"
                "All settings restored to defaults for next scan."
            )

        if len(parts) < 3:
            return (
                "Usage: `set <param> <value>`\n"
                "Multiple same line: `set min_iv_rank 0 min_iv 0.40`\n"
                "Multiple lines also works.\n"
                "Send `config` to see parameter names."
            )

        # ── Build token pairs — supports both formats: ────────────────────
        # Single line:  set param1 val1 param2 val2
        # Multi-line:   set param1 val1\nset param2 val2\nset param3 val3
        # Strategy: collect all (param, value) pairs from all lines.
        pairs = []   # list of (param_str, value_str)

        if raw_text:
            for line in raw_text.splitlines():
                line = line.strip()
                if not line:
                    continue
                line_parts = line.split()
                # Each line may start with "set" or just be "param value"
                tokens = line_parts[1:] if line_parts[0].lower() == "set" else line_parts
                if len(tokens) == 0:
                    continue
                if len(tokens) % 2 != 0:
                    # Odd tokens on this line — report and skip line
                    pairs.append((tokens[0], None))   # None value = error
                    continue
                for i in range(0, len(tokens), 2):
                    pairs.append((tokens[i], tokens[i + 1]))
        else:
            # Fallback: use parts as before
            tokens = parts[1:]
            if len(tokens) % 2 != 0:
                return (
                    "Each parameter needs a value.\n\n"
                    "Usage: `set <param> <value>`\n"
                    "Multiple: `set min_iv_rank 0 min_iv 0.40`\n"
                    "Send `config` to see all parameter names."
                )
            for i in range(0, len(tokens), 2):
                pairs.append((tokens[i], tokens[i + 1]))

        updated = []    # list of (param, value, desc)
        errors  = []    # list of error strings

        for param, raw_value in pairs:
            param = param.lower()
            if raw_value is None:
                errors.append(f"`{param}` -- missing value")
                continue

            if param not in SETTABLE_PARAMS:
                errors.append(f"`{param}` -- unknown parameter")
                continue

            attr, typ, desc = SETTABLE_PARAMS[param]

            try:
                if typ == bool:
                    if raw_value.lower() in ("true", "1", "on", "yes"):
                        value = True
                    elif raw_value.lower() in ("false", "0", "off", "no"):
                        value = False
                    else:
                        errors.append(f"`{param}` -- must be true/false (got `{raw_value}`)")
                        continue
                elif typ == int:
                    value = int(raw_value)
                elif typ == float:
                    value = float(raw_value)
                elif typ == str:
                    value = raw_value.lower()
                    if param == "strategy" and value not in ("cc", "csp", "both"):
                        errors.append("`strategy` must be `cc`, `csp`, or `both`")
                        continue
                    if param == "data_source" and value not in ("yahoo", "ibkr"):
                        errors.append("`data_source` must be `yahoo` or `ibkr`")
                        continue
                else:
                    value = raw_value
            except ValueError:
                errors.append(
                    f"`{param}` -- invalid value `{raw_value}` (expected {typ.__name__})"
                )
                continue

            self._config_overrides[attr] = value
            log.info("Config override: %s = %s", attr, value)
            updated.append((param, value, desc))

        # ── Build reply ───────────────────────────────────────────────────
        lines = []

        if updated:
            # Everything inside ONE code block — avoids Telegram Markdown parse errors
            lines.append("```")
            lines.append("Config updated")
            lines.append("")
            lines.append("%-18s %12s" % ("Parameter", "New Value"))
            lines.append("-" * 32)
            for param, value, desc in updated:
                lines.append(f"{param:<18} {str(value):>12}")

            notes = []
            for param, value, _ in updated:
                if param == "min_iv_rank":
                    if value == 0:
                        notes.append("IV Rank disabled -- pair with min_iv as gate.")
                    elif value < 30:
                        notes.append(f"IV Rank {value} below 30 -- cheap premium, use carefully.")
                    elif value >= 50:
                        notes.append(f"IV Rank {value} -- high-vol only, fewer signals.")
                elif param == "min_iv":
                    if value == 0:
                        notes.append("Raw IV filter disabled -- no quality gate active.")
                    elif value < 0.30:
                        notes.append(f"IV {value*100:.0f}% is low -- thin-premium trades may appear.")
                    elif value >= 0.50:
                        notes.append(f"IV {value*100:.0f}% -- high-vol contracts only. Good for TSLA.")
                    else:
                        notes.append(f"Raw IV floor: {value*100:.0f}%. Below this IV = rejected.")
                elif param == "data_source":
                    if value == "yahoo":
                        notes.append("Data source: Yahoo Finance. No IBKR needed.")
                        notes.append("15-min delayed data. Bot runs 24/7 without login.")
                    else:
                        notes.append("Data source: IBKR. IB Gateway must be open + logged in.")
                        notes.append("Phone login will kick the session. Keep desktop Gateway open.")
                elif param == "min_oi" and value > 0:
                    notes.append("Warning: IBKR delayed data returns OI=0.")
                    notes.append("This may reject everything. Use: set min_oi 0")
                elif param == "autostar":
                    if value == 0:
                        notes.append("Auto-star disabled. Use star <n> manually.")
                    else:
                        notes.append(f"Score >= {value:.0f} will be auto-starred after scan.")

            if notes:
                lines.append("")
                for note in notes:
                    lines.append(f"  {note}")

            lines.append("")
            lines.append("Overrides permanent until: set reset")
            lines.append("Applies to next scan. Send: scan or config")
            lines.append("```")

        if errors:
            lines.append("```")
            lines.append("Errors:")
            for err in errors:
                lines.append(f"  {err.replace(chr(96), '')}")
            lines.append("```")

        return "\n".join(lines) if lines else "Nothing was updated."

    def _send_long(self, chat_id: str, text: str, use_markdown: bool = True):
        """
        Send a message that may exceed Telegram's 4096-char per-message limit.
        Splits at line boundaries, keeping ``` code-block fences correctly paired
        so each chunk is valid Markdown on its own.
        """
        LIMIT = 4000    # slightly under 4096 for safety
        if len(text) <= LIMIT:
            self._send(chat_id, text, use_markdown=use_markdown)
            return

        lines   = text.splitlines(keepends=True)
        chunk   = ""
        in_code = False   # tracks whether we are inside a ``` block

        for line in lines:
            # Would adding this line push us over the limit?
            if chunk and len(chunk) + len(line) > LIMIT:
                # Close any open code block before flushing
                send_chunk = (chunk.rstrip() + "\n```") if in_code else chunk
                self._send(chat_id, send_chunk, use_markdown=use_markdown)
                # Start the new chunk; reopen code block if we were inside one
                chunk = "```\n" if in_code else ""

            # Track fence transitions (``` opens or closes a code block)
            stripped = line.strip()
            if stripped == "```" or (stripped.startswith("```") and len(stripped) <= 6):
                in_code = not in_code

            chunk += line

        if chunk.strip():
            self._send(chat_id, chunk, use_markdown=use_markdown)

    def _send_with_keyboard(
        self, chat_id: str, text: str,
        keyboard: list, use_markdown: bool = True,
    ) -> bool:
        """
        Send a Telegram message with an inline keyboard.
        keyboard: list of rows; each row is a list of dicts:
          [{"text": "Label", "callback_data": "cb_key"}, ...]
        Falls back to plain _send() if the keyboard call fails.
        """
        url  = TELEGRAM_API.format(token=self.token, method="sendMessage")
        body = {
            "chat_id":                chat_id,
            "text":                   text,
            "disable_web_page_preview": True,
            "reply_markup":           json.dumps({"inline_keyboard": keyboard}),
        }
        if use_markdown:
            body["parse_mode"] = "Markdown"
        payload = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            url, data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read())
            if result.get("ok"):
                return True
            log.warning("send_with_keyboard not ok: %s", result)
        except Exception as e:
            log.error("send_with_keyboard error: %s", e)
        # Fallback — send without buttons
        return self._send(chat_id, text, use_markdown=use_markdown)

    def _answer_callback(self, callback_query_id: str, text: str = ""):
        """
        Acknowledge a Telegram callback_query (required to dismiss
        the loading spinner on the button).  Non-fatal if it fails.
        """
        url  = TELEGRAM_API.format(token=self.token, method="answerCallbackQuery")
        body = {"callback_query_id": callback_query_id}
        if text:
            body["text"] = text
        payload = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            url, data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                json.loads(resp.read())
        except Exception as e:
            log.warning("answerCallbackQuery error (non-fatal): %s", e)

    def _send(self, chat_id: str, text: str, use_markdown: bool = True) -> bool:
        """
        Send a Telegram message.
        If Markdown causes a 400 Bad Request, automatically retries as plain
        text so the message always gets delivered even if formatting breaks.
        """
        url = TELEGRAM_API.format(token=self.token, method="sendMessage")

        def _do_send(parse_mode):
            body = {"chat_id": chat_id, "text": text,
                    "disable_web_page_preview": True}
            if parse_mode:
                body["parse_mode"] = parse_mode
            payload = json.dumps(body).encode("utf-8")
            req = urllib.request.Request(
                url, data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read())

        try:
            result = _do_send("Markdown" if use_markdown else None)
            if result.get("ok"):
                return True
            # Telegram returned ok=false without raising — treat as failure
            log.warning("Telegram send not ok: %s", result)
            return False

        except urllib.error.HTTPError as e:
            if e.code == 400 and use_markdown:
                # Markdown parse error — retry as plain text
                log.warning("Markdown parse error (400) — retrying as plain text")
                try:
                    result = _do_send(None)
                    return result.get("ok", False)
                except Exception as e2:
                    log.error("Send error (plain text retry): %s", e2)
                    return False
            log.error("Send error HTTP %s: %s", e.code, e)
            return False
        except Exception as e:
            log.error("Send error: %s", e)
            return False


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s -- %(message)s",
        datefmt="%H:%M:%S",
    )
    from dotenv import load_dotenv
    load_dotenv()
    bot = TelegramBotListener()
    log.info("Bot listener running. Send /help in Telegram.")
    bot.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        bot.stop()
