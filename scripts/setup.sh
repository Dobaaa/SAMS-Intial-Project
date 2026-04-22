#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="/var/www/sams"
BACKEND_DIR="$APP_ROOT/backend"
FRONTEND_DIR="$APP_ROOT/frontend"
VENV_DIR="$BACKEND_DIR/venv"

echo "Updating packages..."
sudo apt update && sudo apt upgrade -y

echo "Installing system dependencies..."
sudo apt install -y \
  python3.11 python3.11-venv python3-pip \
  postgresql postgresql-contrib redis-server nginx supervisor \
  git curl nodejs npm certbot python3-certbot-nginx \
  python3-cffi python3-brotli libpango-1.0-0 libpangoft2-1.0-0 \
  libffi-dev libcairo2 libgdk-pixbuf2.0-0 shared-mime-info

echo "Creating app directories..."
sudo mkdir -p "$APP_ROOT"
sudo mkdir -p "$APP_ROOT/uploads"
sudo chown -R "$USER:$USER" "$APP_ROOT"

echo "Configuring PostgreSQL database and user..."
sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname = 'sams_db'" | grep -q 1 || \
  sudo -u postgres psql -c "CREATE DATABASE sams_db;"

sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname = 'sams_user'" | grep -q 1 || \
  sudo -u postgres psql -c "CREATE USER sams_user WITH PASSWORD 'CHANGE_ME_STRONG_PASSWORD';"

sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE sams_db TO sams_user;"

if [ -d "$BACKEND_DIR" ]; then
  echo "Creating virtual environment and installing backend requirements..."
  python3.11 -m venv "$VENV_DIR"
  # shellcheck disable=SC1091
  source "$VENV_DIR/bin/activate"
  pip install --upgrade pip
  if [ -f "$BACKEND_DIR/requirements.txt" ]; then
    pip install -r "$BACKEND_DIR/requirements.txt"
  fi
fi

echo "Enabling and restarting core services..."
sudo systemctl enable postgresql redis-server nginx supervisor
sudo systemctl restart postgresql redis-server nginx supervisor

echo "Setup finished. Next:"
echo "1) Copy nginx/sams.conf to /etc/nginx/sites-available/sams"
echo "2) Link it to sites-enabled and restart nginx"
echo "3) Configure Supervisor using supervisord.conf"
