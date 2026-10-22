from __future__ import annotations

from typing import Any, Dict
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.models import AgentRun, Incident, Integration, RequestEvent, Workspace
from backend.app.schemas import DashboardSummaryResponse


class AnalyticsService:
    @staticmethod
    def get_dashboard_summary(db: Session, workspace_id: str = "ws_prod_01") -> DashboardSummaryResponse:
        total_requests = db.scalar(
            select(func.count(RequestEvent.id)).where(RequestEvent.workspace_id == workspace_id)
        ) or 0

        failed_requests = db.scalar(
            select(func.count(RequestEvent.id)).where(
                RequestEvent.workspace_id == workspace_id,
                RequestEvent.error_classification != "NONE",
            )
        ) or 0

        drift_events = db.scalar(
            select(func.count(RequestEvent.id)).where(
                RequestEvent.workspace_id == workspace_id,
                RequestEvent.error_classification == "SCHEMA_DRIFT",
            )
        ) or 0

        monitored_integrations = db.scalar(
            select(func.count(Integration.id)).where(Integration.workspace_id == workspace_id)
        ) or 0

        open_incidents = db.scalar(
            select(func.count(Incident.id)).where(
                Incident.workspace_id == workspace_id,
                Incident.status.notin_(["RESOLVED", "DEPLOYED", "CLOSED"]),
            )
        ) or 0

        awaiting_approval = db.scalar(
            select(func.count(AgentRun.id)).where(
                AgentRun.workspace_id == workspace_id,
                AgentRun.workflow_state == "AWAITING_APPROVAL",
            )
        ) or 0

        resolved_incidents = db.scalar(
            select(func.count(Incident.id)).where(
                Incident.workspace_id == workspace_id,
                Incident.status.in_(["RESOLVED", "DEPLOYED"]),
            )
        ) or 0

        # Retrieve business assumptions
        ws = db.scalar(select(Workspace).where(Workspace.id == workspace_id))
        assumptions = (ws.business_assumptions if ws else None) or {
            "hourly_downtime_cost_usd": 4200,
            "engineer_hourly_rate_usd": 145,
            "avg_manual_fix_hours": 3.5,
        }

        hourly_downtime = assumptions.get("hourly_downtime_cost_usd", 4200)
        engineer_rate = assumptions.get("engineer_hourly_rate_usd", 145)
        avg_fix_hours = assumptions.get("avg_manual_fix_hours", 3.5)

        # Explicit ROI formula:
        # Savings = (resolved * avg_fix_hours * engineer_rate) + (resolved * 0.5hr prevented downtime * downtime_rate)
        engineer_savings = resolved_incidents * avg_fix_hours * engineer_rate
        downtime_savings = resolved_incidents * 0.5 * hourly_downtime
        total_savings = engineer_savings + downtime_savings

        uptime = 99.98
        if total_requests > 0:
            uptime = round(((total_requests - failed_requests) / total_requests) * 100, 2)

        return DashboardSummaryResponse(
            monitored_integrations=monitored_integrations,
            total_requests=total_requests,
            failed_requests=failed_requests,
            schema_drift_events=drift_events,
            open_incidents=open_incidents,
            awaiting_approval=awaiting_approval,
            uptime_percentage=uptime,
            total_estimated_savings_usd=total_savings,
        )
