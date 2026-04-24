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
4. **All returns go back to Admin**, not the previous reviewer. On resubmit the **same step** reactivates, not the whole chain.
5. **All reviewers can see and edit all comments.** Every edit writes a row in `comment_edit_history`. Only Admin can mark a comment `resolved`.
6. **No auto-approvals.** Every AI output is a suggestion that a human must confirm before action.
7. **Reference number is BGCC-controlled**, format suggestion `SAG-[PROJECT_CODE]-[YEAR]-[SEQ]`, editable until GM approval.
8. **When subcontractor signs:** lock the agreement (`is_executed=true`, `current_status=completed`, no more edits).
9. **PDF is always generated, never edited.** Regenerate from stored data.
10. **Subcontractor is external** — never a system user. All contact via email.

8 agreement status values: `under_drafting`, `under_internal_review`, `draft_forwarded_to_subcontractor`, `under_subcontractor_review`, `under_subcontractor_signature`, `under_bgcc_revision`, `under_gm_signature`, `completed`.

5 roles: `admin`, `project_director`, `accounts`, `operation_manager`, `gm`. ~15 users total.

---

## 6. Known gaps and landmines

From the handover report + direct code inspection. Treat each as "needs review before production."

**Empty files declared as done (re-check intent: implement or delete):**
- `backend/services/audit_service.py`
- `frontend/src/pages/AgreementDetail.tsx`
- `frontend/src/pages/Reports.tsx`
- `frontend/src/components/AppendixBuilder.tsx`
- `frontend/src/components/DeviationReport.tsx`

**Functional gaps:**
- `seed_fields.py` seeds 27 fields — needs the full 44 (F01–F08 + C01–C13 + A01–A23).
- `Agreement.status_updated_on` event listener uses tz-naive `datetime.now()` — should be tz-aware UTC.
- Frontend routing is `?view=` in `App.tsx`; wire `react-router-dom` properly.
- Status transitions scattered across routers/services — needs a central state machine.
- `routers/pdf.py` may have overlapping paths after a restructure — audit via `/openapi.json`.
- AI `suggest_responses` signature mixes `sheet_id` and `agreement_id` — unify contract.
- Resolution approval reuses `workflow_steps` with no `kind` column — consider separating.
- PDF placeholder replacement is mapping-based; needs a generic field-driven engine so new admin-added fields render automatically.
- `security.py` middleware sanitizes JSON globally via bleach — no regression coverage; risk of corrupting rich-text payloads.
- **Zero tests** — no pytest / vitest / e2e anywhere.
- `requirements.txt` is UTF-16 LE (reads OK for pip but not for most linters/CI).
- No root `.gitignore`; `logs/error.log` is committed.

**Infra not executed yet (server-side, not runnable from this workspace):**
- Certbot HTTPS + cron auto-renew
- Daily `pg_dump` cron
- Real 15-user seed
- Real 3 client master templates seed
- Load testing (`ab`) against live VPS

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

## 10. Session log (most recent first)

> Append one bullet per session after meaningful work. Keep terse.

- **2026-04-24** — Initial project survey completed: read PDF v3 (28 pages, all 14 tasks), handover report, all `ahmed` code (≈5,200 LoC), confirmed spec vs. code drift. Saved memories (`MEMORY.md` index + 6 files). Created `staging` branch off `ahmed` and pushed to `origin`. Added this `CLAUDE.md`. GitHub access: pushes authenticated as `SeifMostafaa` (WRITE confirmed) via `gh`-backed HTTPS credential helper. No features built or bugs fixed yet.
