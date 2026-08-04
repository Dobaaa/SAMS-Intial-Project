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
2. Every master template change = new version. Old agreements keep FK to the exact version. **⚠️ Still not really true for the SCA docx pipeline** — `Agreement.form_version_id`/`conditions_version_id`/`appendix_version_id` exist but are never consulted by `render_agreement_docx_to_pdf`; every render reads the single live `backend/masters/sca_master_v1.docx`. **Package H (2026-08-04, done) narrows the actual risk**: `generate_agreement_pdf` now refuses to regenerate once `agreement.is_executed` is `True` (`ValueError` → HTTP 400), so a later master-docx edit (Packages F/G) can no longer silently rewrite an already-signed agreement's PDF. One deliberate exception: `resolution_service.record_subcontractor_response`'s auto-regen right after marking an agreement signed (`allow_regenerate_completed=True`) — that's the render that produces the actual final PDF, not a rewrite of one. This is still not true version-pinning — non-executed agreements (under review, with the subcontractor, mid-resolution) are still rendered from whatever the master docx currently looks like.
3. Appendix is a diff document. Auto-populates from F/C. Admin can show/hide rows + add notes.
4. **Internal review is sequential again (2026-08-04 change, Phase 2 Package A — see §13).** Chain order is **Accounts → PD → OM → GM**: `submit_for_review` (`agreement_service.py`) builds the 4 steps in that order, and `_previous_step_approved()` (`workflow_engine.py`) gates both `get_pending_for_role` and `approve_step` so a role only becomes actionable once the prior role in its chain has approved. Applies uniformly to the main chain and the resolution chain (OM→GM, unchanged order). Three reviewer actions: **Approved**, **Approved with comments** (approves + attaches a `WorkflowComment` in one call), **Rejected with comments** (uses `return_step`/`/workflow/{id}/return` — flips the agreement to `under_bgcc_revision`; `resubmit_agreement` then restarts the WHOLE chain from step 1 on resubmit). Admin can forward to the subcontractor only once **all four roles have approved** (`all_main_steps_approved` gate in `send_to_subcontractor`), same as before. (Supersedes the 2026-05-20 flat/parallel model — the old free-standing "Add Comment" non-blocking action was removed from the primary Review Action panel; `add_comment`/`POST /workflow/{step_id}/comment` still backs the per-clause inline comment cells in the Clause/Appendix Review matrices, unchanged.)
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

## 11. Workflow preference (permanent)

After every code change, automatically:
1. Commit (conventional commit, imperative mood, `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>`)
2. Push the current branch to remote (`git push`)
3. Deploy to alpha (`./scripts/deploy-to-vps.sh` — uses the current branch by default)
4. Smoke-test the change live on alpha (2026-08-04 addition) — throwaway `smoketest-*@example.com` users bootstrapped via a one-off script run through the VPS backend venv (SSH), exercised against the real HTTPS API, cleaned up afterward. Direct DB writes to alpha need explicit user sign-off each session (the permission classifier blocks them by default) — ask once if not already authorized. Never use real employee credentials for this.

No confirmation needed unless the change is destructive to the DB (e.g. dropping columns, irreversible data migrations).

---

## 12. Session log (most recent first)

- **2026-08-04** — **Package C verified live on alpha**, including a real visual check (not just the unit tests): rendered a page from the actual `GET /pdf/{id}/preview/gm-highlighted` PDF to PNG (`pdftoppm`) and scanned pixels — confirmed real red text at the exact location of a substituted field value ("RedTestCo Subcontractor"), 250 red-ish pixels found. Then generated the **standard** PDF for the same agreement via the normal `/pdf/{id}/generate` + `/preview` path and re-ran the same pixel scan: **zero** red pixels — confirms the critical safety property (`highlight_admin_content` default-off) holds on a real render, not just in code review. Also confirmed role gating: non-GM (admin) gets 403 on the highlighted endpoint, GM gets 200. Cleaned up (agreement/project/both throwaway users; both logins 401 afterward).
- **2026-08-04** — **Phase 2 Package C shipped** on `staging` (commit `cc7f1ca`), pending deploy + live verification. New `highlight_admin_content` render mode: `_add_rpr_style`/`_emit_styled_run` gain a `color` param (`<w:color w:val="FF0000"/>` on the run's rPr); `_substitute_in_paragraph` colors only the substituted field-value runs (never the boilerplate between tokens); threaded through `render_agreement_docx_to_pdf`, default `False`. New `GET /pdf/{id}/preview/gm-highlighted`, gated `require_role(RoleEnum.gm)`, modeled on the existing `with_changes` preview endpoint. Known limitation: Pass 2 (tokens inside pending track-change spans) has no run isolation, so those values won't render red — documented, not blocking. New `backend/tests/test_docx_pdf_service.py`, direct unit tests on `_substitute_in_paragraph` (no DB/HTTP/LibreOffice needed). 41/42 backend pytest (1 pre-existing flake), `tsc -b` clean — no frontend work in this package (GM Dashboard consuming this endpoint is Package B).
- **2026-08-04** — **Corrected Package F verified live on alpha**: migration `021_show_a15_again` applied cleanly. Confirmed `GET /workflow/agreements/{id}/appendix-fields` returns A15 again (`is_required: false`, unchanged). Real render with A15 left blank: Appendix Table 3 now shows "Commencement Date | 4.1 | The date specified in the written instruction issued by the Main Contractor directing the Subcontractor to commence the Subcontract Works" — no longer blank. Entered `A15=2026-09-01` and regenerated: renders as "01st September 2026" (long-date superscript formatting via `DATE_FIELDS` still works), and clause 4.3's original sentence is back verbatim ("...within {{C08}} from the Commencement Date or by {{A17}}."). Cleaned up (agreement/project/user; throwaway login 401s).
- **2026-08-04** — **Package F corrected** on `staging` (commit `4684b4b`), deployed + verified live (see entry above). User caught a misreading of req 3: "no longer required" meant A15 (Commencement Date) should become *optional*, not be deleted from the appendix. It was already `is_required=False` at the model level (no requiredness change was ever actually needed), so the real fix is a fallback: when A15 is left blank, the appendix cell now shows clause 4.1's own definition text rather than rendering empty. Reverted the master docx, `DATE_FIELDS`, and `AgreementCreate.tsx`'s appendix filter to byte-identical pre-Package-F state (verified via `git diff` against the parent commit); deleted the now-wrong `apply_master_remove_commencement_date_patch.py`; added migration `021_show_a15_again` reversing `020_hide_a15` (kept both in history, linear, per this repo's migration convention — never edit/delete an already-deployed one). New `pdf_service._build_value_map()` centralizes value-map construction (field values + `{{REFERENCE}}` + the A15 fallback + percentage injection) so `generate_agreement_pdf` and the `with_changes` preview endpoint — which had silently duplicated this logic — can't drift out of sync again. Confirmed no real (non-throwaway) agreement was created on alpha during the ~hours-long window A15 was hidden, so no retroactive `AppendixConfig` fix was needed. New tests `test_a15_fallback_when_blank`/`test_a15_value_preserved_when_entered` via a `captured_docx_values` fixture. 38/39 backend pytest (1 pre-existing flake), `tsc -b` clean, single alembic head.
- **2026-08-04** — **Package F verified live on alpha**: migration `020_hide_a15` applied cleanly on deploy. Created a real throwaway agreement, confirmed `GET /workflow/agreements/{id}/appendix-fields` no longer returns A15, generated an actual PDF via LibreOffice and extracted its text — Appendix Table 3 jumps straight from the retention rows to "Time for Completion" (Commencement Date row gone), the clause-4.3 sentence reads "...within [C08] or by [A17]." (tokens empty since no field values were entered — expected for a throwaway agreement), and clause 4.1's own Commencement Date definition + the insurance clause (~para 640) render fully intact, unchanged. Cleaned up the agreement/project/throwaway user (login now 401s); one generated PDF file on disk couldn't be deleted (permission denied under the `developer` SSH user) — harmless orphaned artifact, not a Package F issue, matches the app's pre-existing behavior of not garbage-collecting `PDFOutput` files on agreement delete.
- **2026-08-04** — **Phase 2 Package F shipped** on `staging` (commit `11915d3`), pending deploy + live verification. Removed Commencement Date per BGCC req 3, scoped minimal: `apply_master_remove_commencement_date_patch.py` deletes Appendix Table 3's `{{A15}}` row (uniquely labeled, no A05-style row-repurposing needed) and rewrites the one clause-4.3 sentence that anchored the completion deadline to it (`"...within {{C08}} from the Commencement Date or by {{A17}}."` → `"...within {{C08}} or by {{A17}}."`). Clause 4.1's own Commencement Date definition and the insurance-submission clause (~para 640) are untouched — neither reads `{{A15}}`. Migration `020_hide_a15` sets `show_in_appendix=False` (existing agreements' stored A15 data/PDFs untouched). `docx_pdf_service.py` `DATE_FIELDS` drops `A15`. `AgreementCreate.tsx`'s `manualAppendixFields` filter excludes A15 (same pattern as the existing A05 exclusion — that wizard step isn't driven by `show_in_appendix`). Req 2 (Time for Completion in days) needed no work — C08/A16/A17 were already text fields. 36/37 backend pytest (1 pre-existing flake), `tsc -b` clean. **Gotcha:** `backend/services/docx_pdf_service.py` had an unrelated pre-existing uncommitted 2-line change (a defensive `hasattr` guard in `_iter_header_footer_text_elements`) sitting in the working tree before this session — temporarily reverted it, committed only the `DATE_FIELDS` change, then restored it so it stays exactly as the user left it, uncommitted.
- **2026-08-04** — **Package H verified live on alpha** via a real (non-stubbed) smoke test: LibreOffice on the VPS actually rendered PDFs. Bootstrapped one throwaway `smoketest-h-admin@example.com` user, created a test agreement, marked it signed (`PATCH .../subcontractor-response {"response_type":"signed"}`) — confirmed the `allow_regenerate_completed=True` auto-regen still produces a real 18-page PDF despite `is_executed=True`. Then confirmed `POST /pdf/{id}/generate` on that now-completed agreement returns 400 with the exact guard message, `/preview` keeps serving the same unaffected PDF afterward, and (pre-existing, sanity-checked) field edits are still separately blocked with "Agreement is locked after execution". Cleaned up (agreement/project/user + VPS scratch files + generated upload dir); throwaway login 401s afterward. **New standing practice**: from here on, smoke-test each package live on alpha right after deploying it, before waiting for the go-ahead on the next package. Also flagged (not fixed): `backend/scripts/seed_alpha_users_projects.py` has real plaintext BGCC employee passwords, currently uncommitted — do not commit as-is, do not use for testing.
- **2026-08-04** — **Phase 2 Package H shipped** on `staging` (commit `22ead74`), deployed to alpha. `generate_agreement_pdf` (`pdf_service.py`) now raises `ValueError` (→ HTTP 400 via the existing router pattern) when `agreement.is_executed` is `True`, unless the caller passes `allow_regenerate_completed=True` — the one legitimate exception, used by `resolution_service.record_subcontractor_response`'s auto-regen right after marking an agreement signed (produces the actual final watermark-stripped PDF, not a rewrite). `AgreementDocument.tsx`'s two admin "regenerate" actions now surface the backend error detail via toast. New tests `test_regenerate_pdf_blocked_after_signed`/`test_regenerate_pdf_allowed_before_signing` (docx render stubbed via `patched_docx_render` fixture — the guard fires before any LibreOffice call, so no rendering infra needed in tests). 36/37 backend pytest (1 pre-existing flake), `tsc -b` clean. See corrected rule #2 above.
- **2026-08-04** — **Package A verified live on alpha** via a manual smoke test (not just local pytest): SSH-bootstrapped 5 throwaway `smoketest-*@example.com` users directly in the alpha DB (blocked once by the permission classifier for being a live-DB write; re-authorized by the user), then drove the real HTTPS API end-to-end — confirmed chain order Accounts(1)→PD(2)→OM(3)→GM(4) on submit, PD approving before Accounts returns 400 and is absent from `/workflow/pending`, in-order approval succeeds, GM "Approved with comments" attaches a comment in the same call, and `send-to-subcontractor` succeeds only once all four have approved. Cleaned up the throwaway agreement/project/users and VPS scratch files afterward (had to delete in FK order: `Agreement` → `Project` → `User`, `WorkflowStep`/`WorkflowComment` cascade off the agreement). Real employee credentials in the uncommitted `seed_alpha_users_projects.py` were never used.
- **2026-08-04** — **Phase 2 Package A shipped** on `staging` (commit `734c69d`), deployed to alpha. Sequential Accounts→PD→OM→GM review chain + 3-button reviewer actions — see updated domain rule #4 above for the mechanics. `_previous_step_approved()` new in `workflow_engine.py`, replacing the resolution-only order gate; `approve_step` now takes optional `comment_text`/`clause_reference` for "Approved with comments"; router adds `ApprovePayload`. `WorkflowReview.tsx` Review Action panel rewritten: 3 buttons + a locked "Waiting for {role} to approve" state when `myStepUnlocked` is false (derived client-side, mirrors the backend chain-scoping logic). Rewrote `test_all_roles_must_approve_before_forwarding`→`test_all_roles_must_approve_in_order_before_forwarding`, `test_all_roles_see_agreement_in_parallel`→`test_only_first_in_chain_sees_agreement_initially`, plus new `test_approve_with_comments_records_comment`/`test_reject_with_comments_returns_step`; fixed `test_submit_creates_four_workflow_steps`'s stale PD-first order assertion. 34/35 backend pytest (1 pre-existing documented flake), `tsc -b` clean, frontend lint unchanged (8 pre-existing errors, none new). **Not yet done:** Packages H, F, G, C, D, B, E (see below) — Package H (regen guard) should land before any master-docx edit (F/G).
- **2026-08-04** — **Phase 2 planned** (not yet built — see §13). Read BGCC's new wishlist, explored the workflow engine/PDF pipeline/archive UI in parallel, resolved 4 ambiguities with the user (QS = drafting Admin not a new role; rejection restarts whole chain; archive bucket 2 approximated via existing statuses; GM fully redirects to new dashboard) plus 3 more from a follow-up correctness check (bucket 4 status-only; Commencement Date removal scoped minimal; sequential ordering guard applies to both chains). Discovered along the way: rule #2's "old agreements keep FK to exact version" isn't actually implemented for the docx pipeline (see corrected rule #2 above) — added Package H to close that gap before any master-docx edits ship. Plan approved, saved to `/home/seif/.claude/plans/home-seif-downloads-approval-process-sh-delegated-honey.md`.
- **2026-06-02** — **C02 inline in clause 3.3 + remove yellow highlights** on `staging`, deployed to alpha. `apply_master_c02_inline_and_dehighlight_patch.py`: (1) Replaced the dots `………………` in "The Quantities mentioned in this Subcontract Agreement is ………………" with `{{C02}}` so the contract type renders inline; deleted the redundant standalone highlighted `{{C02}}` paragraph that was appearing on a separate line above the sentence. (2) Removed all 62 `<w:highlight>` elements from the entire document (body, tables, headers/footers).
- **2026-06-02** — **Four improvements** on `staging`, deployed to alpha. (1) C02/A08 renamed from "Subcontract Quantities Type" → "Contract Type" (migration `017_rename_c02`). (2) C15 long-content table-break fix: `_split_paras_in_cell` now strips `keepLines`/`keepNext` from every generated paragraph so cells with 40+ bullet points can break across pages in LibreOffice instead of overflowing. (3) Email paused: `EMAIL_PAUSED` config flag added (default `false`); **VPS `.env` needs `EMAIL_PAUSED=true` added manually** — deploy script cannot write `.env`. (4) All email notifications now include Project, Subcontractor, and Scope of Work (C01 truncated to 300 chars) in the body via `_get_email_context(db, agreement)` helper. 32/33 pytest (1 flake), `tsc -b` clean.
- **2026-06-02** — **Appendix display polish** on `staging`, deployed to alpha. Five changes via `apply_master_appendix_polish_patch.py` + migration `016_appendix_polish`: (1) Removed "Maximum Liquidated Damages" row (`{{A21_DISPLAY}}`) from Table 4. (2) Rate Of Liquidated Damages value cell: `{{C11}}` → `AED {{C11}} per day`. (3) Subcontract Price value cell (Table 3): `{{F08}}` → `AED {{F08}}`. (4) Insurance Policies value cell: `{{A22}}` → `{{A22}} days`, plus fixed missing `<w:w val='105'/>` run-property that caused font rendering inconsistency. (5) Defects Liability Period (C10/A19) changed from `number` to `text` input_type so admin can enter "12 months" / "365 days". 32/33 pytest (1 flake), `tsc -b` clean.
- **2026-06-02** — **Resubmit email + sticky clause headers + AI grammar check** on `staging`, deployed to alpha. (1) Email sent to all project users when Admin resubmits agreement after editing (subject "Agreement Resubmitted for Review"), with project/subcontractor/scope context. (2) Clause Review and Appendix Review table headers are now sticky on scroll — outer `div` changed to `overflow-auto max-h-[70vh]`, `<thead>` gets `sticky top-0 z-10`. (3) New "Grammar & Wording" button in AI Review tab hits `POST /ai/{id}/grammar`; `check_grammar_wording` service collects all text/textarea field values and asks the AI to flag grammar, spelling, punctuation, clarity, and legal-wording issues; results rendered via new `GrammarList` component with colour-coded issue-type badges, original vs suggested text diff; `grammar` added to `ReviewTypeEnum` + migration `018_grammar_review_type` (`ALTER TYPE review_type_enum ADD VALUE 'grammar'`). 32/33 pytest (1 documented flake), `tsc -b` clean.
- **2026-06-02** — **Remove A05 (Main Contractor address) from appendix and Step 1 wizard** on `staging`, deployed to alpha. The "Communications Address for Serving of the Notices" appendix section now shows only The Subcontractor Address (A06). `apply_master_remove_a05_row_patch.py` repurposes the A05 row's value cell with Subcontractor content then deletes the redundant A06 row (avoids python-docx label corruption that occurs when deleting the first of two adjacent same-label rows). Migration `015_hide_a05` sets `show_in_appendix=False` for A05; `AgreementCreate.tsx` excludes A05 from `manualAppendixFields` filter. Milestone table tokens (A24/A25/A26) also re-applied via `apply_master_milestone_table_patch.py` (docx was restored from backup during A05 debugging). 32/33 pytest (1 documented flake), `tsc -b` clean.
- **2026-06-02** — **General comments surfaced in Clause Review tab** on `staging`, deployed to alpha. Root cause of badge/UI count mismatch: comments submitted without a `clause_reference` (general comments) were invisible in the Clause Review matrix — they only appeared in the Summary tab's "All Comments" panel. Fix: added a highlighted amber "General Comments (N)" section below the matrix in the Clause Review tab. Confirmed via production DB query: agreement SAG-BGCC-QS-2026-313-SXX had 5 open comments, 1 with no clause_reference (OM general comment) was the missing one.
- **2026-06-02** — **Dashboard comment badge scoped to Workflow Review roles** on `staging`, deployed to alpha. The open-comment badge next to each reference number now counts only unresolved comments from main-chain steps (PD / Accounts / OM / GM). Resolution-chain comments ("Resolution - Operation Manager" / "Resolution - General Manager") are excluded via a `JOIN workflow_steps` + `NOT IN RESOLUTION_STEP_NAMES` filter in `reports.py`. Matches exactly what the Workflow Review page shows.
- **2026-06-02** — **Dashboard comment-count live refresh** on `staging`, deployed to alpha. The open-comment-count badge next to each agreement's reference number now stays current automatically: `Dashboard.tsx` polls `/reports/dashboard/agreements` every 30 s via a `useCallback`+`setInterval` pair (re-registers when any filter changes). Poll is silent — no error toast on background failure. Filters (status/reference/date) are captured correctly via `useCallback` deps so stale-closure is not an issue. `tsc -b` clean.
- **2026-06-02** — **A24/A25/A26 material-submission and shop-drawing fields** on `staging`, deployed to alpha. Added three new text-input fields that render inline in the page-22 milestone table (Table 5) under "b) The Subcontractor shall complete the following Milestones": "Start of Material Submission" (A24), "Complete all Material Submission" (A25), "Start of Submission of Shop Drawings" (A26). `{{A24}}`/`{{A25}}`/`{{A26}}` tokens wired into Table 5's "Time for Completion" cells via `scripts/apply_master_milestone_table_patch.py` (also removes any stale A24/A25/A26 rows from Table 3 appendix summary; idempotent). Fields have `show_in_appendix=False` — admin enters values in AppendixBuilder, they render in the milestone table, not as appendix summary rows. Migration `013_material_fields` adds the DB fields; `014_milestone_table_tokens` sets `show_in_appendix=False`. **Gotcha (recurring):** alembic `version_num` is `varchar(32)` — keep revision IDs ≤ 32 chars. 32/33 pytest (1 documented flake), `tsc -b` clean.
- **2026-05-20** — **Predefined projects + wizard autofill** on `feat/rev01-pdf-fidelity`, deployed to alpha. From BGCC's `Project Details.xlsx`: seeded 8 fixed projects and added a Step-1 **project dropdown** that autofills name / site no / location / employer / engineer / reference and locks those fields; "Others" clears them for manual entry. Manually-entered "Others" projects are saved to the `projects` table on draft creation (existing dedup by `project_code`). Added nullable `projects.reference` column. Migration `007_predefined_projects` adds the column + seeds the 8 projects (`ON CONFLICT (project_code) DO NOTHING` — note: avoid reusing a named bind param twice under asyncpg, it raises `AmbiguousParameterError`). New `GET /api/projects/` (projects_router) feeds the dropdown; `ProjectPayload.reference` added; create payload sends `project.reference`. 32/33 pytest (1 flake), `tsc -b` clean. **DEFERRED (Task 2):** the same xlsx lists per-project users (QS / SR.QS / PD-PM / ACCOUNTS / OM / GM columns) + a 20-row master user list (rows 11–31) — "users attached to each project" is a follow-up task, not yet started.
- **2026-05-20** — **Flat/parallel approval workflow** on `feat/rev01-pdf-fidelity`, deployed to alpha. Replaced the sequential PD→Accounts→OM→GM chain with a flat model: on Submit for Review all four reviewer roles see the agreement at once (no ordering gate). Each role approves or adds a **non-blocking** comment (visible to all, no bounce to Admin, no chain restart, commenter's step stays pending). Admin can forward to subcontractor only once **all four roles approve** (`all_main_steps_approved` gate). No schema change (reuses `WorkflowStep`/`WorkflowComment`). Engine: `get_pending_for_role` drops the prev-approval gate for main-chain steps (resolution chain still sequential); `approve_step` split into resolution handler vs main "all-approved → ready"; new `add_comment` (non-blocking) + `POST /workflow/{step}/comment`; summary now returns comment `author_name`/`author_role`. `send_to_subcontractor` gated. Frontend `WorkflowReview.tsx`: "Return"→"Add Comment", shows comment author+role, parallel-model helper text. Tests rewritten (`test_comment_is_nonblocking`, `test_all_roles_must_approve_before_forwarding`, `test_all_roles_see_agreement_in_parallel`); `test_send_to_subcontractor...` approves all steps via the model layer first. 32/33 pytest (1 documented flake), `tsc -b` clean. See domain rule #4. **Note:** `return_step`/`resubmit_agreement`/`/workflow/{id}/return` kept for the resolution path; `under_bgcc_revision` now only reached via subcontractor-comment resolution, not reviewer returns.
- **2026-05-20** — **BGCC small tweaks** on `feat/rev01-pdf-fidelity`, deployed to alpha. (1) C14 Performance Security Type dropdown option `Company Undated Security Cheque` → `Company Security Cheque` (hard-coded in `FieldInput.tsx`, the only functional source; comment in `seed_fields.py` matched). Data migration `005_security_cheque_label` rewrites existing `agreement_field_values` rows (field_id=C14) from the old literal. **Gotcha:** alembic `version_num` is `varchar(32)` — first revision id `005_rename_security_cheque_option` (33 chars) overflowed and rolled back; shortened to fit. (2) New free-text clause **C15 "Optional Terms"** renders as the last row of the APPENDIX continuation table on page 7 (after Dispute Resolution). New idempotent `scripts/apply_master_c15_patch.py` clones the Dispute-Resolution `<w:tr>` and appends `Optional Terms | (blank) | {{C15}}`; `seed_fields.py` adds the C15 conditions/textarea field (blank clause_number); migration `006_add_c15_optional_terms` inserts it into existing conditions templates (NOT EXISTS guard, mirrors C14/002). **Verification:** render with a sample C15 value → multi-line value on page 7, page count holds at 42; 32/33 pytest (1 documented flake). **Deploy gotcha:** `deploy-to-vps.sh` uses `git archive | tar -x` which never deletes files — a renamed/removed migration resurfaces on the VPS and creates a 2nd alembic head; had to manually `rm` the stale file on the VPS. Latent bug worth patching (sync deletions).
- **2026-05-18** — **BGCC Rev 02 round** on `feat/rev01-pdf-fidelity` (commits `274c866` feat + `eeaa3cd` revert, deployed to alpha). Six items landed: (1) Comms Address Appendix rows wired to `{{A05}}`/`{{A06}}` (5+5 dotted sub-rows collapsed into one row per side); (2) Time-for-Completion + Milestones rows wired to `{{A16}}`/`{{A17}}`/`{{A18}}`; (3) Subcontractor cell + (8) M/s. Microfab body substitutions render bold via new `BOLD_FIELDS = {"F02"}` and a rewritten Pass 1 that emits styled segments instead of dumping everything into run 0; (8) F01/A15 date substitutions split into `[day][superscript suffix][rest]` runs so `"05ᵗʰ May 2026"` renders properly; running header stamp swapped from static `"BGCC P-XXX / SCA#-ZZZ"` to a `{{REFERENCE}}` token resolved at render time against `agreement.reference_number` (body paragraphs P45/P113 + every footer xml's `<wps:txbx>` + `<v:textbox>` legacy copy). Item 11 (3.4(e) page break) reverted per client direction; helper kept as dead code. `scripts/apply_master_rev02_patches.py` is the one-shot reproducible patch; writes a `.pre-rev02.bak` on first run. TOKEN_RE widened to accept alphabetic tokens (`{{REFERENCE}}`); `_iter_header_footer_text_elements` added so substitution reaches textbox content python-docx doesn't expose. **Verification:** demo render → 42 pages, bold + superscript confirmed via OOXML inspection. 32/33 backend pytest (1 documented flake). **Status:** items 1/2/3/8 + reference stamp shipped; 9/10/12/14 already shipped in Rev 01 (need BGCC retest); 4/5/6/13/15 blocked on BGCC clarification.
- **2026-05-16 → 18** — **BGCC Rev 01 round** on `feat/rev01-pdf-fidelity` (26 commits, head `000bb96`). 4 phases shipped: (1) foundations — US Letter, Tahoma install, new reference format, long-date, A-field auto-recompute with `is_manual_override`, Masters help panel; (2) **PDF pipeline pivot** from WeasyPrint+HTML to python-docx + LibreOffice with tokenized master from user's hand-tuned 42-page docx; (3) Document view at `/agreements/:id/document` (admin edits left, PDF iframe right; reviewers see read-only summary); (4) Compare view + clause-level track-changes — migration `004_clause_revisions.py`, OOXML `<w:del>/<w:ins>` markup rendered inline, accept/reject with segregation-of-duties (creator can't self-accept). **Status:** 11 RESOLVED, 13 done in round 1, 1 awaits SMTP (#25), 1 awaits BGCC retest (#30), 6 reference-only. **Verification:** 33 backend pytest + 13 frontend vitest, `tsc -b` clean. Demo agreement `f53587ab-7ed2-4ba1-b3bd-f0b547b8cf79` on alpha with 4 pending + 1 accepted clause revisions. PR to `staging` held pending BGCC sign-off.
- **2026-05-11** — User-feedback round 1 on `staging`. Migration `002_user_feedback_round1.py` (C05/06/07 number→text, new C14 Performance Security Type dropdown, `original_clause_text` on resolution sheets). `DELETE /api/agreements/{id}` (admin, pre-GM only), subcontractor search picker, wizard Back buttons, Step 2 drops F02–F08 dups, Step 4 collapses to inline edit, side-by-side AppendixView in WorkflowReview, per-comment cards in CommentsResolution, en-US number formatting + `money` Jinja filter, BGCC brand block in nav, Edit/Delete extended to `under_internal_review`. 22/22 pytest, 13/13 vitest.
- **2026-05-01** — **Alpha deployed** to Hostinger VPS. Found + patched 3 repo bugs on the VPS only (nginx trailing slash, missing `asyncpg`, backup.sh user/cwd). Added `scripts/deploy-to-vps.sh`. SMTP placeholder by design. See §10.
- **2026-04-24** — Buckets 1 & 2 (8 🔴 blockers) cleared on `staging`: tz-aware `datetime.now(UTC)` in agreement listener, masters route order fix, removed global `SanitizationMiddleware`, Redis-backed refresh-token revocation, full frontend auth layer (zustand store + axios interceptor + Login + RequireAuth + react-router v7), C03 = 10% of F08 + manual-override preservation, AI service `sheet_id`/`agreement_id` unified, resolution rollback + send-to-subcontractor path. Buckets 3 & 4 same day: generic `{{FIELD_ID}}` PDF engine, Appendix Builder UI + endpoints, inline deviation report, root `.gitignore`, `.env.example`, UTF-8 requirements, status filter fixes, audit page_size cap, `docs/launch-runbook.md`. Test infra landed (pytest+pytest-postgresql+fakeredis backend, vitest+@testing-library frontend) — 25 backend + 13 frontend.
- **2026-04-24** — Initial survey + full Task 01–14 static audit. Created `staging` off `ahmed`, added this CLAUDE.md, saved memory index. Key findings vs handover: seed covers all 44 fields (not 27); SanitizationMiddleware destroys HTML globally; no frontend auth; refresh revocation was in-memory; masters route order makes `/fields/reorder` 422; resolution cycle dead-ended after OM/GM.

---

## 13. Phase 2 — in progress

BGCC's Phase 2 wishlist (`~/Downloads/Approval process shall be step by step .md`, 14 items) has a plan approved 2026-08-04. Full plan with file:line references: `/home/seif/.claude/plans/home-seif-downloads-approval-process-sh-delegated-honey.md`.

**Deferred, not in this phase:** mobile app + push notifications (item 4), e-signature portal (item 5), and the mobile-only "push notification opens Compare page" sub-item (6.2).

**In scope — 8 work packages, build order A→H→F/G→C→D→B→E:**
- ✅ **A** (DONE, 2026-08-04, `staging` commit `734c69d`, deployed to alpha) — Reversed §4 rule #4 back to sequential: chain reorder to Accounts→PD→OM→GM, real ordering guard in `approve_step` (the flat model had none), 3-button reviewer UI (Approved / Approved with comments / Rejected with comments) replacing the old Approve+Comment pair, wiring the already-built-but-previously-unused `return_step`/`/workflow/{id}/return` into the frontend. "QS" in "Admin/QS→Accounts..." = the drafting Admin, not a new role — the dormant `quality_surveyor` DB role stays unused.
- ✅ **H** (DONE, 2026-08-04, `staging` commit `22ead74`) — Guard in `generate_agreement_pdf` blocking PDF regeneration for completed/executed agreements (closes the version-pinning gap noted in §4 rule #2). Landed before F/G, as planned.
- ✅ **F** (DONE, 2026-08-04, corrected in `staging` commit `4684b4b` — see session log) — Time-for-Completion already satisfied "in days" (C08/A16/A17 were already text fields, no work needed there). Commencement Date (A15) **stays in the appendix**, unchanged, already optional (`is_required=False`) — the client's "no longer required" meant optional, not deleted (initial commit `11915d3` misread this and removed the field entirely; reverted). When A15 is left blank, the appendix cell now falls back to clause 4.1's own definition text instead of rendering empty (`pdf_service._build_value_map`, new, also fixes a latent inconsistency where the Compare view's `with_changes` preview built its own separate value-map).
- **G** — Payment/retention clause wording (C04 advance-payment release condition, C05 progress payments, C06/C07 retention) — genuinely new legal text (PDC + Engineer's Certificate mechanism), not currently present anywhere in the master; **blocked on client sign-off of exact wording** before scripting.
- ✅ **C** (DONE, 2026-08-04, `staging` commit `cc7f1ca`) — Red-highlight admin-entered content in a new GM-only "View PDF" render mode (`highlight_admin_content` flag on `render_agreement_docx_to_pdf`, default off — standard/archived PDF never changes). New `GET /pdf/{id}/preview/gm-highlighted`, gm-only. Consumed by Package B's GM Dashboard (not yet built).
- **D** — New simple 3-column Compare table (Original/Revised+Amendment/Generated-by) for GM Portal, reusing the existing `agreement_clause_revisions` data — does **not** touch the existing `AgreementCompare.tsx`/`ClauseRevisionsPanel.tsx` used elsewhere.
- **B** — New restricted GM Dashboard (5 columns, View PDF + Compare only); GM's nav fully redirects here away from the general `ReviewerDashboard`.
- **E** — Archive tab needs more than an extension: today's `/archive/projects/{id}` and `/archive/subcontractors/{id}` both *require* a UUID typed into a text box — there's no "list everything" mode. New `GET /archive/agreements` endpoint + near-total `Archive.tsx` rewrite for the flat list, 4 status-derived buckets, and the 6 requested filters.
- **Item 11 (Advance Payment 10%)** — already implemented, zero work (`agreement_service.py` C03 = 10% of F08).

Once packages start landing, log each here per the usual session-log convention and flip §4 rule #4 back to describing sequential review as current fact (not planned).
