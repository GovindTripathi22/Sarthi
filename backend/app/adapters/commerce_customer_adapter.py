# backend/app/adapters/commerce_customer_adapter.py
from typing import Dict, Any
from pydantic import BaseModel

class NormalizedCustomer(BaseModel):
    id: str
    email: str
    is_active: bool

def parse_commerce_customer(payload: Dict[str, Any]) -> NormalizedCustomer:
    """
    Adapter for CommerceCore GET /v2/customers/{id}
    Contract Version: v2.1.0 + v2.2.0 Dual-Compatibility Patch (AutoPatch / Sarthi)
    Ref: https://docs.commercecore.internal/migrations/v2.1-to-v2.2
    """
    customer_id = payload.get("customerId") or payload.get("customer_id")
    if not customer_id:
        raise KeyError("Missing required customer identifier ('customerId' or 'customer_id')")
    
    return NormalizedCustomer(
        id=str(customer_id),
        email=str(payload["email"]),
        is_active=(payload.get("status") == "ACTIVE")
    )
