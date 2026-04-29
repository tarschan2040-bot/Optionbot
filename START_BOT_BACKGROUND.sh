#!/bin/bash
# ============================================================
# START_BOT_BACKGROUND.sh — Run Bot Silently in Background
# ============================================================
# Mac equivalent of START_BOT_MINIMIZED.vbs on Windows.
#
# HOW TO USE (from Terminal):
#   bash START_BOT_BACKGROUND.sh          — start in background
#   bash START_BOT_BACKGROUND.sh stop     — stop the running bot
#   bash START_BOT_BACKGROUND.sh status   — check if bot is running
#
# IMPORTANT: After running this script, the Terminal window
# will stay open — that is NORMAL. You can close it manually
# after you see "Bot started in background." The bot keeps
# running even after you close the Terminal.
#
# To make executable (run once):
#   chmod +x START_BOT_BACKGROUND.sh
# ============================================================

# Navigate to the folder where this script lives
cd "$(dirname "$0")"

PID_FILE="bot.pid"
LOG_FILE="bot.log"

# ── Auto-detect Python 3 ──────────────────────────────────────────────────
# Checks common Mac locations in order of preference
PYTHON=""
for candidate in python3.11 python3.10 python3.9 python3 python; do
    if command -v "$candidate" &>/dev/null; then
        ver=$("$candidate" --version 2>&1)
        if [[ "$ver" == *"Python 3"* ]]; then
            PYTHON=$(command -v "$candidate")
            break
        fi
    fi
done

# Also check common Mac install paths if not found yet
if [ -z "$PYTHON" ]; then
    for path in /usr/local/bin/python3 /opt/homebrew/bin/python3 /usr/bin/python3; do
        if [ -x "$path" ]; then
            PYTHON="$path"
            break
        fi
    done
fi

if [ -z "$PYTHON" ]; then
    echo "============================================================"
    echo "  ERROR: Python 3 not found!"
    echo ""
    echo "  Install Python 3 from: https://www.python.org/downloads/"
    echo "  Then run this script again."
    echo "============================================================"
    echo "Press Enter to close..."
    read
    exit 1
fi

# ── stop ──────────────────────────────────────────────────────────────────
if [ "$1" = "stop" ]; then
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if kill -0 "$PID" 2>/dev/null; then
            kill "$PID"
            rm -f "$PID_FILE"
            echo "Bot stopped (PID $PID)."
        else
            echo "Bot is not running (stale PID file)."
            rm -f "$PID_FILE"
        fi
    else
        echo "Bot is not running (no PID file found)."
    fi
    exit 0
fi

# ── status ────────────────────────────────────────────────────────────────
if [ "$1" = "status" ]; then
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if kill -0 "$PID" 2>/dev/null; then
            echo "Bot is RUNNING (PID $PID)."
        else
            echo "Bot is NOT running (stale PID file)."
        fi
    else
        echo "Bot is NOT running."
    fi
    exit 0
fi

# ── start ─────────────────────────────────────────────────────────────────
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        echo "Bot is already running (PID $PID)."
        echo "Use 'bash START_BOT_BACKGROUND.sh stop' to stop it first."
        exit 1
    fi
fi

echo "Starting bot in background..."
echo "  Python : $PYTHON ($($PYTHON --version 2>&1))"
echo "  Folder : $(pwd)"
echo "  Log    : $(pwd)/$LOG_FILE"
echo ""

nohup "$PYTHON" scheduler.py >> "$LOG_FILE" 2>&1 &
BOT_PID=$!
echo $BOT_PID > "$PID_FILE"

# Wait 3 seconds then check the log for a startup confirmation
sleep 3
if kill -0 "$BOT_PID" 2>/dev/null; then
    echo "============================================================"
    echo "  Bot started in background.  (PID: $BOT_PID)"
    echo ""
    echo "  You can now CLOSE THIS TERMINAL WINDOW."
    echo "  The bot will keep running after you close it."
    echo ""
    echo "  To watch logs : tail -f $(pwd)/$LOG_FILE"
    echo "  To stop bot   : bash START_BOT_BACKGROUND.sh stop"
    echo "  Or from Telegram: /stopbot (password: killbot)"
    echo "============================================================"
else
    echo "============================================================"
    echo "  ERROR: Bot failed to start!"
    echo ""
    echo "  Check the log for details:"
    echo "  $(pwd)/$LOG_FILE"
    echo ""
    tail -20 "$LOG_FILE" 2>/dev/null || echo "  (log file is empty)"
    echo "============================================================"
    rm -f "$PID_FILE"
    exit 1
fi
