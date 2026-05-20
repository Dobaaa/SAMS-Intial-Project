# CLAUDE.md — SAMS Project Guide

> First thing a new session reads after `git status`. Keep it current — append a session log bullet after meaningful work.

---

## 1. What this is

**SAMS (Subcontract Agreement Management System)** for **Bhatia General Contracting Co. (BGCC)**, Dubai UAE. Workflow + compliance web app for the full subcontract lifecycle: create from master templates → multi-step approval (PD → Accounts → OM → GM) → send PDF to subcontractor → resolve comments → signature → archive. **Not** a document editor or e-signature tool.

Each agreement = 3 docs combined into one PDF: Form (F01–F08), Conditions (C01–C13), Appendix (A01–A23, mostly auto-populated). Authoritative spec: `final context for project.pdf` (v3.0).

---

## 2. Branches

- **`main`** — empty scaffold. Do not branch features off main.
- **`ahmed`** — trunk of original Task 01–14 work.
- **`staging`** — active working branch, cut from `ahmed`. All feature work merges here.
- **`feat/rev01-pdf-fidelity`** — current Rev 01 branch off `staging`, 26 commits ahead. PR held pending BGCC alpha sign-off.

New work: cut `feat/<slug>` from `staging` (or current rev branch), PR back.

---

## 3. Stack

- **Backend** (`backend/`): Python 3.11 (3.12 on VPS) · FastAPI · async SQLAlchemy 2.0 · Alembic · PostgreSQL · Redis · WeasyPrint+Jinja2 (legacy) · python-docx + LibreOffice headless (SCA pipeline) · OpenAI GPT-4o · python-jose JWT · bcrypt · aiosmtplib · APScheduler · slowapi · bleach · openpyxl.
- **Frontend** (`frontend/`): React 19 · Vite · TS · Tailwind v4 · TipTap · TanStack Query · axios · react-hook-form · zod · zustand · react-router-dom v7 · lucide-react.
- **Infra**: Hostinger VPS, nginx, supervisord, no Docker. See §10.

---

## 4. Key domain rules (don't violate)

1. Admin fills `[Insert]` fields only — legal boilerplate is never retyped.
2. Every master template change = new version. Old agreements keep FK to the exact version.
3. Appendix is a diff document. Auto-populates from F/C. Admin can show/hide rows + add notes.
4. **Internal review is FLAT/parallel (2026-05-20 change).** On Submit for Review all four reviewer roles (PD, Accounts, OM, GM) see the agreement at once — no hierarchy. Each role either approves or adds a comment. Comments are **non-blocking**: visible to all roles, no bounce to Admin, no chain restart, the commenter's step stays pending. Admin can forward to the subcontractor only once **all four roles have approved** (`all_main_steps_approved` gate in `send_to_subcontractor`). The separate **resolution chain** (OM→GM, after subcontractor comments via `under_bgcc_revision`) is still sequential. (Superseded the old "all returns go to Admin / resubmit restarts the chain from PD" rule for the main review; `return_step`/`resubmit_agreement`/`/workflow/{id}/return` remain for the resolution path.)
5. All reviewers can see/edit all comments; edits write `comment_edit_history`. Only Admin marks `resolved`.
6. No auto-approvals. AI output is a suggestion; human must confirm.
7. Reference format `SAG-{YEAR}-{SITE_NO}-{REF_NO}` (Rev 01 change), editable until GM approval.
8. Subcontractor signs → lock (`is_executed=true`, `current_status=completed`).
9. PDF is always generated, never edited. Regenerate from stored data.
10. Subcontractor is external — never a system user. Contact via email only.

8 statuses: `under_drafting`, `under_internal_review`, `draft_forwarded_to_subcontractor`, `under_subcontractor_review`, `under_subcontractor_signature`, `under_bgcc_revision`, `under_gm_signature`, `completed`. 5 roles: `admin`, `project_director`, `accounts`, `operation_manager`, `gm`. ~15 users.

---

## 5. PDF pipeline

SCA agreement PDF (the main legal doc) is rendered via **python-docx + LibreOffice headless**, NOT WeasyPrint. Master is `backend/masters/sca_master_v1.docx` with `{{F##}}/{{C##}}/{{A##}}` tokens. Tahoma is the body font — installed legally via Microsoft IELPKTH.CAB (see `scripts/install-fonts.sh`). Currency fields auto-formatted by `_format_money` (`MONEY_FIELDS = {F08, C03, C11, A07, A09, A10, A20, A21}`).

WeasyPrint is still used for the deviation report and resolution report only.

**42-page count is content-density dependent** — long admin-entered free text naturally pushes to 43+. Documented in the Rev 01 resolution report.

---

## 6. Outstanding known issues

Most of the original Task 01–14 audit gaps (8 🔴 blockers across Buckets 1–2, plus Buckets 3–4 polish) were resolved over the 2026-04-24 → 2026-05-18 window. **What's still open:**

- **🔴 SMTP not configured on alpha** — comment #25 / Rev 01 item 25. Backend wired, awaits BGCC IT creds in `/var/www/sams/backend/.env`.
- **🟡 Item 30 (Rev 01)** — Step 2 sub-contractor name duplication. Already filtered & reworded; BGCC re-test needed.
- **🟡 Master template UI** — `auto_source_field_id` / `appendix_row_label` / `appendix_clause_ref` / `show_in_appendix` not editable in `FieldCatalog.tsx`.
- **🟡 Resolution steps** share `workflow_steps` table with main chain (no `workflow_kind` column).
- **🟡 Open items requiring BGCC**: subcontractor master content seeding for Form/Conditions HTML (when WeasyPrint pipeline is exercised).
- **🟡 Test coverage**: 33 backend pytest + 13 frontend vitest. No Playwright e2e. One flaky `test_logout_revokes_refresh_token` in full-suite runs (passes in isolation).

The full historical gap register is in git history (`git log -- CLAUDE.md`); restore from commit `74109c3` if needed.

---

## 7. Common commands

**Frontend (`frontend/`):**
```bash
npm install
npm run dev          # Vite, :5173
npm run build        # tsc -b && vite build
npm run lint
npm run test:run     # vitest
```

**Backend (`backend/`):**
```bash
python3.11 -m venv venv && source venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
uvicorn main:app --reload --port 8000
alembic upgrade head
alembic revision --autogenerate -m "<message>"
python scripts/seed_fields.py
pytest -q
```

---

## 8. Git conventions

- Conventional Commits: `feat:` / `fix:` / `chore:` / `docs:` / `refactor:` / `test:` / `perf:` / `build:` / `ci:`. Scope optional.
- Imperative mood, present tense.
- **New commits, never `--amend`** unless asked. **Never** `--no-verify`. Never force-push `main` or `ahmed`.
- Trailer for Claude commits: `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>`
- PRs: `feat/…` → `staging` (or current rev branch). `staging` → `ahmed` decided per session.

---

## 9. Local secrets

`backend/.env` holds **placeholders only**. Real values (Postgres, OpenAI, JWT, SMTP) live per-environment, never committed. Verify with `git diff -- backend/.env` before any env-touching commit.

---

## 10. Live VPS / Deploy

**Alpha URL:** https://76-13-159-24.sslip.io  (switches to `sams.bgcc.ae` once BGCC IT publishes DNS).

**VPS:** Hostinger KVM 1 · Ubuntu 24.04 · `developer@76.13.159.24` · SSH key `~/.ssh/sams_deploy_ed25519`. Postgres 16 (`sams_db` / `sams_user`), Redis 7, nginx + Let's Encrypt (auto-renew 03:00), supervisord (`sams-api`), Python 3.12 venv at `/var/www/sams/backend/venv`, Node 20.20. Daily backup 02:00 → `/backups/sams_*.sql.gz` (30-day retention).

**Deploy:**
```bash
./scripts/deploy-to-vps.sh           # default: staging
./scripts/deploy-to-vps.sh feat/foo  # any local branch
```
Steps: `git archive | ssh | tar -x` → `pip install` → `alembic upgrade head` → `npm install && npm run build` → `supervisorctl restart sams-api` → `systemctl reload nginx`. Tar preserves `.env`, `venv/`, `node_modules/`, `dist/`, `uploads/` (gitignored). ~90–150s wall-clock. **No DB rollback, no blue/green** — brief 3–5s 502 window on restart.

**VPS-only patches still un-backported** (will land in a follow-up commit):
- `nginx/sams.conf` — drop trailing slash on `proxy_pass http://127.0.0.1:8000/` (strips `/api`, all routes 404).
- `backend/requirements.txt` — add `asyncpg` (code uses `postgresql+asyncpg://`).
- `scripts/backup.sh` — `cd /tmp` after `set -euo pipefail`; `DB_USER="${DB_USER:-postgres}"` (peer auth via socket).

**Diagnose / rollback:**
```bash
sudo supervisorctl status sams-api
sudo supervisorctl tail -f sams-api stderr
sudo tail -f /var/log/sams/error.log
ls -lh /backups/
gunzip -c /backups/sams_X.sql.gz | psql -U postgres sams_db
```

KVM 1 is fine for alpha demo; recommend KVM 2+ before BGCC's 15 users hit concurrent PDF generation.

---

## 11. Session log (most recent first)

- **2026-05-20** — **Flat/parallel approval workflow** on `feat/rev01-pdf-fidelity`, deployed to alpha. Replaced the sequential PD→Accounts→OM→GM chain with a flat model: on Submit for Review all four reviewer roles see the agreement at once (no ordering gate). Each role approves or adds a **non-blocking** comment (visible to all, no bounce to Admin, no chain restart, commenter's step stays pending). Admin can forward to subcontractor only once **all four roles approve** (`all_main_steps_approved` gate). No schema change (reuses `WorkflowStep`/`WorkflowComment`). Engine: `get_pending_for_role` drops the prev-approval gate for main-chain steps (resolution chain still sequential); `approve_step` split into resolution handler vs main "all-approved → ready"; new `add_comment` (non-blocking) + `POST /workflow/{step}/comment`; summary now returns comment `author_name`/`author_role`. `send_to_subcontractor` gated. Frontend `WorkflowReview.tsx`: "Return"→"Add Comment", shows comment author+role, parallel-model helper text. Tests rewritten (`test_comment_is_nonblocking`, `test_all_roles_must_approve_before_forwarding`, `test_all_roles_see_agreement_in_parallel`); `test_send_to_subcontractor...` approves all steps via the model layer first. 32/33 pytest (1 documented flake), `tsc -b` clean. See domain rule #4. **Note:** `return_step`/`resubmit_agreement`/`/workflow/{id}/return` kept for the resolution path; `under_bgcc_revision` now only reached via subcontractor-comment resolution, not reviewer returns.
- **2026-05-20** — **BGCC small tweaks** on `feat/rev01-pdf-fidelity`, deployed to alpha. (1) C14 Performance Security Type dropdown option `Company Undated Security Cheque` → `Company Security Cheque` (hard-coded in `FieldInput.tsx`, the only functional source; comment in `seed_fields.py` matched). Data migration `005_security_cheque_label` rewrites existing `agreement_field_values` rows (field_id=C14) from the old literal. **Gotcha:** alembic `version_num` is `varchar(32)` — first revision id `005_rename_security_cheque_option` (33 chars) overflowed and rolled back; shortened to fit. (2) New free-text clause **C15 "Optional Terms"** renders as the last row of the APPENDIX continuation table on page 7 (after Dispute Resolution). New idempotent `scripts/apply_master_c15_patch.py` clones the Dispute-Resolution `<w:tr>` and appends `Optional Terms | (blank) | {{C15}}`; `seed_fields.py` adds the C15 conditions/textarea field (blank clause_number); migration `006_add_c15_optional_terms` inserts it into existing conditions templates (NOT EXISTS guard, mirrors C14/002). **Verification:** render with a sample C15 value → multi-line value on page 7, page count holds at 42; 32/33 pytest (1 documented flake). **Deploy gotcha:** `deploy-to-vps.sh` uses `git archive | tar -x` which never deletes files — a renamed/removed migration resurfaces on the VPS and creates a 2nd alembic head; had to manually `rm` the stale file on the VPS. Latent bug worth patching (sync deletions).
- **2026-05-18** — **BGCC Rev 02 round** on `feat/rev01-pdf-fidelity` (commits `274c866` feat + `eeaa3cd` revert, deployed to alpha). Six items landed: (1) Comms Address Appendix rows wired to `{{A05}}`/`{{A06}}` (5+5 dotted sub-rows collapsed into one row per side); (2) Time-for-Completion + Milestones rows wired to `{{A16}}`/`{{A17}}`/`{{A18}}`; (3) Subcontractor cell + (8) M/s. Microfab body substitutions render bold via new `BOLD_FIELDS = {"F02"}` and a rewritten Pass 1 that emits styled segments instead of dumping everything into run 0; (8) F01/A15 date substitutions split into `[day][superscript suffix][rest]` runs so `"05ᵗʰ May 2026"` renders properly; running header stamp swapped from static `"BGCC P-XXX / SCA#-ZZZ"` to a `{{REFERENCE}}` token resolved at render time against `agreement.reference_number` (body paragraphs P45/P113 + every footer xml's `<wps:txbx>` + `<v:textbox>` legacy copy). Item 11 (3.4(e) page break) reverted per client direction; helper kept as dead code. `scripts/apply_master_rev02_patches.py` is the one-shot reproducible patch; writes a `.pre-rev02.bak` on first run. TOKEN_RE widened to accept alphabetic tokens (`{{REFERENCE}}`); `_iter_header_footer_text_elements` added so substitution reaches textbox content python-docx doesn't expose. **Verification:** demo render → 42 pages, bold + superscript confirmed via OOXML inspection. 32/33 backend pytest (1 documented flake). **Status:** items 1/2/3/8 + reference stamp shipped; 9/10/12/14 already shipped in Rev 01 (need BGCC retest); 4/5/6/13/15 blocked on BGCC clarification.
- **2026-05-16 → 18** — **BGCC Rev 01 round** on `feat/rev01-pdf-fidelity` (26 commits, head `000bb96`). 4 phases shipped: (1) foundations — US Letter, Tahoma install, new reference format, long-date, A-field auto-recompute with `is_manual_override`, Masters help panel; (2) **PDF pipeline pivot** from WeasyPrint+HTML to python-docx + LibreOffice with tokenized master from user's hand-tuned 42-page docx; (3) Document view at `/agreements/:id/document` (admin edits left, PDF iframe right; reviewers see read-only summary); (4) Compare view + clause-level track-changes — migration `004_clause_revisions.py`, OOXML `<w:del>/<w:ins>` markup rendered inline, accept/reject with segregation-of-duties (creator can't self-accept). **Status:** 11 RESOLVED, 13 done in round 1, 1 awaits SMTP (#25), 1 awaits BGCC retest (#30), 6 reference-only. **Verification:** 33 backend pytest + 13 frontend vitest, `tsc -b` clean. Demo agreement `f53587ab-7ed2-4ba1-b3bd-f0b547b8cf79` on alpha with 4 pending + 1 accepted clause revisions. PR to `staging` held pending BGCC sign-off.
- **2026-05-11** — User-feedback round 1 on `staging`. Migration `002_user_feedback_round1.py` (C05/06/07 number→text, new C14 Performance Security Type dropdown, `original_clause_text` on resolution sheets). `DELETE /api/agreements/{id}` (admin, pre-GM only), subcontractor search picker, wizard Back buttons, Step 2 drops F02–F08 dups, Step 4 collapses to inline edit, side-by-side AppendixView in WorkflowReview, per-comment cards in CommentsResolution, en-US number formatting + `money` Jinja filter, BGCC brand block in nav, Edit/Delete extended to `under_internal_review`. 22/22 pytest, 13/13 vitest.
- **2026-05-01** — **Alpha deployed** to Hostinger VPS. Found + patched 3 repo bugs on the VPS only (nginx trailing slash, missing `asyncpg`, backup.sh user/cwd). Added `scripts/deploy-to-vps.sh`. SMTP placeholder by design. See §10.
- **2026-04-24** — Buckets 1 & 2 (8 🔴 blockers) cleared on `staging`: tz-aware `datetime.now(UTC)` in agreement listener, masters route order fix, removed global `SanitizationMiddleware`, Redis-backed refresh-token revocation, full frontend auth layer (zustand store + axios interceptor + Login + RequireAuth + react-router v7), C03 = 10% of F08 + manual-override preservation, AI service `sheet_id`/`agreement_id` unified, resolution rollback + send-to-subcontractor path. Buckets 3 & 4 same day: generic `{{FIELD_ID}}` PDF engine, Appendix Builder UI + endpoints, inline deviation report, root `.gitignore`, `.env.example`, UTF-8 requirements, status filter fixes, audit page_size cap, `docs/launch-runbook.md`. Test infra landed (pytest+pytest-postgresql+fakeredis backend, vitest+@testing-library frontend) — 25 backend + 13 frontend.
- **2026-04-24** — Initial survey + full Task 01–14 static audit. Created `staging` off `ahmed`, added this CLAUDE.md, saved memory index. Key findings vs handover: seed covers all 44 fields (not 27); SanitizationMiddleware destroys HTML globally; no frontend auth; refresh revocation was in-memory; masters route order makes `/fields/reorder` 422; resolution cycle dead-ended after OM/GM.
