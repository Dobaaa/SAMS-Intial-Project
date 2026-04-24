"""Tests for the resolution cycle (subcontractor comments -> revised send)."""

from __future__ import annotations

from datetime import date

import pytest
import pytest_asyncio


@pytest_asyncio.fixture
async def patched_suggest_responses(monkeypatch):
    """Replace ai_service.suggest_responses with a deterministic stub so tests
    don't need a real OpenAI key or network. The stub returns a predictable
    suggestion array keyed by the rows it finds."""
    from services import ai_service, resolution_service

    async def _stub(db, agreement_id: str):
        # Return nothing -- covers the "AI empty/failed" happy path without
        # needing real row IDs, since we're only asserting rows exist.
        return ai_service.AIResult(data=[], cached=False)

    monkeypatch.setattr(ai_service, "suggest_responses", _stub)
    monkeypatch.setattr(resolution_service, "suggest_responses", _stub)
    yield


async def _seeded_agreement(authed_client) -> dict:
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
    return create.json()


@pytest.mark.asyncio
async def test_record_signed_locks_agreement(authed_client, admin_user, patched_suggest_responses):
    agreement = await _seeded_agreement(authed_client)

    resp = await authed_client.patch(
        f"/api/agreements/{agreement['id']}/subcontractor-response",
        json={"response_type": "signed"},
    )
    assert resp.status_code == 200
    assert resp.json()["is_executed"] is True
    assert resp.json()["agreement_status"] == "completed"

    # After signing, further field updates must 400 (locked).
    fields = await authed_client.put(
        f"/api/agreements/{agreement['id']}/fields",
        json={"values": {"F02": "attempt-to-edit"}},
    )
    assert fields.status_code == 400


@pytest.mark.asyncio
async def test_create_resolution_sheet_and_list_rows(
    authed_client, admin_user, patched_suggest_responses
):
    agreement = await _seeded_agreement(authed_client)

    # Record comments-style response.
    await authed_client.patch(
        f"/api/agreements/{agreement['id']}/subcontractor-response",
        json={"response_type": "comments"},
    )

    create = await authed_client.post(
        f"/api/agreements/{agreement['id']}/resolution-sheet",
        json={
            "items": [
                {"subcontractor_comment": "Please reduce LD rate", "clause_reference": "6.2"},
                {"subcontractor_comment": "Extend time by 2 weeks", "clause_reference": "4.3"},
            ]
        },
    )
    assert create.status_code == 200
    assert len(create.json()["items"]) == 2

    rows = await authed_client.get(f"/api/resolution/{agreement['id']}")
    assert rows.status_code == 200
    assert len(rows.json()) == 2


@pytest.mark.asyncio
async def test_send_to_subcontractor_after_resolution_transitions_to_signature(
    authed_client, admin_user, patched_suggest_responses
):
    """After OM+GM approve the resolution and Admin calls send-to-subcontractor,
    the agreement must land in under_subcontractor_signature."""
    agreement = await _seeded_agreement(authed_client)
    # Record comments-style response -> status becomes under_bgcc_revision.
    await authed_client.patch(
        f"/api/agreements/{agreement['id']}/subcontractor-response",
        json={"response_type": "comments"},
    )

    # Admin sends revised -> transitions to under_subcontractor_signature.
    resp = await authed_client.post(f"/api/agreements/{agreement['id']}/send-to-subcontractor")
    assert resp.status_code == 200
    assert resp.json()["agreement_status"] == "under_subcontractor_signature"


@pytest.mark.asyncio
async def test_send_to_subcontractor_rejects_unexpected_status(
    authed_client, admin_user, patched_suggest_responses
):
    """From `under_drafting` the endpoint must 400 -- only internal-review
    and bgcc-revision statuses are forwardable."""
    agreement = await _seeded_agreement(authed_client)
    resp = await authed_client.post(f"/api/agreements/{agreement['id']}/send-to-subcontractor")
    assert resp.status_code == 400
