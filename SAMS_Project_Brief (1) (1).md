# Subcontract Agreement Management System (SAMS)
## Project Brief — For Any AI Model or Developer

---

## 1. What Is This System?

SAMS is a web-based application that manages the full lifecycle of subcontract agreements in a construction/engineering company. It controls how agreements are created from master templates, reviewed through an approval chain, sent to subcontractors, and revised based on feedback — with AI assistance at every step.

The system is NOT a document editor. It is a workflow + version control + compliance system built around legal contract documents.

---

## 2. The Three Core Documents

Every subcontract agreement is a package of exactly three documents generated from master templates:

### File 1: Form of Subcontract Agreement
- Contains specific clauses with variable input fields
- Admin fills in the variable data only (project name, subcontractor name, amounts, dates, etc.)
- The boilerplate legal text comes from the Master Template — Admin does NOT rewrite it
- Each agreement gets a unique serial/reference number (e.g., SAG-PROJ-2025-001)

### File 2: Conditions of Subcontract Agreement
- Contains the master conditions (legal terms, obligations, penalties, etc.)
- Master conditions are updated periodically by Admin (each update = new version)
- Has specific fields where variable data is entered per agreement
- The system tracks which version of the Conditions was used for each agreement

### File 3: Appendix to the Subcontract Agreement
- A summary table with three columns: Clause Title | Clause Number | Value entered in that clause
- Shows only the clauses that DEVIATED from the master (modified clauses)
- Admin controls which clauses appear in the Appendix
- Admin can add extra notes to specific clauses in the Appendix
- This is the "diff" document — it highlights what changed from the standard template

### Final Output
The system generates a single PDF combining:
Cover Page + Form of Subcontract + Conditions + Appendix

---

## 3. User Roles (10 Users Total)

### Admin (internal, ~2 users)
**Can do:**
- Create and manage Master Templates (Form, Conditions, Appendix)
- Create new agreements — fills in variable fields ONLY, does not rewrite boilerplate
- Select which clauses were modified vs. the master
- Build the Appendix (select clauses to show, add extra notes)
- Generate final PDF
- Send agreement to subcontractor via email
- Create Comments Resolution Sheet when subcontractor replies with comments
- Revise agreement after internal review of subcontractor comments
- Assign unique reference numbers
- Manage users

**Cannot do:**
- Approve agreements (no self-approval)
- Modify master templates without creating a new version

### Project Director (~1 user)
**Can do:**
- View any agreement assigned to them
- Approve or return with comments
- In comments cycle: review and update responses to subcontractor comments
- See AI-generated summary of the agreement

**Cannot do:**
- Edit the agreement content
- Access master template management

### Accounts Department (~1–2 users)
**Can do:**
- View financial clauses in the agreement
- Approve or return with comments (focused on financial terms)
- See AI financial compliance check

**Cannot do:**
- Edit agreement content
- Access non-financial sections (view-only for those)

### Operation Manager (~1–2 users)
**Can do:**
- View operational clauses
- Approve or return with comments
- In comments cycle: review responses AFTER Project Director, confirm or edit them
- Final approval in the comments cycle before GM

**Cannot do:**
- Edit agreement content

### General Manager (~1 user)
**Can do:**
- View complete agreement with AI executive summary
- Give final internal approval before sending to subcontractor
- Approve revised agreement after comments cycle

**Cannot do:**
- Edit agreement content

### Subcontractor (external, not a system user)
- Receives PDF via email
- Signs and returns OR sends back comments via email
- Admin manually records their response in the system

---

## 4. The Complete Workflow

### Part A: Initial Approval Chain

```
Admin
  └── Creates agreement (fills variable fields, selects modified clauses, builds Appendix)
        └── Submits for review

Project Director
  ├── Returns with comments → Admin revises → resubmits to PD
  └── Approves ↓

Accounts Department
  ├── Returns with comments → Admin revises → resubmits from PD stage
  └── Approves ↓

Operation Manager
  ├── Returns with comments → Admin revises → resubmits from PD stage
  └── Approves ↓

General Manager
  ├── Returns with comments → Admin revises → resubmits from PD stage
  └── Approves ↓

Admin
  └── Generates final PDF → Sends to Subcontractor via email
```

### Part B: Subcontractor Response

```
Subcontractor receives PDF
  ├── Signs → DONE (Admin records signed copy, status = Final)
  └── Sends comments ↓

Admin
  └── Creates Comments Resolution Sheet
        (lists each subcontractor comment, AI suggests response)
        ↓

Project Director
  └── Reviews comments + suggested responses, updates/approves responses
        ↓

Operation Manager
  └── Reviews and confirms/edits responses
        ↓

Admin
  └── Revises agreement based on agreed responses
        ↓

Operation Manager → Approves revised agreement
  ↓
General Manager → Approves revised agreement
  ↓

Admin
  └── Sends revised agreement to Subcontractor

[Repeat Part B cycle if subcontractor sends new comments]
```

---

## 5. Agreement Status Values (7 States)

| Status | Meaning |
|--------|---------|
| Under Preparation | Admin is still building the agreement |
| Draft Under GM Review | Inside the internal approval chain |
| Draft Forwarded to Subcontractor | Sent to subcontractor for first time |
| Final Forwarded to Subcontractor for Signature | Sent after comments resolved |
| Received Subcontractor's Signed Copy | Subcontractor signed |
| Under BGCC Signature | Being signed by the company |
| Signed / Complete | Fully executed |

---

## 6. AI Features (Assistive Only — No Auto-Approvals)

Every AI output is a suggestion. A human must confirm before any action is taken.

| AI Feature | Trigger | Output |
|-----------|---------|--------|
| Clause Comparison | When agreement is submitted | Highlights differences from master template |
| Risk Detection | After clause comparison | Risk score + explanation per modified clause |
| Smart Summary | When reviewer opens agreement | Role-specific summary (financial for Accounts, operational for OM, executive for GM) |
| Financial Compliance Check | For Accounts Department | Checks payment terms, penalties, amounts |
| Comments Response Generator | When Admin creates Resolution Sheet | Suggests response to each subcontractor comment |
| Revision Validation | After Admin revises agreement | Confirms revision addresses the comments |
| Learning (optional) | Ongoing | Learns from past agreements to improve suggestions |

---

## 7. Key Business Rules

1. **Admin fills variable fields only** — The master template text is never retyped. Only designated input fields are filled.
2. **Every change to a Master Template = new version** — Old agreements keep a reference to the version they used.
3. **Appendix = diff document** — Only shows what changed from the master. If nothing changed in a clause, it doesn't appear.
4. **All returns go back to Admin** — Any reviewer who rejects sends it to Admin to fix, not to the previous reviewer.
5. **Comments Resolution Sheet is a separate document** — It lives alongside the agreement, not inside it.
6. **No auto-approvals** — AI only suggests. Every approval is a conscious human action.
7. **Full audit trail** — Every action (who, what, when, comment) is logged and cannot be deleted.
8. **Reference number is immutable** — Once assigned, the reference number never changes through revisions.
9. **PDF is generated, not edited** — Nobody edits the PDF. The system generates it fresh from the stored data each time.
10. **Subcontractor is external** — They never log into the system. All communication is via email.

---

## 8. Technical Stack

### Backend: Python + FastAPI
**Why Python, not Node.js:**
- AI/ML ecosystem: OpenAI, LangChain, spaCy, and every NLP library is Python-first. Using Node.js would mean fighting the ecosystem on the most critical feature of the system.
- PDF generation: WeasyPrint (best HTML→PDF with RTL support) is Python-only. No equivalent in Node.js.
- Document processing: python-docx, diff libraries, text comparison tools are all mature in Python.
- FastAPI gives async performance comparable to Node.js with Python's ecosystem benefits.
- The team's AI prompting, testing, and data processing will all be in Python — one language across the stack is simpler.

### Frontend: React + TypeScript + TailwindCSS + Vite
- TipTap (ProseMirror-based) for the rich text / template editor with placeholder support
- React Hook Form + Zod for form validation
- WebSocket for real-time workflow notifications

### Database: PostgreSQL
- ACID compliance for audit trail integrity
- JSONB columns for flexible clause content storage
- Alembic for migrations
- Redis for caching and Celery task queue

### PDF: WeasyPrint + Jinja2 (100% free, open source)
- HTML templates rendered server-side with Jinja2
- WeasyPrint converts to PDF with full RTL, headers, footers, page numbers, watermarks
- No paid PDF library needed

### Auth: Keycloak (open source)
- Role-based access control (RBAC)
- JWT tokens
- Self-hosted on the same VPS

### AI: OpenAI GPT-4o via API
- LangChain for prompt management and chaining
- Redis cache for AI results (avoid re-running same analysis)
- Rate limiting and spending caps via OpenAI dashboard

### Infrastructure: Hostinger VPS KVM 4
- $17.99/month (or $149/year)
- Docker Compose for all services
- MinIO for PDF/file storage (self-hosted S3-compatible, free)
- Prometheus + Grafana for monitoring
- GitHub Actions for CI/CD

---

## 9. Database Key Tables

| Table | Purpose |
|-------|---------|
| users | System users with roles |
| master_templates | All versions of the three master documents |
| clauses | Individual clauses within each template |
| agreements | Each subcontract agreement instance |
| agreement_clauses | The filled-in values for each clause per agreement |
| workflow_steps | Each step in the approval chain with status |
| comments | Comments from reviewers at each step |
| comments_resolution_sheets | Subcontractor comment + suggested response + final response |
| ai_reviews | AI analysis results per agreement per step |
| audit_log | Immutable record of every action |
| pdf_outputs | Generated PDF files with MinIO references |

---

## 10. Monthly Running Costs

| Service | Cost |
|---------|------|
| Hostinger VPS KVM 4 | $17.99/month |
| OpenAI GPT-4o (typical usage) | $20–50/month |
| SendGrid (email notifications) | $0–20/month |
| Hostinger Email | $1.99/month |
| Everything else (Keycloak, MinIO, Redis, Monitoring) | $0 (self-hosted) |
| **Total** | **~$40–90/month** |

---

## 11. What This System Is NOT

- It is NOT a general document editor (like Google Docs)
- It is NOT a e-signature platform (subcontractor signs physically and sends scanned copy)
- It is NOT a contract drafting tool (templates are pre-written by legal team)
- It is NOT accessible to subcontractors (they only receive emails)
- It is NOT replacing legal review (AI is assistive only)

---

*Version 1.0 — Generated for SAMS project briefing*
