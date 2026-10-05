"""Mobile push: send_email -> notification row (+ FCM when tokens exist),
device registration, and the polling/feed endpoints."""

import pytest
import pytest_asyncio
from sqlalchemy import select

from models.device import DeviceToken, Notification
from services import push_service


@pytest_asyncio.fixture
async def reviewer(db_session):
    from models.user import RoleEnum, User
    from services.auth_service import hash_password

    u = User(name="Rev", email="rev@test.example", password_hash=hash_password("testpass1"), role=RoleEnum.accounts, is_active=True)
    db_session.add(u)
    await db_session.commit()
    await db_session.refresh(u)
    return u


async def _login(client, email="rev@test.example"):
    r = await client.post("/api/auth/login", json={"email": email, "password": "testpass1"})
    client.headers["Authorization"] = f"Bearer {r.json()['access_token']}"


@pytest.mark.asyncio
async def test_record_and_push_creates_notification_and_calls_fcm(db_session, reviewer, monkeypatch):
    sent = []
    monkeypatch.setattr(push_service, "_fcm_send", lambda tokens, t, b, a: sent.append(tokens) or [])
    db_session.add(DeviceToken(user_id=reviewer.id, token="tok-1", platform="android"))
    await db_session.commit()

    await push_service.record_and_push(db_session, "rev@test.example", "Agreement X ready", "body")
    await push_service.record_and_push(db_session, "subcontractor@external.example", "ignored", "body")  # not a user

    rows = (await db_session.execute(select(Notification))).scalars().all()
    assert [n.title for n in rows] == ["Agreement X ready"]
    assert sent == [["tok-1"]]


@pytest.mark.asyncio
async def test_dead_tokens_are_pruned(db_session, reviewer, monkeypatch):
    monkeypatch.setattr(push_service, "_fcm_send", lambda *a: ["tok-dead"])
    db_session.add(DeviceToken(user_id=reviewer.id, token="tok-dead", platform="ios"))
    await db_session.commit()
    await push_service.record_and_push(db_session, "rev@test.example", "s", "b")
    assert (await db_session.execute(select(DeviceToken))).scalars().all() == []


@pytest.mark.asyncio
async def test_device_and_notification_endpoints(client, db_session, reviewer):
    await _login(client)
    assert (await client.post("/api/devices", json={"token": "t1", "platform": "ios"})).status_code == 204
    assert (await client.post("/api/devices", json={"token": "t1", "platform": "ios"})).status_code == 204  # upsert
    assert len((await db_session.execute(select(DeviceToken))).scalars().all()) == 1

    await push_service.record_and_push(db_session, "rev@test.example", "Hello", "world")
    feed = (await client.get("/api/notifications")).json()
    assert feed["unread"] == 1 and feed["items"][0]["title"] == "Hello"

    assert (await client.post(f"/api/notifications/{feed['items'][0]['id']}/read")).status_code == 204
    assert (await client.get("/api/notifications")).json()["unread"] == 0
    assert (await client.delete("/api/devices", params={"token": "t1"})).status_code == 204


@pytest.mark.asyncio
async def test_send_email_triggers_push_even_when_paused(monkeypatch):
    import services.email_service as es

    calls = []

    async def spy(*a):
        calls.append(a)

    monkeypatch.setattr(es, "notify_by_email", spy)
    monkeypatch.setattr(es.settings, "EMAIL_PAUSED", True)
    await es.send_email("x@y.z", "s", "b")
    assert calls == [("x@y.z", "s", "b")]
