# CLAUDE.md — AI Agent Instructions

This file provides guidance to AI coding agents (Claude Code, Copilot, etc.) when working with this repository.

## Repository Status

**This is a fully implemented codebase.** All 10 checkpoints from the planning phase are complete. The backend API, frontend SPA, worker, scheduler, and deployment artifacts are all implemented with passing tests and clean lint/type checks.

- **Backend:** 90 Python source files, 57 tests passing
- **Frontend:** 13 TypeScript/React files, clean typecheck and build
- **Deployment:** Docker Compose (7 services) + Kubernetes manifests (9 YAML files)
- **Status:** All checks pass — `make test && make lint && make typecheck` clean

## Codebase Overview

```
odw-pulse/
├── pulse-api/            # FastAPI backend (90 Python source files)
│   ├── src/pulse/
│   │   ├── api/          # HTTP endpoints (7 routers under /api/v1/)
│   │   ├── auth/         # JWT auth, password hashing, dependencies
│   │   ├── core/         # Logging, experiment subsystem
│   │   ├── cultural/     # Cultural adaptation engine (10 markets)
│   │   ├── db/           # SQLAlchemy async session, Alembic migrations
│   │   ├── generation/   # 8-step generation orchestrator pipeline
│   │   ├── integrations/ # Vault, S3/MinIO, webhooks, analytics
│   │   ├── llm/          # LLM abstraction layer (OpenAI, Anthropic, Ollama)
│   │   ├── middleware/   # TenantMiddleware (workspace isolation)
│   │   ├── models/       # 18 ORM entities with PostgreSQL RLS
│   │   ├── prompts/      # Prompt composer with versioning
│   │   ├── quality/      # Heuristic quality scoring engine
│   │   ├── services/     # Business logic layer
│   │   └── worker/       # Redis Streams consumer for bulk jobs
│   └── tests/            # 57 tests across 10 files
├── pulse-ui/             # React 18 + TypeScript + Vite SPA
│   └── src/
│       ├── api/          # Axios HTTP client
│       ├── components/   # Layout, NavLink
│       ├── pages/        # 7 pages (Dashboard, Generate, Content, BulkJobs, Experiments, Settings)
│       └── types/        # TypeScript type definitions
├── pulse-worker/         # Standalone async worker package
├── pulse-scheduler/      # Standalone scheduler package
├── k8s/                  # Kubernetes deployment manifests (9 YAML files)
├── docker-compose.yml    # Full dev stack (7 services)
├── Makefile              # Development commands
├── .env.example          # Environment variable template
├── prd.md                # Product Requirements Document (~101 KB)
├── tsd.md                # Technical Specification Document (~106 KB)
├── sad.md                # System Architecture Document (~84 KB)
├── tbk.md                # Task Breakdown Knowledge (~139 KB)
├── research.md           # Competitive landscape analysis
├── DEVELOPMENT.md        # Implementation status, known gaps, roadmap
└── .env.example          # Environment template (30+ variables)
```

## Architecture

### Backend (pulse-api/)

FastAPI monolith with SQLAlchemy 2.0 async ORM and PostgreSQL RLS.

**Layer structure:**
1. `api/v1/` — HTTP routers (7 routers: auth, generate, content, bulk_jobs, experiments, integrations, health)
2. `services/` — Business logic (content_service, review_service, bulk_job_service, experiment_service)
3. `models/` — 18 ORM entities with PostgreSQL RLS for multi-tenancy
4. `core/` — Shared utilities (logging, experiment subsystem: assignment, statistics, tracking)
5. `integrations/` — External connectors (vault, storage/S3, webhooks, analytics: GA4/Mixpanel/Segment)
6. `llm/` — LLM abstraction layer with adapters (OpenAI, Anthropic, Ollama), registry, fallback router with circuit breaker
7. `cultural/` — Cultural adaptation engine (10 market profiles, Hofstede dimensions)
8. `generation/` — 8-step generation orchestrator pipeline
9. `quality/` — Heuristic quality scoring engine
10. `prompts/` — Prompt composer with versioning
11. `middleware/` — TenantMiddleware for workspace resolution from JWT
12. `worker/` — Redis Streams consumer for bulk job processing

**Key patterns:**
- **Multi-tenant:** JWT → workspace_id → `SET app.current_workspace` → PostgreSQL RLS filters all queries
- **Deterministic A/B assignment:** `SHA256(entity_id + experiment_id) % 10000` → bucket → variant
- **Circuit breaker:** LLM adapters have failure thresholds with fallback routing
- **Prompt versioning:** Every generation records prompt_version_id for reproducibility
- **Event-driven:** Webhooks, audit logs, and analytics on content state changes

**Dependencies:** fastapi, sqlalchemy[asyncio], asyncpg, redis, pydantic v2, alembic, httpx, python-jose, passlib, prometheus-client, structlog, opentelemetry

### Frontend (pulse-ui/)

React 18 SPA with TypeScript, Vite, TanStack Query, React Router v6, Tailwind CSS.

**Pages:** Dashboard, Generate, ContentList, ContentDetail, BulkJobs, Experiments, Settings

**Key patterns:**
- API client: axios instance with base URL from `VITE_API_URL`
- State management: TanStack Query for server state (no global client store)
- Routing: React Router v6 with layout wrapper
- Styling: Tailwind CSS utility classes

### Data Model

18 entities: workspace, user, content, content_version, brand_voice, market_profile, glossary, glossary_term, bulk_job, bulk_job_item, experiment, experiment_variant, performance_event, prompt_version, audit_log, webhook_config, api_key, generation_cache

Partitioned tables: content (HASH by workspace_id), audit_log (RANGE by created_at)

### Deployment

- **Docker Compose (dev):** postgres, redis, minio, pulse-api, pulse-worker, pulse-scheduler, pulse-ui
- **Kubernetes (prod):** StatefulSet for Postgres, Deployments for app services (2 replicas for API/UI/worker, 1 for scheduler), nginx ingress

## Build & Verification Commands

```bash
# Full stack
make dev                        # Docker Compose (all 7 services)
make build                      # Build all Docker images

# Backend (from pulse-api/)
source .venv/bin/activate
uvicorn pulse.main:app --reload --port 8000   # Run API
pytest tests -v                                # 57 tests, ~2.6s
ruff check src tests                           # Lint (90 files)
mypy src                                       # Type check strict (90 files)

# Frontend (from pulse-ui/)
npm run dev           # Dev server (port 5173)
npm run typecheck     # TypeScript check
npm run build         # Production build (Vite, ~900ms)
npm run lint          # ESLint

# Database
alembic upgrade head   # Run migrations (from pulse-api/)
```

## When Making Changes

### Adding a new API endpoint
1. Add schema in `pulse-api/src/pulse/api/schemas/`
2. Add router function in `pulse-api/src/pulse/api/v1/`
3. Add business logic in `pulse-api/src/pulse/services/`
4. Add model in `pulse-api/src/pulse/models/` (if new entity)
5. Register router in `pulse-api/src/pulse/main.py`
6. Add tests in `pulse-api/tests/`
7. Run `pytest tests -v && ruff check src tests && mypy src`

### Adding a new frontend page
1. Create component in `pulse-ui/src/pages/`
2. Add route in `pulse-ui/src/App.tsx`
3. Add nav link in `pulse-ui/src/components/Layout.tsx`
4. Add types in `pulse-ui/src/types/index.ts` (if new API types)
5. Run `npm run typecheck && npm run build`

### Adding a new LLM provider
1. Create adapter in `pulse-api/src/pulse/llm/providers/`
2. Register in `pulse-api/src/pulse/llm/registry.py`
3. Add config in `pulse-api/src/pulse/config.py`
4. Add env var in `.env.example`
5. Add tests

### Adding a database migration
```bash
cd pulse-api
alembic revision --autogenerate -m "description"
alembic upgrade head
```

## Known Gaps

See `DEVELOPMENT.md` for the full list. Top priorities:

1. **No CI/CD** — No `.github/workflows/`. Tests/lint/build run manually.
2. **k8s ConfigMap missing** — Manifests reference `pulse-config` ConfigMap that doesn't exist.
3. **Analytics connectors are stubs** — GA4/Mixpanel/Segment log calls but don't send data.
4. **Vault connector is a mock** — Returns canned responses, doesn't call real API.
5. **No rate limiting** — No per-tenant or per-IP limits.
6. **Worker/scheduler inconsistency** — Launched from pulse-api venv in Makefile but are separate packages.
7. **No E2E tests** — Only unit/integration tests via pytest.
8. **Heuristic quality scoring** — No LLM-based evaluation.
9. **No pagination on bulk endpoints** — Large jobs will OOM.
10. **No streaming responses** — Long-running generation blocks the request.

## Future Improvements

See `DEVELOPMENT.md` §Future Improvements for the full roadmap. Key areas:

1. **CI/CD pipeline** — GitHub Actions for test/lint/build/deploy
2. **E2E testing** — Playwright for frontend, integration tests with real PostgreSQL
3. **Production hardening** — Rate limiting, request validation, database backups
4. **Real integrations** — Connect analytics, Vault, webhooks to real services
5. **LLM-based quality** — Evaluate content quality beyond heuristics
6. **Content moderation** — Automated safety/appropriateness checks
7. **Streaming responses** — SSE for long-running generation
8. **Prompt A/B testing** — Test different prompt templates
9. **Multi-workspace admin** — Super-admin dashboard
10. **Content personalization** — Audience-segment-specific variants

## Conventions

- **Python:** ruff for lint (py311, line-length 100, select `E F I N W UP B C4 SIM`), mypy strict
- **TypeScript:** strict mode, ESLint with react-hooks/react-refresh plugins
- **Imports:** isort via ruff (I rule), sorted alphabetically
- **Error handling:** Use `raise ... from err` for exception chains (B904)
- **Logging:** structlog for structured JSON logging
- **Async:** All DB operations are async (SQLAlchemy async session)
- **Types:** Pydantic v2 for API schemas, dataclasses for internal models
- **Testing:** pytest-asyncio with `asyncio_mode = "auto"`, httpx TestClient for API tests
- **Commits:** Conventional commits preferred (`feat:`, `fix:`, `docs:`, `refactor:`)

## Environment Variables

See `.env.example` for the complete template (30+ variables). Key categories:
- **Application:** `PULSE_ENV`, `PULSE_SECRET_KEY`, `PULSE_DEBUG`, `PULSE_LOG_LEVEL`
- **Database:** `DATABASE_URL`, `DATABASE_POOL_SIZE`, `DATABASE_MAX_OVERFLOW`
- **Redis:** `REDIS_URL`
- **JWT:** `JWT_ALGORITHM`, `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`
- **LLM:** `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `MISTRAL_API_KEY`, `OLLAMA_BASE_URL`, `VLLM_BASE_URL`
- **Storage:** `STORAGE_ENDPOINT`, `STORAGE_ACCESS_KEY`, `STORAGE_SECRET_KEY`, `STORAGE_BUCKET`
- **Vault:** `VAULT_API_URL`, `VAULT_API_KEY`
- **Analytics:** `SEGMENT_WRITE_KEY`, `GA4_MEASUREMENT_ID`, `GA4_API_SECRET`, `MIXPANEL_PROJECT_TOKEN`
- **Webhooks:** `WEBHOOK_SIGNING_SECRET`
