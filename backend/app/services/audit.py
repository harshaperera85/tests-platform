"""Append-only audit recording helper."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.core.logging import request_id_ctx
from app.models.audit_event import AuditEventRow


def record(
    db: Session,
    *,
    action: str,
    entity_type: str,
    entity_id: str | None = None,
    detail: dict[str, Any] | None = None,
) -> None:
    """Append an audit event (own commit; independent of the caller's transaction)."""
    db.add(
        AuditEventRow(
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            request_id=request_id_ctx.get(),
            detail=detail or {},
        )
    )
    db.commit()
