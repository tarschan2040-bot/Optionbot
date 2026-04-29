"""
check_telegram.py — Quick Telegram connection test
===================================================
This file is completely self-contained.
Just run:  python check_telegram.py
"""

import os
import json
import urllib.request
from datetime import date, timedelta

# ── Step 1: Load your .env file manually ─────────────────────
def load_env():
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    if not os.path.exists(env_path):
        print("❌ ERROR: .env file not found!")
        print(f"   Expected location: {env_path}")
        print("   Make sure you copied .env.example to .env and filled in your credentials.")
        exit(1)

    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ[key.strip()] = value.strip()

load_env()

# ── Step 2: Read credentials ──────────────────────────────────
TOKEN   = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

if not TOKEN or TOKEN == "your_bot_token_here":
    print("❌ ERROR: TELEGRAM_BOT_TOKEN not set in your .env file")
    print("   Open .env and replace 'your_bot_token_here' with your actual bot token")
    exit(1)

if not CHAT_ID or CHAT_ID == "your_chat_id_here":
    print("❌ ERROR: TELEGRAM_CHAT_ID not set in your .env file")
    print("   Open .env and replace 'your_chat_id_here' with your actual chat ID")
    exit(1)

# ── Step 3: Send function ─────────────────────────────────────
def send_telegram(text):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = json.dumps({
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }).encode("utf-8")

    try:
        req = urllib.request.Request(
            url, data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read())
            return result.get("ok", False)
    except Exception as e:
        print(f"❌ Network error: {e}")
        return False

# ── Step 4: Run the tests ─────────────────────────────────────
if __name__ == "__main__":
    print()
    print("=" * 50)
    print("  Sell Option Scanner — Telegram Test")
    print("=" * 50)
    print(f"  Token  : {TOKEN[:10]}...{TOKEN[-5:]}")
    print(f"  Chat ID: {CHAT_ID}")
    print()

    # Test 1: basic connection test
    print("Test 1: Sending connection test message...")
    ok = send_telegram(
        "✅ *Connection test successful!*\n"
        "Your Sell Option Scanner is connected to Telegram.\n\n"
        "🤖 Bot is ready to send you daily option alerts!"
    )
    if ok:
        print("  ✅ PASSED — check your Telegram now!")
    else:
        print("  ❌ FAILED — check your token and chat ID in .env")
        exit(1)

    # Test 2: send a sample scan result card
    print()
    print("Test 2: Sending sample scan result...")
    ok = send_telegram(
        "📊 *Sample Scan Result* — This is what your daily alerts look like:\n\n"
        "```\n"
        "#  Ticker Type  Strike  DTE   Prem    Δ    IVR  Ann%  Score\n"
        "─────────────────────────────────────────────────────────\n"
        "1  NVDA   CSP  $780.0   21  $9.82 -0.28   72  116%   81.4\n"
        "2  TSLA   CC   $212.1   16  $9.03 +0.26   65  107%   78.8\n"
        "3  AMD    CSP  $158.2   16  $5.91 -0.27   55   81%   77.0\n"
        "```"
    )
    if ok:
        print("  ✅ PASSED — sample results sent!")
    else:
        print("  ❌ FAILED")
        exit(1)

    # Test 3: send a detailed opportunity card
    print()
    print("Test 3: Sending sample opportunity card...")
    expiry = (date.today() + timedelta(days=21)).strftime("%Y-%m-%d")
    ok = send_telegram(
        f"💰 *NVDA* — Cash-Secured Put\n\n"
        f"*Strike:* `$780.00`   *Expiry:* `{expiry}` (21 DTE)\n"
        f"*Premium:* `$9.82` per share  (`$982` per contract)\n\n"
        f"*Greeks*\n"
        f"  Delta: `-0.280`   Theta: `$0.180/day`\n"
        f"  IV: `55.0%`   IV Rank: `72/100`\n\n"
        f"*Returns*\n"
        f"  Annualised: `116.0%`\n"
        f"  Break-even: `$770.18`\n\n"
        f"🟢 *Score: 81.4/100*\n"
        f"`████████░░`"
    )
    if ok:
        print("  ✅ PASSED — opportunity card sent!")
    else:
        print("  ❌ FAILED")
        exit(1)

    print()
    print("=" * 50)
    print("  ALL TESTS PASSED! 🎉")
    print("  Your bot is ready. Run:  python scheduler.py --dry-run")
    print("=" * 50)
    print()
