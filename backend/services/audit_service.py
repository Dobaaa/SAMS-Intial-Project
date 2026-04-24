"""Central helper for writing rows to the audit_log table.

Every mutation of a domain entity (user, master template, master field,
agreement, workflow step, etc.) should call ``record_audit`` so we have
one consistent place to tweak the schema, add IP capture, or later swap in
a background queue. Do not construct ``AuditLog`` rows directly in new code.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from models.audit import AuditLog


async def record_audit(
    db: AsyncSession,
    *,
    actor_id: uuid.UUID | None,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID | None = None,
    old_value: dict[str, Any] | list[Any] | None = None,
    new_value: dict[str, Any] | list[Any] | None = None,
    ip_address: str | None = None,
) -> None:
    """Insert a single audit row in the current session (no commit here).

    Callers own the commit so the audit write stays in the same transaction
    as the mutation it describes. If the mutation rolls back, the audit row
    rolls back with it -- we don't log events that didn't happen.
    """
    db.add(
        AuditLog(
            user_id=actor_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            old_value_json=old_value,
            new_value_json=new_value,
            ip_address=ip_address,
        )
    )
