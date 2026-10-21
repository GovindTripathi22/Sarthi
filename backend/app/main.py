from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware

try:
    from backend.app.adapters.commerce_customer_adapter import parse_commerce_customer
    from backend.app.agents.workflow import (
        BASELINE_ADAPTER_CODE,
        PATCHED_ADAPTER_CODE,
        compute_sha256_digest,
        execute_langgraph_repair_workflow,
        validate_payload_against_contract,
    )
    from backend.app.github.client import GitHubIntegrationClient, generate_unified_patch
    from backend.app.models import init_db
    from backend.app.sandbox.runner import EphemeralSandboxRunner
except ImportError:
    from app.adapters.commerce_customer_adapter import parse_commerce_customer  # type: ignore
    from app.agents.workflow import (  # type: ignore
        BASELINE_ADAPTER_CODE,
        PATCHED_ADAPTER_CODE,
        compute_sha256_digest,
        execute_langgraph_repair_workflow,
        validate_payload_against_contract,
    )
    from app.github.client import GitHubIntegrationClient, generate_unified_patch  # type: ignore
    from app.models import init_db  # type: ignore
    from app.sandbox.runner import EphemeralSandboxRunner  # type: ignore

app = FastAPI(
    title="Sarthi / AutoPatch — Self-Healing API & Integration Middleware",
    version="1.4.0",
    description="API Gateway, Contract Drift Detector, Qdrant RAG, 11-Node LangGraph & Docker Sandbox",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SENSITIVE_HEADER_RE = re.compile(
    r"authorization|api[-_]?key|secret|password|token|cookie|session|private_key",
    re.IGNORECASE,
)


def redact_sensitive(obj: Any) -> Any:
    """Recursively redact sensitive keys from headers and payloads before persistence."""
    if isinstance(obj, dict):
        return {
            k: ("[REDACTED_BY_GATEWAY_POLICY]" if SENSITIVE_HEADER_RE.search(str(k)) else redact_sensitive(v))
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [redact_sensitive(item) for item in obj]
    return obj


def build_initial_state() -> Dict[str, Any]:
    now_iso = datetime.now(timezone.utc).isoformat()
    return {
        "workspace": {
            "id": "ws_prod_01",
            "name": "Acme FinTech Core Production",
            "approval_policy": "STRICT_TWO_STAGE",
            "demo_mode": True,
            "drift_active": False,
            "upstream_failure_mode": "NONE",
            "llm_config": {
                "provider": "deterministic_demo",
                "model": "gpt-4o-mini",
                "api_key_masked": "",
                "input_cost_per_1k": 0.00015,
                "output_cost_per_1k": 0.00060,
            },
            "github_config": {
                "configured": False,
                "owner": "acme-corp",
                "repo": "commerce-integrations-service",
                "base_branch": "main",
                "token_masked": "",
            },
            "business_assumptions": {
                "hourly_downtime_cost_usd": 4200,
                "engineer_hourly_rate_usd": 145,
                "avg_manual_fix_hours": 3.5,
            },
        },
        "integrations": [
            {
                "id": "int_commerce_01",
                "workspace_id": "ws_prod_01",
                "name": "CommerceCore Customer API",
                "provider": "CommerceCore",
                "base_url": "https://api.commercecore.internal",
                "proxy_route": "/proxy/int_commerce_01/v2/customers/{id}",
                "health_route": "/v2/health",
                "auth_method": "Bearer Token (Vault Ref: sec_cc_991)",
                "repository": "acme-corp/commerce-integrations-service",
                "target_adapter_file": "src/adapters/commerce_customer_adapter.py",
                "status": "HEALTHY",
                "monitoring_paused": False,
                "latency_threshold_ms": 450,
                "error_rate_threshold_pct": 5.0,
                "active_contract_version": "v2.1.0",
                "doc_ingestion_status": "INDEXED",
                "last_success_at": now_iso,
                "last_incident_at": None,
            },
            {
                "id": "int_stripe_02",
                "workspace_id": "ws_prod_01",
                "name": "PayStream Settlement Webhook",
                "provider": "PayStream",
                "base_url": "https://api.paystream.io",
                "proxy_route": "/proxy/int_stripe_02/v1/payouts",
                "health_route": "/v1/health",
                "auth_method": "Webhook Secret",
                "repository": "acme-corp/commerce-integrations-service",
                "target_adapter_file": "src/adapters/paystream_adapter.py",
                "status": "HEALTHY",
                "monitoring_paused": False,
                "latency_threshold_ms": 300,
                "error_rate_threshold_pct": 2.0,
                "active_contract_version": "v1.8.4",
                "doc_ingestion_status": "INDEXED",
                "last_success_at": now_iso,
                "last_incident_at": None,
            },
            {
                "id": "int_ship_03",
                "workspace_id": "ws_prod_01",
                "name": "GlobalFreight Logistics Rates",
                "provider": "GlobalFreight",
                "base_url": "https://api.globalfreight.com",
                "proxy_route": "/proxy/int_ship_03/v3/rates",
                "health_route": "/v3/ping",
                "auth_method": "API Key",
                "repository": "acme-corp/commerce-integrations-service",
                "target_adapter_file": "src/adapters/freight_adapter.py",
                "status": "HEALTHY",
                "monitoring_paused": False,
                "latency_threshold_ms": 600,
                "error_rate_threshold_pct": 5.0,
                "active_contract_version": "v3.0.1",
                "doc_ingestion_status": "INDEXED",
                "last_success_at": now_iso,
                "last_incident_at": None,
            },
        ],
        "contract_versions": [
            {
                "id": "cv_cc_210",
                "integration_id": "int_commerce_01",
                "version": "v2.1.0",
                "created_at": now_iso,
                "is_baseline": True,
                "schema": {
                    "type": "object",
                    "required": ["customer_id", "email", "status"],
                    "properties": {
                        "customer_id": {"type": "string"},
                        "email": {"type": "string"},
                        "status": {"type": "string"},
                    },
                },
            },
            {
                "id": "cv_cc_220_observed",
                "integration_id": "int_commerce_01",
                "version": "v2.2.0-observed",
                "created_at": now_iso,
                "is_baseline": False,
                "schema": {
                    "type": "object",
                    "required": ["customerId", "email", "status"],
                    "properties": {
                        "customerId": {"type": "string"},
                        "email": {"type": "string"},
                        "status": {"type": "string"},
                        "schemaVersion": {"type": "string"},
                    },
                },
            },
        ],
        "documentation_sources": [
            {
                "id": "doc_cc_mig_22",
                "integration_id": "int_commerce_01",
                "provider": "CommerceCore",
                "title": "CommerceCore API v2.2 Migration Guide & Breaking Changes",
                "source_url": "https://docs.commercecore.internal/migrations/v2.1-to-v2.2",
                "doc_type": "MIGRATION_GUIDE",
                "version": "v2.2",
                "ingested_at": now_iso,
                "content": "Effective in API revision 2026-10, GET /v2/customers/{id} renames `customer_id` to `customerId`.",
                "content_hash": compute_sha256_digest(
                    "CommerceCore REST API v2.2 Breaking Change Notice customer_id renamed to customerId"
                ),
                "chunks": [
                    {
                        "chunk_id": "chk_01",
                        "text": "Effective in API revision 2026-10, the GET /v2/customers/{id} endpoint standardizes JSON keys to lowerCamelCase. BREAKING: The primary key field `customer_id` (string) has been renamed to `customerId` (string).",
                        "keywords": ["customer_id", "customerid", "/v2/customers", "rename", "camelcase"],
                    }
                ],
            }
        ],
        "request_events": [],
        "incidents": [],
        "repairs": [],
        "audit_logs": [],
    }


STATE: Dict[str, Any] = build_initial_state()
init_db()


def record_audit(role: str, action: str, target: str, outcome: str, details: str) -> None:
    STATE["audit_logs"].insert(
        0,
        {
            "id": f"aud_{uuid.uuid4().hex[:8]}",
            "workspace_id": STATE["workspace"]["id"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "actor": f"Elena Rostova ({role})",
            "role": role,
            "action": action,
            "target": target,
            "outcome": outcome,
            "details": details,
        },
    )


def require_roles(allowed: List[str], action_label: str):
    def _dep(x_autopatch_role: str = Header(default="Admin")) -> str:
        if x_autopatch_role not in allowed:
            record_audit(
                x_autopatch_role,
                "UNAUTHORIZED_ACTION_BLOCKED",
                action_label,
                "DENIED_403",
                f"Role '{x_autopatch_role}' attempted '{action_label}'. Allowed: {allowed}",
            )
            raise HTTPException(
                status_code=403,
                detail=f"RBAC Policy Enforcement: Role '{x_autopatch_role}' cannot perform '{action_label}'. Required: {allowed}",
            )
        return x_autopatch_role

    return _dep


# Root & Compatibility Health Endpoints
@app.get("/")
async def root():
    return {
        "status": "OPERATIONAL",
        "system": "Sarthi / AutoPatch AI Self-Healing API Middleware Gateway",
        "version": "1.4.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/health")
async def health():
    return {
        "status": "HEALTHY",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "active_integrations": len(STATE["integrations"]),
        "gateway_mode": "ACTIVE",
    }


@app.get("/integrations")
async def get_integrations_compat():
    return {"integrations": STATE["integrations"], "total": len(STATE["integrations"])}


@app.get("/contracts/{integration_id}")
async def get_contract_compat(integration_id: str):
    integration = next((i for i in STATE["integrations"] if i["id"] == integration_id), None)
    if not integration:
        raise HTTPException(status_code=404, detail=f"Integration '{integration_id}' not found")
    contract = next((c for c in STATE["contract_versions"] if c["integration_id"] == integration_id and c["is_baseline"]), None)
    if not contract:
        contract = STATE["contract_versions"][0]
    return {
        "integration_id": integration_id,
        "provider": integration["provider"],
        "version": contract["version"],
        "schema": contract["schema"],
    }


@app.post("/proxy/{integration_id}/validate")
async def validate_integration_payload(integration_id: str, request: Request):
    integration = next((i for i in STATE["integrations"] if i["id"] == integration_id), None)
    if not integration:
        raise HTTPException(status_code=404, detail=f"Integration '{integration_id}' not found")
    payload = await request.json()
    try:
        norm = parse_commerce_customer(payload)
        return {
            "valid": True,
            "normalized": {"id": norm.id, "email": norm.email, "is_active": norm.is_active},
            "schema_check": "PASS",
        }
    except Exception as exc:
        return {"valid": False, "error": str(exc), "schema_check": "FAIL"}


@app.api_route("/proxy/{integration_id}/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy_gateway(
    integration_id: str,
    path: str,
    request: Request,
    failure_mode: Optional[str] = Query(default=None),
    simulate_drift: Optional[bool] = Query(default=False),
) -> Dict[str, Any]:
    """
    Explicitly configured API Gateway route that observes traffic, redacts sensitive headers,
    validates response schemas against baseline contracts, and creates incidents on drift.
    """
    integration = next(
        (i for i in STATE["integrations"] if i["id"] == integration_id),
        None,
    )
    if not integration:
        raise HTTPException(status_code=404, detail=f"Integration '{integration_id}' not found")

    if integration.get("monitoring_paused"):
        raise HTTPException(status_code=503, detail="Integration monitoring is paused.")

    now_iso = datetime.now(timezone.utc).isoformat()
    corr_id = f"corr_{uuid.uuid4().hex[:8]}"
    mode = failure_mode or (
        "SCHEMA_DRIFT"
        if (simulate_drift or STATE["workspace"]["drift_active"])
        else STATE["workspace"]["upstream_failure_mode"]
    )

    deployed_repair = next(
        (
            r
            for r in STATE["repairs"]
            if r["integration_id"] == integration["id"] and r["workflow_state"] == "DEPLOYED"
        ),
        None,
    )

    status_code = 200
    duration_ms = 122
    error_classification = "NONE"
    schema_validation_result = "PASS"
    adapter_exception = None

    customer_match = re.match(r"^v2/customers/([^/?]+)", path)
    if customer_match:
        cust_id = customer_match.group(1)
        if mode == "AUTH_401":
            status_code = 401
            upstream_payload = {"error": "invalid_token", "error_description": "Token expired or revoked."}
            error_classification = "AUTH_FAILURE"
            schema_validation_result = "SKIPPED_HTTP_ERROR"
        elif mode == "RATE_LIMIT_429":
            status_code = 429
            upstream_payload = {"error": "rate_limit_exceeded", "retry_after_seconds": 30}
            error_classification = "RATE_LIMIT"
            schema_validation_result = "SKIPPED_HTTP_ERROR"
        elif mode == "SCHEMA_DRIFT" or cust_id == "cust_9041" or simulate_drift:
            upstream_payload = {
                "customerId": cust_id,
                "email": "buyer@enterprise.io" if cust_id != "cust_9099" else "hold@enterprise.io",
                "status": "SUSPENDED" if cust_id == "cust_9099" else "ACTIVE",
                "schemaVersion": "2.2",
            }
        else:
            upstream_payload = {
                "customer_id": cust_id,
                "email": "legacy@enterprise.io" if cust_id == "cust_8810" else ("hold@enterprise.io" if cust_id == "cust_9099" else "buyer@enterprise.io"),
                "status": "SUSPENDED" if cust_id == "cust_9099" else "ACTIVE",
            }
    else:
        if mode == "AUTH_401":
            status_code = 401
            upstream_payload = {"error": "invalid_token", "error_description": "Token expired or revoked."}
            error_classification = "AUTH_FAILURE"
            schema_validation_result = "SKIPPED_HTTP_ERROR"
        elif mode == "RATE_LIMIT_429":
            status_code = 429
            upstream_payload = {"error": "rate_limit_exceeded", "retry_after_seconds": 30}
            error_classification = "RATE_LIMIT"
            schema_validation_result = "SKIPPED_HTTP_ERROR"
        elif mode == "SCHEMA_DRIFT":
            upstream_payload = {
                "customerId": "cust_9041",
                "email": "buyer@enterprise.io",
                "status": "ACTIVE",
                "schemaVersion": "2.2",
            }
        else:
            upstream_payload = {
                "customer_id": "cust_9041",
                "email": "buyer@enterprise.io",
                "status": "ACTIVE",
            }

    baseline_contract = next(
        (
            c
            for c in STATE["contract_versions"]
            if c["integration_id"] == integration["id"] and c["is_baseline"]
        ),
        None,
    )

    validation_report = None
    if status_code == 200 and baseline_contract:
        validation_report = validate_payload_against_contract(
            upstream_payload, baseline_contract["schema"]
        )
        if not validation_report["valid"] and not deployed_repair:
            schema_validation_result = "FAIL_DRIFT"
            error_classification = "SCHEMA_DRIFT"
            adapter_exception = "KeyError: Missing required contract field: 'customer_id' in src/adapters/commerce_customer_adapter.py:14"
        elif not validation_report["valid"] and deployed_repair:
            schema_validation_result = "PASS_COMPAT_PATCHED"
            error_classification = "NONE"

    linked_incident_id = None
    if error_classification != "NONE":
        integration["status"] = "DEGRADED"
        integration["last_incident_at"] = now_iso
        existing = next(
            (
                inc
                for inc in STATE["incidents"]
                if inc["integration_id"] == integration["id"]
                and inc["failure_type"] == error_classification
                and inc["status"] not in ("DEPLOYED", "RESOLVED")
            ),
            None,
        )
        if existing:
            existing["failure_count"] += 1
            existing["last_occurrence"] = now_iso
            linked_incident_id = existing["id"]
        else:
            new_id = f"inc_{1041 + len(STATE['incidents'])}"
            new_inc = {
                "id": new_id,
                "workspace_id": STATE["workspace"]["id"],
                "integration_id": integration["id"],
                "integration_name": integration["name"],
                "provider": integration["provider"],
                "severity": "CRITICAL" if error_classification == "SCHEMA_DRIFT" else "HIGH",
                "status": "DETECTED",
                "failure_type": error_classification,
                "endpoint": f"GET /{path}",
                "first_occurrence": now_iso,
                "detected_at": now_iso,
                "diagnosed_at": None,
                "proposed_at": None,
                "recovered_at": None,
                "last_occurrence": now_iso,
                "failure_count": 1,
                "assigned_reviewer": "Elena Rostova (Admin)",
                "workflow_state": "DETECTED",
                "error_trace": adapter_exception or str(upstream_payload),
                "sanitized_payload": redact_sensitive(upstream_payload),
                "contract_diff": validation_report or {"valid": False},
                "timeline": [
                    {
                        "timestamp": now_iso,
                        "event": f"AutoPatch Gateway detected {error_classification} on /proxy/{integration_id}/{path} ({corr_id})",
                    }
                ],
            }
            STATE["incidents"].insert(0, new_inc)
            linked_incident_id = new_id

    raw_headers = dict(request.headers)
    raw_headers.setdefault("Authorization", "Bearer sk_live_redacted_sample")

    req_event = {
        "id": f"req_{9906 + len(STATE['request_events'])}",
        "workspace_id": STATE["workspace"]["id"],
        "integration_id": integration["id"],
        "method": request.method,
        "normalized_route": f"/{path}",
        "upstream_host": "api.commercecore.internal",
        "timestamp": now_iso,
        "duration_ms": duration_ms,
        "status_code": status_code,
        "response_size_bytes": len(str(upstream_payload)),
        "error_classification": error_classification,
        "schema_validation_result": schema_validation_result,
        "correlation_id": corr_id,
        "incident_id": linked_incident_id,
        "sanitized_headers": redact_sensitive(raw_headers),
        "sanitized_payload": redact_sensitive(upstream_payload),
    }
    STATE["request_events"].insert(0, req_event)

    response_data: Dict[str, Any] = {
        "event": req_event,
        "incident_id": linked_incident_id,
        "upstream_payload": upstream_payload,
    }

    # If customer adapter can parse, provide normalized customer object for compatibility
    if status_code == 200:
        try:
            norm_cust = parse_commerce_customer(upstream_payload)
            response_data["customer"] = {
                "id": norm_cust.id,
                "email": norm_cust.email,
                "is_active": norm_cust.is_active,
            }
            response_data["contract_validation"] = "PASS_DUAL_COMPAT"
            if simulate_drift:
                response_data["simulated_drift"] = True
        except Exception:
            pass

    return response_data


@app.get("/api/v1/health")
async def get_health() -> Dict[str, Any]:
    return {
        "status": "healthy",
        "version": "1.4.0",
        "workspace_id": STATE["workspace"]["id"],
        "drift_active": STATE["workspace"]["drift_active"],
    }


@app.get("/api/v1/state")
async def get_full_workspace_state() -> Dict[str, Any]:
    """Return full synchronized state for the frontend dashboard."""
    return STATE


@app.post("/api/v1/demo/toggle-drift")
async def toggle_demo_drift() -> Dict[str, Any]:
    STATE["workspace"]["drift_active"] = not STATE["workspace"]["drift_active"]
    STATE["workspace"]["upstream_failure_mode"] = (
        "SCHEMA_DRIFT" if STATE["workspace"]["drift_active"] else "NONE"
    )
    record_audit(
        "Admin",
        "DEMO_API_DRIFT_TOGGLED",
        "int_commerce_01",
        "SUCCESS",
        f"drift_active={STATE['workspace']['drift_active']}",
    )
    return {"drift_active": STATE["workspace"]["drift_active"]}


@app.get("/api/v1/dashboard/summary")
async def get_dashboard_summary() -> Dict[str, Any]:
    events = STATE["request_events"]
    total = len(events)
    failed = sum(1 for e in events if e["error_classification"] != "NONE" or e["status_code"] >= 400)
    drift_events = sum(1 for e in events if e["error_classification"] == "SCHEMA_DRIFT")
    return {
        "monitored_integrations": len(STATE["integrations"]),
        "total_requests": total,
        "failed_requests": failed,
        "schema_drift_events": drift_events,
        "open_incidents": sum(1 for i in STATE["incidents"] if i["status"] != "DEPLOYED"),
        "awaiting_approval": sum(1 for r in STATE["repairs"] if r["workflow_state"] == "AWAITING_APPROVAL"),
    }


@app.get("/api/v1/dashboard/timeseries")
async def get_dashboard_timeseries() -> Dict[str, Any]:
    return {"series": STATE["request_events"][:25]}


@app.get("/api/v1/integrations")
async def list_integrations() -> List[Dict[str, Any]]:
    return STATE["integrations"]


@app.post("/api/v1/integrations")
async def create_integration(
    payload: Dict[str, Any],
    role: str = Depends(require_roles(["Admin"], "Register Integration")),
) -> Dict[str, Any]:
    new_id = f"int_custom_{len(STATE['integrations']) + 1}"
    item = {
        "id": new_id,
        "workspace_id": STATE["workspace"]["id"],
        "name": payload.get("name", "Custom API Integration"),
        "provider": payload.get("provider", "CustomProvider"),
        "base_url": payload.get("base_url", "https://api.example.com"),
        "proxy_route": f"/proxy/{new_id}/v1/resource",
        "health_route": "/v1/health",
        "auth_method": "Bearer Token",
        "repository": payload.get("repository", "acme-corp/custom-service"),
        "target_adapter_file": "src/adapters/custom_adapter.py",
        "status": "HEALTHY",
        "monitoring_paused": False,
        "latency_threshold_ms": 500,
        "error_rate_threshold_pct": 5.0,
        "active_contract_version": "v1.0.0",
        "doc_ingestion_status": "INDEXED",
        "last_success_at": datetime.now(timezone.utc).isoformat(),
        "last_incident_at": None,
    }
    STATE["integrations"].append(item)
    record_audit(role, "INTEGRATION_REGISTERED", new_id, "SUCCESS", item["name"])
    return item


@app.post("/api/v1/integrations/{integration_id}/test")
async def test_integration_connectivity(integration_id: str, request: Request) -> Dict[str, Any]:
    return await proxy_gateway(integration_id, "v2/customers/cust_9041", request)


@app.post("/api/v1/integrations/{integration_id}/contracts/import")
async def import_contract(integration_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    new_cv = {
        "id": f"cv_{uuid.uuid4().hex[:6]}",
        "integration_id": integration_id,
        "version": payload.get("version", "v2.2.0"),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "is_baseline": payload.get("is_baseline", False),
        "schema": payload.get("schema", {}),
    }
    STATE["contract_versions"].append(new_cv)
    return new_cv


@app.get("/api/v1/integrations/{integration_id}/contracts/diff")
async def diff_contracts(integration_id: str) -> Dict[str, Any]:
    baseline = STATE["contract_versions"][0]["schema"]
    observed_sample = {"customerId": "cust_9041", "email": "buyer@enterprise.io", "status": "ACTIVE"}
    return validate_payload_against_contract(observed_sample, baseline)


@app.post("/api/v1/integrations/{integration_id}/documents")
async def ingest_document(
    integration_id: str,
    payload: Dict[str, Any],
    role: str = Depends(require_roles(["Admin", "Operator"], "Ingest Documentation")),
) -> Dict[str, Any]:
    content = payload.get("content", "")
    digest = compute_sha256_digest(content)
    existing = next((d for d in STATE["documentation_sources"] if d["content_hash"] == digest), None)
    if existing:
        return {"status": "DEDUPLICATED_SKIPPED", "document": existing}

    doc = {
        "id": f"doc_{uuid.uuid4().hex[:6]}",
        "integration_id": integration_id,
        "provider": payload.get("provider", "CommerceCore"),
        "title": payload.get("title", "Uploaded Migration Guide"),
        "source_url": payload.get("source_url", "https://docs.commercecore.internal/upload"),
        "doc_type": "MIGRATION_GUIDE",
        "version": payload.get("version", "v2.3"),
        "ingested_at": datetime.now(timezone.utc).isoformat(),
        "content": content,
        "content_hash": digest,
        "chunks": [{"chunk_id": f"chk_{uuid.uuid4().hex[:6]}", "text": content, "keywords": content.lower().split()}],
    }
    STATE["documentation_sources"].insert(0, doc)
    record_audit(role, "DOCUMENT_INGESTED", doc["id"], "SUCCESS", f"Hash: {digest}")
    return {"status": "INDEXED", "document": doc}


@app.post("/api/v1/integrations/{integration_id}/documents/reindex")
async def reindex_documents(integration_id: str) -> Dict[str, Any]:
    docs = [d for d in STATE["documentation_sources"] if d["integration_id"] == integration_id]
    return {"reindexed_count": len(docs), "status": "INDEXED"}


@app.get("/api/v1/incidents")
async def list_incidents() -> List[Dict[str, Any]]:
    return STATE["incidents"]


@app.get("/api/v1/incidents/{incident_id}")
async def get_incident(incident_id: str) -> Dict[str, Any]:
    inc = next((i for i in STATE["incidents"] if i["id"] == incident_id), None)
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")
    return inc


@app.post("/api/v1/incidents/{incident_id}/investigate")
@app.post("/api/v1/incidents/{incident_id}/repair")
async def run_incident_repair(
    incident_id: str,
    role: str = Depends(require_roles(["Admin", "Operator", "Reviewer"], "Execute LangGraph Repair")),
) -> Dict[str, Any]:
    inc = next((i for i in STATE["incidents"] if i["id"] == incident_id), None)
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")

    existing = next((r for r in STATE["repairs"] if r["incident_id"] == incident_id), None)
    if existing:
        return existing

    rag_results = {
        "duration_ms": 16,
        "results": [
            {
                "chunk_id": "chk_01",
                "doc_id": "doc_cc_mig_22",
                "title": "CommerceCore API v2.2 Migration Guide & Breaking Changes",
                "source_url": "https://docs.commercecore.internal/migrations/v2.1-to-v2.2",
                "version": "v2.2",
                "doc_type": "MIGRATION_GUIDE",
                "excerpt": STATE["documentation_sources"][0]["chunks"][0]["text"],
                "score": 0.97,
                "content_hash": STATE["documentation_sources"][0]["content_hash"],
            }
        ],
    }

    wf_out = execute_langgraph_repair_workflow(inc, rag_results)
    now_iso = datetime.now(timezone.utc).isoformat()
    repair_id = f"rep_{501 + len(STATE['repairs'])}"

    repair = {
        "id": repair_id,
        "incident_id": inc["id"],
        "workspace_id": STATE["workspace"]["id"],
        "integration_id": inc["integration_id"],
        "repository": "acme-corp/commerce-integrations-service",
        "base_branch": "main",
        "target_file": "src/adapters/commerce_customer_adapter.py",
        "created_at": now_iso,
        "updated_at": now_iso,
        "iteration_count": 1,
        "max_iterations": 3,
        "estimated_cost_usd": 0.0,
        "input_tokens": 0,
        "output_tokens": 0,
        "rag_retrieval": rag_results,
        "approval_record": None,
        "rejection_record": None,
        "revision_notes": [],
        "pull_request": None,
        "deployment_record": None,
        **wf_out,
    }
    inc["status"] = repair["workflow_state"]
    inc["workflow_state"] = repair["workflow_state"]
    inc["diagnosed_at"] = now_iso
    inc["proposed_at"] = now_iso
    STATE["repairs"].insert(0, repair)
    record_audit(role, "AGENT_REPAIR_WORKFLOW_EXECUTED", repair_id, "CHECKPOINT_PAUSED", f"Incident {incident_id}")
    return repair


@app.get("/api/v1/repairs/{repair_id}")
async def get_repair(repair_id: str) -> Dict[str, Any]:
    rep = next((r for r in STATE["repairs"] if r["id"] == repair_id), None)
    if not rep:
        raise HTTPException(status_code=404, detail="Repair not found")
    return rep


@app.get("/api/v1/repairs/{repair_id}/diff")
async def get_repair_diff(repair_id: str) -> Dict[str, Any]:
    rep = await get_repair(repair_id)
    return {
        "repair_id": repair_id,
        "target_file": rep["target_file"],
        "baseline_code": rep["baseline_code"],
        "proposed_code": rep["proposed_code"],
        "unified_patch": generate_unified_patch(rep["incident_id"], rep["proposed_code"]),
    }


@app.get("/api/v1/repairs/{repair_id}/tests")
async def get_repair_tests(repair_id: str) -> Dict[str, Any]:
    rep = await get_repair(repair_id)
    return rep.get("validation_test_run") or {}


@app.post("/api/v1/repairs/{repair_id}/approve")
async def approve_repair(
    repair_id: str,
    role: str = Depends(require_roles(["Admin", "Reviewer"], "Approve Repair Proposal")),
) -> Dict[str, Any]:
    rep = await get_repair(repair_id)
    now_iso = datetime.now(timezone.utc).isoformat()
    rep["workflow_state"] = "APPROVED_READY_FOR_PR"
    rep["current_node_index"] = 10
    rep["approval_record"] = {
        "approved_by": f"Elena Rostova ({role})",
        "timestamp": now_iso,
        "comment": "Verified dual-compatibility fallback and 4/4 isolated pytest results.",
    }
    rep["nodes"][8]["status"] = "COMPLETED"
    rep["nodes"][9]["status"] = "AWAITING_ACTION"
    record_audit(role, "REPAIR_APPROVED", repair_id, "SUCCESS", f"Approved by {role}")
    return rep


@app.post("/api/v1/repairs/{repair_id}/reject")
async def reject_repair(
    repair_id: str,
    payload: Dict[str, Any],
    role: str = Depends(require_roles(["Admin", "Reviewer"], "Reject Repair Proposal")),
) -> Dict[str, Any]:
    rep = await get_repair(repair_id)
    reason = (payload or {}).get("reason", "").strip()
    if not reason:
        raise HTTPException(status_code=400, detail="Rejection reason is mandatory.")
    now_iso = datetime.now(timezone.utc).isoformat()
    rep["workflow_state"] = "REJECTED"
    rep["rejection_record"] = {
        "rejected_by": f"Elena Rostova ({role})",
        "timestamp": now_iso,
        "reason": reason,
    }
    rep["nodes"][8]["status"] = "FAILED"
    record_audit(role, "REPAIR_REJECTED", repair_id, "SUCCESS", f"Reason: {reason}")
    return rep


@app.post("/api/v1/repairs/{repair_id}/request-revision")
async def request_repair_revision(
    repair_id: str,
    payload: Dict[str, Any],
    role: str = Depends(require_roles(["Admin", "Reviewer", "Operator"], "Request Patch Revision")),
) -> Dict[str, Any]:
    rep = await get_repair(repair_id)
    if rep["iteration_count"] >= rep["max_iterations"]:
        raise HTTPException(status_code=400, detail="Bounded iteration limit (3) reached.")
    note = (payload or {}).get("note", "Add explicit string stripping on customerId.")
    rep["iteration_count"] += 1
    rep["revision_notes"].append(
        {"iteration": rep["iteration_count"], "requested_by": role, "note": note}
    )
    runner = EphemeralSandboxRunner()
    rep["validation_test_run"] = runner.run_validation(rep["proposed_code"])
    rep["workflow_state"] = "AWAITING_APPROVAL"
    record_audit(role, "REPAIR_REVISION_ITERATION", repair_id, "SUCCESS", f"Iteration {rep['iteration_count']}: {note}")
    return rep


@app.post("/api/v1/repairs/{repair_id}/create-pr")
async def create_pull_request(
    repair_id: str,
    role: str = Depends(require_roles(["Admin", "Reviewer", "Operator"], "Create Pull Request")),
) -> Dict[str, Any]:
    rep = await get_repair(repair_id)
    if rep["workflow_state"] not in ("APPROVED_READY_FOR_PR", "PR_CREATED", "DEPLOYED"):
        raise HTTPException(status_code=400, detail="Node 9 Human Approval is required before PR creation.")
    if rep.get("pull_request"):
        return rep

    gh_cfg = STATE["workspace"]["github_config"]
    gh_client = GitHubIntegrationClient(
        owner=gh_cfg["owner"],
        repo=gh_cfg["repo"],
        base_branch=gh_cfg["base_branch"],
        token=None,
    )
    pr_record = await gh_client.create_pull_request_or_export(
        incident_id=rep["incident_id"],
        repair_id=rep["id"],
        target_file=rep["target_file"],
        proposed_code=rep["proposed_code"],
        pr_body="AutoPatch automated dual-compatibility fix.",
    )
    rep["pull_request"] = pr_record
    rep["workflow_state"] = "PR_CREATED"
    rep["current_node_index"] = 11
    rep["nodes"][9]["status"] = "COMPLETED"
    rep["nodes"][10]["status"] = "AWAITING_ACTION"
    record_audit(role, "PATCH_ARTIFACT_FINALIZED", repair_id, "SUCCESS", f"Branch: {pr_record['branch']}")
    return rep


@app.post("/api/v1/repairs/{repair_id}/authorize-deployment")
async def authorize_deployment(
    repair_id: str,
    role: str = Depends(require_roles(["Admin"], "Authorize Production Deployment")),
) -> Dict[str, Any]:
    rep = await get_repair(repair_id)
    if rep["workflow_state"] != "PR_CREATED":
        raise HTTPException(status_code=400, detail="PR creation must complete before deployment authorization.")
    now_iso = datetime.now(timezone.utc).isoformat()
    rep["workflow_state"] = "DEPLOYED"
    rep["deployment_record"] = {
        "authorized_by": f"Elena Rostova ({role})",
        "environment": "production-us-east-1",
        "timestamp": now_iso,
        "verification_status": "VERIFIED_RECOVERY",
    }
    rep["nodes"][10]["status"] = "COMPLETED"
    inc = next((i for i in STATE["incidents"] if i["id"] == rep["incident_id"]), None)
    if inc:
        inc["status"] = "DEPLOYED"
        inc["workflow_state"] = "DEPLOYED"
        inc["recovered_at"] = now_iso
    record_audit(role, "PRODUCTION_DEPLOYMENT_AUTHORIZED", repair_id, "SUCCESS", "Verified recovery")
    return rep


@app.get("/api/v1/analytics/summary")
async def get_analytics_summary() -> Dict[str, Any]:
    return await get_dashboard_summary()


@app.get("/api/v1/analytics/costs")
async def get_analytics_costs() -> Dict[str, Any]:
    total_spend = sum(r.get("estimated_cost_usd", 0.0) for r in STATE["repairs"])
    return {
        "provider": STATE["workspace"]["llm_config"]["provider"],
        "total_spend_usd": total_spend,
        "repairs_count": len(STATE["repairs"]),
    }


@app.get("/api/v1/audit-logs")
async def get_audit_logs() -> List[Dict[str, Any]]:
    return STATE["audit_logs"]
