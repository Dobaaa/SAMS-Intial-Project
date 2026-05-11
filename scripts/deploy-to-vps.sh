#!/usr/bin/env bash
# One-shot deploy of a local branch (default: staging) to the alpha VPS.
# See CLAUDE.md §10 for what this does and what it does NOT do.
set -euo pipefail

VPS_HOST="${SAMS_VPS_HOST:-developer@76.13.159.24}"
VPS_KEY="${SAMS_DEPLOY_KEY:-$HOME/.ssh/sams_deploy_ed25519}"
APP_DIR="/var/www/sams"
BRANCH="${1:-staging}"

if ! git rev-parse --verify "$BRANCH" >/dev/null 2>&1; then
    echo "✗ branch '$BRANCH' not found locally" >&2
    exit 1
fi
if [[ ! -f "$VPS_KEY" ]]; then
    echo "✗ SSH key not found at $VPS_KEY (set SAMS_DEPLOY_KEY to override)" >&2
    exit 1
fi

echo "→ deploying branch '$BRANCH' ($(git rev-parse --short "$BRANCH")) to $VPS_HOST:$APP_DIR"

git archive --format=tar "$BRANCH" \
    | ssh -i "$VPS_KEY" -o BatchMode=yes "$VPS_HOST" \
        "cd $APP_DIR && tar -xf - --exclude='backend/.env' --exclude='frontend/.env'"

ssh -i "$VPS_KEY" -o BatchMode=yes "$VPS_HOST" 'bash -s' <<'REMOTE'
set -euo pipefail
cd /var/www/sams/backend
source venv/bin/activate

echo "→ pip install"
pip install -q -r requirements.txt

echo "→ alembic upgrade head"
alembic upgrade head

# Idempotent re-seed of master_templates.content_html from
# backend/seeds/*.html. Only updates the most recent active template per
# type, no-ops if content matches. Treat seed files as source of truth;
# any edits via the Masters UI will be overwritten on next deploy.
echo "→ seed_master_content"
python -m scripts.seed_master_content

cd ../frontend
echo "→ npm install"
npm install --silent --no-audit --no-fund
echo "→ vite build"
npm run build 2>&1 | tail -5

echo "→ supervisor restart sams-api"
sudo supervisorctl restart sams-api

echo "→ nginx reload"
sudo systemctl reload nginx

echo
sudo supervisorctl status sams-api
REMOTE

echo "✓ deploy complete — https://76-13-159-24.sslip.io"
