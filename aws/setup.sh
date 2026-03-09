#!/usr/bin/env bash
# =============================================================================
# setup.sh — BRA API test setup (Ubuntu 22.04)
# Assumes repo is already cloned at APP_DIR.
# =============================================================================

set -euo pipefail

APP_DIR="/home/ubuntu/ibr_backend_system_design"
VENV_DIR="/home/ubuntu/venv"
DB_NAME="bra_db"
DB_USER="bra_user"
DB_PASSWORD="bra_test_password"

echo "=== BRA API Test Setup ==="

# ── 1. System packages ────────────────────────────────────────────────────────
echo "[1/5] Installing system packages..."
sudo apt-get update -qq

# deadsnakes PPA — required for Python 3.11 on Ubuntu 22.04
sudo apt-get install -y -qq software-properties-common
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt-get update -qq

sudo apt-get install -y -qq \
    python3.11 python3.11-venv python3.11-dev python3.11-distutils \
    build-essential libpq-dev \
    postgresql postgresql-client \
    curl

# ── 2. PostgreSQL ─────────────────────────────────────────────────────────────
echo "[2/5] Setting up PostgreSQL..."
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Create user (skip if exists)
sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname='${DB_USER}'" \
    | grep -q 1 || \
    sudo -u postgres psql -c "CREATE USER ${DB_USER} WITH PASSWORD '${DB_PASSWORD}';"

# Create database (skip if exists)
sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='${DB_NAME}'" \
    | grep -q 1 || \
    sudo -u postgres psql -c "CREATE DATABASE ${DB_NAME} OWNER ${DB_USER};"

# Allow password auth for bra_user
PG_HBA=$(sudo find /etc/postgresql -name pg_hba.conf | head -1)
if ! sudo grep -q "$DB_USER" "$PG_HBA"; then
    sudo sed -i "/^local   all             all/i local   ${DB_NAME}    ${DB_USER}    md5" "$PG_HBA"
    sudo systemctl reload postgresql
fi

# ── 3. Python venv + dependencies ─────────────────────────────────────────────
echo "[3/5] Setting up Python environment..."
python3.11 -m venv "$VENV_DIR"
"${VENV_DIR}/bin/pip" install --upgrade pip -q
"${VENV_DIR}/bin/pip" install -r "${APP_DIR}/requirements.txt" -q

# ── 4. Write .env ─────────────────────────────────────────────────────────────
echo "[4/5] Writing .env..."
cat > "${APP_DIR}/.env" <<EOF
DATABASE_URL=postgresql+asyncpg://${DB_USER}:${DB_PASSWORD}@localhost:5432/${DB_NAME}
APP_ORIGINS=*
WORKER_THREADS=2
EOF

# ── 5. Create DB tables ───────────────────────────────────────────────────────
echo "[5/5] Creating database tables..."
cd "$APP_DIR"
"${VENV_DIR}/bin/python" - <<'PYEOF'
import os, sys, asyncio
for line in open(".env").read().splitlines():
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())
sys.path.insert(0, os.getcwd())
from db.database import init_db
asyncio.run(init_db())
print("  Tables created.")
PYEOF

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo "=== Setup complete ==="
echo ""
echo "Start the server:"
echo "  cd ${APP_DIR}"
echo "  source ${VENV_DIR}/bin/activate"
echo "  uvicorn api.server:app --host 0.0.0.0 --port 8000"
echo ""
echo "Test it:"
echo "  curl http://localhost:8000/health/live"
echo "  curl http://localhost:8000/health/ready"
echo ""
echo "DB credentials:"
echo "  Name     : ${DB_NAME}"
echo "  User     : ${DB_USER}"
echo "  Password : ${DB_PASSWORD}"
