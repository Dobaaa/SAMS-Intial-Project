# CLAUDE.md — SAMS Project Guide

> **Purpose:** Onboarding + running log for Claude Code sessions. Keep this file current — update it with findings, decisions, and landmines as we work. It is the first thing a new session reads after `git status`.

---

## 1. What this project is

**SAMS (Subcontract Agreement Management System)** for **Bhatia General Contracting Co. (BGCC)**, Dubai UAE.

A workflow + compliance web app that manages the full lifecycle of a subcontract agreement: create from master templates → multi-step internal approval (PD → Accounts → OM → GM) → send PDF to subcontractor → resolve their comments → signature → archive. Explicitly **not** a document editor or e-signature tool.

Every agreement is a package of **3 documents** combined into one PDF: Form (8 `[Insert]` fields F01–F08), Conditions (13 fields C01–C13), Appendix (23 rows A01–A23, mostly auto-populated from F and C).

Authoritative spec: `final context for project.pdf` (v3.0, 28 pages, Section 8 contains the 14-task breakdown).

---

## 2. Branch layout

- **`main`** — empty scaffold (Vite + FastAPI template + `.env`). **Do not** branch features off main.
- **`ahmed`** — the implementation done via Tasks 01–14 prompts. Treat as the "trunk" of real work.
- **`staging`** — our active working branch, cut from `ahmed`. All feature work happens here. Push to `origin/staging`.

**Branching for new work:** cut from `staging` as `feat/<slug>`, `fix/<slug>`, `chore/<slug>`. Open a PR back to `staging`.

---

## 3. Stack

**Backend** (`backend/`) — Python 3.11 · FastAPI (async) · SQLAlchemy 2.0 (async) · Alembic · PostgreSQL · Redis · WeasyPrint + Jinja2 · OpenAI GPT-4o · python-jose (JWT) · passlib/bcrypt · aiosmtplib · APScheduler · slowapi · bleach · openpyxl.

**Frontend** (`frontend/`) — React 19 · Vite · TypeScript · Tailwind v4 · TipTap (ProseMirror) · @tanstack/react-query · axios · react-hook-form · zod · zustand · react-router-dom v7 · lucide-react.

**Infra target** — Hostinger VPS KVM 4 · nginx reverse proxy · supervisord · no Docker (direct deploy per spec). MinIO + Prometheus/Grafana + GitHub Actions planned, not wired.

**Stack drift vs. PDF v3 spec:** React 19 (PDF: 18), router 7 (PDF: 6), Tailwind 4 (PDF: 3), FastAPI 0.136 (PDF: 0.115). Not wrong, but the PDF's copy-paste snippets will not always work verbatim.

---

## 4. Folder structure (on `staging`)

```
backend/
  main.py                FastAPI app, CORS, /health, /health/db, 11 routers mounted at /api
  config.py              pydantic-settings reading .env
  database.py            async SQLAlchemy engine + AsyncSessionLocal + Base
  alembic.ini
  .env                   placeholder values — real secrets never commit
  models/                user, master, agreement, workflow, resolution, ai_review, audit
  routers/               auth, users, masters, agreements, workflow, comments,
                         resolution, ai, pdf, archive, reports
  services/              auth, master, agreement, workflow_engine, resolution,
                         ai, pdf, deviation, email, audit(EMPTY)
  middleware/            rbac, security
  templates/             cover_page, form_of_agreement, conditions, appendix,
                         deviation_report, base_pdf.css
  migrations/versions/   001_initial.py
  scripts/seed_fields.py seeds 27/44 fields (incomplete)
  requirements.txt       ⚠ UTF-16 LE with CRLF (should be converted to UTF-8)

frontend/src/
  App.tsx                ⚠ uses ?view= query-string routing; react-router v7 installed but unused
  main.tsx
  index.css              @import "tailwindcss";
  pages/
    Dashboard, UserManagement, MasterTemplates, AgreementCreate,
    WorkflowReview, CommentsResolution, Archive
    AgreementDetail.tsx, Reports.tsx                      (EMPTY files)
  components/
    FieldCatalog, FieldInput, WorkflowTimeline, CommentThread, AIReviewPanel
    AppendixBuilder.tsx, DeviationReport.tsx              (EMPTY files)

nginx/sams.conf          reverse proxy + static frontend
supervisord.conf         FastAPI process
scripts/setup.sh         one-shot VPS bootstrap
scripts/backup.sh        pg_dump cron target
logs/error.log           ⚠ committed log file (should be in .gitignore)
contract Pdfs/           real BGCC client docs (Form, Conditions, Appendix)
final context for project.pdf     v3 spec — single source of truth
SAMS_Project_Brief (1) (1).md     earlier narrative (superseded by PDF where conflicting)
SAMS_Implementation_Handover_Report.md   what Tasks 01–14 delivered + known gaps
```

---

## 5. Key domain rules (don't violate these)

1. **Admin fills `[Insert]` fields only** — legal boilerplate is never retyped. Field catalog is the F/C/A IDs only.
2. **Every master template change = new version.** Old agreements keep a FK to the exact version they were built from.
3. **Appendix is a diff document.** Auto-populates from F/C. Admin can show/hide rows per agreement and add extra notes.
4. **All returns go back to Admin**, not the previous reviewer. On resubmit the **whole chain restarts from step 1 (PD)** — any prior approvals on this agreement are wiped and every reviewer must re-approve.
5. **All reviewers can see and edit all comments.** Every edit writes a row in `comment_edit_history`. Only Admin can mark a comment `resolved`.
6. **No auto-approvals.** Every AI output is a suggestion that a human must confirm before action.
7. **Reference number is BGCC-controlled**, format suggestion `SAG-[PROJECT_CODE]-[YEAR]-[SEQ]`, editable until GM approval.
8. **When subcontractor signs:** lock the agreement (`is_executed=true`, `current_status=completed`, no more edits).
9. **PDF is always generated, never edited.** Regenerate from stored data.
10. **Subcontractor is external** — never a system user. All contact via email.

8 agreement status values: `under_drafting`, `under_internal_review`, `draft_forwarded_to_subcontractor`, `under_subcontractor_review`, `under_subcontractor_signature`, `under_bgcc_revision`, `under_gm_signature`, `completed`.

5 roles: `admin`, `project_director`, `accounts`, `operation_manager`, `gm`. ~15 users total.

---

## 6. Task 01–14 gap register (2026-04-24 audit)

Legend: 🔴 blocker (functionally broken or spec-violating) · 🟡 should-fix (working but fragile, drifts from spec, or UX-bad) · 🟢 polish (optional hardening).

### Cross-cutting (apply everywhere)

- 🔴 **Frontend has no auth layer.** Every page does `axios.create({ baseURL: "/api" })` with **no `Authorization` header**. Backend requires JWT on almost every endpoint → the whole app 401s as soon as auth is enforced.
- 🔴 **No login page / auth flow on the frontend.** No way to get a token from the UI.
- 🔴 **Frontend routing is a `?view=` query-string hack** in `App.tsx`; `react-router-dom` v7 is installed but unused.
- 🔴 **Empty files declared as done**: `backend/services/audit_service.py` (orphan import), `frontend/src/pages/AgreementDetail.tsx`, `frontend/src/pages/Reports.tsx`, `frontend/src/components/AppendixBuilder.tsx`, `frontend/src/components/DeviationReport.tsx`.
- 🟡 No root `.gitignore`; `logs/error.log` is committed.
- 🟡 Zero tests (pytest / vitest / playwright).
- 🟡 `backend/requirements.txt` is UTF-16 LE with CRLF (pip tolerates, linters/CI often don't).
- 🟡 No `.env.example` for the backend; real `.env` with placeholders is committed.
- 🟡 No CI/CD pipeline (spec called for GitHub Actions).

---

### TASK 01 — VPS setup + project scaffolding — **mostly OK**
- ✅ `main.py` (FastAPI + CORS + `/health` + `/health/db`), `config.py` (pydantic-settings), `database.py` (async SQLAlchemy), `alembic.ini`, `nginx/sams.conf`, `supervisord.conf`, `scripts/setup.sh`.
- 🟡 `setup.sh` has hardcoded `CHANGE_ME_STRONG_PASSWORD` for the Postgres user (expected, but should read from env).
- 🟡 `config.py` does not expose `JWT_ALGORITHM` or `UPLOAD_DIR` despite `.env` mentioning them; values are hardcoded in services.

### TASK 02 — Models + migrations + seed — **mostly OK, 1 real bug**
- ✅ All 10+ tables present in models + migration `001_initial.py`. Matches PDF Section 3 one-for-one.
- ✅ `seed_fields.py` actually covers **all 44 fields** (F01–F08, C01–C13, A01–A23) — **the handover's "only 27" claim is wrong**.
- 🔴 `models/agreement.py:123-126` `_on_status_change` event listener uses **naive `datetime.now()`** while column is `DateTime(timezone=True)` — tz-aware vs naive mix will raise or silently corrupt.
- 🟡 `MasterField.auto_source_field_id` is declared but **not consumed** by the services. Admin adding a new auto-populating field via UI has no effect; `update_agreement_fields` hardcodes F02→A01, F05→A02, F08→A07/C03.
- 🟡 `create_draft_agreement` creates `AppendixConfig` only for fields whose ID starts with `A`. If Admin adds a non-A field with `show_in_appendix=true`, it won't render in the PDF appendix.
- 🟡 `C09` (milestones table) input type is `table` but there's no storage model for row data — frontend renders it as a textarea.

### TASK 03 — Auth + user CRUD — **mostly OK, 1 real bug**
- ✅ Login / refresh / logout, bcrypt, 8h access / 30d refresh, JWT HS256, `get_current_user` + `require_role` deps, audit log on user ops.
- ✅ Rate limit `10/minute` on auth routes (Task 14 forward).
- 🔴 Refresh-token revocation uses an **in-memory Python `set`** (`_revoked_refresh_jti` in `auth_service.py`) — **lost on every restart**. Should be Redis.
- 🟡 Missing `GET /api/auth/me` (practically required by any frontend auth store).
- 🟡 No password strength validation on create/update; no password-change endpoint.

### TASK 04 — Master template management — **real routing bug + UI gap**
- ✅ Grouped listing by type, get-with-fields, create new version (auto-switches `is_active`), field CRUD, audit logged.
- 🔴 `routers/masters.py:212` — `PUT /fields/reorder` is declared **after** `PUT /fields/{field_id}`. FastAPI validates `field_id: uuid.UUID` before dispatching, so `/fields/reorder` → 422 because `"reorder"` is not a UUID. Route order must be swapped.
- 🟡 `FieldCatalog.tsx` edit mode exposes `field_id/clause_number/label/input_type/sort_order` but **not** `auto_source_field_id`, `appendix_row_label`, `appendix_clause_ref`, `show_in_appendix` — so those can't be changed from the UI.
- 🟡 No template-delete / archive endpoint; no "Legal Editor" role (spec said optional).

### TASK 05 — Agreement creation wizard — **2 real bugs**
- ✅ 5-step wizard in `AgreementCreate.tsx`, POST `/agreements/`, PUT `/fields`, POST `/submit`. Reference format `SAG-{CODE}-{YEAR}-{SEQ:03d}` implemented.
- 🔴 `agreement_service.py:134` sets `values["C03"] = values["F08"]` — copies the full F08 amount to C03. Spec says C03 default is "10% of F08". Should compute numeric 10%.
- 🔴 `update_agreement_fields` **always re-runs** F→A/C auto-population, so any Admin-set manual override on A01/A02/A07/C03 is **overwritten on the next update** of F02/F05/F08.
- 🟡 Step 4 ("Appendix Builder") renders appendix fields as inputs — it does **not** expose the "show/hide per row" toggle or the `admin_extra_note` editor that the spec requires (and that `AppendixConfig` supports).
- 🟡 Step 5 "modified" amber highlight compares raw strings — `"10"` vs number `10` diverges.
- 🟡 Auto-population rules are duplicated: in `AgreementCreate.tsx` onChange AND `agreement_service.update_agreement_fields`. One source of truth needed.
- 🟡 `react-hook-form` + `zod` installed but not used (no per-step form validation).

### TASK 06 — PDF generation — **fragile placeholder engine**
- ✅ WeasyPrint + Jinja2, 5 templates + `base_pdf.css`, 4-doc combined PDF (Cover + Form + Conditions + Appendix), watermark DRAFT/FINAL/EXECUTED, A4 / 2cm margins / page numbers, endpoints `/pdf/{id}/generate` + `/pdf/{id}/preview`.
- 🔴 `pdf_service._render_master_with_values` is **hardcoded string replacement** tied to the exact phrases in the client's current docs (e.g. `"(……Insert…..) Scope to be detailed here"`). If Admin edits the template, placeholders stop resolving. Spec required a generic field-driven engine.
- 🔴 Only F02–F08 and C01–C04 get explicit mappings; C05–C13 fall through a sequential "pop-next" fallback that's order-dependent and breaks silently when the HTML reorders.
- 🟡 `pdf_outputs.pdf_type` is always `draft` — never `final` or `executed` as the spec's 3-value enum expects.
- 🟡 Upload dir is hardcoded at `BASE_DIR/uploads/agreements/…`; ignores `.env`'s `UPLOAD_DIR`.
- 🟡 BGCC logo is a blank string (`context["bgcc_logo_url"] = ""`). No RTL support despite stack rationale.

### TASK 07 — Deviation report — **OK-ish**
- ✅ Full deviation report PDF with Clause / Title / Default / Entered / Change Type / Risk columns, summary line, `/agreements/{id}/deviation-report` + `/regenerate`, stored in `deviation_reports` with `report_data_json`.
- 🟡 `rows.sort(key=lambda r: (r["clause_number"], r["clause_title"]))` — clause numbers are strings like "3.4.1", sort is lexicographic ("10" < "2").
- 🟡 `change_type` compares raw strings — numeric default `"10% of F08"` vs numeric entered `"5000"` will always read as "Modified".
- 🟡 "Risk" column is always `"Pending AI"` — no wiring to `ai_service.detect_risks` output.

### TASK 08 — Approval workflow — **OK**
- ✅ On submit: 4 `workflow_steps` created (PD/Acc/OM/GM), all `pending`. `approve_step` activates next via role check, `return_step` requires comment, resubmit restarts the **whole chain** from PD (wipes prior approvals). Email notifications to next reviewer on approve, to Admin on return. GM approval sets `gm_approval_date`.
- 🟡 GM approval leaves `current_status = under_internal_review` — spec says Admin then sends; no explicit transition to a post-GM status.
- 🟡 `resubmit_agreement` wipes `acted_by/acted_at` on **every step in the chain** — full audit of who approved or returned what during the prior pass is lost on the steps themselves; only the `WorkflowComment` rows preserve return history.
- 🟡 `get_pending_for_role` works because previous-step-approved check guards it, but **4 pre-created pending steps visible to no-one** is a bit weird; serial gating is implicit.
- 🟡 `CommentThread` component exists but isn't wired into `WorkflowReview.tsx` (which renders its own simpler list).

### TASK 09 — Collaborative comments — **OK**
- ✅ GET all comments with edit-history, PUT /comments/{id} edits with history entry, PATCH status, Admin-only `resolved`, email to original author on edit.
- 🟡 `PUT /comments/{id}` has no role restriction beyond `get_current_user` — any authenticated user can edit any comment. Matches spec literally but worth noting.
- 🟡 No validation of `clause_reference` against `master_fields`.

### TASK 10 — AI integration — **2 real bugs**
- ✅ 5 functions matching spec (`compare_clauses`, `detect_risks`, `generate_summary(role)`, `suggest_responses`, `validate_revision`), Redis cache key `sams:ai:{agreement_id}:{review_type}[:{suffix}]` with 24h TTL, results persisted to `ai_reviews`, GPT-4o model, confirm-button UI.
- 🔴 `ai_service.validate_revision` queries `CommentsResolutionSheet.agreement_id == sheet_id` — the parameter is named `sheet_id` but matched on `agreement_id`. Either rename or fix the query; currently the only way it works is if callers pass an agreement_id.
- 🔴 `suggest_responses` accepts `sheet_id` but OR-matches on both `agreement_id` and `row.id`. The one caller (`resolution_service.create_resolution_sheet`) always passes `agreement.id`, so "sheet_id" is a misnomer. Contract should be cleaned up.
- 🟡 `_chat_json` doesn't request OpenAI `response_format={"type":"json_object"}`; relies on prompt wording + a fallback regex extractor.
- 🟡 No try/except for OpenAI client errors (rate limits, timeouts). Module-level `openai_client = AsyncOpenAI(...)` creation will raise at import if `OPENAI_API_KEY` is missing or malformed.
- 🟡 `AIReviewPanel` is not wired into any page (`WorkflowReview` has a placeholder div).

### TASK 11 — Resolution cycle — **2 real bugs + workflow gap**
- ✅ `record_subcontractor_response` handles signed vs comments, sheet CRUD, AI prefill, submit-for-approval creates 2 steps (OM→GM), frontend `CommentsResolution.tsx` page.
- 🔴 `resolution_service.create_resolution_sheet` exception handler does `await db.rollback()` **after** `await db.commit()`, then re-adds the already-persisted rows — the rollback is a no-op relative to the prior commit, and the re-adds are incoherent.
- 🔴 After OM+GM approve the resolution, there's **no code path** to transition the agreement to `under_subcontractor_signature` and re-send. The flow dead-ends at resolution approval.
- 🟡 `signed_scan_path` is accepted in the payload but never stored (no field on `agreement`, no upload endpoint).
- 🟡 Resolution steps share `workflow_steps` with the main chain — no `workflow_kind` column, so pending lists for OM/GM mix both.
- 🟡 Comment wiring `"Remove stale returned/pending resolution steps if any, keep history otherwise"` lies — the code only short-circuits when steps exist; nothing is removed.

### TASK 12 — Archive — **OK, UX issue**
- ✅ Project-wise + subcontractor-wise lists with filters, detail endpoint, download final/executed PDF, Excel export via openpyxl, 8 status labels, SQLAlchemy event listener on `status_updated_on`.
- 🔴 Same tz-naive `datetime.now()` bug in the `status_updated_on` event listener (re-flagged from Task 02).
- 🟡 `Archive.tsx` requires the user to **paste UUIDs** for project/subcontractor IDs — unusable without a picker.
- 🟡 `download` endpoint only returns `final|executed` PDFs — returns 404 even when a draft PDF exists.

### TASK 13 — Dashboard + user UI + audit viewer — **OK, small bugs**
- ✅ Dashboard summary cards, filtered agreements table, paginated audit log, active master-versions panel, user management page wired to Task 03 APIs.
- 🔴 `reports.py:35` uses deprecated `datetime.utcnow()` (Python 3.12+ warnings).
- 🟡 `under_review` card counts only `under_internal_review`; ignores `under_bgcc_revision` + `under_gm_signature`.
- 🟡 Status filter dropdown in `Dashboard.tsx` lists only 4 of 8 statuses.
- 🟡 No `page_size` cap on audit-log endpoint.
- 🟡 `Reports.tsx` is empty (Dashboard effectively is Reports).

### TASK 14 — Security / monitoring / launch — **critical middleware bug**
- ✅ `security.py`: slowapi limiter (100/min default), bleach sanitizer, global exception handler logs to file. `nginx/sams.conf`: HTTPS redirect + security headers + `/api/` reverse proxy. `backup.sh`: pg_dump | gzip → `/backups`, 30-day retention, suggested cron. `supervisord.conf`: autorestart + rotated logs.
- 🔴 **`SanitizationMiddleware` strips ALL HTML tags from ALL JSON payloads globally.** This **destroys** TipTap-generated rich text in `content_html` (Task 04), and any comment/response text containing `<em>`, `<strong>`, `<ul>`, etc. Needs per-route or per-field opt-out.
- 🔴 Two sanitization paths coexist and fight each other: the middleware (above) **and** the `SanitizedModel` base used by `routers/auth.py` request models. Should be one clean Pydantic validator, not a mutating middleware.
- 🟡 Server-side items never executed from the workspace (as expected): certbot HTTPS, cron installs, real user seed, real client template seed, `ab` load test.
- 🟡 No Sentry / external monitoring integration.

---

### Implementation priority (my proposed order)

Bucket 1 — **unblock the app** (nothing else matters until these are green):
1. Fix `SanitizationMiddleware` so it doesn't shred HTML (Task 14 🔴).
2. Add auth layer on the frontend — axios interceptor + token store + login page + protected routes + `GET /api/auth/me` (cross-cutting 🔴 + Task 03 🟡).
3. Move refresh-token revocation to Redis (Task 03 🔴).
4. Fix tz-naive `datetime.now()` in `agreement.py` event listener (Task 02/12 🔴).
5. Fix route order in `routers/masters.py` so reorder works (Task 04 🔴).

Bucket 2 — **data-correctness bugs**:
6. Fix C03 "10% of F08" logic + preserve manual A01/A02/A07/C03 overrides (Task 05 🔴 ×2).
7. Disambiguate AI service `sheet_id` vs `agreement_id` contract + fix `validate_revision` query (Task 10 🔴 ×2).
8. Fix resolution-sheet rollback/commit ordering + re-send-to-subcontractor path (Task 11 🔴 ×2).

Bucket 3 — **empty files & routing**:
9. Fill or delete the 4 empty frontend files + empty `audit_service.py`. Wire `react-router-dom` properly; remove `?view=` hack.
10. Rewrite `pdf_service._render_master_with_values` as a generic `master_fields`-driven engine (Task 06 🔴).
11. Wire the Appendix Builder UI (show/hide toggle + extra note) into Step 4 of the wizard (Task 05 🟡).

Bucket 4 — **polish & hardening**:
12. `.gitignore`, convert `requirements.txt` to UTF-8, add `.env.example`, replace `datetime.utcnow()`, cap audit page_size, fix status filter dropdowns, etc.
13. Tests (auth flow, agreement lifecycle, workflow return/resubmit, resolution cycle, archive export).
14. Server-side runbook for Task 14 launch steps (certbot, crons, seeds, `ab`).

---

## 7. Common commands

**Frontend (`frontend/`):**
```bash
npm install
npm run dev          # Vite dev server, defaults to :5173
npm run build        # tsc -b && vite build
npm run lint         # eslint .
npm run preview
```

**Backend (`backend/`):**
```bash
python3.11 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
# Postgres + Redis must be running locally (see .env)
uvicorn main:app --reload --port 8000
# Migrations:
alembic upgrade head
alembic revision --autogenerate -m "<message>"
# Seed:
python scripts/seed_fields.py
```

**Git:**
```bash
git checkout staging                      # active working branch
git checkout -b feat/<slug> staging       # new feature branch off staging
```

---

## 8. Git / commit conventions

- **Style:** Conventional Commits — `feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:`, `perf:`, `build:`, `ci:`.
- **Scope optional** — e.g. `feat(agreements): add reference override before gm approval`.
- **Message in imperative mood**, present tense ("add X", not "added X").
- **Each commit = new commit** (never `--amend` unless explicitly requested). **Never** `--no-verify`.
- **Co-author trailer** for Claude Code commits:
  ```
  Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
  ```
- **Never force-push** to `main` or `ahmed`. Force-push to own feature branches OK only if asked.
- **PRs** are opened from `feat/…` → `staging`. `staging` → `ahmed` merges are decided session-by-session.

---

## 9. Local secrets

`backend/.env` in the repo holds **placeholders only**. Real values (Postgres, OpenAI key, JWT secret, SMTP creds) are configured per environment and **must not be committed**. Before any commit that touches env, verify with `git diff -- backend/.env` that it still contains placeholders only.

---

## 10. Live VPS / Deploy

**Alpha env URL:** https://76-13-159-24.sslip.io  (sslip.io wildcard → 76.13.159.24; switches to `sams.bgcc.ae` once BGCC IT publishes the DNS record)

**VPS:** Hostinger KVM 1 — Ubuntu 24.04 — `developer@76.13.159.24` — passwordless sudo, SSH key at `~/.ssh/sams_deploy_ed25519`. Password auth still enabled (alpha; tighten by setting `PasswordAuthentication no` in `/etc/ssh/sshd_config` once stable).

**Stack on the VPS:** Postgres 16 (db `sams_db`, role `sams_user`) · Redis 7 · nginx 1.24 + Let's Encrypt (auto-renew daily 03:00 via root crontab) · supervisord (`sams-api` program) · Python **3.12** in `/var/www/sams/backend/venv` (NB: spec said 3.11; Ubuntu 24.04 default is 3.12 — works fine) · Node 20.20 + Vite build · daily backup 02:00 via postgres crontab → `/backups/sams_*.sql.gz` (30-day retention).

**Deploy after pushing to `staging` (or any local branch):**
```bash
./scripts/deploy-to-vps.sh           # defaults to staging
./scripts/deploy-to-vps.sh feat/foo  # any local branch
```

What the script does, in order:
1. `git archive <branch> | ssh ... | tar -xf -` into `/var/www/sams`. Tar only **adds/overwrites** files — `.env`, `venv/`, `node_modules/`, `dist/`, `uploads/` are NOT in the archive (gitignored), so production state is preserved.
2. `pip install -r requirements.txt` (idempotent; fast no-op if no deps changed).
3. `alembic upgrade head` (idempotent).
4. `npm install && npm run build` — always rebuilds Vite bundle.
5. `supervisorctl restart sams-api` (FastAPI picks up new code).
6. `systemctl reload nginx` (only matters if nginx config changed).

Total wall clock on the 1-vCPU box: ~90–150 s for a no-op redeploy; longer if pip / npm pulls in new packages.

**What the script does NOT do:**
- No DB rollback. If `alembic upgrade` fails mid-deploy, fix forward.
- No blue/green or atomic swap. Brief window (~3-5 s) where supervisor is restarting and `/api` returns 502.
- No Vite dist atomic swap; `dist/` is overwritten in place.
- No pre-deploy backup (the 02:00 cron is the only safety net).

**Manual touch-ups still on the live VPS that haven't been backported to the repo yet** (will land in a follow-up commit):
- `nginx/sams.conf` — `proxy_pass http://127.0.0.1:8000;` (no trailing slash). The repo version has a trailing slash that strips `/api`, making every backend route 404.
- `backend/requirements.txt` — needs `asyncpg` added; the code uses `postgresql+asyncpg://` but only `psycopg2-binary` is pinned, so uvicorn + alembic both fail to start without it.
- `scripts/backup.sh` — `cd /tmp` after `set -euo pipefail` (avoids `find` cwd error when run from anywhere); `DB_USER="${DB_USER:-postgres}"` instead of hardcoded `sams_user` (peer auth via Unix socket).

**Diagnosis & rollback toolkit on the VPS:**
```bash
sudo supervisorctl status sams-api
sudo supervisorctl tail -f sams-api stderr
sudo tail -f /var/log/sams/error.log
sudo journalctl -u nginx -n 200
ls -lh /backups/                  # most recent dump
gunzip -c /backups/sams_X.sql.gz | psql -U postgres sams_db   # restore
```

**Resource caveat:** KVM 1 (1 vCPU / 4 GB) is fine for alpha demo (~600 MB used after bring-up, plenty of headroom). Recommend upgrading to KVM 2 minimum / KVM 4 ideal before BGCC's 15 users start using PDF generation concurrently — WeasyPrint is CPU-heavy and shares the single core with Postgres + Redis + uvicorn.

---

## 11. Session log (most recent first)

> Append one bullet per session after meaningful work. Keep terse.

- **2026-05-01** — **Alpha environment deployed to Hostinger VPS** at https://76-13-159-24.sslip.io (sslip.io wildcard since `bgcc.ae` not published yet). Box is Hostinger KVM 1 / Ubuntu 24.04 / 1 vCPU / 4 GB RAM (smaller than spec'd KVM 4) — added 2 GB swap as a cushion. Stack: Postgres 16, Redis 7, nginx 1.24 + Let's Encrypt, supervisord, FastAPI on Python 3.12, Vite build under Node 20.20 (Ubuntu's default Node 18 was too old for Vite 7). Five test users seeded (one per role, `change-me-<role>` temp passwords). 45 master_fields seeded behind 3 placeholder master_templates — admin must replace the template HTML via the UI before real PDFs render. SMTP intentionally placeholder; email path is best-effort and silently no-ops. **3 repo bugs found while running the runbook, patched on the VPS only**: (a) `nginx/sams.conf` `proxy_pass` trailing slash strips `/api` → all backend routes 404; (b) `backend/requirements.txt` missing `asyncpg` (runtime crash); (c) `scripts/backup.sh` hardcoded `sams_user` peer-auth fails + missing `cd` before `find`. Added `scripts/deploy-to-vps.sh` for one-command redeploys (option 1 deploy plan). Added §10 to this file documenting the live env. Daily backups @ 02:00, certbot renewal @ 03:00, both verified. Smoke test green: login, `/api/auth/me`, HTTPS redirect, JS asset 200.
- **2026-04-24** — Initial project survey completed: read PDF v3 (28 pages, all 14 tasks), handover report, all `ahmed` code (≈5,200 LoC), confirmed spec vs. code drift. Saved memories (`MEMORY.md` index + 6 files). Created `staging` branch off `ahmed` and pushed to `origin`. Added this `CLAUDE.md`. GitHub access: pushes authenticated as `SeifMostafaa` (WRITE confirmed) via `gh`-backed HTTPS credential helper. No features built or bugs fixed yet.
- **2026-04-24** — Full Task 01–14 static audit. Read every backend service/router/model/migration/template and every frontend page/component. Replaced the placeholder "known gaps" section with a task-by-task gap register (severity-marked) + implementation priority buckets (section 6). Key corrections vs. the handover report: seed script actually covers all **44 fields**, not 27. Key new findings: (1) `SanitizationMiddleware` globally strips HTML from all JSON payloads — will destroy TipTap rich-text; (2) frontend has no auth layer / no login page; (3) refresh-token revocation is in-process set, lost on restart; (4) route order in `masters.py` makes `PUT /fields/reorder` permanently 422; (5) `ai_service.validate_revision` queries by agreement_id but names parameter `sheet_id`; (6) resolution cycle dead-ends after OM/GM approve — no path back to subcontractor-signature.
- **2026-04-24** — Test infrastructure landed on both sides.
  - `test(backend): add pytest suite with ephemeral Postgres + fakeredis` — `backend/requirements-dev.txt` (pytest, pytest-asyncio, pytest-postgresql, asyncpg, fakeredis), `backend/pytest.ini` (asyncio_mode=auto, `postgresql_exec` → `/usr/lib/postgresql/18/bin/pg_ctl`), and `backend/migrations/env.py` + `script.py.mako` (alembic was missing its env.py entirely; would have failed anywhere but this workspace). Tests cover: auth (login / refresh / logout / me / Redis-backed refresh revocation), masters (the `/fields/reorder` ordering regression, versioning toggle, CRUD, 401/422 edges), agreements (reference number format, F08→A07/C03 cascade with the 10% fix, manual override preservation, submit-creates-4-steps, send-to-subcontractor transitions), workflow (return requires comment, resubmit reactivates returned step, pending filters by role), resolution (signed locks the agreement, sheet CRUD with AI monkeypatched, send-to-subcontractor-after-resolution → `under_subcontractor_signature`). Run with `cd backend && pytest`.
  - `test(frontend): add vitest + @testing-library/react suite` — Node 20.17 constraint forced vitest 2 + happy-dom (jsdom 27 / vitest 4 both want Node ≥ 20.19). 13 tests across auth store (CRUD + persistence round-trip), api client (request interceptor attaches Bearer, omits when empty), RequireAuth guard (4 paths including /auth/me hydration and role-block), Login page (structure + happy-path submit). Two edge-case tests are deferred with `TODO` comments (401→refresh retry path in `lib/api.test.ts`, error-message rendering in `Login.test.tsx`) — both relate to happy-dom + userEvent quirks on Node 20.17. Small accessibility win alongside: added `htmlFor`/`id` pairs on the Login form inputs. `cd frontend && npm run test:run`.
- **2026-04-24** — Buckets 3 & 4 (minus tests) cleared. Commits on `staging`:
  - `refactor(audit): centralize audit_log writes in a single service helper` — re-introduced `backend/services/audit_service.py` (previously empty) with `record_audit()`; `users.py`, `masters.py`, `master_service.py` migrated off inline `db.add(AuditLog(...))`. Deleted the empty `frontend/src/pages/AgreementDetail.tsx` and `frontend/src/pages/Reports.tsx` stubs.
  - `feat(pdf): generic {{FIELD_ID}} placeholder engine driven by master_fields` — replaced the hardcoded phrase-substitution engine. Admin-added fields now render automatically when referenced as `{{F02}}` etc. in template content. `LEGACY_TOKEN_MAP` retained for the initial client docs as a migration bridge.
  - `feat(appendix): implement Appendix Builder with show/hide, note, reorder` — new backend endpoints `GET /api/agreements/{id}/appendix` and `PUT /api/agreements/{id}/appendix/{field_id}`; new `AppendixBuilder.tsx` component rendering the full Step-4 UX (order arrows, clause, item label, value, show/hide toggle, admin note). Wired into `AgreementCreate` Step 4 alongside a collapsed A-field overrides panel.
  - `feat(workflow): render deviation report inline on the review page` — new `DeviationReport.tsx` fetches the PDF blob via the auth'd axios client, embeds via object URL, revokes on unmount. "Regenerate" + "Open in new tab" buttons. Replaces the broken link in `WorkflowReview`.
  - `chore: polish pass (gitignore, env example, encoding, page caps, dropdowns)` — added root `.gitignore`, added `backend/.env.example`, converted `requirements.txt` from UTF-16 LE / CRLF to UTF-8 / LF, fixed `datetime.utcnow()` → `datetime.now(UTC)` in `reports.py`, capped audit-log `page_size` at 200 via `Query(ge=1, le=...)`, surfaced all 8 statuses in Dashboard's filter dropdown.
  - `fix(reports): count all BGCC-internal statuses in dashboard "under review"` — now includes `under_internal_review` + `under_bgcc_revision` + `under_gm_signature`.
  - `docs: add Task 14 launch runbook for server-side deploy steps` — `docs/launch-runbook.md` covers certbot HTTPS, renewal + backup crons, supervisor bring-up, user seeding Python snippet, master-template seeding, `ab` load test, 10-step smoke path.
  Still outstanding from Bucket 4: **integration tests** (pytest + pytest-asyncio + httpx; needs a test Postgres). Next session: set up test infra + author suites for auth/agreement lifecycle/workflow return+resubmit/resolution cycle/archive export.
- **2026-04-24** — Buckets 1 & 2 cleared (8 🔴 blockers). Commits on `staging`:
  - `fix(models): use tz-aware UTC in Agreement.status_updated_on listener`
  - `fix(masters): move /fields/reorder route above /fields/{field_id}`
  - `fix(security): remove global bleach sanitization middleware` (kept `SanitizedModel` as opt-in; doc'd that rich-text fields must NOT use it)
  - `fix(auth): persist refresh-token revocation in Redis` (key `sams:auth:revoked_refresh:{jti}` with TTL = remaining exp; made `invalidate_refresh_token` / `is_refresh_token_revoked` async + updated callers)
  - `feat(auth): add frontend auth store, axios client, login, and router` — added `GET /api/auth/me`, zustand store (localStorage-persisted), shared authed `lib/api.ts` with 401→refresh interceptor, `/login` page, `RequireAuth` guard, `AppLayout` shell, react-router-dom v7 wired, QueryClientProvider on main.
  - `refactor(frontend): route all API calls through the shared authed client` — every page + CommentThread now imports `{ api }` from `lib/api` (replaces per-file `axios.create`).
  - `fix(agreements): compute C03 as 10% of F08 and preserve manual overrides` — `_advance_payment_from_price` helper on backend + matching `tenPercentOf` + `isAutoFollow` guard on frontend; admin overrides in the Appendix Builder are no longer clobbered on the next F02/F05/F08 edit.
  - `fix(ai): unify sheet_id/agreement_id contract in AI service` — `suggest_responses` and `validate_revision` both take `agreement_id` only; endpoint path renamed to `/ai/resolution/{agreement_id}/suggest`; `sheet_id` query param dropped from `/validate-revision`.
  - `fix(resolution): repair rollback path and add send-to-subcontractor flow` — create-sheet AI rollback no longer re-adds committed rows; workflow_engine now recognizes the Resolution - OM/GM chain (2-step, separate terminal branch); new endpoint `POST /api/agreements/{id}/send-to-subcontractor` transitions `under_internal_review → draft_forwarded_to_subcontractor` or `under_bgcc_revision → under_subcontractor_signature`.
  Frontend typechecks clean (`tsc -b` EXIT 0). No runtime validation yet — still static analysis only. Next up: Bucket 3 (empty files, PDF generic engine, Appendix Builder UI, `react-router` wiring cleanup is already done).
