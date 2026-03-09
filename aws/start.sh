#!/bin/bash
# =============================================================================
# start.sh — Start the BRA server in the background
# Usage: ./start.sh
# =============================================================================

APP_DIR="/home/ubuntu/ibr_system_design"
VENV_DIR="$APP_DIR/venv"
LOG_DIR="$APP_DIR/logs"
PID_FILE="$APP_DIR/server.pid"

GREEN="\033[1;32m"
RED="\033[1;31m"
YELLOW="\033[1;33m"
NC="\033[0m"

info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# ── Check already running ─────────────────────────────────────────────────────
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p "$PID" > /dev/null 2>&1; then
        warn "Server is already running (PID $PID)."
        warn "Run ./stop.sh first if you want to restart."
        exit 0
    else
        rm -f "$PID_FILE"
    fi
fi

# ── Setup ─────────────────────────────────────────────────────────────────────
cd "$APP_DIR" || error "App directory not found: $APP_DIR"
mkdir -p "$LOG_DIR"

source "$VENV_DIR/bin/activate" || error "Virtualenv not found at $VENV_DIR"
set -a && source "$APP_DIR/.env" && set +a || error ".env file not found at $APP_DIR/.env"

# ── Start ─────────────────────────────────────────────────────────────────────
info "Starting BRA server..."

nohup uvicorn api.server:app \
    --host 0.0.0.0 \
    --port 8000 \
    > "$LOG_DIR/server.log" 2>&1 &

echo $! > "$PID_FILE"

sleep 2

# ── Verify ────────────────────────────────────────────────────────────────────
PID=$(cat "$PID_FILE")
if ps -p "$PID" > /dev/null 2>&1; then
    info "================================================================"
    info " Server started successfully!"
    info " PID     : $PID"
    info " Port    : 8000"
    info " Logs    : tail -f $LOG_DIR/server.log"
    info " Stop    : ./stop.sh"
    info "================================================================"
else
    error "Server failed to start. Check logs: $LOG_DIR/server.log"
fi
