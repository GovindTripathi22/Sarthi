from __future__ import annotations

import uuid
from typing import List, Optional
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models import Integration, ApiContractVersion, utcnow
from backend.app.schemas import IntegrationCreate, IntegrationUpdate
from backend.app.security.ssrf import validate_upstream_url


class IntegrationService:
    @staticmethod
    def list_integrations(db: Session, workspace_id: str = "ws_prod_01") -> List[Integration]:
        return list(db.scalars(select(Integration).where(Integration.workspace_id == workspace_id)).all())

    @staticmethod
    def get_integration(db: Session, integration_id: str) -> Integration:
        integration = db.scalar(select(Integration).where(Integration.id == integration_id))
        if not integration:
            raise HTTPException(status_code=404, detail=f"Integration '{integration_id}' not found.")
        return integration

    @staticmethod
    def create_integration(
        db: Session,
        payload: IntegrationCreate,
        workspace_id: str = "ws_prod_01",
    ) -> Integration:
        # Validate base_url for SSRF
        validate_upstream_url(payload.base_url)

        new_id = f"int_{uuid.uuid4().hex[:8]}"
        proxy_route = payload.proxy_route or f"/proxy/{new_id}/v1"

        integration = Integration(
            id=new_id,
            workspace_id=workspace_id,
            name=payload.name,
            provider=payload.provider,
            base_url=payload.base_url.rstrip("/"),
            proxy_route=proxy_route,
            health_route=payload.health_route,
            auth_method=payload.auth_method,
            repository=payload.repository,
            target_adapter_file=payload.target_adapter_file,
            status="HEALTHY",
            monitoring_paused=False,
            latency_threshold_ms=payload.latency_threshold_ms,
            error_rate_threshold_pct=payload.error_rate_threshold_pct,
            active_contract_version=payload.active_contract_version,
            doc_ingestion_status="INDEXED",
            is_simulation_mode=payload.is_simulation_mode,
            created_at=utcnow(),
        )
        db.add(integration)

        # Baseline contract version placeholder
        baseline_contract = ApiContractVersion(
            id=f"cv_{uuid.uuid4().hex[:6]}",
            workspace_id=workspace_id,
            integration_id=new_id,
            version=payload.active_contract_version,
            is_baseline=True,
            schema_json={
                "type": "object",
                "required": ["id"],
                "properties": {"id": {"type": "string"}},
            },
            created_at=utcnow(),
        )
        db.add(baseline_contract)
        db.commit()
        db.refresh(integration)
        return integration

    @staticmethod
    def update_integration(
        db: Session,
        integration_id: str,
        payload: IntegrationUpdate,
    ) -> Integration:
        integration = IntegrationService.get_integration(db, integration_id)

        if payload.name is not None:
            integration.name = payload.name
        if payload.provider is not None:
            integration.provider = payload.provider
        if payload.base_url is not None:
            validate_upstream_url(payload.base_url)
            integration.base_url = payload.base_url.rstrip("/")
        if payload.health_route is not None:
            integration.health_route = payload.health_route
        if payload.latency_threshold_ms is not None:
            integration.latency_threshold_ms = payload.latency_threshold_ms
        if payload.error_rate_threshold_pct is not None:
            integration.error_rate_threshold_pct = payload.error_rate_threshold_pct
        if payload.monitoring_paused is not None:
            integration.monitoring_paused = payload.monitoring_paused
            integration.status = "PAUSED" if payload.monitoring_paused else "HEALTHY"
        if payload.is_simulation_mode is not None:
            integration.is_simulation_mode = payload.is_simulation_mode

        db.commit()
        db.refresh(integration)
        return integration

    @staticmethod
    def toggle_monitoring(db: Session, integration_id: str) -> Integration:
        integration = IntegrationService.get_integration(db, integration_id)
        integration.monitoring_paused = not integration.monitoring_paused
        integration.status = "PAUSED" if integration.monitoring_paused else "HEALTHY"
        db.commit()
        db.refresh(integration)
        return integration

    @staticmethod
    def delete_integration(db: Session, integration_id: str) -> None:
        integration = IntegrationService.get_integration(db, integration_id)
        db.delete(integration)
        db.commit()
