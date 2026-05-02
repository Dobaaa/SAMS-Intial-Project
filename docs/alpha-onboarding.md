# SAMS Alpha — Onboarding & Walkthrough

**Live URL:** https://76-13-159-24.sslip.io
**Status:** alpha — for internal testing only. Will move to `sams.bgcc.ae` once BGCC IT publishes DNS.

---

## 1. Test users (one per role)

All passwords below are **alpha-only test credentials**. Change them on first login (Admin → User Management → edit).

| Role | Name | Email | Temporary password |
|---|---|---|---|
| Admin | BGCC Admin | `admin@bgcc.ae` | `change-me-admin` |
| Project Director | Project Director | `pd@bgcc.ae` | `change-me-pd` |
| Accounts | Accounts | `accounts@bgcc.ae` | `change-me-accounts` |
| Operation Manager | Operation Manager | `om@bgcc.ae` | `change-me-om` |
| GM | General Manager | `gm@bgcc.ae` | `change-me-gm` |

Login screen: https://76-13-159-24.sslip.io/login

---

## 2. Before you create your first agreement

The system was deployed with **placeholder master templates** so the rest of the app could be tested. The 45 field definitions (F01–F09, C01–C13, A01–A23) are all seeded correctly, but the three legal documents themselves are not. Until you upload real HTML, generated PDFs will show a placeholder block instead of the BGCC contract text.

**Replace the placeholder templates** (one-time setup, Admin only):

1. Sign in as `admin@bgcc.ae`.
2. Go to **Master Templates**.
3. For each of the three types — `form`, `conditions`, `appendix` — click **Create new version** and paste the real BGCC HTML. Use `{{F02}}`, `{{C03}}`, `{{A07}}` etc. as the placeholders where field values should plug in. The PDF engine substitutes those tokens at render time.
4. Save each version. The new version becomes `is_active=true` automatically; old versions stay attached to any agreements that were already built from them.

You can keep working with the placeholders for testing the workflow itself — the PDF will just look bare until the real templates land.

---

## 3. End-to-end example: drafting an agreement and sending it to the subcontractor

This walks every role through their part. **All five users participate** — there is no shortcut.

### 3.1 Admin creates the draft

Sign in as `admin@bgcc.ae`. Go to **New Agreement**. The wizard has 5 steps.

**Step 1 — Project & Subcontractor**
- Pick the project (or create a new one with project code, e.g. `BGCC-2026-014`).
- Pick the subcontractor (or add a new one with name, trade licence, address).
- Reference number is auto-generated as `SAG-{PROJECT_CODE}-{YEAR}-{SEQ:03d}`. Editable until GM approves.

**Step 2 — Form fields (F01–F09)**
Eight `[Insert]` slots from the Form of Agreement. Required: F01 (signing date), F02 (subcontractor name), F05 (employer entity), F06 (project), F07 (location), F08 (price in AED), F09 (scope title).

**Step 3 — Conditions (C01–C13)**
Thirteen clauses. Two important auto-behaviours:
- **C03** (advance payment) auto-fills to **10% of F08**. Override if the contract differs.
- C09 is a milestones table — for now it's a textarea (table editor not yet implemented).

**Step 4 — Appendix Builder (A01–A23)**
Most A-fields auto-populate from the F/C values you already entered (e.g. A01 ← F02, A07 ← F08, A09 ← C03). For each row, you can:
- Edit the value (overrides survive subsequent F/C edits).
- Toggle **show in PDF** (hide rows that aren't relevant to this contract).
- Add an **admin note** (free-text annotation rendered next to the row).
- Reorder rows with the up/down arrows.

**Step 5 — Review & Submit**
Final summary. Modified-from-default values are highlighted. Click **Submit for internal review**. This:
- Creates 4 workflow steps (PD → Accounts → OM → GM), all `pending`.
- Sets agreement status to `under_internal_review`.
- Activates the PD step.
- Emails the PD (best-effort; see "Caveats" §5).

### 3.2 PD reviews

Sign in as `pd@bgcc.ae`. The Dashboard shows agreements pending your review.

1. Open the agreement → **Workflow Review** page.
2. The deviation report is embedded inline — it lists every field where the entered value differs from the master template default, with a Risk column populated by the AI panel (suggested only; you confirm).
3. The AI Review Panel (right side) shows clause comparison + risk detection + role-specific summary. Each suggestion has a **Confirm** button — nothing AI says is auto-applied.
4. Add comments on specific clauses if needed. Any reviewer (not just PD) can edit any comment; edits are recorded in `comment_edit_history`.
5. Click **Approve** to advance to Accounts, or **Return to Admin** with a required comment if anything is wrong.

> **Returning restarts the whole chain.** When Admin resubmits, all four steps go back to `pending` and PD must re-approve before Accounts can act. Earlier approvals are wiped — this is by design (BGCC compliance rule, not a bug).

### 3.3 Accounts reviews

Sign in as `accounts@bgcc.ae`. Same Workflow Review screen, scoped to the financial clauses (price, payments, retention). Approve or return.

### 3.4 OM reviews

Sign in as `om@bgcc.ae`. Time-for-completion, milestones, LDs are the focus. Approve or return.

### 3.5 GM approves

Sign in as `gm@bgcc.ae`. Final sign-off. Approve sets `gm_approval_date` and stamps the workflow step as `approved`.

> **GM approval does NOT auto-send to the subcontractor.** Status stays `under_internal_review` and the ball is back in Admin's court.

### 3.6 Admin sends to the subcontractor

Sign in as `admin@bgcc.ae`. Open the now-fully-approved agreement.

1. Verify the PDF renders correctly (download from the Dashboard or the agreement detail page).
2. Click **Send to subcontractor**. This calls `POST /api/agreements/{id}/send-to-subcontractor` and transitions the agreement:
   - `under_internal_review` → `draft_forwarded_to_subcontractor`
3. Subcontractor receives the PDF by email (best-effort — see §5).

### 3.7 What happens after (out of scope for this walkthrough)

- **Subcontractor signs** → admin records a signed scan; agreement is locked (`is_executed=true`, `current_status=completed`); appears in Archive.
- **Subcontractor comments** → admin builds a Resolution Sheet, OM + GM approve the resolution, admin clicks **Send to subcontractor** again; status moves to `under_subcontractor_signature`.

---

## 4. Quick reference

| Action | URL |
|---|---|
| Login | https://76-13-159-24.sslip.io/login |
| Dashboard | /dashboard |
| New Agreement (5-step wizard) | /agreements/new |
| Workflow review (per agreement) | /agreements/{id}/review |
| Comments resolution | /agreements/{id}/resolution |
| Master Templates | /masters |
| User Management (admin only) | /users |
| Archive | /archive |

---

## 5. Alpha caveats (deliberate gaps)

- **Email notifications are best-effort.** SMTP is a placeholder right now; emails to reviewers / Admin / subcontractor will silently no-op until real Hostinger SMTP credentials are wired in. The workflow itself works without email — reviewers just won't get a ping.
- **Master templates are placeholders.** PDFs render but show stub content. See §2 to upload the real ones.
- **C09 milestones is a textarea, not a table.** Storage model for table rows is not implemented yet.
- **Excel-only Archive export.** PDF re-download supported only for `final` and `executed` PDFs; drafts return 404 from the download endpoint.
- **No "forgot password" flow.** Password resets happen via Admin → User Management.
- **PDF generation is CPU-heavy.** This alpha box is 1 vCPU; expect 1–3 s per PDF at low load. Production will need a bigger plan.
- **Resource note:** the VPS is a Hostinger KVM 1 (1 vCPU / 4 GB RAM). Comfortable for this kind of demo. Recommend KVM 2 or KVM 4 before opening to all 15 BGCC users.

---

## 6. If something breaks

| Symptom | Where to look |
|---|---|
| Login returns 401 unexpectedly | `/var/log/sams/error.log` (uvicorn / FastAPI errors) |
| 502 Bad Gateway | `sudo supervisorctl status sams-api` — should be `RUNNING` |
| 500 on a specific page | `sudo tail -f /var/log/sams/error.log` while reproducing |
| Frontend assets 404 | Was the last deploy run with `npm run build`? `ls /var/www/sams/frontend/dist` |
| Stuck workflow / phantom pending steps | DB inspection: `SELECT * FROM workflow_steps WHERE agreement_id = '…';` |

For server access details, deploy procedure, and rollback steps see `CLAUDE.md` §10.
