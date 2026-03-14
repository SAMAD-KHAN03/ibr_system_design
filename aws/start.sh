#!/bin/bash
# =============================================================================
# start.sh — Start the BRA server + Cloudflare tunnel in the background
# Usage: ./start.sh
# =============================================================================

APP_DIR="/home/ubuntu/ibr_system_design"
VENV_DIR="$APP_DIR/venv"
LOG_DIR="$APP_DIR/logs"

APP_PID_FILE="$APP_DIR/server.pid"
TUNNEL_PID_FILE="$APP_DIR/tunnel.pid"
TUNNEL_URL_FILE="$APP_DIR/tunnel_url.txt"

APP_PORT=8000

GREEN="\033[1;32m"
RED="\033[1;31m"
YELLOW="\033[1;33m"
NC="\033[0m"

info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# ── Cleanup stale PID files ───────────────────────────────────────────────────
cleanup_pid_file() {
    local pid_file="$1"
    if [ -f "$pid_file" ]; then
        local pid
        pid=$(cat "$pid_file")
        if ! ps -p "$pid" > /dev/null 2>&1; then
            rm -f "$pid_file"
        fi
    fi
}

cleanup_pid_file "$APP_PID_FILE"
cleanup_pid_file "$TUNNEL_PID_FILE"

# ── Check already running ─────────────────────────────────────────────────────
if [ -f "$APP_PID_FILE" ]; then
    APP_PID=$(cat "$APP_PID_FILE")
    if ps -p "$APP_PID" > /dev/null 2>&1; then
        warn "App server is already running (PID $APP_PID)."
        warn "Run ./stop.sh first if you want to restart."
        exit 0
    fi
fi

if [ -f "$TUNNEL_PID_FILE" ]; then
    TUNNEL_PID=$(cat "$TUNNEL_PID_FILE")
    if ps -p "$TUNNEL_PID" > /dev/null 2>&1; then
        warn "Tunnel is already running (PID $TUNNEL_PID)."
        warn "Run ./stop.sh first if you want to restart."
        exit 0
    fi
fi

# ── Setup ─────────────────────────────────────────────────────────────────────
cd "$APP_DIR" || error "App directory not found: $APP_DIR"
mkdir -p "$LOG_DIR"

source "$VENV_DIR/bin/activate" || error "Virtualenv not found at $VENV_DIR"
set -a && source "$APP_DIR/.env" && set +a || error ".env file not found at $APP_DIR/.env"

# ── Start FastAPI app ─────────────────────────────────────────────────────────
info "Starting BRA server on port $APP_PORT..."

nohup uvicorn api.server:app \
    --host 0.0.0.0 \
    --port "$APP_PORT" \
    > "$LOG_DIR/server.log" 2>&1 &

echo $! > "$APP_PID_FILE"

sleep 3

APP_PID=$(cat "$APP_PID_FILE")
if ! ps -p "$APP_PID" > /dev/null 2>&1; then
    error "Server failed to start. Check logs: $LOG_DIR/server.log"
fi

# ── Optional: verify app responds locally ─────────────────────────────────────
if ! curl -s "http://localhost:$APP_PORT" > /dev/null 2>&1; then
    warn "App started, but / returned non-200 or no body. This may be OK if root route is not defined."
fi

# ── Start Cloudflare tunnel ───────────────────────────────────────────────────
info "Starting Cloudflare Tunnel..."

rm -f "$TUNNEL_URL_FILE"

nohup cloudflared tunnel --url "http://localhost:$APP_PORT" \
    > "$LOG_DIR/tunnel.log" 2>&1 &

echo $! > "$TUNNEL_PID_FILE"

sleep 8

TUNNEL_PID=$(cat "$TUNNEL_PID_FILE")
if ! ps -p "$TUNNEL_PID" > /dev/null 2>&1; then
    error "Cloudflare Tunnel failed to start. Check logs: $LOG_DIR/tunnel.log"
fi

# ── Extract tunnel URL ────────────────────────────────────────────────────────
TUNNEL_URL=$(grep -o 'https://[-a-zA-Z0-9]*\.trycloudflare\.com' "$LOG_DIR/tunnel.log" | tail -n 1)

if [ -n "$TUNNEL_URL" ]; then
    echo "$TUNNEL_URL" > "$TUNNEL_URL_FILE"
fi

# ── Success output ────────────────────────────────────────────────────────────
info "================================================================"
info " BRA server started successfully!"
info " App PID       : $APP_PID"
info " App Port      : $APP_PORT"
info " App Logs      : tail -f $LOG_DIR/server.log"
info " Tunnel PID    : $TUNNEL_PID"
info " Tunnel Logs   : tail -f $LOG_DIR/tunnel.log"

if [ -n "$TUNNEL_URL" ]; then
    info " Public URL    : $TUNNEL_URL"
    info " Docs URL      : $TUNNEL_URL/docs"
else
    warn "Tunnel started, but URL not parsed yet. Check: tail -f $LOG_DIR/tunnel.log"
fi

info " Stop both     : ./stop.sh"
info "================================================================"