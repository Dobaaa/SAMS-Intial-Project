#!/usr/bin/env python3
"""End-to-end flow test against the live alpha VPS.

Drives each role through the agreement lifecycle and verifies every state
transition. Idempotent — each run uses a timestamped project_code and
reference_number so it can be re-run without DB cleanup.

Usage:
    python3 scripts/e2e-flow-test.py
    BASE_URL=https://sams.bgcc.ae python3 scripts/e2e-flow-test.py
"""

from __future__ import annotations

import os
import sys
import time
from datetime import date

import requests

BASE_URL = os.environ.get("BASE_URL", "https://76-13-159-24.sslip.io")
TIMEOUT = 30

USERS = {
    "admin":            ("admin@bgcc.ae",     "change-me-admin"),
    "project_director": ("pd@bgcc.ae",        "change-me-pd"),
    "accounts":         ("accounts@bgcc.ae",  "change-me-accounts"),
    "operation_manager":("om@bgcc.ae",        "change-me-om"),
    "gm":               ("gm@bgcc.ae",        "change-me-gm"),
}

USE_COLOR = sys.stdout.isatty()
GREEN = "\033[32m" if USE_COLOR else ""
RED   = "\033[31m" if USE_COLOR else ""
YEL   = "\033[33m" if USE_COLOR else ""
DIM   = "\033[2m"  if USE_COLOR else ""
END   = "\033[0m"  if USE_COLOR else ""

PASS_COUNT = 0
FAIL_COUNT = 0
START = time.monotonic()


def log_step(title: str) -> None:
    print(f"\n{YEL}── {title}{END}")


def ok(msg: str) -> None:
    global PASS_COUNT
    PASS_COUNT += 1
    print(f"  {GREEN}✓{END} {msg}")


def fail(msg: str, detail: str = "") -> None:
    global FAIL_COUNT
    FAIL_COUNT += 1
    print(f"  {RED}✗{END} {msg}")
    if detail:
        print(f"    {DIM}{detail}{END}")


def fatal(msg: str, detail: str = "") -> None:
    fail(msg, detail)
    summary()
    sys.exit(1)


def summary() -> int:
    elapsed = time.monotonic() - START
    print(
        f"\n{DIM}─────────────────────────────────────────{END}\n"
        f"  passed: {GREEN}{PASS_COUNT}{END}   "
        f"failed: {RED if FAIL_COUNT else DIM}{FAIL_COUNT}{END}   "
        f"time: {elapsed:.1f}s"
    )
    return 0 if FAIL_COUNT == 0 else 1


def login(email: str, password: str) -> str:
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": email, "password": password},
        timeout=TIMEOUT,
    )
    if r.status_code != 200:
        fatal(f"login failed for {email}", f"HTTP {r.status_code}: {r.text[:200]}")
    return r.json()["access_token"]


def api(method: str, path: str, token: str, json=None, **kwargs) -> requests.Response:
    headers = {"Authorization": f"Bearer {token}"}
    return requests.request(
        method, f"{BASE_URL}{path}",
        headers=headers, json=json, timeout=TIMEOUT, **kwargs,
    )


def find_pending_step(token: str, agreement_id: str) -> str | None:
    r = api("GET", "/api/workflow/pending", token)
    if r.status_code != 200:
        return None
    for item in r.json():
        step = item.get("step") or item
        agreement = item.get("agreement") or {}
        ag_id = str(agreement.get("id") or step.get("agreement_id") or "")
        if ag_id == agreement_id and step.get("status") == "pending":
            return str(step["id"])
    return None


def num_eq(value, expected: float) -> bool:
    """Tolerant numeric compare — backend may store '100000', '100000.0', '100000.00'."""
    try:
        return float(value) == float(expected)
    except (TypeError, ValueError):
        return False


def main() -> int:
    print(f"{DIM}base url:{END} {BASE_URL}")
    print(f"{DIM}run tag:{END}  {int(time.time())}")

    # ── Phase 1: all five users can log in ────────────────────────────────
    log_step("Phase 1: authentication for all 5 roles")
    tokens: dict[str, str] = {}
    for role, (email, pw) in USERS.items():
        token = login(email, pw)
        if not token:
            fatal(f"no token returned for {email}")
        tokens[role] = token
        # /me confirms role
        r = api("GET", "/api/auth/me", token)
        if r.status_code != 200:
            fatal(f"/me failed for {email}", f"HTTP {r.status_code}")
        if r.json().get("role") != role:
            fatal(f"/me role mismatch", f"expected {role}, got {r.json().get('role')}")
        ok(f"login + /me as {role:<18} ({email})")

    admin = tokens["admin"]

    # ── Phase 2: Admin creates project + subcontractor + agreement ────────
    log_step("Phase 2: Admin creates draft agreement")
    tag = int(time.time())
    project_code = f"E2E-{tag}"
    subcontractor_name = f"E2E Subcontractor {tag}"
    reference = f"SAG-E2E-{tag}-001"

    payload = {
        "project": {
            "project_name": f"E2E Test Project {tag}",
            "project_code": project_code,
            "project_location": "Dubai, UAE",
            "employer_name": "BGCC",
            "engineer_name": "Test Engineer",
        },
        "subcontractor": {
            "company_name": subcontractor_name,
            "po_box": "12345",
            "trade_licence_no": "LIC-9999",
            "contact_person": "John Doe",
            "email": "subcontractor@example.test",
            "phone": "+971 50 000 0000",
            "address": "Dubai Marina",
        },
        "reference_number": reference,
    }
    r = api("POST", "/api/agreements/", admin, json=payload)
    if r.status_code != 200:
        fatal("create agreement", f"HTTP {r.status_code}: {r.text[:300]}")
    agreement_id = r.json()["id"]
    ok(f"created agreement {agreement_id} ref={reference}")
    if r.json().get("status") != "under_drafting":
        fail("initial status", f"expected under_drafting, got {r.json().get('status')}")
    else:
        ok("initial status = under_drafting")

    # ── Phase 3: Fill required fields, verify F→C/A auto-cascade ──────────
    log_step("Phase 3: fill fields, verify auto-cascade (F08 → C03=10%, A07, A09)")
    today = date.today().isoformat()
    fields = {
        "F01": today,
        "F02": subcontractor_name,
        "F05": "BGCC",
        "F06": "E2E test scope",
        "F07": "Dubai",
        "F08": "1000000",
        "F09": "Test scope title",
        "C01": "Detailed scope of works for the e2e test.",
        "C02": "Lump Sum",
        "C05": "30",
        "C08": "180 days",
        "C11": "5000",
        "C13": "DIFC Courts",
    }
    r = api("PUT", f"/api/agreements/{agreement_id}/fields", admin, json={"values": fields})
    if r.status_code != 200:
        fatal("update fields", f"HTTP {r.status_code}: {r.text[:300]}")
    values = r.json().get("values", {})

    if values.get("F08") == "1000000":
        ok("F08 stored as 1000000")
    else:
        fail("F08 stored", f"got {values.get('F08')!r}")

    if num_eq(values.get("C03"), 100000):
        ok(f"C03 auto = 10% of F08 (got {values.get('C03')!r})")
    else:
        fail("C03 auto-cascade", f"got {values.get('C03')!r}")

    if num_eq(values.get("A07"), 1000000):
        ok(f"A07 auto-mirrors F08 (got {values.get('A07')!r})")
    else:
        fail("A07 auto-mirror", f"got {values.get('A07')!r}")

    if num_eq(values.get("A09"), 100000):
        ok(f"A09 auto-mirrors C03 (got {values.get('A09')!r})")
    else:
        fail("A09 auto-mirror", f"got {values.get('A09')!r}")

    # ── Phase 4: Manual override on A07, then re-edit F08, override survives
    log_step("Phase 4: manual override on A07 survives subsequent F08 edit")
    r = api("PUT", f"/api/agreements/{agreement_id}/fields", admin,
            json={"values": {"A07": "999999"}})
    if r.status_code != 200:
        fail("override A07", f"HTTP {r.status_code}: {r.text[:200]}")
    else:
        # Now bump F08 — A07 should NOT be reset
        r2 = api("PUT", f"/api/agreements/{agreement_id}/fields", admin,
                 json={"values": {"F08": "1500000"}})
        v = r2.json().get("values", {})
        if num_eq(v.get("A07"), 999999):
            ok(f"A07 manual override preserved after F08 changed (got {v.get('A07')!r})")
        else:
            fail("A07 override clobbered", f"A07={v.get('A07')!r} after F08=1500000")
        if num_eq(v.get("F08"), 1500000):
            ok(f"F08 updated to 1500000 (got {v.get('F08')!r})")
        else:
            fail("F08 update", f"got {v.get('F08')!r}")

    # ── Phase 5: Submit → 4 workflow steps created ────────────────────────
    log_step("Phase 5: submit for internal review")
    r = api("POST", f"/api/agreements/{agreement_id}/submit", admin)
    if r.status_code != 200:
        fatal("submit", f"HTTP {r.status_code}: {r.text[:300]}")
    ok("submit 200")

    # Verify 4 workflow steps via the workflow summary endpoint
    r = api("GET", f"/api/workflow/agreements/{agreement_id}", admin)
    if r.status_code != 200:
        fatal("workflow summary", f"HTTP {r.status_code}: {r.text[:300]}")
    summary_data = r.json()
    steps = summary_data.get("steps") or summary_data.get("workflow_steps") or []
    if len(steps) >= 4:
        ok(f"workflow has {len(steps)} steps")
    else:
        fail(f"workflow steps count", f"got {len(steps)}")

    # Verify status is now under_internal_review
    r = api("GET", f"/api/agreements/{agreement_id}", admin)
    cur_status = r.json().get("current_status")
    if cur_status == "under_internal_review":
        ok("status → under_internal_review")
    else:
        fail("post-submit status", f"got {cur_status!r}")

    # ── Phase 6-9: Each reviewer approves in order ────────────────────────
    chain = [
        ("project_director", "PD"),
        ("accounts",         "Accounts"),
        ("operation_manager","OM"),
        ("gm",               "GM"),
    ]
    for role, label in chain:
        log_step(f"Phase {6 + chain.index((role, label))}: {label} approves")
        token = tokens[role]
        step_id = find_pending_step(token, agreement_id)
        if not step_id:
            fatal(f"{label}: no pending step found", "/api/workflow/pending returned no match")
        ok(f"{label} sees the agreement in their pending list")
        r = api("POST", f"/api/workflow/{step_id}/approve", token)
        if r.status_code != 200:
            fatal(f"{label} approve", f"HTTP {r.status_code}: {r.text[:300]}")
        if r.json().get("status") == "approved":
            ok(f"{label} approve 200")
        else:
            fail(f"{label} approve response", str(r.json()))

    # ── Phase 10: Admin sends to subcontractor ────────────────────────────
    log_step("Phase 10: Admin sends agreement to subcontractor")
    r = api("POST", f"/api/agreements/{agreement_id}/send-to-subcontractor", admin)
    if r.status_code != 200:
        fatal("send-to-subcontractor", f"HTTP {r.status_code}: {r.text[:300]}")
    ok("send-to-subcontractor 200")

    r = api("GET", f"/api/agreements/{agreement_id}", admin)
    cur_status = r.json().get("current_status")
    if cur_status == "draft_forwarded_to_subcontractor":
        ok(f"status → draft_forwarded_to_subcontractor")
    else:
        fail("post-send status", f"got {cur_status!r}")

    # ── Phase 11: PDF generation ──────────────────────────────────────────
    log_step("Phase 11: PDF generation")
    r = api("POST", f"/api/pdf/{agreement_id}/generate", admin)
    if r.status_code in (200, 201):
        ok(f"PDF generate 200 ({len(r.content)} bytes returned in body or stored)")
    else:
        fail("PDF generate", f"HTTP {r.status_code}: {r.text[:300]}")

    # ── Phase 12: Deviation report ────────────────────────────────────────
    log_step("Phase 12: deviation report PDF")
    r = api("GET", f"/api/agreements/{agreement_id}/deviation-report", admin)
    if r.status_code == 200:
        ok(f"deviation report 200 ({len(r.content)} bytes)")
    else:
        fail("deviation report", f"HTTP {r.status_code}: {r.text[:200]}")

    # ── Phase 13: Return + resubmit cycle (independent agreement) ─────────
    log_step("Phase 13: return + resubmit (whole chain restarts)")
    tag2 = tag + 1
    payload2 = dict(payload)
    payload2["project"] = {**payload["project"], "project_code": f"E2E-{tag2}"}
    payload2["subcontractor"] = {**payload["subcontractor"], "company_name": f"E2E Sub Return {tag2}"}
    payload2["reference_number"] = f"SAG-E2E-{tag2}-002"

    r = api("POST", "/api/agreements/", admin, json=payload2)
    if r.status_code != 200:
        fail("create 2nd agreement for return cycle", f"HTTP {r.status_code}")
    else:
        ag2 = r.json()["id"]
        api("PUT", f"/api/agreements/{ag2}/fields", admin, json={"values": fields})
        r = api("POST", f"/api/agreements/{ag2}/submit", admin)
        if r.status_code != 200:
            fail("submit 2nd agreement", f"HTTP {r.status_code}")
        else:
            ok("2nd agreement submitted")
            # PD returns it
            pd_token = tokens["project_director"]
            step_id = find_pending_step(pd_token, ag2)
            r = api("POST", f"/api/workflow/{step_id}/return", pd_token,
                    json={"comment_text": "E2E test: please revise C11 LD rate", "clause_reference": "C11"})
            if r.status_code != 200:
                fail("PD return", f"HTTP {r.status_code}: {r.text[:200]}")
            else:
                ok("PD returned to admin with comment")
                # Status flips to under_bgcc_revision (admin revises after a return)
                r = api("GET", f"/api/agreements/{ag2}", admin)
                if r.json().get("current_status") == "under_bgcc_revision":
                    ok("status → under_bgcc_revision after return")
                else:
                    fail("post-return status", f"got {r.json().get('current_status')!r}")
                # Admin resubmits → chain should restart at PD
                r = api("POST", f"/api/agreements/{ag2}/resubmit", admin)
                if r.status_code != 200:
                    fail("resubmit", f"HTTP {r.status_code}")
                else:
                    ok("resubmit 200")
                    pd_step = find_pending_step(pd_token, ag2)
                    if pd_step:
                        ok("PD has a fresh pending step after resubmit (chain restarted)")
                    else:
                        fail("PD pending after resubmit", "no pending step found for PD")

    # ── Phase 14: Subcontractor signs → agreement locks ───────────────────
    log_step("Phase 14: record subcontractor signed → agreement locks")
    r = api("PATCH", f"/api/agreements/{agreement_id}/subcontractor-response", admin,
            json={"response_type": "signed"})
    if r.status_code != 200:
        fail("record signed", f"HTTP {r.status_code}: {r.text[:200]}")
    else:
        body = r.json()
        if body.get("is_executed") is True:
            ok("agreement is_executed=True")
        else:
            fail("is_executed flag", str(body))
        if body.get("agreement_status") == "completed":
            ok("status → completed")
        else:
            fail("post-sign status", f"got {body.get('agreement_status')!r}")
        # Verify field edits are now blocked
        r = api("PUT", f"/api/agreements/{agreement_id}/fields", admin, json={"values": {"F02": "x"}})
        if r.status_code == 400:
            ok("field edits correctly rejected on locked agreement (400)")
        else:
            fail("locked-agreement edit guard", f"got HTTP {r.status_code}")

    return summary()


if __name__ == "__main__":
    sys.exit(main())
