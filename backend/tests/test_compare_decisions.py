"""Tests for per-row Compare-table decisions (2026-08-26 client feedback:
"a decision action for every change ... not for all the changes").

Covers the new field-row decision endpoint, the finalize-check aggregate
(approve_step/return_step reuse), and that resubmit clears stale per-cycle
field decisions without touching clause-revision decisions.
"""
from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import select

from models.agreement import AgreementFieldReview
from services.auth_service import hash_password

pytestmark = pytest.mark.asyncio


ROLE_LOGINS = [
    ("accounts", "accounts@test.example"),
    ("project_director", "project_director@test.example"),
    ("operation_manager", "operation_manager@test.example"),
    ("gm", "gm@test.example"),
]


@pytest.fixture
async def seeded_reviewers(db_session):
    from models.user import RoleEnum, User

    users = {}
    for role in [
        RoleEnum.project_director,
        RoleEnum.accounts,
        RoleEnum.operation_manager,
        RoleEnum.gm,
    ]:
        user = User(
            name=f"Test {role.value}",
            email=f"{role.value}@test.example",
            password_hash=hash_password("testpass1"),
            role=role,
            is_active=True,
        )
        db_session.add(user)
        users[role.value] = user
    await db_session.commit()
    for u in users.values():
        await db_session.refresh(u)
    return users


async def _login(client, email, password="testpass1") -> str:
    resp = await client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


async def _make_submitted_agreement_with_field(authed_client) -> dict:
    """Seed templates + one real Conditions field (C01) + create a draft,
    fill C01, and submit for review — so the compare-table has exactly one
    "field" kind row to decide on."""
    template_ids: dict[str, str] = {}
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
        template_ids[template_type] = resp.json()["id"]

    field = await authed_client.post(
        "/api/masters/fields/",
        json={
            "template_id": template_ids["conditions"],
            "field_id": "C01",
            "clause_number": "2.2",
            "field_label": "Scope of Works",
            "input_type": "textarea",
        },
    )
    assert field.status_code == 200, field.text

    create = await authed_client.post(
        "/api/agreements/",
        json={
            "project": {"project_name": "P", "project_code": "P001"},
            "subcontractor": {"company_name": "S"},
        },
    )
    agreement = create.json()

    fields_resp = await authed_client.put(
        f"/api/agreements/{agreement['id']}/fields", json={"values": {"C01": "Steel works"}}
    )
    assert fields_resp.status_code == 200, fields_resp.text

    submit = await authed_client.post(f"/api/agreements/{agreement['id']}/submit")
    assert submit.status_code == 200, submit.text
    return agreement


async def _walk_to_gm(client, agreement_id: str) -> None:
    """Approve Accounts -> PD -> OM in order via the plain workflow-step
    endpoint (unrelated to per-row decisions), leaving GM as the only
    actionable reviewer."""
    steps = (await client.get(f"/api/workflow/agreements/{agreement_id}")).json()["steps"]
    steps_by_role = {s["role_required"]: s for s in steps}
    for role_value, email in ROLE_LOGINS[:3]:
        token = await _login(client, email)
        client.headers["Authorization"] = f"Bearer {token}"
        approve = await client.post(f"/api/workflow/{steps_by_role[role_value]['id']}/approve")
        assert approve.status_code == 200, approve.text


async def _login_as_gm(client) -> None:
    token = await _login(client, "gm@test.example")
    client.headers["Authorization"] = f"Bearer {token}"


async def test_partial_field_decisions_leave_step_pending(authed_client, admin_user, seeded_reviewers):
    agreement = await _make_submitted_agreement_with_field(authed_client)
    await _walk_to_gm(authed_client, agreement["id"])
    await _login_as_gm(authed_client)

    finalize = await authed_client.post(f"/api/agreements/{agreement['id']}/compare-table/finalize-check")
    assert finalize.status_code == 200
    assert finalize.json()["step_finalized"] is False

    steps = (await authed_client.get(f"/api/workflow/agreements/{agreement['id']}")).json()["steps"]
    gm_step = next(s for s in steps if s["role_required"] == "gm")
    assert gm_step["status"] == "pending"


async def test_all_approved_finalizes_step_and_sets_gm_approval_date(
    authed_client, admin_user, seeded_reviewers
):
    agreement = await _make_submitted_agreement_with_field(authed_client)
    await _walk_to_gm(authed_client, agreement["id"])
    await _login_as_gm(authed_client)

    decide = await authed_client.post(
        f"/api/agreements/{agreement['id']}/compare-table/fields/C01/decision",
        json={"decision": "approved", "comment_text": "Looks fine"},
    )
    assert decide.status_code == 200, decide.text
    assert decide.json()["decision_status"] == "approved"

    finalize = await authed_client.post(f"/api/agreements/{agreement['id']}/compare-table/finalize-check")
    assert finalize.status_code == 200, finalize.text
    assert finalize.json() == {"step_finalized": True, "step_result": "approved"}

    steps = (await authed_client.get(f"/api/workflow/agreements/{agreement['id']}")).json()["steps"]
    gm_step = next(s for s in steps if s["role_required"] == "gm")
    assert gm_step["status"] == "approved"

    summary = await authed_client.get(f"/api/workflow/agreements/{agreement['id']}")
    assert summary.json()["agreement"]["gm_approval_date"] is not None


async def test_reject_finalizes_via_return_step(authed_client, admin_user, seeded_reviewers):
    agreement = await _make_submitted_agreement_with_field(authed_client)
    await _walk_to_gm(authed_client, agreement["id"])
    await _login_as_gm(authed_client)

    decide = await authed_client.post(
        f"/api/agreements/{agreement['id']}/compare-table/fields/C01/decision",
        json={"decision": "rejected", "comment_text": "Please reword this clause"},
    )
    assert decide.status_code == 200, decide.text

    finalize = await authed_client.post(f"/api/agreements/{agreement['id']}/compare-table/finalize-check")
    assert finalize.status_code == 200
    assert finalize.json() == {"step_finalized": True, "step_result": "returned"}

    detail = await authed_client.get(f"/api/agreements/{agreement['id']}")
    assert detail.json()["current_status"] == "under_bgcc_revision"


async def test_field_decision_403_without_actionable_step(authed_client, admin_user, seeded_reviewers):
    agreement = await _make_submitted_agreement_with_field(authed_client)
    # Nobody has approved yet -- GM is not actionable.
    await _login_as_gm(authed_client)

    decide = await authed_client.post(
        f"/api/agreements/{agreement['id']}/compare-table/fields/C01/decision",
        json={"decision": "approved", "comment_text": None},
    )
    assert decide.status_code == 403


async def test_reject_field_requires_comment(authed_client, admin_user, seeded_reviewers):
    agreement = await _make_submitted_agreement_with_field(authed_client)
    await _walk_to_gm(authed_client, agreement["id"])
    await _login_as_gm(authed_client)

    decide = await authed_client.post(
        f"/api/agreements/{agreement['id']}/compare-table/fields/C01/decision",
        json={"decision": "rejected", "comment_text": "   "},
    )
    assert decide.status_code == 400


async def test_field_decision_idempotent_upsert(authed_client, admin_user, seeded_reviewers, db_session):
    agreement = await _make_submitted_agreement_with_field(authed_client)
    await _walk_to_gm(authed_client, agreement["id"])
    await _login_as_gm(authed_client)

    first = await authed_client.post(
        f"/api/agreements/{agreement['id']}/compare-table/fields/C01/decision",
        json={"decision": "approved", "comment_text": None},
    )
    assert first.status_code == 200

    second = await authed_client.post(
        f"/api/agreements/{agreement['id']}/compare-table/fields/C01/decision",
        json={"decision": "rejected", "comment_text": "Actually no"},
    )
    assert second.status_code == 200
    assert second.json()["decision_status"] == "rejected"

    rows = (
        await db_session.execute(
            select(AgreementFieldReview).where(AgreementFieldReview.field_id == "C01")
        )
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].status == "rejected"


async def test_unknown_field_id_404s(authed_client, admin_user, seeded_reviewers):
    agreement = await _make_submitted_agreement_with_field(authed_client)
    await _walk_to_gm(authed_client, agreement["id"])
    await _login_as_gm(authed_client)

    decide = await authed_client.post(
        f"/api/agreements/{agreement['id']}/compare-table/fields/DOES-NOT-EXIST/decision",
        json={"decision": "approved", "comment_text": None},
    )
    assert decide.status_code == 404


async def test_resubmit_clears_stale_field_reviews(authed_client, admin_user, seeded_reviewers, db_session):
    agreement = await _make_submitted_agreement_with_field(authed_client)
    await _walk_to_gm(authed_client, agreement["id"])
    await _login_as_gm(authed_client)

    await authed_client.post(
        f"/api/agreements/{agreement['id']}/compare-table/fields/C01/decision",
        json={"decision": "rejected", "comment_text": "Needs work"},
    )
    finalize = await authed_client.post(f"/api/agreements/{agreement['id']}/compare-table/finalize-check")
    assert finalize.json()["step_result"] == "returned"

    admin_token = await _login(authed_client, "admin@test.example", password="adminpass1")
    authed_client.headers["Authorization"] = f"Bearer {admin_token}"
    resubmit = await authed_client.post(f"/api/agreements/{agreement['id']}/resubmit")
    assert resubmit.status_code == 200, resubmit.text

    remaining = (
        await db_session.execute(
            select(AgreementFieldReview).where(AgreementFieldReview.field_id == "C01")
        )
    ).scalars().all()
    assert remaining == []
