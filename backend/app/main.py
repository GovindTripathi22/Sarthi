# backend/app/main.py — FastAPI Gateway & Health Endpoint
from fastapi import FastAPI, Request, HTTPException, Path, Query
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any, Optional
import time

from backend.app.adapters.commerce_customer_adapter import (
    parse_commerce_customer,
    NormalizedCustomer
)

app = FastAPI(
    title="Sarthi Middleware Gateway",
    version="1.4.0",
    description="Autonomous API Self-Healing & Contract Drift Middleware"
)

# Enable CORS for browser integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

REGISTERED_INTEGRATIONS = {
    "int_commerce_01": {
        "id": "int_commerce_01",
        "name": "CommerceCore Customer API",
        "provider": "CommerceCore",
        "base_url": "https://api.commercecore.internal",
        "proxy_route": "/proxy/int_commerce_01/v2/customers/{id}",
        "active_contract_version": "v2.1.0",
        "status": "HEALTHY",
    },
    "int_stripe_02": {
        "id": "int_stripe_02",
        "name": "PayStream Settlement Webhook",
        "provider": "PayStream",
        "base_url": "https://api.paystream.io",
        "proxy_route": "/proxy/int_stripe_02/v1/payouts",
        "active_contract_version": "v1.8.4",
        "status": "HEALTHY",
    },
    "int_ship_03": {
        "id": "int_ship_03",
        "name": "GlobalFreight Logistics Rates",
        "provider": "GlobalFreight",
        "base_url": "https://rates.globalfreight.net",
        "proxy_route": "/proxy/int_ship_03/api/v3/quotes",
        "active_contract_version": "v3.0.1",
        "status": "HEALTHY",
    }
}

# Baseline customer fixtures for mock proxy responses
MOCK_CUSTOMERS = {
    "cust_9041": {
        "customerId": "cust_9041",
        "email": "buyer@enterprise.io",
        "status": "ACTIVE",
        "schemaVersion": "2.2"
    },
    "cust_8810": {
        "customer_id": "cust_8810",
        "email": "legacy@enterprise.io",
        "status": "ACTIVE"
    },
    "cust_9099": {
        "customerId": "cust_9099",
        "email": "hold@enterprise.io",
        "status": "SUSPENDED"
    }
}

@app.get("/")
def read_root():
    return {
        "system": "Sarthi (AutoPatch)",
        "status": "OPERATIONAL",
        "version": "1.4.0",
        "proxy_route_prefix": "/proxy/{integration_id}/*",
        "docs_url": "/docs"
    }

@app.get("/health")
def health_check():
    return {"status": "HEALTHY", "timestamp": time.time()}

@app.get("/integrations")
def list_integrations():
    return {"integrations": list(REGISTERED_INTEGRATIONS.values())}

@app.get("/proxy/{integration_id}/v2/customers/{customer_id}")
def proxy_get_customer(
    integration_id: str = Path(..., description="Registered integration identifier"),
    customer_id: str = Path(..., description="Customer ID to look up"),
    simulate_drift: bool = Query(default=False, description="Simulate upstream v2.2 camelCase payload drift")
):
    if integration_id not in REGISTERED_INTEGRATIONS:
        raise HTTPException(status_code=404, detail=f"Integration '{integration_id}' not found in gateway registry")

    # Retrieve fixture
    raw_payload = MOCK_CUSTOMERS.get(customer_id)
    if not raw_payload:
        raw_payload = {
            "customerId" if simulate_drift else "customer_id": customer_id,
            "email": f"{customer_id}@enterprise.io",
            "status": "ACTIVE"
        }

    try:
        normalized: NormalizedCustomer = parse_commerce_customer(raw_payload)
        return {
            "status": 200,
            "integration_id": integration_id,
            "customer": normalized.model_dump(),
            "contract_validation": "PASS_DUAL_COMPAT",
            "latency_ms": 115
        }
    except KeyError as e:
        raise HTTPException(
            status_code=502,
            detail=f"Contract Drift / Adapter Failure: {str(e)}"
        )

@app.post("/proxy/{integration_id}/validate")
async def proxy_validate_payload(
    integration_id: str,
    request: Request
):
    if integration_id not in REGISTERED_INTEGRATIONS:
        raise HTTPException(status_code=404, detail=f"Integration '{integration_id}' not found")

    payload = await request.json()
    try:
        normalized = parse_commerce_customer(payload)
        return {"valid": True, "normalized": normalized.model_dump()}
    except KeyError as err:
        return {"valid": False, "error": str(err)}
