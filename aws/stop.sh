#!/bin/bash
# =============================================================================
# stop.sh — Stop the BRA server + Cloudflare tunnel
# Usage: ./stop.sh
# =============================================================================

APP_DIR="/home/ubuntu/ibr_system_design"
APP_PID_FILE="$APP_DIR/server.pid"
TUNNEL_PID_FILE="$APP_DIR/tunnel.pid"
TUNNEL_URL_FILE="$APP_DIR/tunnel_url.txt"

GREEN="\033[1;32m"
RED="\033[1;31m"
YELLOW="\033[1;33m"
NC="\033[0m"

info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

stop_process() {
    local pid_file="$1"
    local name="$2"
    local fallback_pattern="$3"

    if [ ! -f "$pid_file" ]; then
        warn "No PID file found for $name."
        if pkill -f "$fallback_pattern" 2>/dev/null; then
            info "Stopped leftover $name process by pattern."
        else
            warn "No $name process found either."
        fi
        return
    fi

    local pid
    pid=$(cat "$pid_file")

    if ps -p "$pid" > /dev/null 2>&1; then
        info "Stopping $name (PID $pid)..."
        kill "$pid"

        for i in $(seq 1 10); do
            if ! ps -p "$pid" > /dev/null 2>&1; then
                break
            fi
            sleep 1
        done

        if ps -p "$pid" > /dev/null 2>&1; then
            warn "$name did not stop cleanly. Force killing..."
            kill -9 "$pid"
        fi

        info "$name stopped."
    else
        warn "PID $pid for $name is not running."
    fi

    rm -f "$pid_file"
}

# ── Stop tunnel first ─────────────────────────────────────────────────────────
stop_process "$TUNNEL_PID_FILE" "Cloudflare Tunnel" "cloudflared tunnel --url http://localhost:8000"

# ── Stop app ──────────────────────────────────────────────────────────────────
stop_process "$APP_PID_FILE" "BRA server" "uvicorn api.server:app"

# ── Cleanup ───────────────────────────────────────────────────────────────────
rm -f "$TUNNEL_URL_FILE"

info "================================================================"
info " Cleanup complete."
info "================================================================"