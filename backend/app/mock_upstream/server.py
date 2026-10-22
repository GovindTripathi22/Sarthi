from __future__ import annotations

from typing import Any, Dict
from fastapi import APIRouter, HTTPException, Response

mock_upstream_router = APIRouter(prefix="/mock-upstream", tags=["Mock Upstream Provider"])


@mock_upstream_router.get("/v2/customers/{customer_id}")
async def get_baseline_customer(customer_id: str) -> Dict[str, Any]:
    """Mock upstream CommerceCore v2.1.0 baseline endpoint."""
    return {
        "customer_id": customer_id,
        "email": "legacy@enterprise.io" if customer_id == "cust_8810" else ("hold@enterprise.io" if customer_id == "cust_9099" else "buyer@enterprise.io"),
        "status": "SUSPENDED" if customer_id == "cust_9099" else "ACTIVE",
    }


@mock_upstream_router.get("/v2/drifted/customers/{customer_id}")
async def get_drifted_customer(customer_id: str) -> Dict[str, Any]:
    """Mock upstream CommerceCore v2.2.0 drifted endpoint (camelCase customerId)."""
    return {
        "customerId": customer_id,
        "email": "buyer@enterprise.io" if customer_id != "cust_9099" else "hold@enterprise.io",
        "status": "SUSPENDED" if customer_id == "cust_9099" else "ACTIVE",
        "schemaVersion": "2.2",
    }


@mock_upstream_router.get("/v2/auth-fail/customers/{customer_id}")
async def get_auth_failure(customer_id: str):
    """Mock upstream returning HTTP 401."""
    raise HTTPException(status_code=401, detail="Invalid upstream Bearer token or token expired.")


@mock_upstream_router.get("/v2/rate-limited/customers/{customer_id}")
async def get_rate_limited(customer_id: str, response: Response):
    """Mock upstream returning HTTP 429."""
    response.status_code = 429
    response.headers["Retry-After"] = "1"
    return {"error": "rate_limit_exceeded", "retry_after": 1}


@mock_upstream_router.get("/v2/server-error/customers/{customer_id}")
async def get_server_error(customer_id: str):
    """Mock upstream returning HTTP 500."""
    raise HTTPException(status_code=500, detail="Internal server crash upstream.")


@mock_upstream_router.get("/v2/health")
async def get_mock_health() -> Dict[str, Any]:
    return {"status": "HEALTHY", "version": "v2.1.0"}
