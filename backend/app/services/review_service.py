from __future__ import annotations

import uuid
from typing import Optional
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models import AgentRun, ApprovalRequest, Incident, User, utcnow
from backend.app.services.audit_service import record_audit


class ReviewService:
    @staticmethod
    def approve_repair(
        db: Session,
        repair_id: str,
        user: User,
        comment: str = "Verified dual-compatibility fallback and isolated sandbox pytest results.",
    ) -> AgentRun:
        repair = db.scalar(select(AgentRun).where(AgentRun.id == repair_id))
        if not repair:
            raise HTTPException(status_code=404, detail="Repair not found.")

        now = utcnow()
        repair.workflow_state = "APPROVED_READY_FOR_PR"
        repair.current_node_index = 10

        # Update node state
        nodes = list(repair.nodes_state or [])
        if len(nodes) > 8:
            nodes[8]["status"] = "COMPLETED"
        if len(nodes) > 9:
            nodes[9]["status"] = "AWAITING_ACTION"
        repair.nodes_state = nodes

        # Persist approval record
        approval = ApprovalRequest(
            id=f"apr_{uuid.uuid4().hex[:8]}",
            agent_run_id=repair.id,
            reviewer_name=user.name,
            reviewer_role=user.role,
            decision="APPROVED",
            reason_or_comment=comment,
            decided_at=now,
        )
        db.add(approval)

        record_audit(
            db=db,
            actor=f"{user.name} ({user.role})",
            role=user.role,
            action="REPAIR_APPROVED",
            target=repair.id,
            outcome="SUCCESS",
            details=f"Approved by {user.role}: {comment}",
        )
        db.commit()
        db.refresh(repair)
        return repair

    @staticmethod
    def reject_repair(
        db: Session,
        repair_id: str,
        user: User,
        reason: str,
    ) -> AgentRun:
        repair = db.scalar(select(AgentRun).where(AgentRun.id == repair_id))
        if not repair:
            raise HTTPException(status_code=404, detail="Repair not found.")

        if not reason.strip():
            raise HTTPException(status_code=400, detail="Rejection reason is mandatory.")

        now = utcnow()
        repair.workflow_state = "REJECTED"
        nodes = list(repair.nodes_state or [])
        if len(nodes) > 8:
            nodes[8]["status"] = "FAILED"
        repair.nodes_state = nodes

        # Persist rejection record
        approval = ApprovalRequest(
            id=f"apr_{uuid.uuid4().hex[:8]}",
            agent_run_id=repair.id,
            reviewer_name=user.name,
            reviewer_role=user.role,
            decision="REJECTED",
            reason_or_comment=reason,
            decided_at=now,
        )
        db.add(approval)

        record_audit(
            db=db,
            actor=f"{user.name} ({user.role})",
            role=user.role,
            action="REPAIR_REJECTED",
            target=repair.id,
            outcome="SUCCESS",
            details=f"Rejected by {user.role}: {reason}",
        )
        db.commit()
        db.refresh(repair)
        return repair
