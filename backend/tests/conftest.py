"""Shared fixtures for the backend test suite.

Layout:
 - ``postgresql_proc`` / ``postgresql`` — pytest-postgresql starts a throwaway
   Postgres process for the test *session* (module scope via the default
   config) so we don't rely on an externally-running DB.
 - ``database_url`` — async URL pointed at that test DB.
 - ``_prepare_schema`` — session-scope alembic ``upgrade head`` run once.
 - Function-scope ``client`` / ``db_session`` — fresh connections per test.
   Each test ends with a ``truncate all`` pass so tests don't leak into
   each other.
 - ``fake_redis`` — monkey-patches ``redis.asyncio.from_url`` with a
   fakeredis stub so ``auth_service`` / ``ai_service`` don't need a real
   Redis. Installed by the session-scope ``_stub_external_services`` fixture.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

import fakeredis.aioredis
import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from pytest_postgresql.janitor import DatabaseJanitor
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

# --- External-service stubs (must run before any module-level client creation) ---


@pytest.fixture(scope="session", autouse=True)
def _stub_external_services():
    """Route all `redis.from_url(...)` and `redis.asyncio.from_url(...)` calls
    through fakeredis. Patched at the ``redis`` package level so every
    module that imports ``redis.asyncio.from_url`` *after* this fixture
    runs sees the stub (lazy imports inside the ``client`` fixture mean
    application code is loaded only when a test first needs it, which is
    always after this autouse fixture has fired).
    """
    import redis
    import redis.asyncio

    def _fake(*args, **kwargs):  # type: ignore[no-untyped-def]
        return fakeredis.aioredis.FakeRedis(decode_responses=True)

    redis.from_url = _fake  # type: ignore[assignment]
    redis.asyncio.from_url = _fake  # type: ignore[assignment]

    # Disable slowapi rate-limiting for the whole test session. In production
    # the auth routes are 10/minute per IP; from a test process every call
    # comes from the same in-memory IP, so cumulative test-suite login
    # traffic would otherwise trip a 429 mid-run.
    from middleware.security import limiter

    limiter.enabled = False

    yield


# --- Database setup ---


@pytest.fixture(scope="session")
def postgresql_proc_url(postgresql_proc):  # type: ignore[no-untyped-def]
    """Sync URL (psycopg dialect-less) for the test Postgres process."""
    return {
        "user": postgresql_proc.user,
        "host": postgresql_proc.host,
        "port": postgresql_proc.port,
        "dbname": "sams_test",
    }


@pytest.fixture(scope="session")
def database_url(postgresql_proc_url):  # type: ignore[no-untyped-def]
    return (
        f"postgresql+asyncpg://{postgresql_proc_url['user']}"
        f"@{postgresql_proc_url['host']}:{postgresql_proc_url['port']}"
        f"/{postgresql_proc_url['dbname']}"
    )


@pytest.fixture(scope="session")
def _create_test_database(postgresql_proc, postgresql_proc_url):  # type: ignore[no-untyped-def]
    """Create + drop the test database around the whole session."""
    with DatabaseJanitor(
        user=postgresql_proc_url["user"],
        host=postgresql_proc_url["host"],
        port=postgresql_proc_url["port"],
        dbname=postgresql_proc_url["dbname"],
        version=postgresql_proc.version,
    ):
        yield


@pytest.fixture(scope="session", autouse=True)
def _configure_env(database_url, _create_test_database):  # type: ignore[no-untyped-def]
    """Point the app's settings at the test database *before* any app
    module imports run. Must be session-scoped and autouse so it fires
    during collection."""
    os.environ["DATABASE_URL"] = database_url
    os.environ.setdefault("REDIS_URL", "redis://fakeredis/0")
    os.environ.setdefault("GROQ_API_KEY", "test-groq-key")
    os.environ.setdefault("OPENAI_API_KEY", "test-key")
    os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-please-do-not-reuse")
    os.environ.setdefault("SMTP_HOST", "localhost")
    os.environ.setdefault("SMTP_USER", "test@example.com")
    os.environ.setdefault("SMTP_PASS", "test")
    os.environ.setdefault("FRONTEND_URL", "http://testserver")

    # Clear cached settings so any already-imported module picks up the new env.
    from config import get_settings

    get_settings.cache_clear()
    yield


@pytest.fixture(scope="session")
def _prepare_schema(_configure_env, database_url):  # type: ignore[no-untyped-def]
    """Run alembic `upgrade head` against the test database once per session."""
    cfg = Config(str(_alembic_ini_path()))
    cfg.set_main_option("script_location", str(_alembic_script_location()))
    cfg.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(cfg, "head")
    yield


def _alembic_ini_path():
    from pathlib import Path

    return Path(__file__).resolve().parents[1] / "alembic.ini"


def _alembic_script_location():
    from pathlib import Path

    return Path(__file__).resolve().parents[1] / "migrations"


@pytest_asyncio.fixture
async def test_engine(_prepare_schema, database_url) -> AsyncIterator[AsyncEngine]:
    """One async engine per test, bound to the running event loop.

    Uses ``NullPool`` so connections are not reused across tests. This is
    the single source of truth for both ``db_session`` and the
    FastAPI-side ``get_db_session`` override -- without that, the
    module-level ``database.engine`` would bind its connection pool to
    the first test's loop and break every test after.
    """
    engine = create_async_engine(database_url, future=True, poolclass=NullPool)
    try:
        yield engine
    finally:
        # Truncate domain tables so state doesn't leak between tests.
        async with engine.connect() as conn:
            tables = await conn.execute(
                text(
                    "SELECT tablename FROM pg_tables "
                    "WHERE schemaname='public' AND tablename <> 'alembic_version'"
                )
            )
            table_list = ", ".join(f'"{row[0]}"' for row in tables)
            if table_list:
                await conn.execute(text(f"TRUNCATE {table_list} RESTART IDENTITY CASCADE"))
                await conn.commit()
        await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine) -> AsyncIterator[AsyncSession]:
    """A fresh async SQLAlchemy session per test, sharing the per-test engine."""
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def client(test_engine) -> AsyncIterator[AsyncClient]:
    """httpx AsyncClient against the FastAPI app, with get_db_session
    overridden to use the per-test engine (same loop as the test body).
    """
    from database import get_db_session
    from main import app

    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)

    async def _override_get_db() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = _override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as c:
            yield c
    finally:
        app.dependency_overrides.pop(get_db_session, None)


@pytest_asyncio.fixture
async def admin_user(db_session):
    """Seed one admin user the auth-dependent tests can log in with."""
    from models.user import RoleEnum, User
    from services.auth_service import hash_password

    user = User(
        name="Test Admin",
        email="admin@test.example",
        password_hash=hash_password("adminpass1"),
        role=RoleEnum.admin,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def authed_client(client, admin_user):
    """httpx client with a valid Admin bearer token attached."""
    resp = await client.post(
        "/api/auth/login",
        json={"email": "admin@test.example", "password": "adminpass1"},
    )
    assert resp.status_code == 200, resp.text
    client.headers["Authorization"] = f"Bearer {resp.json()['access_token']}"
    return client
