from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy import select, and_
from sqlalchemy.orm import Session

from backend.app.models import Incident, IncidentEvent, Integration, utcnow


class IncidentService:
    @staticmethod
    def list_incidents(
        db: Session,
        status: Optional[str] = None,
        failure_type: Optional[str] = None,
        integration_id: Optional[str] = None,
    ) -> List[Incident]:
        query = select(Incident).order_by(Incident.last_occurrence.desc())
        conditions = []
        if status:
            if status == "ACTIVE":
                conditions.append(Incident.status.notin_(["DEPLOYED", "RESOLVED", "CLOSED"]))
            else:
                conditions.append(Incident.status == status)
        if failure_type:
            conditions.append(Incident.failure_type == failure_type)
        if integration_id:
            conditions.append(Incident.integration_id == integration_id)
        if conditions:
            query = query.where(and_(*conditions))
        return list(db.scalars(query).all())

    @staticmethod
    def get_incident(db: Session, incident_id: str) -> Optional[Incident]:
        return db.scalar(select(Incident).where(Incident.id == incident_id))

    @staticmethod
    def record_or_deduplicate_incident(
        db: Session,
        integration: Integration,
        failure_type: str,
        endpoint: str,
        error_trace: str,
        sanitized_payload: Dict[str, Any],
        contract_diff: Dict[str, Any],
        correlation_id: str,
    ) -> Incident:
        """
        Deterministic deduplication:
        Finds any unresolved incident for the exact same integration + failure_type + endpoint.
        If found, increments failure_count and updates last_occurrence.
        Otherwise, creates a new incident with appropriate severity.
        """
        now = utcnow()
        existing = db.scalar(
            select(Incident).where(
                and_(
                    Incident.integration_id == integration.id,
                    Incident.failure_type == failure_type,
                    Incident.endpoint == endpoint,
                    Incident.status.notin_(["RESOLVED", "CLOSED"]),
                )
            )
        )

        if existing:
            existing.failure_count += 1
            existing.last_occurrence = now
            existing.error_trace = error_trace
            existing.sanitized_payload = sanitized_payload
            existing.contract_diff = contract_diff

            event = IncidentEvent(
                id=f"iev_{uuid.uuid4().hex[:8]}",
                incident_id=existing.id,
                timestamp=now,
                event_description=f"Repeat failure #{existing.failure_count} detected (CorrId: {correlation_id}).",
            )
            db.add(event)
            db.commit()
            db.refresh(existing)
            return existing

        # Assign severity based on explicit rules
        if failure_type == "SCHEMA_DRIFT":
            severity = "CRITICAL"
        elif failure_type in ("SERVER_ERROR", "TIMEOUT", "AUTH_FAILURE"):
            severity = "HIGH"
        else:
            severity = "MEDIUM"

        new_id = f"inc_{1041 + len(db.scalars(select(Incident.id)).all())}"
        incident = Incident(
            id=new_id,
            workspace_id=integration.workspace_id,
            integration_id=integration.id,
            integration_name=integration.name,
            provider=integration.provider,
            severity=severity,
            status="DETECTED",
            failure_type=failure_type,
            endpoint=endpoint,
            first_occurrence=now,
            detected_at=now,
            last_occurrence=now,
            failure_count=1,
            assigned_reviewer="Elena Rostova (Admin)",
            workflow_state="DETECTED",
            error_trace=error_trace,
            sanitized_payload=sanitized_payload,
            contract_diff=contract_diff,
        )
        db.add(incident)

        event = IncidentEvent(
            id=f"iev_{uuid.uuid4().hex[:8]}",
            incident_id=new_id,
            timestamp=now,
            event_description=f"Initial incident detected via Gateway Proxy on {endpoint} ({correlation_id}).",
        )
        db.add(event)

        integration.status = "DEGRADED"
        integration.last_incident_at = now
        db.commit()
        db.refresh(incident)
        return incident

    @staticmethod
    def update_incident_status(
        db: Session,
        incident_id: str,
        new_status: str,
        note: Optional[str] = None,
    ) -> Incident:
        incident = IncidentService.get_incident(db, incident_id)
        if not incident:
            raise ValueError(f"Incident '{incident_id}' not found.")

        incident.status = new_status
        incident.workflow_state = new_status
        now = utcnow()
        if new_status in ("RESOLVED", "DEPLOYED"):
            incident.recovered_at = now

        desc = f"Status updated to {new_status}."
        if note:
            desc += f" Note: {note}"

        event = IncidentEvent(
            id=f"iev_{uuid.uuid4().hex[:8]}",
            incident_id=incident.id,
            timestamp=now,
            event_description=desc,
        )
        db.add(event)
        db.commit()
        db.refresh(incident)
        return incident
