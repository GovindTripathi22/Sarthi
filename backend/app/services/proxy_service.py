from __future__ import annotations

import asyncio
import random
import re
import time
import uuid
from typing import Any, Dict, Optional
import httpx
from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from backend.app.adapters.commerce_customer_adapter import parse_commerce_customer
from backend.app.config import settings
from backend.app.models import Integration, RequestEvent, ApiContractVersion, utcnow
from backend.app.security.ssrf import validate_upstream_url
from backend.app.services.contract_service import ContractValidationService
from backend.app.services.incident_service import IncidentService

SENSITIVE_HEADER_RE = re.compile(
    r"authorization|api[-_]?key|secret|password|token|cookie|session|private_key",
    re.IGNORECASE,
)


def redact_sensitive(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {
            k: ("[REDACTED_BY_GATEWAY_POLICY]" if SENSITIVE_HEADER_RE.search(str(k)) else redact_sensitive(v))
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [redact_sensitive(item) for item in obj]
    return obj


class ProxyGatewayService:
    @staticmethod
    async def dispatch_request(
        db: Session,
        integration: Integration,
        subpath: str,
        request: Request,
        failure_mode: Optional[str] = None,
        simulate_drift: Optional[bool] = False,
    ) -> Dict[str, Any]:
        """
        Executes an authentic API Gateway proxy request:
        1. Validates upstream URL (Anti-SSRF).
        2. Applies retry with exponential backoff & jitter for idempotent requests.
        3. Measures latency and captures real status.
        4. Validates payload against contract schema.
        5. Persists telemetry in RequestEvent and deduplicates Incidents.
        """
        if integration.monitoring_paused:
            raise HTTPException(status_code=503, detail="Integration monitoring is paused.")

        now = utcnow()
        corr_id = f"corr_{uuid.uuid4().hex[:8]}"
        is_idempotent = request.method in ("GET", "HEAD", "OPTIONS", "PUT")
        max_retries = 3 if is_idempotent else 1

        # Check simulation mode
        is_simulation = integration.is_simulation_mode or bool(simulate_drift) or (failure_mode is not None)

        status_code = 200
        duration_ms = 0
        upstream_payload: Dict[str, Any] = {}
        error_classification = "NONE"
        schema_validation_result = "PASS"
        adapter_exception = None

        if is_simulation:
            # Deterministic simulation runner
            start_ts = time.perf_counter()
            mode = failure_mode or ("SCHEMA_DRIFT" if simulate_drift else "NONE")

            # Emulate realistic latency
            await asyncio.sleep(0.02)
            duration_ms = max(18, int((time.perf_counter() - start_ts) * 1000))

            customer_match = re.match(r"^v2/customers/([^/?]+)", subpath)
            cust_id = customer_match.group(1) if customer_match else "cust_9041"

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
            # Real upstream network forwarder
            target_url = f"{integration.base_url.rstrip('/')}/{subpath.lstrip('/')}"
            validate_upstream_url(target_url)

            # Build forwarded headers (redact internal gateway auth headers)
            fwd_headers = {
                k: v for k, v in request.headers.items()
                if k.lower() not in ("host", "content-length", "x-autopatch-role", "x-api-key")
            }
            fwd_headers["User-Agent"] = "Sarthi-AutoPatch-Gateway/1.4"

            # Execute with exponential backoff & jitter
            attempt = 0
            while attempt < max_retries:
                attempt += 1
                start_ts = time.perf_counter()
                try:
                    async with httpx.AsyncClient(timeout=10.0) as client:
                        req_body = await request.body()
                        resp = await client.request(
                            method=request.method,
                            url=target_url,
                            headers=fwd_headers,
                            content=req_body if req_body else None,
                            params=request.query_params,
                        )
                        duration_ms = max(5, int((time.perf_counter() - start_ts) * 1000))
                        status_code = resp.status_code
                        try:
                            upstream_payload = resp.json()
                        except Exception:
                            upstream_payload = {"raw_text": resp.text[:1000]}

                        # Handle rate limit retry
                        if status_code == 429 and attempt < max_retries:
                            retry_after = resp.headers.get("Retry-After")
                            wait_s = float(retry_after) if retry_after and retry_after.isdigit() else (0.1 * (2 ** attempt))
                            await asyncio.sleep(min(2.0, wait_s))
                            continue

                        # Break on successful or non-retryable response
                        break

                except (httpx.ConnectTimeout, httpx.ReadTimeout):
                    duration_ms = max(10, int((time.perf_counter() - start_ts) * 1000))
                    status_code = 504
                    upstream_payload = {"error": "gateway_timeout", "detail": f"Upstream timed out on attempt {attempt}"}
                    error_classification = "TIMEOUT"
                    if attempt < max_retries:
                        await asyncio.sleep(0.05 * (2 ** attempt) + random.uniform(0.01, 0.05))
                        continue
                except httpx.RequestError as exc:
                    duration_ms = max(10, int((time.perf_counter() - start_ts) * 1000))
                    status_code = 502
                    upstream_payload = {"error": "bad_gateway", "detail": str(exc)}
                    error_classification = "SERVER_ERROR"
                    break

        # Classify HTTP Status Codes
        if status_code == 401 or status_code == 403:
            error_classification = "AUTH_FAILURE"
            schema_validation_result = "SKIPPED_HTTP_ERROR"
        elif status_code == 429:
            error_classification = "RATE_LIMIT"
            schema_validation_result = "SKIPPED_HTTP_ERROR"
        elif status_code >= 500:
            error_classification = "SERVER_ERROR"
            schema_validation_result = "SKIPPED_HTTP_ERROR"

        # Check baseline contract schema validation if 200 OK
        validation_report = None
        if status_code == 200:
            contract = db.query(ApiContractVersion).filter_by(
                integration_id=integration.id, is_baseline=True
            ).first()
            if contract and isinstance(upstream_payload, dict):
                report = ContractValidationService.validate_payload(
                    upstream_payload, contract.schema_json
                )
                validation_report = report.model_dump()

                # Check if drift occurred
                if not report.valid:
                    schema_validation_result = "FAIL_DRIFT"
                    error_classification = "SCHEMA_DRIFT"
                    adapter_exception = f"Contract mismatch: Missing required fields {report.missing_required} in {integration.target_adapter_file}"
                else:
                    schema_validation_result = "PASS"

        # Record Incident if an error occurred
        linked_incident_id = None
        if error_classification != "NONE":
            incident = IncidentService.record_or_deduplicate_incident(
                db=db,
                integration=integration,
                failure_type=error_classification,
                endpoint=f"{request.method} /{subpath}",
                error_trace=adapter_exception or str(upstream_payload),
                sanitized_payload=redact_sensitive(upstream_payload),
                contract_diff=validation_report or {"valid": False},
                correlation_id=corr_id,
            )
            linked_incident_id = incident.id
        else:
            integration.last_success_at = now
            if integration.status == "DEGRADED":
                integration.status = "HEALTHY"

        # Record Request Event
        req_event = RequestEvent(
            id=f"req_{uuid.uuid4().hex[:8]}",
            workspace_id=integration.workspace_id,
            integration_id=integration.id,
            method=request.method,
            normalized_route=f"/{subpath}",
            upstream_host=integration.base_url,
            timestamp=now,
            duration_ms=duration_ms,
            status_code=status_code,
            response_size_bytes=len(str(upstream_payload)),
            error_classification=error_classification,
            schema_validation_result=schema_validation_result,
            correlation_id=corr_id,
            incident_id=linked_incident_id,
            sanitized_headers=redact_sensitive(dict(request.headers)),
            sanitized_payload=redact_sensitive(upstream_payload),
        )
        db.add(req_event)
        db.commit()

        # Build response dictionary
        response_dict: Dict[str, Any] = {
            "event": {
                "id": req_event.id,
                "correlation_id": corr_id,
                "status_code": status_code,
                "duration_ms": duration_ms,
                "error_classification": error_classification,
                "schema_validation_result": schema_validation_result,
                "incident_id": linked_incident_id,
            },
            "incident_id": linked_incident_id,
            "upstream_payload": upstream_payload,
        }

        # Compatibility fields for existing tests and UI
        if status_code == 200:
            try:
                norm_cust = parse_commerce_customer(upstream_payload)
                response_dict["customer"] = {
                    "id": norm_cust.id,
                    "email": norm_cust.email,
                    "is_active": norm_cust.is_active,
                }
                response_dict["contract_validation"] = "PASS_DUAL_COMPAT"
                if simulate_drift:
                    response_dict["simulated_drift"] = True
            except Exception:
                pass

        return response_dict
