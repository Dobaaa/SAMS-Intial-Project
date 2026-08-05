"""Tests for the Archive tab's flat listing endpoint (Phase 2 Package E,
req 8/9/10). Bucketing itself is computed client-side from these fields —
covered here is that the endpoint actually lists everything (no id
required, unlike /projects/{id} and /subcontractors/{id}) and that every
filter + the scope_of_works/is_executed/gm_approval_date fields needed for
bucketing are present and correct.
"""

from __future__ import annotations

from datetime import date

import pytest

pytestmark = pytest.mark.asyncio


async def _seed_active_templates(authed_client):
    for template_type in ("form", "conditions", "appendix"):
        resp = await authed_client.post(
            "/api/masters/",
            json={
                "type": template_type,
                "version_number": "v1",
                "content_html": "<p>placeholder</p>",
                "version_date": str(date.today()),
                "is_active": True,
            },
        )
        assert resp.status_code == 200, resp.text


async def _create_agreement(authed_client, *, project_code, project_name, subcontractor_name) -> dict:
    resp = await authed_client.post(
        "/api/agreements/",
        json={
            "project": {"project_name": project_name, "project_code": project_code},
            "subcontractor": {"company_name": subcontractor_name},
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


async def test_archive_agreements_lists_everything_no_id_required(authed_client, admin_user):
    """The old /projects/{id} and /subcontractors/{id} endpoints require an
    id and can't list everything. /archive/agreements needs none."""
    await _seed_active_templates(authed_client)
    a1 = await _create_agreement(
        authed_client, project_code="ARC-001", project_name="Archive Project One", subcontractor_name="Archive Sub One"
    )
    a2 = await _create_agreement(
        authed_client, project_code="ARC-002", project_name="Archive Project Two", subcontractor_name="Archive Sub Two"
    )

    resp = await authed_client.get("/api/archive/agreements")
    assert resp.status_code == 200, resp.text
    ids = {row["id"] for row in resp.json()}
    assert a1["id"] in ids
    assert a2["id"] in ids


async def test_archive_agreements_filters(authed_client, admin_user):
    await _seed_active_templates(authed_client)
    a1 = await _create_agreement(
        authed_client, project_code="ARC-100", project_name="Filter Target Project", subcontractor_name="Filter Target Sub"
    )
    await _create_agreement(
        authed_client, project_code="ARC-200", project_name="Other Project", subcontractor_name="Other Sub"
    )
    await authed_client.put(
        f"/api/agreements/{a1['id']}/fields",
        json={"values": {"C01": "Distinctive scope of works for filter test"}},
    )

    by_project_code = await authed_client.get("/api/archive/agreements", params={"project_code": "ARC-100"})
    assert [r["id"] for r in by_project_code.json()] == [a1["id"]]

    by_project_name = await authed_client.get(
        "/api/archive/agreements", params={"project_name": "Filter Target"}
    )
    assert [r["id"] for r in by_project_name.json()] == [a1["id"]]

    by_subcontractor = await authed_client.get(
        "/api/archive/agreements", params={"subcontractor_name": "Filter Target Sub"}
    )
    assert [r["id"] for r in by_subcontractor.json()] == [a1["id"]]

    by_scope = await authed_client.get(
        "/api/archive/agreements", params={"scope_of_works": "Distinctive scope"}
    )
    assert [r["id"] for r in by_scope.json()] == [a1["id"]]

    by_reference = await authed_client.get(
        "/api/archive/agreements", params={"reference_number": a1["reference_number"]}
    )
    assert [r["id"] for r in by_reference.json()] == [a1["id"]]

    row = by_scope.json()[0]
    assert row["scope_of_works"] == "Distinctive scope of works for filter test"


async def test_archive_agreements_bucket_fields_present(authed_client, admin_user):
    """Buckets are computed client-side — confirm the raw fields they need
    (is_executed, current_status, gm_approval_date) are all in the row."""
    await _seed_active_templates(authed_client)
    agreement = await _create_agreement(
        authed_client, project_code="ARC-300", project_name="Bucket Fields Project", subcontractor_name="Bucket Sub"
    )

    resp = await authed_client.get(
        "/api/archive/agreements", params={"reference_number": agreement["reference_number"]}
    )
    row = resp.json()[0]
    assert row["is_executed"] is False
    assert row["current_status"] == "under_drafting"
    assert row["gm_approval_date"] is None


async def test_export_no_longer_requires_project_or_subcontractor_id(authed_client, admin_user):
    """Package E relaxes the old 400 guard so the flat/filtered view can be
    exported without picking a specific project or subcontractor."""
    await _seed_active_templates(authed_client)
    await _create_agreement(
        authed_client, project_code="ARC-400", project_name="Export Project", subcontractor_name="Export Sub"
    )

    resp = await authed_client.get("/api/archive/export")
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"] == (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
