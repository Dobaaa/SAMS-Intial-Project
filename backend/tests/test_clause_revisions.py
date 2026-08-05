"""Tests for the per-agreement clause-revision flow (Phase 4 v2.0 + v2.1).

Covers: list master clauses, create a revision, withdraw a pending one,
accept (segregation-of-duties guarded), reject, and the audit-log writes
that happen on every decision.
"""

import pytest

from services.auth_service import hash_password


pytestmark = pytest.mark.asyncio


async def _seed_active_templates(authed_client):
    """Mirror of helper in test_agreements — registers one active version
    per template type so /agreements/ POST succeeds."""
    for template_type in ("form", "conditions", "appendix"):
        resp = await authed_client.post(
            "/api/masters/",
            json={
                "type": template_type,
                "version_number": "v1",
                "content_html": "<p>placeholder</p>",
                "version_date": "2026-05-17",
                "is_active": True,
            },
        )
        assert resp.status_code == 200, resp.text


async def _create_agreement(authed_client) -> dict:
    resp = await authed_client.post(
        "/api/agreements/",
        json={
            "project": {
                "project_name": "Revision Test",
                "project_code": "REV001",
                "project_location": "Dubai",
                "employer_name": "Test Employer",
                "engineer_name": "Test Engineer",
            },
            "subcontractor": {
                "company_name": "Test Subco LLC",
                "po_box": "12345",
                "trade_licence_no": "TL-001",
                "email": "subco@test.example",
            },
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


async def _seed_reviewer(db_session, *, email: str, role):
    """Drop a non-admin reviewer into the DB so we can test segregation
    of duties (admin creates, reviewer accepts)."""
    from models.user import User

    user = User(
        name=f"Test {role.value}",
        email=email,
        password_hash=hash_password("revpass1"),
        role=role,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


async def _login(client, email: str, password: str) -> str:
    resp = await client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


@pytest.fixture
async def project_director_user(db_session):
    from models.user import RoleEnum

    return await _seed_reviewer(
        db_session, email="pd@test.example", role=RoleEnum.project_director
    )


async def test_list_master_clauses_returns_paragraphs(authed_client):
    """The master tokenized docx ships with hundreds of revisable paragraphs;
    the listing endpoint should expose them deduped + sorted."""
    await _seed_active_templates(authed_client)
    agreement = await _create_agreement(authed_client)

    resp = await authed_client.get(f"/api/agreements/{agreement['id']}/clauses")
    assert resp.status_code == 200, resp.text
    clauses = resp.json()["clauses"]
    assert len(clauses) > 50, "master should have many revisable paragraphs"
    # Each clause carries the stable anchor hash + label + presence flags.
    first = clauses[0]
    assert set(first) >= {"clause_hash", "clause_label", "text", "section", "has_pending", "has_accepted"}
    assert len(first["clause_hash"]) == 64
    assert first["has_pending"] is False
    assert first["has_accepted"] is False


async def test_create_revision_round_trip_and_withdraw(authed_client):
    """Admin creates a revision (status=pending), list reflects it, then
    DELETE drops it."""
    await _seed_active_templates(authed_client)
    agreement = await _create_agreement(authed_client)
    clauses = (await authed_client.get(f"/api/agreements/{agreement['id']}/clauses")).json()["clauses"]
    target = clauses[0]

    create = await authed_client.post(
        f"/api/agreements/{agreement['id']}/revisions",
        json={
            "clause_hash": target["clause_hash"],
            "modified_text": "[edited] " + target["text"],
            "change_reason": "test",
        },
    )
    assert create.status_code == 200, create.text
    rev_id = create.json()["id"]
    assert create.json()["status"] == "pending"
    assert create.json()["clause_label"] == target["clause_label"]

    listed = await authed_client.get(f"/api/agreements/{agreement['id']}/revisions")
    assert listed.status_code == 200
    assert len(listed.json()["revisions"]) == 1

    # Picker should now flag the clause as has_pending=True.
    refreshed = (await authed_client.get(f"/api/agreements/{agreement['id']}/clauses")).json()["clauses"]
    flagged = next(c for c in refreshed if c["clause_hash"] == target["clause_hash"])
    assert flagged["has_pending"] is True

    delete = await authed_client.delete(
        f"/api/agreements/{agreement['id']}/revisions/{rev_id}"
    )
    assert delete.status_code == 200
    assert delete.json()["status"] == "deleted"


async def test_cannot_create_revision_with_unchanged_text(authed_client):
    """Submitting a revision whose modified_text equals the original is
    rejected so reviewers don't have to triage no-op edits."""
    await _seed_active_templates(authed_client)
    agreement = await _create_agreement(authed_client)
    clauses = (await authed_client.get(f"/api/agreements/{agreement['id']}/clauses")).json()["clauses"]
    target = clauses[0]

    resp = await authed_client.post(
        f"/api/agreements/{agreement['id']}/revisions",
        json={
            "clause_hash": target["clause_hash"],
            "modified_text": target["text"],
        },
    )
    assert resp.status_code == 400
    assert "identical" in resp.json()["detail"].lower()


async def test_admin_cannot_self_accept(authed_client):
    """Segregation of duties: the user who created the revision can't be
    the one to accept it. Withdraw exists for that case."""
    await _seed_active_templates(authed_client)
    agreement = await _create_agreement(authed_client)
    clauses = (await authed_client.get(f"/api/agreements/{agreement['id']}/clauses")).json()["clauses"]
    create = await authed_client.post(
        f"/api/agreements/{agreement['id']}/revisions",
        json={
            "clause_hash": clauses[0]["clause_hash"],
            "modified_text": "[edited self-accept] " + clauses[0]["text"],
        },
    )
    rev_id = create.json()["id"]

    resp = await authed_client.post(
        f"/api/agreements/{agreement['id']}/revisions/{rev_id}/accept"
    )
    assert resp.status_code == 400
    assert "cannot accept or reject a revision you created" in resp.json()["detail"]


async def test_reviewer_accepts_revision_and_writes_audit(
    client, authed_client, admin_user, project_director_user, db_session
):
    """Admin creates -> PD accepts. PD's user has project_director role
    which is in REVIEWER_ROLES, so accept succeeds. An audit_log row is
    emitted with action=clause_revision.accepted."""
    await _seed_active_templates(authed_client)
    agreement = await _create_agreement(authed_client)
    clauses = (await authed_client.get(f"/api/agreements/{agreement['id']}/clauses")).json()["clauses"]
    target = clauses[5]  # any clause past the first few

    create = await authed_client.post(
        f"/api/agreements/{agreement['id']}/revisions",
        json={
            "clause_hash": target["clause_hash"],
            "modified_text": "[reviewer-accepted edit] " + target["text"],
        },
    )
    rev_id = create.json()["id"]

    # Switch to PD's token to perform the accept.
    pd_token = await _login(client, "pd@test.example", "revpass1")
    client.headers["Authorization"] = f"Bearer {pd_token}"
    accept = await client.post(
        f"/api/agreements/{agreement['id']}/revisions/{rev_id}/accept",
        json={"decision_note": "Reviewed by PD"},
    )
    assert accept.status_code == 200, accept.text
    body = accept.json()
    assert body["status"] == "accepted"
    assert body["decided_by"] == str(project_director_user.id)
    assert body["decision_note"] == "Reviewed by PD"
    assert body["decided_at"] is not None

    # Audit log entry must exist with the right action.
    from sqlalchemy import select
    from models.audit import AuditLog

    audits = (
        await db_session.execute(
            select(AuditLog).where(AuditLog.action == "clause_revision.accepted")
        )
    ).scalars().all()
    assert len(audits) == 1
    assert audits[0].entity_id == accept.json()["id"] or str(audits[0].entity_id) == rev_id
    assert audits[0].user_id == project_director_user.id


async def test_reviewer_rejects_with_note(client, authed_client, project_director_user):
    """Reject path mirrors accept: status flips, audit row written, original
    master text remains canonical for the render."""
    await _seed_active_templates(authed_client)
    agreement = await _create_agreement(authed_client)
    clauses = (await authed_client.get(f"/api/agreements/{agreement['id']}/clauses")).json()["clauses"]
    target = clauses[7]

    create = await authed_client.post(
        f"/api/agreements/{agreement['id']}/revisions",
        json={
            "clause_hash": target["clause_hash"],
            "modified_text": "[reviewer-rejected edit] " + target["text"],
        },
    )
    rev_id = create.json()["id"]

    pd_token = await _login(client, "pd@test.example", "revpass1")
    client.headers["Authorization"] = f"Bearer {pd_token}"
    reject = await client.post(
        f"/api/agreements/{agreement['id']}/revisions/{rev_id}/reject",
        json={"decision_note": "Out of scope for this round"},
    )
    assert reject.status_code == 200
    body = reject.json()
    assert body["status"] == "rejected"
    assert body["decision_note"] == "Out of scope for this round"


async def test_with_changes_pdf_embeds_pending_revisions(
    authed_client, admin_user, db_session
):
    """Phase 4 v2.2: the /preview/with_changes endpoint should render the
    pending revision's modified text inside the PDF AND keep the original
    text (as a <w:del> strikethrough that LibreOffice rasterises). Both
    strings have to appear in the extracted text so the side-by-side
    Compare view actually shows what changed."""
    import subprocess
    import tempfile

    await _seed_active_templates(authed_client)
    agreement = await _create_agreement(authed_client)

    # Populate F-fields so the rendered PDF has agreement-specific values.
    await authed_client.put(
        f"/api/agreements/{agreement['id']}/fields",
        json={"values": {"F02": "Test Subco Ltd", "F08": "1,234,567.00"}},
    )

    # Create a pending revision against a known clause.
    clauses = (await authed_client.get(f"/api/agreements/{agreement['id']}/clauses")).json()["clauses"]
    target = clauses[15]
    await authed_client.post(
        f"/api/agreements/{agreement['id']}/revisions",
        json={
            "clause_hash": target["clause_hash"],
            "modified_text": "[TRACK CHANGES MARKER] " + target["text"],
        },
    )

    resp = await authed_client.get(
        f"/api/pdf/{agreement['id']}/preview/with_changes"
    )
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"] == "application/pdf"

    # Persist + run pdftotext to peek inside.
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(resp.content)
        pdf_path = f.name
    text = subprocess.check_output(["pdftotext", "-layout", pdf_path, "-"]).decode()
    assert "[TRACK CHANGES MARKER]" in text, "pending revision text missing from with_changes PDF"
    # Both branches present: deletion (original) AND insertion (modified)
    # render in the PDF when track-changes is on. pdftotext can't see the
    # strikethrough style but DOES extract the deleted text.
    head = target["text"][:25]
    assert head in text, "original (deletion) text missing from with_changes PDF"


async def test_compare_table_shape_and_status(
    client, authed_client, admin_user, project_director_user
):
    """Package D (req 6.4): GET .../compare-table reshapes every clause
    revision on the agreement into Original / Revised+Amendment /
    Generated-by-Whom rows, regardless of status."""
    await _seed_active_templates(authed_client)
    agreement = await _create_agreement(authed_client)
    clauses = (await authed_client.get(f"/api/agreements/{agreement['id']}/clauses")).json()["clauses"]

    create = await authed_client.post(
        f"/api/agreements/{agreement['id']}/revisions",
        json={
            "clause_hash": clauses[3]["clause_hash"],
            "modified_text": "[compare-table edit] " + clauses[3]["text"],
            "change_reason": "client requested wording change",
        },
    )
    rev_id = create.json()["id"]

    # Still pending — should already show up in the table.
    table = await authed_client.get(f"/api/agreements/{agreement['id']}/compare-table")
    assert table.status_code == 200, table.text
    rows = table.json()["rows"]
    assert len(rows) == 1
    row = rows[0]
    assert row["id"] == rev_id
    assert row["clause_label"] == clauses[3]["clause_label"]
    assert row["original_text"] == clauses[3]["text"]
    assert row["revised_text"] == "[compare-table edit] " + clauses[3]["text"]
    assert row["change_reason"] == "client requested wording change"
    assert row["status"] == "pending"
    assert row["generated_by_name"] == admin_user.name
    assert row["generated_by_role"] == "admin"

    # PD accepts — the table reflects the new status without a new row.
    pd_token = await _login(client, "pd@test.example", "revpass1")
    client.headers["Authorization"] = f"Bearer {pd_token}"
    await client.post(f"/api/agreements/{agreement['id']}/revisions/{rev_id}/accept")

    table2 = await authed_client.get(f"/api/agreements/{agreement['id']}/compare-table")
    rows2 = table2.json()["rows"]
    assert len(rows2) == 1
    assert rows2[0]["status"] == "accepted"


async def test_compare_table_empty_when_no_revisions(authed_client):
    await _seed_active_templates(authed_client)
    agreement = await _create_agreement(authed_client)

    table = await authed_client.get(f"/api/agreements/{agreement['id']}/compare-table")
    assert table.status_code == 200
    assert table.json()["rows"] == []


async def test_cannot_decide_an_already_decided_revision(
    client, authed_client, project_director_user
):
    await _seed_active_templates(authed_client)
    agreement = await _create_agreement(authed_client)
    clauses = (await authed_client.get(f"/api/agreements/{agreement['id']}/clauses")).json()["clauses"]
    create = await authed_client.post(
        f"/api/agreements/{agreement['id']}/revisions",
        json={
            "clause_hash": clauses[9]["clause_hash"],
            "modified_text": "[double-decide] " + clauses[9]["text"],
        },
    )
    rev_id = create.json()["id"]

    pd_token = await _login(client, "pd@test.example", "revpass1")
    client.headers["Authorization"] = f"Bearer {pd_token}"
    await client.post(f"/api/agreements/{agreement['id']}/revisions/{rev_id}/accept")
    second = await client.post(
        f"/api/agreements/{agreement['id']}/revisions/{rev_id}/reject"
    )
    assert second.status_code == 400
    assert "already" in second.json()["detail"].lower()
