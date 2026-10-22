# Implementation Audit — Sarthi / AutoPatch Platform

**Audit Date:** October 22, 2026  
**Auditor:** Senior Software Architect, Security Engineer & DevOps Engineer  
**Codebase:** `C:\Users\USER\.gemini\antigravity\scratch\Sarthi`  
**Git Branch / Commit:** `main` (`969068e`)

---

## 1. Executive Summary

This audit assesses the real production readiness, architectural integrity, and end-to-end functionality of the Sarthi / AutoPatch platform. While the user interface exhibits an aesthetic, polished Stitch-based design and the test suite passes under simulated conditions (31 backend pytest tests + 28 synthetic DOM tests), a thorough architectural inspection reveals that **core operational workflows rely on in-memory mock state, client-side localStorage mutations, and fabricated upstream proxy responses**.

The objective of the upcoming implementation phases is to transform this working prototype into a genuine, robust, enterprise-grade self-healing API middleware platform where:
- State is genuinely persisted in a relational database (SQLite in development, PostgreSQL in production).
- The proxy executes real HTTP requests to configured upstreams with anti-SSRF protections and retry policies.
- Contract validation utilizes standard JSON Schema engines and rigorous rename heuristics.
- Incidents are deduplicated, persisted, and tracked across a real lifecycle.
- Patch generation integrates genuine LLM providers (with fallback to an intelligent local deterministic engine).
- Sandboxes execute real tests in isolated environments.
- Staging deployments are verified by actual health checks.
- Authentication, role enforcement, and audit logs are secure and tamper-resistant.

---

## 2. Feature-by-Feature Classification Matrix

Every existing feature has been inspected and classified according to the 6 mandated tiers:
1. **Fully implemented and verified**
2. **Implemented but incomplete**
3. **Simulated or hard-coded**
4. **Broken**
5. **Blocked by external credentials or infrastructure**
6. **Not implemented**

| Feature / Subsystem | Current Classification | Primary File Paths | Supporting Functions / Modules | Analysis & Deficiencies |
| :--- | :---: | :--- | :--- | :--- |
| **Frontend UI Presentation** | **1. Fully Implemented & Verified** | `index.html`<br>`autopatch_platform_self_healing_middleware.html` | Stitch styling, 10-view workspace, 2-button website hero, interactive showcase, button guide | The visual design, responsive layouts, glassmorphism modals, and micro-interactions meet high aesthetic standards. |
| **Frontend-to-Backend State Binding** | **3. Simulated or Hard-coded** | `index.html` | `appState`, `saveState()`, `STORAGE_KEY = 'autopatch_production_mvp_state_v1'` | Frontend acts as the source of truth via browser `localStorage`. Metrics, status badges, and incident transitions are driven by client state rather than backend database queries. |
| **Database Persistence** | **2. Implemented but Incomplete** | `backend/app/models.py`<br>`backend/app/main.py` | `Base.metadata.create_all()`, 21 SQLAlchemy tables | 21 relational tables are declared in `models.py`. However, `main.py` operates on a global Python dictionary `STATE` and never performs SQLAlchemy session queries (`select`, `insert`, `commit`). State is lost on restart. |
| **API Gateway Proxy** | **3. Simulated or Hard-coded** | `backend/app/main.py` | `proxy_gateway()` | Does not forward HTTP requests to `integration.base_url`. Fabricates mock JSON dictionaries (`upstream_payload = ...`) based on query flags. Lacks real `httpx` dispatch, connection timeouts, retries, and Anti-SSRF guards. |
| **Anti-SSRF Protection** | **6. Not Implemented** | `backend/app/main.py` | N/A | Missing host validation, loopback/private/link-local/metadata IP traps, protocol whitelisting, and path traversal guards on upstream URLs. |
| **Contract Validation** | **2. Implemented but Incomplete** | `backend/app/agents/workflow.py` | `validate_payload_against_contract()` | Uses custom recursive dictionary inspection. Does not support standard JSON Schema (`jsonschema` library) features (`$ref`, `pattern`, `anyOf`, array items). Rename heuristic is limited to snake_case vs camelCase string stripping. |
| **Incident Management & Lifecycle** | **2. Implemented but Incomplete** | `backend/app/main.py` | `list_incidents()`, `get_incident()` | Incidents are stored in Python memory list. Rudimentary deduplication exists, but does not persist across restarts. Severity rules and resolution verification are not formalized. |
| **Repair State Machine (11-Node Graph)** | **3. Simulated or Hard-coded** | `backend/app/agents/workflow.py` | `execute_langgraph_repair_workflow()` | Returns hardcoded strings `BASELINE_ADAPTER_CODE` and `PATCHED_ADAPTER_CODE`. Node execution is a static list of dictionaries with hardcoded millisecond durations. Does not invoke LangGraph or an actual state machine. |
| **LLM Provider Abstraction** | **3. Simulated or Hard-coded** | `backend/app/main.py`<br>`backend/app/agents/workflow.py` | `llm_config` | No real LLM client (OpenAI, Gemini, Anthropic) is called. Configuration exists as an unused metadata dictionary. |
| **Sandbox Execution & Security** | **2. Implemented but Incomplete** | `backend/app/sandbox/runner.py` | `EphemeralSandboxRunner`, `verify_python_ast_security()`, `run_validation()` | AST security gate correctly parses and rejects unsafe imports and calls. Isolated tempdir subprocess runs pytest. However, it hardcodes `COMMERCE_ADAPTER_TEST_SUITE` rather than dynamically testing proposed patches. Docker execution in `validate_patch()` has a mock fallback. |
| **Document Ingestion & RAG** | **3. Simulated or Hard-coded** | `backend/app/main.py`<br>`backend/app/agents/workflow.py` | `ingest_document()`, `compute_sha256_digest()` | SHA-256 deduplication works for uploaded text. However, vector retrieval in `run_incident_repair()` returns a static hardcoded result (`doc_cc_mig_22`, score 0.97). Qdrant is not connected. |
| **Human Review & Unified Patch** | **1. Fully Implemented & Verified** | `backend/app/github/client.py` | `generate_unified_patch()` | Produces standard reproducible Git unified diffs with commit hashes and evidence citations. |
| **GitHub Pull Request Integration** | **2. Implemented but Incomplete** | `backend/app/github/client.py` | `GitHubIntegrationClient.create_pull_request_or_export()` | Real `httpx` client implementation for GitHub REST API v3 exists. Correctly falls back to local export when token is missing. Needs integration with server-side credentials and repository verification. |
| **Authentication & RBAC** | **3. Simulated or Hard-coded** | `backend/app/main.py` | `require_roles()`, header `x-autopatch-role` | Security relies on an unverified HTTP header `x-autopatch-role: Admin` passed by the client. No password verification, JWT, session cookies, or cryptographic tokens exist. |
| **Production Staging Deployment** | **3. Simulated or Hard-coded** | `backend/app/main.py` | `authorize_deployment()` | Sets state to `DEPLOYED` and fabricates a mock deployment record. No actual deployment target is updated, no live adapter hot-reload is verified, and no rollback instructions exist. |
| **Analytics & ROI Calculation** | **3. Simulated or Hard-coded** | `backend/app/main.py`<br>`index.html` | `/api/v1/analytics/summary`, `computeKpis()` | Computed in-memory or in the browser from synthetic counts. Formulas are not documented or backed by database queries. |
| **Docker & Compose Environment** | **4. Broken** | `docker-compose.yml` | `dockerfile: Dockerfile` | `docker-compose.yml` specifies `dockerfile: Dockerfile`, but **no `Dockerfile` exists in the repository**. Running `docker compose up` fails immediately. |
| **Audit Logging** | **2. Implemented but Incomplete** | `backend/app/main.py` | `record_audit()`, `get_audit_logs()` | Audit records are appended to an in-memory list `STATE["audit_logs"]` rather than persisted to the SQLAlchemy `audit_logs` table. |

---

## 3. Detailed Component Audits

### 3.1. Gateway & Proxy Subsystem (`backend/app/main.py`)
- **Observed Behavior:**
  Lines 227–342 in `backend/app/main.py` define `proxy_gateway(integration_id, path, request, ...)`. When a request is received, it executes:
  ```python
  if mode == "SCHEMA_DRIFT" or cust_id == "cust_9041" or simulate_drift:
      upstream_payload = {
          "customerId": cust_id,
          "email": "buyer@enterprise.io" if cust_id != "cust_9099" else "hold@enterprise.io",
          "status": "SUSPENDED" if cust_id == "cust_9099" else "ACTIVE",
          "schemaVersion": "2.2",
      }
  ```
  It does not open an HTTP connection to the provider's `base_url`.
- **Requirements for Phase 4:**
  1. Build a real `httpx.AsyncClient` forwarder.
  2. Implement Anti-SSRF validator: verify target IP address against RFC 1918, RFC 3927 (link-local `169.254.0.0/16`), RFC 5735 (loopback `127.0.0.0/8`), and cloud metadata IP (`169.254.169.254`). Provide an explicit `ALLOW_LOCAL_PROXY=true` flag for local development/testing.
  3. Support retries with exponential backoff and jitter for idempotent HTTP methods (`GET`, `HEAD`, `OPTIONS`, `PUT`).
  4. Build a local mock upstream server fixture so development and automated tests run against real HTTP sockets.

### 3.2. Persistence & Database Sessions (`backend/app/models.py`)
- **Observed Behavior:**
  `backend/app/models.py` defines 21 clean SQLAlchemy ORM classes with table arguments, indexes, foreign keys, and cascading deletes.
  However, `backend/app/main.py` never instantiates `SessionLocal()` or injects a database session into route handlers. All database models are currently unused tables in SQLite.
- **Requirements for Phase 2 & 3:**
  1. Implement a FastAPI dependency `get_db() -> Generator[Session, None, None]`.
  2. Implement repository/service classes (`IntegrationService`, `IncidentService`, `RepairService`, `AuditService`) that perform real CRUD operations against SQLAlchemy.
  3. Ensure that when the server restarts, all integrations, incidents, repairs, and audit logs persist and reload seamlessly.

### 3.3. Contract Validation Engine (`backend/app/agents/workflow.py`)
- **Observed Behavior:**
  `validate_payload_against_contract()` performs manual recursive dictionary matching. While it correctly catches missing keys in a basic dictionary, it lacks validation against standard JSON Schema Draft-07 / 2020-12 specifications.
- **Requirements for Phase 5:**
  1. Leverage the installed `jsonschema` library (`jsonschema.Draft202012Validator` or `Draft7Validator`).
  2. Extract precise JSON paths (`$.properties.customerId`).
  3. Implement a multi-factor field rename heuristic:
     - Levenshtein / Normalized distance (e.g. `customer_id` vs `customerId`)
     - Same data type (both string)
     - Sibling value equality in sample payloads
     - Migration guide keyword correlation
     - Output confidence score ($0.0 - 1.0$) and explicit reasoning.

### 3.4. Repair State Machine & LLM Integration (`backend/app/agents/workflow.py`)
- **Observed Behavior:**
  `execute_langgraph_repair_workflow()` hardcodes the output:
  ```python
  "baseline_code": BASELINE_ADAPTER_CODE,
  "proposed_code": PATCHED_ADAPTER_CODE if is_schema_drift else BASELINE_ADAPTER_CODE,
  ```
- **Requirements for Phase 7:**
  1. Implement a genuine 12-stage executable state machine.
  2. Implement an `LLMProvider` interface with:
     - `GeminiProvider` (via `google-genai` SDK or REST)
     - `OpenAIProvider`
     - `DeterministicLocalProvider` (rules-based AST patch synthesizer for offline / zero-token development)
  3. Ensure the generator analyzes the actual source code of the target adapter, the detected schema diff, and ingested documentation.
  4. Enforce strict bounded revision ceiling (maximum 3 iterations).

### 3.5. Sandbox Runner (`backend/app/sandbox/runner.py`)
- **Observed Behavior:**
  `run_validation()` executes `pytest` against an isolated temporary directory, which is a great foundation. However, it only writes a single hardcoded test file (`COMMERCE_ADAPTER_TEST_SUITE`).
- **Requirements for Phase 8:**
  1. Accept target test suites and adapter files dynamically.
  2. Enforce execution timeouts, memory limits, and process isolation.
  3. Report truthful command outputs, exit codes, and durations.

### 3.6. Review, GitHub, & Deployment (`backend/app/github/client.py`, `backend/app/main.py`)
- **Observed Behavior:**
  - `generate_unified_patch()` is working.
  - `GitHubIntegrationClient` is implemented for GitHub REST API v3, but lacks integration with server-stored secrets.
  - Deployment is currently simulated in `authorize_deployment()`.
- **Requirements for Phase 10 & 11:**
  1. Implement verified server-side authentication (Admin / Reviewer session or API key).
  2. Connect GitHub client to encrypted server configuration.
  3. Implement a real Staging Deployment provider with live adapter hot-reloading and post-deployment verification HTTP request.

### 3.7. Containerization & Docker (`docker-compose.yml`)
- **Observed Behavior:**
  `docker-compose.yml` attempts to build from `Dockerfile`, which does not exist.
- **Requirements for Phase 16:**
  1. Author a secure, multi-stage, non-root `Dockerfile` using Python 3.12-slim.
  2. Update `docker-compose.yml` with proper health checks, environment variables, and network configuration.

---

## 4. Remediation Plan & Execution Roadmap

| Phase | Core Objective | Key Deliverables |
| :---: | :--- | :--- |
| **Phase 2** | Coherent Architecture | Service layer, SQLAlchemy session dependency, repository pattern, unified Pydantic schemas. |
| **Phase 3** | Integration Management | Real CRUD endpoints with database persistence, connectivity testing, secret masking. |
| **Phase 4** | Real API Proxy | `httpx` async forwarder, Anti-SSRF filter, exponential backoff retries, local mock upstream service. |
| **Phase 5** | Contract Validation | Real `jsonschema` engine, path-based diff detection, rename confidence heuristics. |
| **Phase 6** | Incident Management | Persistent incident lifecycle in DB, deterministic deduplication, severity grading. |
| **Phase 7** | Repair Planning & AI | 12-stage state machine, LLM provider abstraction (Gemini / OpenAI / Deterministic), dynamic patch generation. |
| **Phase 8** | Sandbox Test Runner | Isolated subprocess/container runner, dynamic test execution, AST security validation. |
| **Phase 9** | Knowledge Base & RAG | Document ingestion, SHA-256 deduplication, SQLite FTS5 / BM25 search fallback. |
| **Phase 10** | Human Review & GitHub | Secure review gate, unified diff viewer, genuine GitHub PR creation / local export fallback. |
| **Phase 11** | Controlled Deployment | Staging deployment provider, hot-reload mechanism, verification health check, rollback plan. |
| **Phase 12** | Analytics & Settings | DB-backed metrics, documented ROI formulas, server-side settings persistence. |
| **Phase 13** | Auth & Audit Security | Real user sessions, RBAC permission dependencies, immutable audit logs. |
| **Phase 14** | Frontend Wiring | Connect `index.html` to backend REST APIs, eliminate client-side fake states, retain Stitch UI. |
| **Phase 15** | Comprehensive Testing | 22-point acceptance test matrix, live integration tests with mock upstream. |
| **Phase 16** | Deployment & Docs | `Dockerfile`, updated `docker-compose.yml`, `.env.example`, full technical documentation suite. |
