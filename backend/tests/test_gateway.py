# backend/tests/test_gateway.py
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)

def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "OPERATIONAL"
    assert "Sarthi" in data["system"]
    assert data["version"] == "1.4.0"

def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "HEALTHY"
    assert "timestamp" in data

def test_list_integrations():
    response = client.get("/integrations")
    assert response.status_code == 200
    data = response.json()
    assert "integrations" in data
    assert len(data["integrations"]) >= 3
    ids = [i["id"] for i in data["integrations"]]
    assert "int_commerce_01" in ids

def test_proxy_customer_baseline_snakecase():
    response = client.get("/proxy/int_commerce_01/v2/customers/cust_8810")
    assert response.status_code == 200
    data = response.json()
    assert data["customer"]["id"] == "cust_8810"
    assert data["customer"]["email"] == "legacy@enterprise.io"
    assert data["customer"]["is_active"] is True
    assert data["contract_validation"] == "PASS_DUAL_COMPAT"

def test_proxy_customer_drifted_camelcase():
    response = client.get("/proxy/int_commerce_01/v2/customers/cust_9041")
    assert response.status_code == 200
    data = response.json()
    assert data["customer"]["id"] == "cust_9041"
    assert data["customer"]["email"] == "buyer@enterprise.io"
    assert data["customer"]["is_active"] is True
    assert data["contract_validation"] == "PASS_DUAL_COMPAT"

def test_proxy_customer_suspended_status():
    response = client.get("/proxy/int_commerce_01/v2/customers/cust_9099")
    assert response.status_code == 200
    data = response.json()
    assert data["customer"]["id"] == "cust_9099"
    assert data["customer"]["is_active"] is False

def test_proxy_unknown_integration_returns_404():
    response = client.get("/proxy/int_unknown_99/v2/customers/cust_001")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()

def test_proxy_validate_payload_valid():
    response = client.post(
        "/proxy/int_commerce_01/validate",
        json={"customerId": "cust_9999", "email": "valid@corp.io", "status": "ACTIVE"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is True
    assert data["normalized"]["id"] == "cust_9999"

def test_proxy_validate_payload_invalid_missing_ids():
    response = client.post(
        "/proxy/int_commerce_01/validate",
        json={"email": "missing_id@corp.io", "status": "ACTIVE"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is False
    assert "customer identifier" in data["error"].lower()
