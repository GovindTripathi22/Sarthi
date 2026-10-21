import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect
from backend.app.main import app, STATE
from backend.app.models import engine, Base
from backend.app.sandbox.runner import (
    verify_python_ast_security,
    EphemeralSandboxRunner,
)
from backend.app.github.client import generate_unified_patch, GitHubIntegrationClient
from backend.app.agents.workflow import (
    validate_payload_against_contract,
    execute_langgraph_repair_workflow,
    compute_sha256_digest,
)

client = TestClient(app)

def test_models_all_21_tables_created():
    inspector = inspect(engine)
    table_names = inspector.get_table_names()
    expected_tables = [
        "users",
        "workspaces",
        "workspace_members",
        "integrations",
        "integration_secrets",
        "api_contract_versions",
        "documentation_sources",
        "document_chunks",
        "request_events",
        "schema_drift_events",
        "incidents",
        "incident_events",
        "agent_runs",
        "agent_run_checkpoints",
        "patch_artifacts",
        "test_runs",
        "github_pull_requests",
        "approval_requests",
        "deployment_records",
        "usage_records",
        "audit_logs",
    ]
    for tbl in expected_tables:
        assert tbl in table_names, f"Missing expected table {tbl}"
    assert len(expected_tables) == 21

def test_ast_security_violations_detected():
    malicious_code = """
import os
import subprocess

def bad_func():
    os.system("rm -rf /")
    return os.environ.get("SECRET_KEY")
"""
    violations = verify_python_ast_security(malicious_code)
    assert len(violations) >= 2
    assert any("subprocess" in v for v in violations)
    assert any("environ" in v for v in violations)

def test_ast_security_clean_code_passes():
    clean_code = """
from pydantic import BaseModel
def good_func(payload):
    return payload.get("id")
"""
    violations = verify_python_ast_security(clean_code)
    assert len(violations) == 0

def test_unified_patch_generation_format():
    patch = generate_unified_patch("inc_1041", "def new_func(): pass")
    assert "From " in patch
    assert "Subject: [PATCH]" in patch
    assert "inc_1041" in patch
    assert "diff --git" in patch
    assert "Dual-Compatibility Patch" in patch

@pytest.mark.asyncio
async def test_github_client_local_export():
    gh_client = GitHubIntegrationClient(owner="acme-corp", repo="commerce-service", token=None)
    res = await gh_client.create_pull_request_or_export(
        incident_id="inc_1041",
        repair_id="rep_501",
        target_file="src/adapter.py",
        proposed_code="test",
        pr_body="body",
    )
    assert res["mode"] == "LOCAL_PATCH_EXPORT"
    assert res["status"] == "EXPORTED_LOCALLY"
    assert "autopatch/fix-inc_1041" in res["branch"]

def test_recursive_schema_validator_field_rename_detection():
    contract = {
        "type": "object",
        "required": ["customer_id", "email"],
        "properties": {
            "customer_id": {"type": "string"},
            "email": {"type": "string"},
        },
    }
    payload = {"customerId": "cust_123", "email": "test@domain.com"}
    report = validate_payload_against_contract(payload, contract)
    assert report["valid"] is False
    assert "customer_id" in report["missingRequired"]
    assert "customerId" in report["unexpectedFields"]
    assert len(report["suspectedRenames"]) == 1
    assert report["suspectedRenames"][0]["old_field"] == "customer_id"
    assert report["suspectedRenames"][0]["new_field"] == "customerId"

def test_langgraph_repair_workflow_nodes_and_evidence():
    incident = {
        "id": "inc_test_01",
        "failure_type": "SCHEMA_DRIFT",
        "error_trace": "KeyError: 'customer_id'",
        "failure_count": 2,
    }
    rag_results = {
        "duration_ms": 12,
        "results": [{"chunk_id": "c1", "score": 0.98, "title": "Guide"}],
    }
    wf = execute_langgraph_repair_workflow(incident, rag_results)
    assert len(wf["nodes"]) == 11
    assert wf["current_node_index"] == 9
    assert wf["workflow_state"] == "AWAITING_APPROVAL"
    assert wf["confidence_score"] == 0.96
    assert wf["nodes"][6]["name"] == "Isolated Validation"
    assert wf["nodes"][6]["status"] == "COMPLETED"

def test_api_v1_health_and_state():
    h_resp = client.get("/api/v1/health")
    assert h_resp.status_code == 200
    assert h_resp.json()["status"] == "healthy"

    s_resp = client.get("/api/v1/state")
    assert s_resp.status_code == 200
    state = s_resp.json()
    assert "workspace" in state
    assert "integrations" in state
    assert len(state["integrations"]) >= 1

def test_api_v1_toggle_drift():
    initial_drift = STATE["workspace"]["drift_active"]
    toggle_resp = client.post("/api/v1/demo/toggle-drift")
    assert toggle_resp.status_code == 200
    assert toggle_resp.json()["drift_active"] == (not initial_drift)

    # Toggle back to restore
    toggle_back = client.post("/api/v1/demo/toggle-drift")
    assert toggle_back.status_code == 200
    assert toggle_back.json()["drift_active"] == initial_drift

def test_api_v1_repair_lifecycle_and_rbac():
    # 1. Trigger simulated drift request to create incident
    resp = client.get("/proxy/int_commerce_01/v2/customers/cust_9041?failure_mode=SCHEMA_DRIFT")
    assert resp.status_code == 200
    incident_id = resp.json()["incident_id"]
    assert incident_id is not None

    # 2. Trigger repair as Operator
    rep_resp = client.post(
        f"/api/v1/incidents/{incident_id}/repair",
        headers={"x-autopatch-role": "Operator"},
    )
    assert rep_resp.status_code == 200
    repair = rep_resp.json()
    repair_id = repair["id"]
    assert repair["workflow_state"] == "AWAITING_APPROVAL"

    # 3. Check diff endpoint
    diff_resp = client.get(f"/api/v1/repairs/{repair_id}/diff")
    assert diff_resp.status_code == 200
    assert "unified_patch" in diff_resp.json()

    # 4. Check RBAC: Viewer should be denied on approve (403)
    viewer_approve = client.post(
        f"/api/v1/repairs/{repair_id}/approve",
        headers={"x-autopatch-role": "Viewer"},
    )
    assert viewer_approve.status_code == 403

    # 5. Admin approves repair
    admin_approve = client.post(
        f"/api/v1/repairs/{repair_id}/approve",
        headers={"x-autopatch-role": "Admin"},
    )
    assert admin_approve.status_code == 200
    assert admin_approve.json()["workflow_state"] == "APPROVED_READY_FOR_PR"

    # 6. Create PR / export
    pr_resp = client.post(
        f"/api/v1/repairs/{repair_id}/create-pr",
        headers={"x-autopatch-role": "Admin"},
    )
    assert pr_resp.status_code == 200
    assert pr_resp.json()["workflow_state"] == "PR_CREATED"

    # 7. Authorize Deployment as Admin
    deploy_resp = client.post(
        f"/api/v1/repairs/{repair_id}/authorize-deployment",
        headers={"x-autopatch-role": "Admin"},
    )
    assert deploy_resp.status_code == 200
    assert deploy_resp.json()["workflow_state"] == "DEPLOYED"

def test_api_v1_analytics_and_audit():
    summary_resp = client.get("/api/v1/analytics/summary")
    assert summary_resp.status_code == 200
    data = summary_resp.json()
    assert "monitored_integrations" in data

    costs_resp = client.get("/api/v1/analytics/costs")
    assert costs_resp.status_code == 200

    audit_resp = client.get("/api/v1/audit-logs")
    assert audit_resp.status_code == 200
    logs = audit_resp.json()
    assert len(logs) > 0
    assert "actor" in logs[0]
