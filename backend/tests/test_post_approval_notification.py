"""Admin editing a field after a reviewer has already approved must (a) leave
that approval in place (no silent reset — see CLAUDE.md domain notes) and
(b) surface as modified_since_approval on that reviewer's step, derived from
agreement.updated_at vs the step's acted_at (no new column)."""

from __future__ import annotations

from datetime import date

import pytest
import pytest_asyncio

from models.user import RoleEnum


@pytest_asyncio.fixture
async def seeded_reviewers(db_session):
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


@pytest.mark.asyncio
async def test_field_edit_after_approval_flags_step_not_reset(
    authed_client, admin_user, seeded_reviewers
):
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

    admin_token = authed_client.headers["Authorization"]
    await authed_client.put(
        f"/api/agreements/{agreement['id']}/fields",
        json={"values": {"F02": "Original Value"}},
    )
    await authed_client.post(f"/api/agreements/{agreement['id']}/submit")

    detail = await authed_client.get(f"/api/workflow/agreements/{agreement['id']}")
    accounts_step = next(
        s for s in detail.json()["steps"] if s["role_required"] == "accounts"
    )
    assert accounts_step["modified_since_approval"] is False

    accounts_token = await _login(authed_client, "accounts@test.example")
    authed_client.headers["Authorization"] = f"Bearer {accounts_token}"
    approve = await authed_client.post(f"/api/workflow/{accounts_step['id']}/approve")
    assert approve.status_code == 200

    # Admin edits a field after Accounts already approved.
    authed_client.headers["Authorization"] = admin_token
    edit = await authed_client.put(
        f"/api/agreements/{agreement['id']}/fields",
        json={"values": {"F02": "Changed after approval"}},
    )
    assert edit.status_code == 200

    detail2 = await authed_client.get(f"/api/workflow/agreements/{agreement['id']}")
    steps_by_role = {s["role_required"]: s for s in detail2.json()["steps"]}

    # Approval itself is untouched — no silent reset.
    assert steps_by_role["accounts"]["status"] == "approved"
    # But it's now flagged as modified since that approval.
    assert steps_by_role["accounts"]["modified_since_approval"] is True
    # A still-pending step has nothing to flag.
    assert steps_by_role["project_director"]["modified_since_approval"] is False
