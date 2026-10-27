import os
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.workers.worker import AutoPatchWorker
from backend.app.agents.workflow import compute_sha256_hash, LangGraphOrchestrator
from backend.app.sandbox.runner import IsolatedSandboxRunner


def test_workbench_ui_endpoint():
    client = TestClient(app)
    response = client.get("/api/workbench-ui")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert "AutoPatch" in response.text or "Sarthi" in response.text


def test_compute_sha256_hash():
    sample = "Test AutoPatch Content"
    h1 = compute_sha256_hash(sample)
    assert isinstance(h1, str)
    assert len(h1) == 64
    assert h1 == compute_sha256_hash(sample)


def test_isolated_sandbox_runner_subclass():
    runner = IsolatedSandboxRunner(timeout_seconds=20)
    assert runner.timeout_seconds == 20
    assert hasattr(runner, "run_validation")


@pytest.mark.asyncio
async def test_worker_ingest_and_repair_job():
    worker = AutoPatchWorker()
    assert worker.running is True

    # Test Document Ingestion job
    doc_job = {
        "job_id": "test_job_1",
        "job_type": "INGEST_DOCUMENT",
        "payload": {
            "title": "Vendor Migration Guide",
            "content": "Section 1: Rename customer_id to customerId\n\nSection 2: Update contract",
        },
    }
    ingest_res = await worker.process_job(doc_job)
    assert ingest_res["status"] == "INDEXED"
    assert "content_hash" in ingest_res
    assert ingest_res["chunk_count"] == 2

    # Test LangGraph Repair job
    repair_job = {
        "job_id": "test_job_2",
        "job_type": "EXECUTE_LANGGRAPH_REPAIR",
        "payload": {
            "incident": {
                "id": "inc_test_9041",
                "failure_type": "SCHEMA_DRIFT",
                "failure_count": 2,
            },
            "integration": {"id": "int_commerce_01"},
            "documentation_sources": [{"title": "Vendor Migration Guide"}],
        },
    }
    repair_res = await worker.process_job(repair_job)
    assert repair_res["state"] == "AWAITING_APPROVAL"
    assert "result" in repair_res
    assert repair_res["incident_id"] == "inc_test_9041"

    # Test Unknown job
    unknown_res = await worker.process_job({"job_id": "test_3", "job_type": "UNKNOWN_JOB"})
    assert unknown_res["status"] == "SKIPPED"


def test_alembic_config_resolves():
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    config = Config("alembic.ini")
    script = ScriptDirectory.from_config(config)
    head_rev = script.get_current_head()
    assert head_rev == "0001_initial"
