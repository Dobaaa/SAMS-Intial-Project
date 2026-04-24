"""Alembic environment for async SQLAlchemy.

Reads the DB URL from the `DATABASE_URL` env var (falling back to whatever
is set in `alembic.ini`). Imports every domain model so `target_metadata`
sees the full `Base.metadata` when running autogenerate.
"""

from __future__ import annotations

import asyncio
import os
import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# Make sibling modules (database, models, ...) importable when alembic is
# invoked from the repo root or from backend/.
_backend_dir = Path(__file__).resolve().parents[1]
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

# Load backend/.env so plain `alembic upgrade head` works without the caller
# having to manually export DATABASE_URL. Tests / CI / Docker can still
# override by setting DATABASE_URL in the process environment first.
try:
    from dotenv import load_dotenv

    load_dotenv(_backend_dir / ".env")
except ImportError:
    pass

from database import Base  # noqa: E402
import models  # noqa: E402,F401 -- side-effect: registers all ORM classes with Base.metadata

config = context.config

# Honour env override so tests (and production) can point alembic at any DB.
env_url = os.getenv("DATABASE_URL")
if env_url:
    config.set_main_option("sqlalchemy.url", env_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:  # type: ignore[no-untyped-def]
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
