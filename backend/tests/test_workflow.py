"""Tests for the approval workflow engine (approve / return / resubmit).

Covers the main 4-step chain. Resolution chain is exercised in test_resolution.
"""

from __future__ import annotations

from datetime import date

import pytest
import pytest_asyncio

from models.user import RoleEnum


@pytest_asyncio.fixture
async def seeded_reviewers(db_session):
    """Seed one user for each approval-chain role + return a dict keyed by role."""
    from models.user import User
    from services.auth_service import hash_password

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
    assert resp.status_code == 200
    return resp.json()["access_token"]


async def _make_submitted_agreement(authed_client) -> dict:
    """Seed templates + create a draft + submit it for review."""
    for template_type in ("form", "conditions", "appendix"):
        await authed_client.post(
            "/api/masters/",
            json={
                "type": template_type,
                "version_number": "v1.0",
                "version_date": str(date.today()),
                "content_html": "<p>seeded</p>",
            },
        )
    create = await authed_client.post(
        "/api/agreements/",
        json={
            "project": {"project_name": "P", "project_code": "P001"},
            "subcontractor": {"company_name": "S"},
        },
    )
    agreement = create.json()
    await authed_client.post(f"/api/agreements/{agreement['id']}/submit")
    return agreement


@pytest.mark.asyncio
async def test_comment_is_nonblocking(
    authed_client, admin_user, seeded_reviewers
):
    """Flat model: a reviewer comment is recorded for all roles WITHOUT
    flipping the step to returned or changing the agreement status."""
    agreement = await _make_submitted_agreement(authed_client)

    detail = await authed_client.get(f"/api/workflow/agreements/{agreement['id']}")
    pd_step = next(
        s for s in detail.json()["steps"] if s["role_required"] == "project_director"
    )

    pd_token = await _login(authed_client, "project_director@test.example")
    authed_client.headers["Authorization"] = f"Bearer {pd_token}"

    # Empty comment is rejected.
    empty = await authed_client.post(
        f"/api/workflow/{pd_step['id']}/comment",
        json={"comment_text": "   "},
    )
    assert empty.status_code == 400

    # A real comment is recorded and tagged with the author.
    resp = await authed_client.post(
        f"/api/workflow/{pd_step['id']}/comment",
        json={"comment_text": "Please clarify clause 3.4.1", "clause_reference": "3.4.1"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "commented"

    detail2 = await authed_client.get(f"/api/workflow/agreements/{agreement['id']}")
    statuses = {s["step_name"]: s["status"] for s in detail2.json()["steps"]}
    # Non-blocking: PD step stays pending, agreement stays under_internal_review.
    assert statuses["Project Director"] == "pending"
    assert detail2.json()["agreement"]["current_status"] == "under_internal_review"
    comments = detail2.json()["comments"]
    assert any("3.4.1" in (c.get("clause_reference") or "") for c in comments)
    assert any(c.get("author_role") == "project_director" for c in comments)


@pytest.mark.asyncio
async def test_all_roles_must_approve_in_order_before_forwarding(
    authed_client, admin_user, seeded_reviewers
):
    """Forwarding to the subcontractor is gated on every reviewer role
    approving, in the sequential order Accounts -> PD -> OM -> GM."""
    agreement = await _make_submitted_agreement(authed_client)
    detail = await authed_client.get(f"/api/workflow/agreements/{agreement['id']}")
    steps_by_role = {s["role_required"]: s for s in detail.json()["steps"]}

    admin_token = await _login(authed_client, "admin@test.example", password="adminpass1")

    # With nobody approved yet, Admin cannot forward.
    authed_client.headers["Authorization"] = f"Bearer {admin_token}"
    early = await authed_client.post(f"/api/agreements/{agreement['id']}/send-to-subcontractor")
    assert early.status_code == 400

    # Out-of-order approval is rejected: OM can't approve before Accounts/PD.
    om_token = await _login(authed_client, "operation_manager@test.example")
    authed_client.headers["Authorization"] = f"Bearer {om_token}"
    out_of_order = await authed_client.post(
        f"/api/workflow/{steps_by_role['operation_manager']['id']}/approve"
    )
    assert out_of_order.status_code == 400

    # Each role approves in the required order.
    for role_value, email in [
        ("accounts", "accounts@test.example"),
        ("project_director", "project_director@test.example"),
        ("operation_manager", "operation_manager@test.example"),
        ("gm", "gm@test.example"),
    ]:
        token = await _login(authed_client, email)
        authed_client.headers["Authorization"] = f"Bearer {token}"
        approve = await authed_client.post(
            f"/api/workflow/{steps_by_role[role_value]['id']}/approve"
        )
        assert approve.status_code == 200

    # All approved -> Admin can now forward.
    authed_client.headers["Authorization"] = f"Bearer {admin_token}"
    forward = await authed_client.post(f"/api/agreements/{agreement['id']}/send-to-subcontractor")
    assert forward.status_code == 200
    assert forward.json()["agreement_status"] == "draft_forwarded_to_subcontractor"


@pytest.mark.asyncio
async def test_only_first_in_chain_sees_agreement_initially(
    authed_client, admin_user, seeded_reviewers
):
    """Sequential model: only Accounts (first in chain) sees a freshly
    submitted agreement in /workflow/pending. PD/OM/GM unlock as each prior
    role approves."""
    agreement = await _make_submitted_agreement(authed_client)

    accounts_token = await _login(authed_client, "accounts@test.example")
    authed_client.headers["Authorization"] = f"Bearer {accounts_token}"
    pending = await authed_client.get("/api/workflow/pending")
    assert pending.status_code == 200
    assert any(
        it["agreement"]["reference_number"] == agreement["reference_number"]
        for it in pending.json()
    ), "Accounts should see the agreement immediately"

    for email in [
        "project_director@test.example",
        "operation_manager@test.example",
        "gm@test.example",
    ]:
        token = await _login(authed_client, email)
        authed_client.headers["Authorization"] = f"Bearer {token}"
        pending = await authed_client.get("/api/workflow/pending")
        assert pending.status_code == 200
        assert not any(
            it["agreement"]["reference_number"] == agreement["reference_number"]
            for it in pending.json()
        ), f"{email} should NOT see the agreement before Accounts approves"

    # Accounts approves -> PD unlocks.
    authed_client.headers["Authorization"] = f"Bearer {accounts_token}"
    detail = await authed_client.get(f"/api/workflow/agreements/{agreement['id']}")
    steps_by_role = {s["role_required"]: s for s in detail.json()["steps"]}
    approve = await authed_client.post(
        f"/api/workflow/{steps_by_role['accounts']['id']}/approve"
    )
    assert approve.status_code == 200

    pd_token = await _login(authed_client, "project_director@test.example")
    authed_client.headers["Authorization"] = f"Bearer {pd_token}"
    pending = await authed_client.get("/api/workflow/pending")
    assert any(
        it["agreement"]["reference_number"] == agreement["reference_number"]
        for it in pending.json()
    ), "PD should see the agreement once Accounts has approved"


@pytest.mark.asyncio
async def test_approve_with_comments_records_comment(
    authed_client, admin_user, seeded_reviewers
):
    """'Approved with comments' approves the step AND attaches a comment,
    in one call."""
    agreement = await _make_submitted_agreement(authed_client)
    detail = await authed_client.get(f"/api/workflow/agreements/{agreement['id']}")
    accounts_step = next(
        s for s in detail.json()["steps"] if s["role_required"] == "accounts"
    )

    token = await _login(authed_client, "accounts@test.example")
    authed_client.headers["Authorization"] = f"Bearer {token}"
    resp = await authed_client.post(
        f"/api/workflow/{accounts_step['id']}/approve",
        json={"comment_text": "Looks fine, minor note on 3.4", "clause_reference": "3.4"},
    )
    assert resp.status_code == 200
    assert resp.json()["comment_id"] is not None

    detail2 = await authed_client.get(f"/api/workflow/agreements/{agreement['id']}")
    statuses = {s["role_required"]: s["status"] for s in detail2.json()["steps"]}
    assert statuses["accounts"] == "approved"
    assert any(
        c["clause_reference"] == "3.4" for c in detail2.json()["comments"]
    )


@pytest.mark.asyncio
async def test_reject_with_comments_returns_step(
    authed_client, admin_user, seeded_reviewers
):
    """'Rejected with comments' flips the step to returned and the agreement
    to under_bgcc_revision, via the existing return_step path."""
    agreement = await _make_submitted_agreement(authed_client)
    detail = await authed_client.get(f"/api/workflow/agreements/{agreement['id']}")
    accounts_step = next(
        s for s in detail.json()["steps"] if s["role_required"] == "accounts"
    )

    token = await _login(authed_client, "accounts@test.example")
    authed_client.headers["Authorization"] = f"Bearer {token}"
    resp = await authed_client.post(
        f"/api/workflow/{accounts_step['id']}/return",
        json={"comment_text": "Please revise clause 3.4", "clause_reference": "3.4"},
    )
    assert resp.status_code == 200

    detail2 = await authed_client.get(f"/api/workflow/agreements/{agreement['id']}")
    statuses = {s["role_required"]: s["status"] for s in detail2.json()["steps"]}
    assert statuses["accounts"] == "returned"
    assert detail2.json()["agreement"]["current_status"] == "under_bgcc_revision"
