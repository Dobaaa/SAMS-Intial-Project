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
            email=f"{role.value}@test.local",
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
async def test_return_step_requires_comment_and_resets_status(
    authed_client, admin_user, seeded_reviewers
):
    agreement = await _make_submitted_agreement(authed_client)

    # Find the PD step.
    detail = await authed_client.get(f"/api/workflow/agreements/{agreement['id']}")
    pd_step = next(
        s for s in detail.json()["steps"] if s["role_required"] == "project_director"
    )

    # Log in as PD.
    pd_token = await _login(authed_client, "project_director@test.local")
    authed_client.headers["Authorization"] = f"Bearer {pd_token}"

    # Empty comment is rejected.
    empty = await authed_client.post(
        f"/api/workflow/{pd_step['id']}/return",
        json={"comment_text": "   "},
    )
    assert empty.status_code == 400

    # With a real comment it returns with status=returned + creates the comment.
    resp = await authed_client.post(
        f"/api/workflow/{pd_step['id']}/return",
        json={"comment_text": "Please fix clause 3.4.1", "clause_reference": "3.4.1"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "returned"

    detail2 = await authed_client.get(f"/api/workflow/agreements/{agreement['id']}")
    statuses = {s["step_name"]: s["status"] for s in detail2.json()["steps"]}
    assert statuses["Project Director"] == "returned"
    comments = detail2.json()["comments"]
    assert any("3.4.1" in (c.get("clause_reference") or "") for c in comments)


@pytest.mark.asyncio
async def test_resubmit_reactivates_the_whole_chain(
    authed_client, admin_user, seeded_reviewers
):
    """A mid-chain return + resubmit must wipe prior approvals and put every
    step (including PD/Accounts that had already approved) back to pending."""
    agreement = await _make_submitted_agreement(authed_client)
    detail = await authed_client.get(f"/api/workflow/agreements/{agreement['id']}")
    steps_by_role = {s["role_required"]: s for s in detail.json()["steps"]}

    # PD approves.
    pd_token = await _login(authed_client, "project_director@test.local")
    authed_client.headers["Authorization"] = f"Bearer {pd_token}"
    await authed_client.post(f"/api/workflow/{steps_by_role['project_director']['id']}/approve")

    # Accounts approves.
    acc_token = await _login(authed_client, "accounts@test.local")
    authed_client.headers["Authorization"] = f"Bearer {acc_token}"
    await authed_client.post(f"/api/workflow/{steps_by_role['accounts']['id']}/approve")

    # OM returns it (mid-chain).
    om_token = await _login(authed_client, "operation_manager@test.local")
    authed_client.headers["Authorization"] = f"Bearer {om_token}"
    await authed_client.post(
        f"/api/workflow/{steps_by_role['operation_manager']['id']}/return",
        json={"comment_text": "rework needed"},
    )

    # Admin resubmits.
    admin_token = await _login(authed_client, "admin@test.local", password="adminpass1")
    authed_client.headers["Authorization"] = f"Bearer {admin_token}"
    resp = await authed_client.post(f"/api/agreements/{agreement['id']}/resubmit")
    assert resp.status_code == 200

    # Every main-chain step must be pending again with cleared actor stamps,
    # i.e. PD + Accounts approvals are wiped and the chain restarts at PD.
    detail2 = await authed_client.get(f"/api/workflow/agreements/{agreement['id']}")
    for s in detail2.json()["steps"]:
        assert s["status"] == "pending", f"{s['step_name']} should be pending"
        assert s["acted_by"] is None, f"{s['step_name']} acted_by should be cleared"
        assert s["acted_at"] is None, f"{s['step_name']} acted_at should be cleared"


@pytest.mark.asyncio
async def test_pending_list_filters_by_current_user_role(
    authed_client, admin_user, seeded_reviewers
):
    agreement = await _make_submitted_agreement(authed_client)

    pd_token = await _login(authed_client, "project_director@test.local")
    authed_client.headers["Authorization"] = f"Bearer {pd_token}"

    pending = await authed_client.get("/api/workflow/pending")
    assert pending.status_code == 200
    items = pending.json()
    assert any(it["agreement"]["reference_number"] == agreement["reference_number"] for it in items)

    # Accounts user should not see it yet (PD must approve first).
    accounts_token = await _login(authed_client, "accounts@test.local")
    authed_client.headers["Authorization"] = f"Bearer {accounts_token}"
    pending2 = await authed_client.get("/api/workflow/pending")
    assert not any(
        it["agreement"]["reference_number"] == agreement["reference_number"] for it in pending2.json()
    )
