# API Reference — Sarthi / AutoPatch Platform

Base URL: `http://localhost:8000`

---

## 1. System & Gateway Routes

### `GET /`
Returns root system health status or serves the web application for browser requests.

### `GET /api/v1/health`
Returns gateway operational status and active drift toggle state.

### `GET /api/v1/state`
Returns the complete synchronized workspace state (workspace, integrations, contract versions, documents, request telemetry, incidents, repairs, and audit logs).

### `POST /api/v1/demo/toggle-drift`
Toggles simulated schema drift mode on the demo upstream connector.

---

## 2. Proxy Gateway

### `ALL /proxy/{integration_id}/{path}`
Primary gateway proxy route. Dispatches the request to the upstream target with anti-SSRF protection, telemetry logging, and response contract validation.

**Query Parameters:**
- `simulate_drift` (boolean, optional): Injects simulated v2.2 schema drift payload.
- `failure_mode` (string, optional): Injects synthetic failures (`AUTH_401`, `RATE_LIMIT_429`, `SERVER_ERROR`, `TIMEOUT`).

### `POST /proxy/{integration_id}/validate`
Direct payload validation endpoint against the registered adapter.

---

## 3. Integrations Management

### `GET /api/v1/integrations`
Lists all registered integrations.

### `POST /api/v1/integrations`
Registers a new integration connector. *(Admin role required)*

### `GET /api/v1/integrations/{integration_id}`
Retrieves configuration for a specific integration.

### `PUT /api/v1/integrations/{integration_id}`
Updates safe configuration fields for an integration. *(Admin/Engineer role required)*

### `POST /api/v1/integrations/{integration_id}/test`
Tests live connectivity to the upstream service.

---

## 4. Contracts & Knowledge Base

### `GET /api/v1/integrations/{integration_id}/contracts`
Retrieves baseline and observed contract schemas.

### `POST /api/v1/integrations/{integration_id}/contracts/import`
Registers a new contract version. *(Admin/Engineer role required)*

### `GET /api/v1/integrations/{integration_id}/contracts/diff`
Computes recursive contract diff and field rename analysis.

### `POST /api/v1/integrations/{integration_id}/documents`
Ingests vendor documentation or migration guides with SHA-256 deduplication.

---

## 5. Incidents & Repair State Machine

### `GET /api/v1/incidents`
Lists incidents with optional `status`, `failure_type`, and `integration_id` filters.

### `GET /api/v1/incidents/{incident_id}`
Retrieves detailed incident forensic record.

### `POST /api/v1/incidents/{incident_id}/repair`
Executes the 12-stage self-healing repair workflow. Pauses at Node 9 for human review.

### `GET /api/v1/repairs/{repair_id}`
Retrieves current repair workflow state and node progression.

### `GET /api/v1/repairs/{repair_id}/diff`
Returns side-by-side baseline and proposed code along with Git unified `.patch`.

### `GET /api/v1/repairs/{repair_id}/tests`
Returns isolated sandbox test execution results and logs.

---

## 6. Review Gate & Deployment

### `POST /api/v1/repairs/{repair_id}/approve`
Human approval for the proposed patch. *(Reviewer/Admin role required)*

### `POST /api/v1/repairs/{repair_id}/reject`
Declines the repair proposal with a mandatory reason. *(Reviewer/Admin role required)*

### `POST /api/v1/repairs/{repair_id}/request-revision`
Requests an AI patch revision with custom engineering instructions. Capped at 3 iterations.

### `POST /api/v1/repairs/{repair_id}/create-pr`
Creates a dedicated branch and Pull Request on GitHub, or exports a local `.patch`.

### `POST /api/v1/repairs/{repair_id}/authorize-deployment`
Authorizes staging deployment, executes hot-reload, and verifies recovery. *(Admin role required)*

---

## 7. Analytics & Audit

### `GET /api/v1/analytics/summary`
Returns database-aggregated metrics (total requests, open incidents, uptime %, estimated savings).

### `GET /api/v1/audit-logs`
Returns immutable audit events with actor, role, action, target, and outcome.
