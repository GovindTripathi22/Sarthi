# Local Setup & Development Guide — Sarthi / AutoPatch

This guide walks you through running Sarthi locally in development or simulation mode.

---

## 1. Prerequisites

- Python 3.11 or 3.12 installed
- Node.js v18+ and npm installed
- Git installed

---

## 2. Installation

1. Clone or navigate to the repository:
   ```bash
   cd C:\Users\USER\.gemini\antigravity\scratch\Sarthi
   ```

2. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. (Optional) Configure environment variables:
   ```bash
   cp .env.example .env
   ```
   *By default, the platform boots with SQLite (`sqlite:///./autopatch_local.db`) and local deterministic LLM synthesis mode, which requires zero external API keys.*

---

## 3. Running the Application

You can start Sarthi with either `npm` or `uvicorn`:

### Option A: Using NPM (Recommended)
```bash
npm run dev
```

### Option B: Using Python / Uvicorn directly
```bash
uvicorn backend.app.main:app --reload --port 8000
```

The application will initialize the 21 database tables and automatically seed the baseline catalog.

---

## 4. Accessing the Application

- **Web Application & Developer Console**: [http://localhost:8000](http://localhost:8000) (or [http://localhost:8000/app](http://localhost:8000/app))
- **FastAPI Interactive Swagger Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **API Health Check**: [http://localhost:8000/api/v1/health](http://localhost:8000/api/v1/health)
- **State Endpoint**: [http://localhost:8000/api/v1/state](http://localhost:8000/api/v1/state)

---

## 5. Running the Test Suites

Execute the comprehensive test suites:

```bash
# Run complete Python backend test suite (53 tests)
npm run test:backend

# Run frontend synthetic DOM acceptance tests (28 tests)
npm run test:frontend

# Run combined test suite
npm test
```
