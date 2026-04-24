# SAMS Launch Runbook — Task 14 Server-Side Steps

Everything in this file must be executed **on the production VPS** (Hostinger KVM 4). The code-side work (security middleware, rate limits, nginx config, backup script, supervisor config) is already on the `staging` branch. This runbook covers only the steps that cannot be verified from a developer workspace.

Assumes:
- Ubuntu 22.04+
- The repo is at `/var/www/sams` (matches `nginx/sams.conf` and `supervisord.conf`).
- A non-root user with `sudo` named `deploy` (or similar) owns `/var/www/sams`.
- DNS records for `yourdomain.com` (and `www.yourdomain.com`) already point to the VPS public IP.

Replace `yourdomain.com` throughout with the real domain.

---

## 0. First-time setup

Skip if you've already run `scripts/setup.sh` on this VPS.

```bash
cd /var/www/sams
sudo bash scripts/setup.sh
```

This installs Python 3.11, Postgres, Redis, nginx, supervisor, certbot, WeasyPrint system deps, creates the `sams_db` database and `sams_user` role, and installs the backend Python deps inside `/var/www/sams/backend/venv`.

**Post-check**
```bash
sudo systemctl status postgresql redis-server nginx supervisor
```

---

## 1. Configure `backend/.env`

Copy the example and fill in real values. Do NOT commit this file.

```bash
cp /var/www/sams/backend/.env.example /var/www/sams/backend/.env
sudo nano /var/www/sams/backend/.env
```

Required values:
- `DATABASE_URL=postgresql+asyncpg://sams_user:<strong-random-password>@localhost:5432/sams_db`
  (Make sure to rotate the default password set by `setup.sh`.)
- `JWT_SECRET_KEY` — generate via `python3 -c "import secrets; print(secrets.token_urlsafe(64))"`
- `OPENAI_API_KEY` — real key (NOT `sk-xxxxxx...`)
- `SMTP_HOST`, `SMTP_USER`, `SMTP_PASS` — from Hostinger Email console
- `FRONTEND_URL=https://yourdomain.com`
- `UPLOAD_DIR=/var/www/sams/uploads`

Rotate the Postgres password to match:

```bash
sudo -u postgres psql -c "ALTER USER sams_user WITH PASSWORD '<strong-random-password>';"
```

---

## 2. Apply migrations

```bash
cd /var/www/sams/backend
source venv/bin/activate
alembic upgrade head
```

Expected: `001_initial` runs cleanly, creates all tables + enum types.

---

## 3. Deploy nginx config

```bash
sudo cp /var/www/sams/nginx/sams.conf /etc/nginx/sites-available/sams
sudo ln -sf /etc/nginx/sites-available/sams /etc/nginx/sites-enabled/sams
sudo rm -f /etc/nginx/sites-enabled/default
sudo sed -i 's/yourdomain.com/<real-domain>/g' /etc/nginx/sites-available/sams
sudo nginx -t
sudo systemctl reload nginx
```

---

## 4. HTTPS with certbot

```bash
sudo certbot --nginx \
  -d yourdomain.com \
  -d www.yourdomain.com \
  --non-interactive --agree-tos -m ops@yourdomain.com
```

Certbot rewrites `/etc/nginx/sites-available/sams` to serve on 443 with the obtained cert.

### Auto-renewal cron

```bash
sudo crontab -e
# Add:
0 3 * * * /usr/bin/certbot renew --quiet --deploy-hook "systemctl reload nginx"
```

Verify: `sudo certbot renew --dry-run`.

---

## 5. Supervisor — FastAPI process

```bash
sudo mkdir -p /var/log/sams
sudo chown deploy:deploy /var/log/sams

sudo cp /var/www/sams/supervisord.conf /etc/supervisor/conf.d/sams.conf

sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start sams-api
sudo supervisorctl status sams-api        # expect: RUNNING
```

Log inspection:
- `tail -f /var/log/sams/app.log`
- `tail -f /var/log/sams/error.log`

---

## 6. Daily backup cron

`scripts/backup.sh` is on-disk; the suggested cron is already in its header.

```bash
# For the root crontab:
sudo crontab -e
# Add:
0 2 * * * /bin/bash /var/www/sams/scripts/backup.sh >> /var/log/sams/backup.log 2>&1
```

Test once by running it manually and checking `/backups/` for a `sams_YYYY-MM-DD_*.sql.gz`.

---

## 7. Seed real users (15)

From a Postgres `psql` shell (as `sams_user`), or a one-off Python script inside the venv. Example for one admin user:

```bash
source /var/www/sams/backend/venv/bin/activate
cd /var/www/sams/backend
python3 - <<'PY'
import asyncio, sys
from database import AsyncSessionLocal
from models.user import User, RoleEnum
from services.auth_service import hash_password

USERS = [
    # (name, email, role, initial_password)
    ("BGCC Admin",        "admin1@bgcc.ae",     RoleEnum.admin,              "change-me-admin-1"),
    ("BGCC Admin 2",      "admin2@bgcc.ae",     RoleEnum.admin,              "change-me-admin-2"),
    ("Project Director",  "pd@bgcc.ae",         RoleEnum.project_director,   "change-me-pd"),
    ("Accounts A",        "accounts1@bgcc.ae",  RoleEnum.accounts,           "change-me-acc-1"),
    ("Accounts B",        "accounts2@bgcc.ae",  RoleEnum.accounts,           "change-me-acc-2"),
    ("Operation Manager", "om1@bgcc.ae",        RoleEnum.operation_manager,  "change-me-om-1"),
    ("Operation Mgr B",   "om2@bgcc.ae",        RoleEnum.operation_manager,  "change-me-om-2"),
    ("General Manager",   "gm@bgcc.ae",         RoleEnum.gm,                 "change-me-gm"),
    # ...add the remaining 7 users from the client's final user list
]

async def main():
    async with AsyncSessionLocal() as db:
        for name, email, role, pwd in USERS:
            db.add(User(
                name=name, email=email,
                password_hash=hash_password(pwd),
                role=role, is_active=True,
            ))
        await db.commit()
    print(f"Seeded {len(USERS)} users.")

asyncio.run(main())
PY
```

Each user must change their password on first login. (Password-change UI is a known gap — until then, Admin edits the user via the UI, which re-hashes.)

---

## 8. Seed real client master templates

The repo's `backend/scripts/seed_fields.py` populates **only the `master_fields` catalog** (F01–F08, C01–C13, A01–A23). The three `master_templates` rows (form / conditions / appendix) — with their actual HTML content — must be created once via the `POST /api/masters/` endpoint, using the real legal text that BGCC supplied in the three client PDFs.

For each of the three documents:

1. Log in as an admin, hit `POST /api/masters/` with:
   ```json
   {
     "type": "form",              // then "conditions", then "appendix"
     "version_number": "v1.0",
     "version_date": "2026-04-24",
     "content_html": "<the HTML version of the legal doc with {{FIELD_ID}} tokens where values plug in>",
     "notes": "Initial version from BGCC PDFs dated 03-MAR-2026"
   }
   ```
2. Once all three templates exist, run the field seeder:
   ```bash
   cd /var/www/sams/backend
   source venv/bin/activate
   python scripts/seed_fields.py
   ```

The PDF placeholder engine now uses `{{FIELD_ID}}` tokens (see `services/pdf_service.py`). When converting the client's `.docx` / PDF content to HTML, replace each `[Insert ...]` / `(……Insert…..)` phrase with the matching `{{FIELD_ID}}` token from the catalog in `SAMS context for project.pdf` Section 2.

A `LEGACY_TOKEN_MAP` still substitutes the original hardcoded phrases for backwards compatibility — so you can paste the legacy HTML and things render, but prefer migrating to the token form so admin-added fields work too.

---

## 9. Load test

```bash
sudo apt install -y apache2-utils
ab -n 500 -c 15 https://yourdomain.com/api/health
```

Pass criteria (per spec Task 14 §8):
- Non-2xx responses = 0
- Time per request (mean, concurrent) < 2000 ms
- No connection errors

If it fails, inspect `/var/log/sams/error.log` and `sudo journalctl -u nginx -n 200`.

---

## 10. Smoke-test the full flow

From a browser:
1. Visit `https://yourdomain.com/login` — should show the login page.
2. Sign in with the seeded admin — lands on `/dashboard`.
3. Go to Masters → Field Catalog; verify all 44 fields are present and sorted correctly.
4. Go to New Agreement → complete the 5-step wizard for one dummy project.
5. Submit for review → log in as PD → approve. Repeat for Accounts / OM / GM.
6. Generate the PDF and open the deviation report.
7. Record a subcontractor "comments" response, build the resolution sheet, run OM/GM approval, then `POST /api/agreements/{id}/send-to-subcontractor`.
8. Record "signed" → confirm the agreement is locked (no more field edits) and shows in Archive.

If everything above passes, the launch is green.

---

## Post-launch maintenance checklist

- `tail -f /var/log/sams/error.log` — watch the first 24h for 500s.
- `sudo supervisorctl status sams-api` — should stay `RUNNING`; restart count should be 0.
- `sudo certbot certificates` — verify renewal date ≥ 30 days away.
- `/backups/` — verify a new `sams_*.sql.gz` shows up each morning, and that the retention script purges beyond 30 days.
- Track OpenAI token spend via the dashboard and adjust spending cap as usage stabilizes.
