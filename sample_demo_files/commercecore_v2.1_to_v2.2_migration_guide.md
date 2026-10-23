# CommerceCore Vendor Migration Notice: v2.1.0 to v2.2.0

**Effective Date:** October 2026  
**Service:** Customer Core & Identity Service  
**Impact Level:** High (Breaking Contract Changes)

---

## 1. Summary of Changes

To comply with the unified OpenAPI 3.1 specification across CommerceCore cloud services, the Customer API is standardizing all property naming conventions to **camelCase**.

### Breaking Property Modifications
1. **Field Rename:**  
   - **Legacy (v2.1.0):** `customer_id` (`string`, required)
   - **New (v2.2.0):** `customerId` (`string`, required)
   - *Impact:* Adapters expecting `payload["customer_id"]` will throw `KeyError: 'customer_id'` if not updated.

2. **Account Status Codes:**  
   - Status remains string enumerated: `ACTIVE`, `SUSPENDED`, `PENDING_VERIFICATION`.
   - Backward compatibility: Systems evaluating `status == "ACTIVE"` should continue evaluating against the uppercase string representation.

---

## 2. Recommended Client Adapter Dual-Compatibility Pattern

To prevent microservice downtime during phased multi-region rollouts, downstream consumers must implement **dual-compatibility fallback**:

```python
# Recommended Python Adapter Transformation
def parse_commerce_customer(payload: dict) -> NormalizedCustomer:
    # Handle both v2.2 camelCase and v2.1 snake_case
    customer_id = payload.get("customerId") or payload.get("customer_id")
    if not customer_id:
        raise KeyError("Missing required customer identifier ('customerId' or 'customer_id')")
    
    return NormalizedCustomer(
        id=str(customer_id),
        email=str(payload["email"]),
        is_active=(payload.get("status") == "ACTIVE")
    )
```

---

## 3. Support & Incident Reporting
For questions, contact `api-support@commercecore.internal` or refer to the internal developer portal changelog.
