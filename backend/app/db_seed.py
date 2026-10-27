from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.database import compute_sha256
from backend.app.models import (
    ApiContractVersion,
    DocumentationSource,
    DocumentChunk,
    Integration,
    User,
    Workspace,
    utcnow,
)
from backend.app.security.auth import hash_password


def seed_database_if_empty(db: Session) -> None:
    """Seed initial workspace, users, integrations, contracts, and docs if empty."""
    # 1. Seed Workspace
    ws = db.scalar(select(Workspace).where(Workspace.id == "ws_prod_01"))
    if not ws:
        ws = Workspace(
            id="ws_prod_01",
            name="Acme FinTech Core Production",
            approval_policy="STRICT_TWO_STAGE",
            demo_mode=True,
            drift_active=False,
            upstream_failure_mode="NONE",
            llm_config={
                "provider": "deterministic_demo",
                "model": "gpt-4o-mini",
                "api_key_masked": "",
            },
            github_config={
                "configured": False,
                "owner": "GovindTripathi22",
                "repo": "Sarthi",
                "base_branch": "main",
            },
            business_assumptions={
                "hourly_downtime_cost_usd": 4200,
                "engineer_hourly_rate_usd": 145,
                "avg_manual_fix_hours": 3.5,
            },
            created_at=utcnow(),
        )
        db.add(ws)

    # 2. Seed Users
    if not db.scalar(select(User).limit(1)):
        users = [
            User(
                id="usr_admin_01",
                email="admin@acme.internal",
                name="Elena Rostova",
                password_hash=hash_password("admin123"),
                role="Admin",
                api_key="sarthi_key_admin_secret",
                is_active=True,
                created_at=utcnow(),
            ),
            User(
                id="usr_eng_02",
                email="engineer@acme.internal",
                name="Marcus Vance",
                password_hash=hash_password("engineer123"),
                role="Engineer",
                api_key="sarthi_key_engineer_secret",
                is_active=True,
                created_at=utcnow(),
            ),
            User(
                id="usr_rev_03",
                email="reviewer@acme.internal",
                name="Sophia Chen",
                password_hash=hash_password("reviewer123"),
                role="Reviewer",
                api_key="sarthi_key_reviewer_secret",
                is_active=True,
                created_at=utcnow(),
            ),
            User(
                id="usr_view_04",
                email="viewer@acme.internal",
                name="Alex Kim",
                password_hash=hash_password("viewer123"),
                role="Viewer",
                api_key="sarthi_key_viewer_secret",
                is_active=True,
                created_at=utcnow(),
            ),
            User(
                id="usr_op_05",
                email="operator@acme.internal",
                name="Samira Khan",
                password_hash=hash_password("operator123"),
                role="Operator",
                api_key="sarthi_key_operator_secret",
                is_active=True,
                created_at=utcnow(),
            ),
        ]
        db.add_all(users)

    # 3. Seed Integrations
    if not db.scalar(select(Integration).limit(1)):
        integrations = [
            Integration(
                id="int_commerce_01",
                workspace_id="ws_prod_01",
                name="CommerceCore Customer API",
                provider="CommerceCore",
                base_url="https://api.commercecore.internal",
                proxy_route="/proxy/int_commerce_01/v2/customers/{id}",
                health_route="/v2/health",
                auth_method="Bearer Token",
                repository="acme-corp/commerce-integrations-service",
                target_adapter_file="src/adapters/commerce_customer_adapter.py",
                status="HEALTHY",
                monitoring_paused=False,
                latency_threshold_ms=450,
                error_rate_threshold_pct=5.0,
                active_contract_version="v2.1.0",
                doc_ingestion_status="INDEXED",
                is_simulation_mode=True,
                created_at=utcnow(),
            ),
            Integration(
                id="int_stripe_02",
                workspace_id="ws_prod_01",
                name="PayStream Settlement Webhook",
                provider="PayStream",
                base_url="https://api.paystream.io",
                proxy_route="/proxy/int_stripe_02/v1/payouts",
                health_route="/v1/health",
                auth_method="Webhook Secret",
                repository="acme-corp/commerce-integrations-service",
                target_adapter_file="src/adapters/paystream_adapter.py",
                status="HEALTHY",
                monitoring_paused=False,
                latency_threshold_ms=300,
                error_rate_threshold_pct=2.0,
                active_contract_version="v1.8.4",
                doc_ingestion_status="INDEXED",
                is_simulation_mode=True,
                created_at=utcnow(),
            ),
            Integration(
                id="int_ship_03",
                workspace_id="ws_prod_01",
                name="GlobalFreight Logistics Rates",
                provider="GlobalFreight",
                base_url="https://api.globalfreight.com",
                proxy_route="/proxy/int_ship_03/v3/rates",
                health_route="/v3/ping",
                auth_method="API Key",
                repository="acme-corp/commerce-integrations-service",
                target_adapter_file="src/adapters/freight_adapter.py",
                status="HEALTHY",
                monitoring_paused=False,
                latency_threshold_ms=600,
                error_rate_threshold_pct=5.0,
                active_contract_version="v3.0.1",
                doc_ingestion_status="INDEXED",
                is_simulation_mode=True,
                created_at=utcnow(),
            ),
        ]
        db.add_all(integrations)

        # Baseline contract for int_commerce_01
        cv = ApiContractVersion(
            id="cv_cc_210",
            workspace_id="ws_prod_01",
            integration_id="int_commerce_01",
            version="v2.1.0",
            is_baseline=True,
            schema_json={
                "type": "object",
                "required": ["customer_id", "email", "status"],
                "properties": {
                    "customer_id": {"type": "string"},
                    "email": {"type": "string"},
                    "status": {"type": "string"},
                },
            },
            created_at=utcnow(),
        )
        db.add(cv)

        # Ingested migration guide for CommerceCore
        doc_content = (
            "Effective in API revision 2026-10, the GET /v2/customers/{id} endpoint "
            "standardizes JSON keys to lowerCamelCase. BREAKING: The primary key field "
            "`customer_id` (string) has been renamed to `customerId` (string)."
        )
        doc = DocumentationSource(
            id="doc_cc_mig_22",
            workspace_id="ws_prod_01",
            integration_id="int_commerce_01",
            provider="CommerceCore",
            title="CommerceCore API v2.2 Migration Guide & Breaking Changes",
            source_url="https://docs.commercecore.internal/migrations/v2.1-to-v2.2",
            doc_type="MIGRATION_GUIDE",
            version="v2.2",
            content=doc_content,
            content_hash=compute_sha256(doc_content),
            ingested_at=utcnow(),
        )
        db.add(doc)

        chunk = DocumentChunk(
            id="chk_01",
            workspace_id="ws_prod_01",
            doc_id="doc_cc_mig_22",
            chunk_index=0,
            text_excerpt=doc_content,
            keywords=["customer_id", "customerid", "/v2/customers", "rename", "camelcase"],
        )
        db.add(chunk)

    db.commit()


if __name__ == "__main__":
    from backend.app.database import SessionLocal
    from backend.app.models import init_db

    init_db()
    with SessionLocal() as session:
        seed_database_if_empty(session)
    print("Database seeding completed successfully.")
