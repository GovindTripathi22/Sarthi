# backend/tests/test_commerce_adapter.py
import pytest
from backend.app.adapters.commerce_customer_adapter import parse_commerce_customer

def test_v2_2_drifted_payload_camelcase():
    fixture = {
        "customerId": "cust_9041",
        "email": "buyer@enterprise.io",
        "status": "ACTIVE",
        "schemaVersion": "2.2"
    }
    result = parse_commerce_customer(fixture)
    assert result.id == "cust_9041"
    assert result.email == "buyer@enterprise.io"
    assert result.is_active is True

def test_v2_1_backward_compatibility_snakecase():
    fixture = {
        "customer_id": "cust_8810",
        "email": "legacy@enterprise.io",
        "status": "ACTIVE"
    }
    result = parse_commerce_customer(fixture)
    assert result.id == "cust_8810"
    assert result.email == "legacy@enterprise.io"
    assert result.is_active is True

def test_suspended_customer_status_mapping():
    fixture = {
        "customerId": "cust_9099",
        "email": "hold@enterprise.io",
        "status": "SUSPENDED"
    }
    result = parse_commerce_customer(fixture)
    assert result.id == "cust_9099"
    assert result.is_active is False

def test_malformed_missing_both_ids_raises_keyerror():
    fixture = {
        "email": "anon@enterprise.io",
        "status": "ACTIVE"
    }
    with pytest.raises(KeyError):
        parse_commerce_customer(fixture)
