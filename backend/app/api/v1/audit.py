"""Read-only audit log (plan §8/§9)."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.audit_event import AuditEventRow

router = APIRouter(prefix="/audit", tags=["audit"])


class AuditEventRead(BaseModel):
    id: str
    action: str
    entity_type: str
    entity_id: str | None
    request_id: str | None
    detail: dict
    created_at: datetime


@router.get("", response_model=list[AuditEventRead])
def list_audit(
    entity_id: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[AuditEventRead]:
    q = db.query(AuditEventRow)
    if entity_id is not None:
        q = q.filter(AuditEventRow.entity_id == entity_id)
    rows = q.order_by(AuditEventRow.created_at.desc()).limit(limit).all()
    return [
        AuditEventRead(
            id=r.id,
            action=r.action,
            entity_type=r.entity_type,
            entity_id=r.entity_id,
            request_id=r.request_id,
            detail=r.detail,
            created_at=r.created_at,
        )
        for r in rows
    ]
