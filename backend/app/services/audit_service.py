from __future__ import annotations

import uuid
from sqlalchemy.orm import Session

from backend.app.models import AuditLog, utcnow


def record_audit(
    db: Session,
    actor: str,
    role: str,
    action: str,
    target: str,
    outcome: str,
    details: str,
    workspace_id: str = "ws_prod_01",
) -> AuditLog:
    """Persist an immutable governance and security audit event to the database."""
    log = AuditLog(
        id=f"aud_{uuid.uuid4().hex[:8]}",
        workspace_id=workspace_id,
        timestamp=utcnow(),
        actor=actor,
        role=role,
        action=action,
        target=target,
        outcome=outcome,
        details=details,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log
