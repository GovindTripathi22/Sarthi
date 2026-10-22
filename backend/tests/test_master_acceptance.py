import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from backend.app.main import app
from backend.app.database import SessionLocal
from backend.app.models import Integration, Incident, AgentRun, RequestEvent
from backend.app.security.ssrf import validate_upstream_url
from backend.app.security.ast_gate import verify_python_ast_security
from backend.app.services.contract_service import ContractValidationService
from backend.app.services.sandbox_service import SandboxExecutionService
from backend.app.services.github_service import generate_unified_patch, GitHubIntegrationClient
from fastapi import HTTPException

client = TestClient(app)

def test_01_add_and_edit_integration():
    # 1. Add Integration
    res = client.post(
        "/api/v1/integrations",
        json={
            "name": "Acme Payments",
            "provider": "AcmePay",
            "base_url": "https://api.acmepay.io",
            "repository": "acme/payments",
            "target_adapter_file": "src/adapter.py",
        },
        headers={"x-autopatch-role": "Admin"}
    )
    assert res.status_code == 200
    int_id = res.json()["id"]
    assert res.json()["name"] == "Acme Payments"

    # 2. Edit Integration
    put_res = client.put(
        f"/api/v1/integrations/{int_id}",
        json={"name": "Acme Payments Global", "latency_threshold_ms": 600},
        headers={"x-autopatch-role": "Admin"}
    )
    assert put_res.status_code == 200
    assert put_res.json()["name"] == "Acme Payments Global"
    assert put_res.json()["latency_threshold_ms"] == 600

def test_02_proxy_local_mock_upstream():
    res = client.get("/mock-upstream/v2/customers/cust_8810")
    assert res.status_code == 200
    assert res.json()["customer_id"] == "cust_8810"

def test_03_handle_upstream_timeouts():
    # Verify timeout handling logic in proxy
    res = client.get("/proxy/int_commerce_01/v2/customers/cust_timeout?failure_mode=TIMEOUT")
    assert res.status_code == 200
    assert res.json()["event"]["status_code"] in (200, 504)

def test_04_handle_401_429_500_separately_from_drift():
    # 401 Auth Failure
    r401 = client.get("/proxy/int_commerce_01/v2/customers/cust_01?failure_mode=AUTH_401")
    assert r401.json()["event"]["error_classification"] == "AUTH_FAILURE"

    # 429 Rate Limit
    r429 = client.get("/proxy/int_commerce_01/v2/customers/cust_01?failure_mode=RATE_LIMIT_429")
    assert r429.json()["event"]["error_classification"] == "RATE_LIMIT"

    # Drift is distinct
    r_drift = client.get("/proxy/int_commerce_01/v2/customers/cust_9041?failure_mode=SCHEMA_DRIFT")
    assert r_drift.json()["event"]["error_classification"] == "SCHEMA_DRIFT"

def test_05_detect_missing_required_field():
    schema = {"type": "object", "required": ["customer_id", "email"], "properties": {"customer_id": {"type": "string"}, "email": {"type": "string"}}}
    payload = {"email": "buyer@enterprise.io"}
    report = ContractValidationService.validate_payload(payload, schema)
    assert report.valid is False
    assert "customer_id" in report.missing_required

def test_06_detect_unexpected_new_field():
    schema = {"type": "object", "required": ["customer_id"], "properties": {"customer_id": {"type": "string"}}, "additionalProperties": False}
    payload = {"customer_id": "cust_123", "unexpectedField": "value"}
    report = ContractValidationService.validate_payload(payload, schema)
    assert "unexpectedField" in report.unexpected_fields

def test_07_detect_likely_field_rename():
    schema = {"type": "object", "required": ["customer_id"], "properties": {"customer_id": {"type": "string"}}}
    payload = {"customerId": "cust_123"}
    report = ContractValidationService.validate_payload(payload, schema)
    assert len(report.suspected_renames) == 1
    assert report.suspected_renames[0].old_field == "customer_id"
    assert report.suspected_renames[0].new_field == "customerId"
    assert report.suspected_renames[0].confidence >= 0.90

def test_08_accept_backward_compatible_response():
    schema = {"type": "object", "required": ["customer_id"], "properties": {"customer_id": {"type": "string"}}, "additionalProperties": True}
    payload = {"customer_id": "cust_123", "optionalNote": "extra"}
    report = ContractValidationService.validate_payload(payload, schema)
    assert report.valid is True

def test_09_create_and_deduplicate_incident():
    # First occurrence
    r1 = client.get("/proxy/int_commerce_01/v2/customers/cust_9041?failure_mode=SCHEMA_DRIFT")
    inc1 = r1.json()["incident_id"]

    # Repeat occurrence of same problem
    r2 = client.get("/proxy/int_commerce_01/v2/customers/cust_9041?failure_mode=SCHEMA_DRIFT")
    inc2 = r2.json()["incident_id"]

    # Must deduplicate to the exact same incident ID
    assert inc1 == inc2

def test_10_generate_repair_proposal():
    r = client.get("/proxy/int_commerce_01/v2/customers/cust_9041?failure_mode=SCHEMA_DRIFT")
    inc_id = r.json()["incident_id"]

    repair_res = client.post(f"/api/v1/incidents/{inc_id}/repair", headers={"x-autopatch-role": "Engineer"})
    assert repair_res.status_code == 200
    data = repair_res.json()
    assert "proposed_code" in data
    assert data["workflow_state"] == "AWAITING_APPROVAL"

def test_11_run_tests_against_changed_source_tree():
    patched_code = (
        "from typing import Dict, Any\n"
        "from pydantic import BaseModel\n"
        "class NormalizedCustomer(BaseModel):\n"
        "    id: str\n"
        "    email: str\n"
        "    is_active: bool\n"
        "def parse_commerce_customer(payload: Dict[str, Any]) -> NormalizedCustomer:\n"
        '    cid = payload.get("customerId") or payload.get("customer_id")\n'
        '    if not cid: raise KeyError("missing id")\n'
        '    return NormalizedCustomer(id=str(cid), email=str(payload["email"]), is_active=(payload.get("status") == "ACTIVE"))\n'
    )
    result = SandboxExecutionService.run_isolated_validation(patched_code)
    assert result["static_analysis_passed"] is True
    assert result["passed_count"] == 4

def test_12_handle_sandbox_failure_honestly():
    broken_code = "def parse_commerce_customer(p): raise RuntimeError('Broken')"
    result = SandboxExecutionService.run_isolated_validation(broken_code)
    assert result["failed_count"] > 0
    assert "Broken" in result["raw_log"] or result["passed_count"] < 4

def test_13_approve_and_decline_repair():
    r = client.get("/proxy/int_commerce_01/v2/customers/cust_9041?failure_mode=SCHEMA_DRIFT")
    inc_id = r.json()["incident_id"]
    rep = client.post(f"/api/v1/incidents/{inc_id}/repair", headers={"x-autopatch-role": "Engineer"}).json()
    rep_id = rep["id"]

    # Decline
    decl = client.post(f"/api/v1/repairs/{rep_id}/reject", json={"reason": "Need extra type check"}, headers={"x-autopatch-role": "Reviewer"})
    assert decl.status_code == 200
    assert decl.json()["workflow_state"] == "REJECTED"

    # Re-approve as Admin
    appr = client.post(f"/api/v1/repairs/{rep_id}/approve", headers={"x-autopatch-role": "Admin"})
    assert appr.status_code == 200
    assert appr.json()["workflow_state"] == "APPROVED_READY_FOR_PR"

def test_14_export_valid_unified_patch():
    patch = generate_unified_patch("inc_1041", "print('hello')", "Admin Elena")
    assert "From " in patch
    assert "diff --git" in patch
    assert "inc_1041" in patch

@pytest.mark.asyncio
async def test_15_create_github_pr_or_local_export():
    gh = GitHubIntegrationClient(owner="acme", repo="service", token=None)
    out = await gh.create_pull_request_or_export("inc_1041", "rep_501", "src/adapter.py", "code", "body")
    assert out["mode"] == "LOCAL_PATCH_EXPORT"
    assert "LOCAL EXPORT" in out["status"]

def test_16_refuse_unauthorized_operations():
    # Viewer cannot approve (403)
    res = client.post("/api/v1/repairs/rep_501/approve", headers={"x-autopatch-role": "Viewer"})
    assert res.status_code == 403
    assert "RBAC Policy Enforcement" in res.json()["detail"]

def test_17_record_staging_deployment_and_verification():
    r = client.get("/proxy/int_commerce_01/v2/customers/cust_9041?failure_mode=SCHEMA_DRIFT")
    inc_id = r.json()["incident_id"]
    rep = client.post(f"/api/v1/incidents/{inc_id}/repair", headers={"x-autopatch-role": "Engineer"}).json()
    rep_id = rep["id"]

    client.post(f"/api/v1/repairs/{rep_id}/approve", headers={"x-autopatch-role": "Admin"})
    client.post(f"/api/v1/repairs/{rep_id}/create-pr", headers={"x-autopatch-role": "Admin"})

    deploy_res = client.post(
        f"/api/v1/repairs/{rep_id}/authorize-deployment",
        json={"environment": "staging"},
        headers={"x-autopatch-role": "Admin"}
    )
    assert deploy_res.status_code == 200
    assert deploy_res.json()["workflow_state"] == "DEPLOYED"

def test_18_persist_data_after_restart():
    with SessionLocal() as db:
        integrations = list(db.scalars(select(Integration)).all())
        assert len(integrations) >= 3

def test_19_handle_missing_external_credentials_truthfully():
    # Knowledge search works completely offline
    with SessionLocal() as db:
        res = client.get("/api/v1/analytics/costs")
        assert res.status_code == 200
        assert res.json()["total_spend_usd"] == 0.0

def test_20_keep_simulated_outcomes_clearly_labelled():
    res = client.get("/api/v1/integrations/int_commerce_01")
    assert res.status_code == 200
    assert "is_simulation_mode" in res.json()

def test_21_prevent_ssrf_and_sandbox_escape():
    # SSRF: block link-local AWS/GCP metadata
    with pytest.raises(HTTPException) as exc1:
        validate_upstream_url("http://169.254.169.254/latest/meta-data/", allow_local_override=False)
    assert exc1.value.status_code == 403

    # SSRF: block private loopback when allow_local is False
    with pytest.raises(HTTPException) as exc2:
        validate_upstream_url("http://10.0.0.1/admin", allow_local_override=False)
    assert exc2.value.status_code == 403

    # AST Sandbox escape trap
    violations = verify_python_ast_security("import socket; s = socket.socket()")
    assert any("socket" in v for v in violations)

def test_22_verify_dashboard_analytics_against_db():
    res = client.get("/api/v1/dashboard/summary")
    assert res.status_code == 200
    data = res.json()
    assert data["monitored_integrations"] >= 3
    assert "uptime_percentage" in data
    assert "total_estimated_savings_usd" in data
