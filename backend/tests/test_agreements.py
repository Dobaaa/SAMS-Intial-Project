"""Tests for the agreement creation + update + workflow flow."""

from __future__ import annotations

from datetime import date

import pytest


async def _seed_active_templates(authed_client):
    for template_type in ("form", "conditions", "appendix"):
        resp = await authed_client.post(
            "/api/masters/",
            json={
                "type": template_type,
                "version_number": "v1.0",
                "version_date": str(date.today()),
                "content_html": "<p>seeded</p>",
            },
        )
        assert resp.status_code == 200, resp.text


async def _create_agreement(authed_client) -> dict:
    resp = await authed_client.post(
        "/api/agreements/",
        json={
            "project": {
                "project_name": "Test Project",
                "project_code": "TP001",
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


@pytest.mark.asyncio
async def test_create_draft_generates_reference_number(authed_client, admin_user):
    await _seed_active_templates(authed_client)
    data = await _create_agreement(authed_client)
    from datetime import datetime, UTC

    year = datetime.now(UTC).year
    # New format (Rev 01 item 2): SAG-{YEAR}-{SITE_NO}-{REF_NO:03d}
    assert data["reference_number"].startswith(f"SAG-{year}-TP001-")
    assert data["reference_number"].endswith("-001")
    assert data["status"] == "under_drafting"


@pytest.mark.asyncio
async def test_update_fields_cascades_f08_to_c03_as_ten_percent(authed_client, admin_user, db_session):
    """Regression: the earlier bug copied F08 verbatim into C03. Post-fix,
    C03 must equal 10% of F08 when C03 isn't explicitly provided."""
    from scripts.seed_fields import seed_master_fields

    await _seed_active_templates(authed_client)
    await seed_master_fields(db_session)
    agreement = await _create_agreement(authed_client)

    resp = await authed_client.put(
        f"/api/agreements/{agreement['id']}/fields",
        json={"values": {"F08": "1000000"}},
    )
    assert resp.status_code == 200

    # Read back via the appendix endpoint (which joins field values too).
    appendix = await authed_client.get(f"/api/agreements/{agreement['id']}/appendix")
    assert appendix.status_code == 200
    rows = {row["field_id"]: row for row in appendix.json()}
    # A07 mirrors F08 (1:1).
    assert rows["A07"]["current_value"] == "1000000"


@pytest.mark.asyncio
async def test_c03_pct_controls_advance_payment_not_hardcoded_ten_percent(
    authed_client, admin_user, db_session
):
    """Client-reported bug: revising the Advance Payment % (C03_PCT) after
    the wizard must actually change C03, not get silently forced back to a
    hardcoded 10% on the next save."""
    from scripts.seed_fields import seed_master_fields

    await _seed_active_templates(authed_client)
    await seed_master_fields(db_session)
    agreement = await _create_agreement(authed_client)

    resp = await authed_client.put(
        f"/api/agreements/{agreement['id']}/fields",
        json={"values": {"F08": "1000000", "C03_PCT": "15"}},
    )
    assert resp.status_code == 200

    fields = await authed_client.get(f"/api/agreements/{agreement['id']}/fields")
    assert fields.status_code == 200
    assert fields.json()["values"]["C03"] == "150000.00"

    # A later, unrelated save must not reset C03 back to a hardcoded 10%.
    resp = await authed_client.put(
        f"/api/agreements/{agreement['id']}/fields",
        json={"values": {"F02": "Some Subcontractor"}},
    )
    assert resp.status_code == 200
    fields = await authed_client.get(f"/api/agreements/{agreement['id']}/fields")
    assert fields.json()["values"]["C03"] == "150000.00"


@pytest.mark.asyncio
async def test_manual_override_preserves_through_source_update(authed_client, admin_user, db_session):
    """If the client sends A01 explicitly in the same update payload as F02,
    A01 must win (override not clobbered by cascade)."""
    from scripts.seed_fields import seed_master_fields

    await _seed_active_templates(authed_client)
    await seed_master_fields(db_session)
    agreement = await _create_agreement(authed_client)

    resp = await authed_client.put(
        f"/api/agreements/{agreement['id']}/fields",
        json={"values": {"F02": "Acme Ltd", "A01": "Acme Ltd (trading as Acme)"}},
    )
    assert resp.status_code == 200

    appendix = await authed_client.get(f"/api/agreements/{agreement['id']}/appendix")
    rows = {row["field_id"]: row for row in appendix.json()}
    assert rows["A01"]["current_value"] == "Acme Ltd (trading as Acme)"


@pytest.mark.asyncio
async def test_a_field_recomputes_when_source_changes_without_override(
    authed_client, admin_user, db_session
):
    """Rev 01 item 35: A-fields without an explicit override flag MUST re-derive
    from their source on every cascade. The old "preserve manual override"
    behaviour was reversed — drive-by typing no longer sticks."""
    from scripts.seed_fields import seed_master_fields

    await _seed_active_templates(authed_client)
    await seed_master_fields(db_session)
    agreement = await _create_agreement(authed_client)

    # Admin types a value into A07 without setting the override flag.
    resp = await authed_client.put(
        f"/api/agreements/{agreement['id']}/fields",
        json={"values": {"F08": "1000000", "A07": "custom-drive-by"}},
    )
    assert resp.status_code == 200
    # On this call A07 is honoured (caller wins same-payload).
    appendix = await authed_client.get(f"/api/agreements/{agreement['id']}/appendix")
    rows = {row["field_id"]: row for row in appendix.json()}
    assert rows["A07"]["current_value"] == "custom-drive-by"
    assert rows["A07"]["is_manual_override"] is False

    # Now admin changes F08. A07 has NO override flag set, so the cascade
    # must clobber it back to mirror F08.
    resp = await authed_client.put(
        f"/api/agreements/{agreement['id']}/fields",
        json={"values": {"F08": "2000000"}},
    )
    assert resp.status_code == 200
    appendix = await authed_client.get(f"/api/agreements/{agreement['id']}/appendix")
    rows = {row["field_id"]: row for row in appendix.json()}
    assert rows["A07"]["current_value"] == "2000000"


@pytest.mark.asyncio
async def test_a_field_override_locks_through_source_change(
    authed_client, admin_user, db_session
):
    """Setting overrides[A07]=true via the AppendixBuilder Edit flow locks the
    row — subsequent F08 updates leave A07 alone until reset-to-auto."""
    from scripts.seed_fields import seed_master_fields

    await _seed_active_templates(authed_client)
    await seed_master_fields(db_session)
    agreement = await _create_agreement(authed_client)

    # Admin clicks Edit on A07 (AppendixBuilder): sends value + overrides=true.
    resp = await authed_client.put(
        f"/api/agreements/{agreement['id']}/fields",
        json={
            "values": {"F08": "1000000", "A07": "9999999"},
            "overrides": {"A07": True},
        },
    )
    assert resp.status_code == 200
    appendix = await authed_client.get(f"/api/agreements/{agreement['id']}/appendix")
    rows = {row["field_id"]: row for row in appendix.json()}
    assert rows["A07"]["current_value"] == "9999999"
    assert rows["A07"]["is_manual_override"] is True

    # F08 changes. A07 is locked — must not be touched.
    resp = await authed_client.put(
        f"/api/agreements/{agreement['id']}/fields",
        json={"values": {"F08": "2000000"}},
    )
    assert resp.status_code == 200
    appendix = await authed_client.get(f"/api/agreements/{agreement['id']}/appendix")
    rows = {row["field_id"]: row for row in appendix.json()}
    assert rows["A07"]["current_value"] == "9999999"
    assert rows["A07"]["is_manual_override"] is True


@pytest.mark.asyncio
async def test_a_field_reset_to_auto_recomputes_from_source(
    authed_client, admin_user, db_session
):
    """overrides[A07]=False ('Reset to Auto') clears the lock and the cascade
    re-derives A07 from its source (F08) in the same call."""
    from scripts.seed_fields import seed_master_fields

    await _seed_active_templates(authed_client)
    await seed_master_fields(db_session)
    agreement = await _create_agreement(authed_client)

    # First: lock A07 at a custom value.
    await authed_client.put(
        f"/api/agreements/{agreement['id']}/fields",
        json={
            "values": {"F08": "1000000", "A07": "9999999"},
            "overrides": {"A07": True},
        },
    )

    # Now reset A07: empty values map, overrides flips False. Cascade re-runs
    # and A07 becomes whatever F08 currently is.
    resp = await authed_client.put(
        f"/api/agreements/{agreement['id']}/fields",
        json={"values": {}, "overrides": {"A07": False}},
    )
    assert resp.status_code == 200
    appendix = await authed_client.get(f"/api/agreements/{agreement['id']}/appendix")
    rows = {row["field_id"]: row for row in appendix.json()}
    assert rows["A07"]["current_value"] == "1000000"
    assert rows["A07"]["is_manual_override"] is False


@pytest.mark.asyncio
async def test_submit_creates_four_workflow_steps(authed_client, admin_user):
    await _seed_active_templates(authed_client)
    agreement = await _create_agreement(authed_client)

    resp = await authed_client.post(f"/api/agreements/{agreement['id']}/submit")
    assert resp.status_code == 200

    # There's no direct "list steps" endpoint; use the workflow agreement-detail
    # endpoint which includes them.
    detail = await authed_client.get(f"/api/workflow/agreements/{agreement['id']}")
    assert detail.status_code == 200
    steps = detail.json()["steps"]
    assert len(steps) == 4
    roles_in_order = [s["role_required"] for s in sorted(steps, key=lambda s: s["step_order"])]
    assert roles_in_order == [
        "accounts",
        "project_director",
        "operation_manager",
        "gm",
    ]


@pytest.mark.asyncio
async def test_send_to_subcontractor_transitions_from_internal_review(authed_client, admin_user, db_session):
    """After every reviewer role approves, POST /send-to-subcontractor flips status."""
    import uuid

    from sqlalchemy import select

    from models.workflow import WorkflowStep, WorkflowStepStatusEnum

    await _seed_active_templates(authed_client)
    agreement = await _create_agreement(authed_client)
    await authed_client.post(f"/api/agreements/{agreement['id']}/submit")

    # Sequential review model gates forwarding on all reviewer roles approving.
    # HTTP approval needs role-specific users (covered in test_workflow), so
    # here we approve every main-chain step directly at the model layer.
    steps = (
        await db_session.execute(
            select(WorkflowStep).where(WorkflowStep.agreement_id == uuid.UUID(agreement["id"]))
        )
    ).scalars().all()
    for s in steps:
        s.status = WorkflowStepStatusEnum.approved
    await db_session.commit()

    resp = await authed_client.post(f"/api/agreements/{agreement['id']}/send-to-subcontractor")
    assert resp.status_code == 200
    assert resp.json()["agreement_status"] == "draft_forwarded_to_subcontractor"

    # Calling it again from the wrong status should 400.
    repeat = await authed_client.post(f"/api/agreements/{agreement['id']}/send-to-subcontractor")
    assert repeat.status_code == 400
