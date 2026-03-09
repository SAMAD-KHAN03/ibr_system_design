#!/bin/bash
# =============================================================================
# stop.sh — Stop the BRA server
# Usage: ./stop.sh
# =============================================================================

APP_DIR="/home/ubuntu/ibr_system_design"
PID_FILE="$APP_DIR/server.pid"

GREEN="\033[1;32m"
RED="\033[1;31m"
YELLOW="\033[1;33m"
NC="\033[0m"

info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# ── Check PID file ────────────────────────────────────────────────────────────
if [ ! -f "$PID_FILE" ]; then
    warn "No PID file found. Server may not be running."
    # Try to kill by name as fallback
    if pkill -f "uvicorn api.server:app" 2>/dev/null; then
        info "Stopped leftover uvicorn process."
    else
        warn "No uvicorn process found either. Nothing to stop."
    fi
    exit 0
fi

PID=$(cat "$PID_FILE")

# ── Stop ──────────────────────────────────────────────────────────────────────
if ps -p "$PID" > /dev/null 2>&1; then
    info "Stopping BRA server (PID $PID)..."
    kill "$PID"

    # Wait up to 10 seconds for clean shutdown
    for i in $(seq 1 10); do
        if ! ps -p "$PID" > /dev/null 2>&1; then
            break
        fi
        sleep 1
    done

    # Force kill if still alive
    if ps -p "$PID" > /dev/null 2>&1; then
        warn "Process did not stop cleanly. Force killing..."
        kill -9 "$PID"
    fi

    rm -f "$PID_FILE"
    info "Server stopped."
else
    warn "PID $PID is not running. Cleaning up stale PID file."
    rm -f "$PID_FILE"
fi
