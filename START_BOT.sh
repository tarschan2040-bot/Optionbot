#!/bin/bash
# ============================================================
# START_BOT.sh — Start the Sell Option Scanner Bot (Mac/Linux)
# ============================================================
# Usage:
#   Double-click this file in Finder (set executable first), or
#   run from Terminal:  bash START_BOT.sh
#
# To make executable (run once in Terminal):
#   chmod +x START_BOT.sh
#
# This is the Mac equivalent of START_BOT.bat on Windows.
# ============================================================

# Navigate to the folder where this script lives (the optionbot folder)
cd "$(dirname "$0")"

echo "============================================================"
echo "  Sell Option Scanner Bot — Starting..."
echo "  Folder: $(pwd)"
echo "  Python: $(python3 --version 2>&1)"
echo "============================================================"
echo ""

# Start the bot (runs in foreground — close this Terminal to stop)
python3 scheduler.py

echo ""
echo "Bot stopped."
