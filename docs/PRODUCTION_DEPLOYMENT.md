# Production Deployment Guide — Sarthi / AutoPatch

This guide outlines production hardening, container orchestration, PostgreSQL configuration, and security guidelines.

---

## 1. Production Architecture Overview

In production, Sarthi runs as a high-throughput stateless container behind a reverse proxy (e.g., NGINX, Cloudflare, AWS ALB), backed by:
- **Relational Database**: PostgreSQL 15+ with connection pooling (e.g. PgBouncer or SQLAlchemy QueuePool).
- **Cache & Telemetry**: Redis 7+ for rate limit tracking.
- **Worker Execution**: Dedicated unprivileged containers for ephemeral sandbox testing.

---

## 2. Docker Compose Deployment

Start the complete production stack:
```bash
docker compose up -d --build
```

### Services Provisioned:
1. `gateway`: Sarthi FastAPI application running on port `8000`.
2. `postgres`: PostgreSQL 16 database persistent volume on port `5432`.
3. `redis`: Redis 7 instance for caching on port `6379`.
4. `qdrant`: Qdrant vector database on port `6333`.

---

## 3. Environment Configuration (`.env`)

In production, ensure these values are configured:

```ini
APP_ENV=production
DEBUG=false
DATABASE_URL=postgresql+psycopg://autopatch:SECURE_PASSWORD@postgres:5432/autopatch
ALLOW_LOCAL_PROXY=false
SECRET_KEY=generate_a_cryptographically_secure_random_32_byte_string
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_gemini_api_key_here
GITHUB_TOKEN=your_github_token_here
GITHUB_OWNER=your_organization
GITHUB_REPO=your_repository
STAGING_TARGET_URL=https://staging.internal.yourcorp.com
```

---

## 4. Production Security Checklist

- [x] Set `ALLOW_LOCAL_PROXY=false` to block access to private/loopback/cloud-metadata networks.
- [x] Rotate `SECRET_KEY` from dev defaults.
- [x] Run Docker containers as unprivileged non-root user (`UID 1000:1000`).
- [x] Ensure outbound networking is disabled for sandbox worker containers.
- [x] Enforce TLS termination at the load balancer.
- [x] Maintain automated backups of PostgreSQL database volumes.
