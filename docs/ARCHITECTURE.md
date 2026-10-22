# Sarthi / AutoPatch Architecture Specification

## 1. System Overview

Sarthi is an autonomous self-healing API middleware gateway engineered to detect third-party contract changes, investigate integration failures, synthesize backward-compatible repair adapters, validate changes in isolated sandboxes, and orchestrate human-gated deliveries with zero downtime.

```mermaid
flowchart TD
    Client["Client / Enterprise Application"] -->|Proxy Route /proxy/{id}/{path}| Gateway["Sarthi Gateway Proxy (FastAPI)"]
    Gateway -->|Anti-SSRF & Retries| Upstream["Upstream 3rd-Party API"]
    Upstream -->|HTTP Response / Drift| Gateway
    
    subgraph Self-Healing Core
        Gateway -->|Contract Failure| ContractValidator["Contract Validation Engine (jsonschema)"]
        ContractValidator -->|Structural Diff & Renames| IncidentManager["Incident Manager & Forensics"]
        IncidentManager -->|Trigger State Machine| RepairEngine["12-Stage Repair Engine"]
        RepairEngine -->|RAG Ingestion & Search| KnowledgeBase["Knowledge Base (SQLite FTS / BM25)"]
        RepairEngine -->|Adapter Synthesis| LLMService["LLM Provider (Gemini / Local Deterministic)"]
        LLMService -->|AST Security Policy| ASTGate["Python AST Security Analyzer"]
        ASTGate -->|Ephemeral Isolated Run| Sandbox["Isolated Test Sandbox (pytest)"]
    end

    Sandbox -->|Evidence & Unified Diff| ReviewGate["Human Review Checkpoint (RBAC)"]
    ReviewGate -->|Admin Authorization| StagingDeploy["Staging Deployment & Hot-Reload"]
    ReviewGate -->|Export / PR| GitHub["GitHub REST API v3 / Patch Export"]
    StagingDeploy -->|Verification Check (200 OK)| IncidentManager
```

---

## 2. Core Subsystems

### 2.1. API Gateway Proxy (`backend/app/services/proxy_service.py`)
- **Forwarding Pipeline**: Validates incoming route parameters, checks if connector monitoring is paused, strips internal credentials, and dispatches HTTP requests using `httpx.AsyncClient`.
- **Anti-SSRF Protection (`backend/app/security/ssrf.py`)**: Blocks private IP addresses (RFC 1918), loopback (`127.0.0.0/8`), link-local (`169.254.0.0/16`), and AWS/GCP cloud metadata endpoints (`169.254.169.254`). Permitted in local development via `ALLOW_LOCAL_PROXY=true`.
- **Transient Resilience**: Applies exponential backoff with jitter for idempotent HTTP methods (`GET`, `HEAD`, `OPTIONS`, `PUT`) and honors upstream `Retry-After` headers.
- **Incident Decoupling**: Categorizes operational errors (401, 403, 429, 500, timeouts) separately from schema drifts.

### 2.2. Contract Validation Engine (`backend/app/services/contract_service.py`)
- Standard JSON Schema Draft-07 / 2020-12 validation via `jsonschema`.
- Multi-factor field rename heuristic:
  - Normalized identifier distance (e.g., `customer_id` vs `customerId`)
  - Datatype matching and sibling value comparison
  - Confidence scoring ($0.0 - 1.0$) with explicit rationale.

### 2.3. Incident Management & Forensics (`backend/app/services/incident_service.py`)
- Deterministic deduplication across repeat occurrences of the same failure pattern.
- Explicit severity rules: `CRITICAL` for schema drift, `HIGH` for server outages/auth failures, `MEDIUM` for rate limits.
- Persisted forensic audit trail in `incident_events` table.

### 2.4. 12-Stage Repair State Machine (`backend/app/services/repair_service.py`)
1. Validate incident evidence
2. Reproduce failure trace
3. Compare baseline & observed contracts
4. Formulate root-cause hypothesis
5. Retrieve vendor migration documentation
6. Plan backward-compatible adapter modification
7. Synthesize code patch via `LLMProvider`
8. Verify Python AST security policy
9. Execute isolated regression tests in sandbox
10. Pause at persistent Human Review Checkpoint (Node 9)
11. Generate GitHub Pull Request or unified `.patch` export
12. Authorize staging deployment and verify recovery

### 2.5. Ephemeral Isolated Sandbox (`backend/app/services/sandbox_service.py`)
- AST security gate parses code to block dangerous builtins (`eval`, `exec`, `__import__`, `os.environ` scraping, `subprocess`, etc.).
- Executes in disposable temporary workspaces with stripped environment variables (`SYSTEMROOT`, `PATH`, sanitized `PYTHONPATH`).
- Records truthful execution durations, exit codes, and test logs.

### 2.6. Database Persistence (`backend/app/models.py`)
21 normalized SQLAlchemy tables:
`users`, `workspaces`, `workspace_members`, `integrations`, `integration_secrets`, `api_contract_versions`, `documentation_sources`, `document_chunks`, `request_events`, `schema_drift_events`, `incidents`, `incident_events`, `agent_runs`, `agent_run_checkpoints`, `patch_artifacts`, `test_runs`, `github_pull_requests`, `approval_requests`, `deployment_records`, `usage_records`, `audit_logs`.
