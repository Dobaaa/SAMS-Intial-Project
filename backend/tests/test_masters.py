"""Tests for master-template / master-field routes.

Primary regression target: the `PUT /api/masters/fields/reorder` route
used to be shadowed by `PUT /api/masters/fields/{field_id: UUID}` and
return 422 because "reorder" is not a UUID. See
``fix(masters): move /fields/reorder route above /fields/{field_id}``.
"""

from __future__ import annotations

import uuid
from datetime import date

import pytest


async def _create_template_and_fields(authed_client):
    """Create a master template and seed three fields; return their IDs in order."""
    template_resp = await authed_client.post(
        "/api/masters/",
        json={
            "type": "form",
            "version_number": "v1.0",
            "version_date": str(date.today()),
            "content_html": "<p>Test template with {{F01}} {{F02}}</p>",
            "notes": "test template",
        },
    )
    assert template_resp.status_code == 200
    template_id = template_resp.json()["id"]

    field_ids: list[str] = []
    for i, fid in enumerate(["F01", "F02", "F03"]):
        resp = await authed_client.post(
            "/api/masters/fields/",
            json={
                "template_id": template_id,
                "field_id": fid,
                "clause_number": "1",
                "field_label": f"Label for {fid}",
                "input_type": "text",
                "sort_order": i,
            },
        )
        assert resp.status_code == 200, resp.text
        field_ids.append(resp.json()["id"])
    return template_id, field_ids


@pytest.mark.asyncio
async def test_reorder_route_is_reachable(authed_client, admin_user):
    """Regression: PUT /fields/reorder must not be 422'd by the UUID path
    validator on /fields/{field_id}."""
    template_id, field_ids = await _create_template_and_fields(authed_client)

    # Reorder: put F03 first.
    resp = await authed_client.put(
        "/api/masters/fields/reorder",
        json={
            "items": [
                {"id": field_ids[2], "sort_order": 0},
                {"id": field_ids[0], "sort_order": 1},
                {"id": field_ids[1], "sort_order": 2},
            ]
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "success"

    # Verify order persisted.
    fields_resp = await authed_client.get(f"/api/masters/fields/{template_id}")
    assert fields_resp.status_code == 200
    sorted_by_order = sorted(fields_resp.json(), key=lambda f: f["sort_order"])
    assert [f["field_id"] for f in sorted_by_order] == ["F03", "F01", "F02"]


@pytest.mark.asyncio
async def test_creating_second_version_deactivates_previous(authed_client, admin_user):
    first = await authed_client.post(
        "/api/masters/",
        json={
            "type": "conditions",
            "version_number": "v1.0",
            "version_date": str(date.today()),
            "content_html": "<p>v1</p>",
        },
    )
    second = await authed_client.post(
        "/api/masters/",
        json={
            "type": "conditions",
            "version_number": "v2.0",
            "version_date": str(date.today()),
            "content_html": "<p>v2</p>",
        },
    )
    assert first.status_code == 200
    assert second.status_code == 200

    grouped = (await authed_client.get("/api/masters/")).json()
    conditions = grouped.get("conditions", [])
    active = [t for t in conditions if t["is_active"]]
    assert len(active) == 1
    assert active[0]["version_number"] == "v2.0"


@pytest.mark.asyncio
async def test_field_crud_round_trip(authed_client, admin_user):
    template_id, field_ids = await _create_template_and_fields(authed_client)

    update = await authed_client.put(
        f"/api/masters/fields/{field_ids[0]}",
        json={
            "template_id": template_id,
            "field_id": "F01",
            "clause_number": "1",
            "field_label": "Updated label",
            "input_type": "date",
            "default_value": "today",
            "is_required": True,
            "show_in_appendix": True,
            "sort_order": 0,
        },
    )
    assert update.status_code == 200
    assert update.json()["field_label"] == "Updated label"
    assert update.json()["input_type"] == "date"

    # Non-UUID field_id path should 422 (still correctly typed as UUID).
    bad = await authed_client.put(
        "/api/masters/fields/not-a-uuid",
        json={
            "template_id": template_id,
            "field_id": "F01",
            "clause_number": "1",
            "field_label": "x",
            "input_type": "text",
            "show_in_appendix": True,
            "sort_order": 0,
        },
    )
    assert bad.status_code == 422

    delete = await authed_client.delete(f"/api/masters/fields/{field_ids[2]}")
    assert delete.status_code == 200
    assert delete.json()["status"] == "deleted"


@pytest.mark.asyncio
async def test_field_endpoints_require_admin(client):
    """Anonymous calls must be rejected before any DB work happens."""
    random_template = str(uuid.uuid4())
    resp = await client.post(
        "/api/masters/fields/",
        json={
            "template_id": random_template,
            "field_id": "F01",
            "clause_number": "1",
            "field_label": "x",
            "input_type": "text",
            "show_in_appendix": True,
            "sort_order": 0,
        },
    )
    assert resp.status_code == 401
