# SAMS Backlog

Snapshot of what's still open as of **2026-05-02**, after the alpha environment went live at https://76-13-159-24.sslip.io.

The original audit lived in `CLAUDE.md` §6; this file extracts only what is still open today, plus items uncovered during deploy and the e2e flow test. Severity legend: 🔴 pre-production blocker · 🟡 functional bug or spec gap · 🟢 polish/UX · ⚙️ operations/infra.

---

## 🔴 Pre-production blockers

Must be done before BGCC's 15 users get access.

| # | Item | Effort | Notes |
|---|---|---|---|
| 1 | Upload real BGCC master template HTML for `form` / `conditions` / `appendix` | ~1 day | Currently 3 placeholder rows; PDFs render bare until replaced. Use `{{F02}}`, `{{C03}}`, etc. as tokens. |
| 2 | Wire real Hostinger SMTP credentials | ~30 min | Email path is best-effort no-op today; reviewers and the subcontractor get no notifications. |
| 3 | Publish DNS for `sams.bgcc.ae` → `76.13.159.24`, then `certbot --expand -d sams.bgcc.ae` | 15 min ours + BGCC IT | sslip.io is fine for alpha but unprofessional for prod. |
| 4 | Upgrade Hostinger plan to KVM 2 (or 4) | 15 min | KVM 1 will queue PDF generations under concurrent load. |
| 5 | Real user roster — replace the 5 test users with the 15 BGCC users + force password resets | ~1 hr | Temp `change-me-*` passwords sitting on prod is unacceptable post-alpha. |
| 6 | Disable SSH password auth + drop the password used in early alpha | 5 min | Key auth confirmed working. |

---

## 🟡 Functional bugs / spec gaps

These are real defects against the spec or against expected UX, but the system functions today without them.

### Medium — should ship in the pre-prod sprint

| # | Item | Where |
|---|---|---|
| 7 | `auto_source_field_id` declared on `MasterField` but **not consumed by services** — admin can't add a new auto-populating field via the UI; the F→A/C cascade is hardcoded. | `agreement_service.update_agreement_fields` |
| 8 | C09 milestones renders as a **textarea**, not a real table — no row-data storage model exists. | spec says `input_type=table` but no schema for rows |
| 9 | `pdf_outputs.pdf_type` always stays `draft` — never flips to `final` or `executed` despite the 3-value enum. | `pdf_service` |
| 10 | Deviation report **Risk column hardcoded to "Pending AI"** — never wired to `ai_service.detect_risks`. | `deviation_service` |
| 11 | GM approval doesn't auto-advance the agreement status — leaves `under_internal_review`; admin still has to click "Send to subcontractor". | `workflow_engine.approve_step` (GM branch) |
| 12 | Archive download endpoint **404s on draft PDFs** — only returns `final` / `executed`. | `routers/archive.py` |
| 13 | Archive page UI **requires pasting raw UUIDs** for project / subcontractor filter (no picker dropdown). | `Archive.tsx` |
| 14 | `signed_scan_path` accepted in the subcontractor-response payload but **never stored** — no column, no upload endpoint. | `models/agreement.py`, `resolution_service` |
| 15 | Resolution workflow steps share the `workflow_steps` table with the main chain — no `workflow_kind` discriminator, so pending lists for OM/GM mix kinds. | needs schema migration |

### Low — defer to post-launch

| # | Item | Where |
|---|---|---|
| 16 | `LEGACY_TOKEN_MAP` still present in `pdf_service` as a backward-compat hack — should be removed once #1 is done. | `services/pdf_service.py` |
| 17 | Auto-population rules duplicated between frontend `AgreementCreate.tsx` and backend `update_agreement_fields` — drift risk. | both files |
| 18 | Step 5 "modified" amber highlight compares raw strings (`"10"` vs `10` reads as different). | `AgreementCreate.tsx` |
| 19 | Deviation report rows sort lexicographically — `"10"` < `"2"`. | `deviation_service.rows.sort` |
| 20 | `change_type` on the deviation report compares raw strings — numeric default `"10% of F08"` vs entered `"5000"` always reads as "Modified". | `deviation_service` |
| 21 | `PUT /comments/{id}` has no role restriction beyond `get_current_user` — any logged-in user can edit any comment (matches spec literally, but worth flagging). | `routers/comments.py` |
| 22 | No validation of `clause_reference` against `master_fields`. | `routers/comments.py` |
| 23 | `FieldCatalog.tsx` edit mode doesn't expose `auto_source_field_id`, `appendix_row_label`, `appendix_clause_ref`, `show_in_appendix`. | `FieldCatalog.tsx` |
| 24 | `_chat_json` doesn't request `response_format={"type":"json_object"}`; relies on prompt + regex fallback. | `services/ai_service.py` |
| 25 | No try/except around AI client calls — rate limits or timeouts will crash the request. | `services/ai_service.py` |
| 26 | bcrypt 4.x / passlib 1.7.4 emits noisy `(trapped) error reading bcrypt version` warning on every hash — pin bcrypt 3.x or upgrade passlib. | requirements |

---

## 🟢 Polish / UX gaps

| # | Item |
|---|---|
| 27 | No "forgot password" flow — admin manually edits user to reset. |
| 28 | No password strength validation on create/update. |
| 29 | No template-delete / archive endpoint; no "Legal Editor" role (spec marked optional). |
| 30 | 4 pre-created pending workflow steps visible to no-one is a strange UX (serial gating is implicit). |
| 31 | `CommentThread` component exists but isn't wired into `WorkflowReview.tsx` (which renders its own simpler list). |
| 32 | `react-hook-form` + `zod` installed but not used — no per-step form validation in the wizard. |
| 33 | BGCC logo URL is blank in PDF templates. |
| 34 | No RTL support despite Dubai context. |
| 35 | `/api/health` is at root (`/health`), not under `/api` — confusing path; we hit this during deploy. |

---

## ⚙️ Operations / Infra

| # | Item |
|---|---|
| 36 | No CI/CD — `./scripts/deploy-to-vps.sh` is manual; consider GitHub Actions on push to `staging`. |
| 37 | No external monitoring — Sentry / Grafana / uptime check. |
| 38 | Backup covers DB only — `uploads/` (subcontractor scans, generated PDFs) is not backed up. |
| 39 | Backup restore procedure untested — should do a drill before going live. |
| 40 | Single-environment deployment — no staging vs production separation. |
| 41 | Pre-deploy DB snapshot would make `deploy-to-vps.sh` safer (free rollback if migrations go wrong). |
| 42 | No load test executed against the alpha (the runbook's `ab` step is documented but skipped). |
| 43 | No automated DB seed for masters/users — requires manual one-shot scripts. |

---

## Tally

- 🔴 Pre-production blockers: **6**
- 🟡 Functional bugs / spec gaps: **20** (9 Med + 11 Low)
- 🟢 Polish / UX: **9**
- ⚙️ Ops / Infra: **8**
- **Total open: ~43**

The original §6 audit flagged 50+; closed across this session and the prior one are: 8 🔴 unblockers + most of buckets 3 & 4 (audit_service, generic PDF engine, Appendix Builder UI, gitignore/encoding/pagination polish, frontend auth layer, three deploy-time runbook bugs, alpha-onboarding doc, e2e smoke test).

---

## Suggested next sprint

Items **#1–#11** (the 6 pre-prod blockers + the 5 highest-impact functional gaps): real master templates, SMTP, DNS, plan upgrade, real users, SSH hardening, then `auto_source_field_id` plumbing, C09 row storage, deviation Risk wiring, GM auto-advance, and Archive UX. Roughly 1–2 weeks of focused work, lands BGCC a meaningfully complete product.

Low-severity 🟡 and Polish items can stay deferred without holding launch.
