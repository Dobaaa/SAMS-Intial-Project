"""Regression tests for the auth flow (login / refresh / logout / me)."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_login_success_returns_tokens_and_user(client, admin_user):
    resp = await client.post(
        "/api/auth/login",
        json={"email": "admin@test.local", "password": "adminpass1"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["access_token"]
    assert data["refresh_token"]
    assert data["user"]["email"] == "admin@test.local"
    assert data["user"]["role"] == "admin"


@pytest.mark.asyncio
async def test_login_wrong_password_is_401(client, admin_user):
    resp = await client.post(
        "/api/auth/login",
        json={"email": "admin@test.local", "password": "not-the-password"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_requires_token_and_returns_self(authed_client, admin_user):
    resp = await authed_client.get("/api/auth/me")
    assert resp.status_code == 200
    assert resp.json()["email"] == admin_user.email


@pytest.mark.asyncio
async def test_me_without_token_is_401(client):
    resp = await client.get("/api/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_cycles_access_token(client, admin_user):
    login = await client.post(
        "/api/auth/login",
        json={"email": "admin@test.local", "password": "adminpass1"},
    )
    refresh_token = login.json()["refresh_token"]

    resp = await client.post("/api/auth/refresh", json={"refresh_token": refresh_token})
    assert resp.status_code == 200
    assert resp.json()["access_token"]


@pytest.mark.asyncio
async def test_logout_revokes_refresh_token(client, admin_user):
    """After logout, the same refresh_token must be rejected -- verifying the
    Redis-backed revocation store from the fix(auth) commit actually works
    end-to-end (fakeredis shim used in tests)."""
    login = await client.post(
        "/api/auth/login",
        json={"email": "admin@test.local", "password": "adminpass1"},
    )
    refresh_token = login.json()["refresh_token"]

    logout = await client.post("/api/auth/logout", json={"refresh_token": refresh_token})
    assert logout.status_code == 200

    resp = await client.post("/api/auth/refresh", json={"refresh_token": refresh_token})
    assert resp.status_code == 401
    assert "revoked" in resp.json()["detail"].lower()
