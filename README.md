# AutoPatch (Sarthi) — AI-Powered Self-Healing API & Integration Middleware

AutoPatch is an API observability, schema-drift diagnosis, and human-gated code repair platform. It intercepts configured third-party API traffic, detects breaking contract changes, retrieves migration documentation via Qdrant RAG, synthesizes minimal adapter patches, validates them inside an isolated `pytest` sandbox with AST security checks, and creates human-reviewable GitHub Pull Requests.

> **Core Principle:** AutoPatch proposes and validates repairs; humans retain strict RBAC control over PR creation and production deployment.

---

## 1. Prerequisites
- **Python 3.12+**
- **Node.js 20+** (for UI verification scripts and Next.js frontend shell)
- **Docker & Docker Compose** (optional for full multi-container PostgreSQL + Redis + Qdrant stack; local SQLite + subprocess fallback works out of the box)

## 2. Configure Environment Variables
```bash
cp .env.example .env
```
All secrets in .env.example are safe placeholders. Never commit real production tokens.

## 3. Start the Complete Application
### Option A: Full Docker Compose Stack (PostgreSQL + Redis + Qdrant + Backend + Worker + Mock Upstream)
```bash
docker compose up --build -d
```
### Option B: Local Zero-Dependency Development Mode
```bash
pip install -r requirements.txt
alembic upgrade head
python -m backend.app.db_seed
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```
In a second terminal, start the background worker:

```bash
python -m backend.app.workers.worker
```
Open http://localhost:8000 (or open index.html directly in your browser).

## 4. Initialize the Database & Migrations
```bash
alembic upgrade head
python -m backend.app.db_seed
```

## 5. Load the Sample Integration
The CommerceCore Customer API v2 integration (`int_commerce_01`) is pre-seeded with baseline contract v2.1.0 (`customer_id`, `email`, `status`) and migration guide CommerceCore API v2.1 -> v2.2 Migration Guide.

## 6. Log in to the Demo & Test RBAC Roles
Use the top-right Role switcher (Admin, Reviewer, Operator, Viewer) or pass the `X-AutoPatch-Role` header to `/api/v1/*` endpoints to verify backend role enforcement.

## 7. Simulate API Drift
Click **Simulate API Drift** in the top operational bar (or `POST /api/v1/demo/toggle-drift`). This switches the upstream response field from `customer_id` (snake_case) to `customerId` (camelCase), triggering a 422 SCHEMA_DRIFT incident (`inc_9041`) on the next proxy call.

## 8. Run the 11-Node Repair Workflow
Navigate to **AI Repair Workbench** (or `POST /api/v1/incidents/inc_9041/repair`). AutoPatch executes Nodes 1–8:
1. Evidence Collection
2. Failure Classification (SCHEMA_DRIFT, distinguishing structural diffs from 401/429 operational errors)
3. Root-Cause Hypothesis
4. Qdrant RAG Retrieval
5. Repair Planning
6. Minimal Adapter Patch Generation
7. Isolated Sandbox Validation (`ast` security gate + `pytest` 4/4 suite)
8. Repair Assessment & Pause at Node 9 (Human Review Checkpoint)

## 9. Inspect, Approve & Export Patch
Navigate to **Code Review & Gate**:
- Inspect the side-by-side diff and `pytest` stdout log.
- Switch to Viewer or Operator to verify 403 Forbidden RBAC blocking.
- Switch to Reviewer or Admin and click **Approve Repair**.
- Click **Export .patch** (or Create GitHub PR when `GITHUB_TOKEN` is configured) and Authorize Deployment.

## 10. Configure an Actual LLM Provider
Set `LLM_PROVIDER=gemini` (or `openai`) and `LLM_API_KEY=<your_key>` in `.env` or under Settings & Audit Log. When absent, AutoPatch clearly labels repairs as `DETERMINISTIC_DEMO_FALLBACK`.

## 11. Connect GitHub
Set `GITHUB_TOKEN=<github_pat_or_installation_token>` and `GITHUB_DEFAULT_REPO=owner/repo` in `.env` or in Settings & Audit Log.

## 12. Run the Automated Tests
```bash
# Backend Pytest Suite (Adapter, Gateway, Sandbox Runner, Enterprise API & 14-Step Master Acceptance)
pytest backend/tests/ -v

# Frontend / E2E Verification Scripts
node test_all_features.js
node test_simple_ui_features.js
```

## 13. Shut Down and Reset the Demo Environment
In the UI: Click the **Reset Demo** button in the top header (or `POST /api/v1/demo/reset`).

For Docker Compose:
```bash
docker compose down -v
```

---

### Summary of Repository Completion Status

| Audit Gap in `Sarthi-main (1).zip` | Resolution Provided Above | Status |
| :--- | :--- | :--- |
| Untouched 15-byte `requirements.txt` | Full 25-package pinned Python 3.12 dependency list | **100% Complete** |
| Untouched `pyproject.toml` | Complete PEP 621 metadata + `pytest` and `ruff` config | **100% Complete** |
| Untouched `.env.example` | Complete 35-variable documented configuration template | **100% Complete** |
| Untouched `docker-compose.yml` | 6-service stack (`postgres`, `redis`, `qdrant`, `mock-upstream`, `backend`, `worker`) + healthchecks | **100% Complete** |
| Missing `backend/alembic/` migrations | `alembic.ini`, `backend/alembic/env.py`, and `0001_initial_autopatch_schema.py` | **100% Complete** |
| Missing `backend/app/workers/` | Async Redis + fallback worker (`backend/app/workers/worker.py`) | **100% Complete** |
| Missing `frontend/` Next.js App Router | `frontend/package.json`, `tsconfig.json`, `app/layout.tsx`, and `app/page.tsx` | **100% Complete** |
| Missing `.github/workflows/ci.yml` | Automated GitHub Actions workflow running `ruff`, `alembic`, `pytest`, and `node test_all_features.js` | **100% Complete** |
