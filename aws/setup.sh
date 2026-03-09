#!/bin/bash
# =============================================================================
# setup.sh — BRA System bootstrap for EC2 Ubuntu
#
# Usage:
#   chmod +x setup.sh
#   ./setup.sh
#
# What it does:
#   1. Updates system packages
#   2. Installs Python 3.11, pip, venv
#   3. Installs & starts PostgreSQL
#   4. Creates DB user + database
#   5. Creates .env with DATABASE_URL
#   6. Creates Python virtualenv & installs requirements
#   7. Creates a systemd service so the app starts on reboot
#
# Edit the variables in the CONFIG section before running.
# =============================================================================

set -euo pipefail

# ── CONFIG — edit these before running ───────────────────────────────────────
APP_DIR="/home/ubuntu/ibr_system_design"          # path to your cloned repo
VENV_DIR="$APP_DIR/.venv"

DB_NAME="bra"
DB_USER="bra_user"
DB_PASS="changeme_strong_password"         # ← change this

APP_PORT="8000"
APP_MODULE="api.server:app"                # uvicorn entry point
APP_WORKERS="2"

SERVICE_NAME="bra"
SERVICE_USER="ubuntu"
# ─────────────────────────────────────────────────────────────────────────────

YELLOW="\033[1;33m"
GREEN="\033[1;32m"
RED="\033[1;31m"
NC="\033[0m"

info()    { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# ── 1. System update ──────────────────────────────────────────────────────────
info "Updating system packages..."
sudo apt-get update -y
sudo apt-get upgrade -y

# ── 2. Python 3.11 ───────────────────────────────────────────────────────────
info "Installing Python 3.11..."
sudo apt-get install -y python3.11 python3.11-venv python3.11-dev python3-pip

# Make python3 → python3.11
sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1
python3 --version

# ── 3. PostgreSQL ─────────────────────────────────────────────────────────────
info "Installing PostgreSQL..."
sudo apt-get install -y postgresql postgresql-contrib libpq-dev

info "Starting PostgreSQL service..."
sudo systemctl enable postgresql
sudo systemctl start postgresql

# ── 4. Create DB user + database ─────────────────────────────────────────────
info "Setting up PostgreSQL database..."
sudo -u postgres psql <<EOF
DO \$\$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '$DB_USER') THEN
    CREATE ROLE $DB_USER WITH LOGIN PASSWORD '$DB_PASS';
  END IF;
END
\$\$;

SELECT 'CREATE DATABASE $DB_NAME OWNER $DB_USER'
  WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '$DB_NAME')
\gexec
EOF

info "Database '$DB_NAME' and user '$DB_USER' ready."

# ── 5. Write .env ─────────────────────────────────────────────────────────────
info "Writing .env file to $APP_DIR/.env ..."

# Create app dir if it doesn't exist yet (e.g. before git clone)
mkdir -p "$APP_DIR"

cat > "$APP_DIR/.env" <<EOF
DATABASE_URL=postgresql://${DB_USER}:${DB_PASS}@localhost:5432/${DB_NAME}
EOF

info ".env written."

# ── 6. Python virtualenv + dependencies ──────────────────────────────────────
info "Creating virtualenv at $VENV_DIR ..."
python3 -m venv "$VENV_DIR"

info "Installing Python dependencies..."
"$VENV_DIR/bin/pip" install --upgrade pip
"$VENV_DIR/bin/pip" install -r "$APP_DIR/requirements.txt"

info "Dependencies installed."

# ── 7. Systemd service ────────────────────────────────────────────────────────
info "Creating systemd service: $SERVICE_NAME ..."

sudo tee "/etc/systemd/system/${SERVICE_NAME}.service" > /dev/null <<EOF
[Unit]
Description=BRA Benefit Risk Assessment API
After=network.target postgresql.service
Requires=postgresql.service

[Service]
Type=simple
User=$SERVICE_USER
WorkingDirectory=$APP_DIR
EnvironmentFile=$APP_DIR/.env
ExecStart=$VENV_DIR/bin/uvicorn $APP_MODULE \\
    --host 0.0.0.0 \\
    --port $APP_PORT \\
    --workers $APP_WORKERS
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"
sudo systemctl restart "$SERVICE_NAME"

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
info "================================================================"
info " BRA system is up!"
info " Service : sudo systemctl status $SERVICE_NAME"
info " Logs    : sudo journalctl -u $SERVICE_NAME -f"
info " API     : http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null || echo '<EC2-PUBLIC-IP>'):$APP_PORT"
info " Health  : http://localhost:$APP_PORT/health"
info "================================================================"
echo ""
warn "Remember to:"
warn "  1. Open port $APP_PORT in your EC2 Security Group"
warn "  2. Change DB_PASS in this script before running in production"
warn "  3. Set up Nginx + SSL if exposing to the internet"