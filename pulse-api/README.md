# Pulse API

FastAPI backend for the Pulse multilingual content generation platform.

## Overview

The Pulse API is a modular monolith that provides:
- **Authentication** — JWT-based auth with multi-tenant workspace isolation
- **Content Generation** — 8-step pipeline with LLM abstraction (OpenAI, Anthropic, Ollama)
- **Content Management** — CRUD, versioning, review workflow, export
- **Cultural Adaptation** — Hofstede cultural dimensions across 10 market profiles
- **Bulk Job Processing** — Redis Streams-based async job queue
- **A/B Experimentation** — Deterministic variant assignment, chi-squared statistics
- **Integrations** — Vault connector, S3/MinIO storage, webhooks, analytics (GA4/Mixpanel/Segment)
- **Quality Scoring** — Heuristic engine for readability, structure, and formatting

## Architecture

```
API Layer (FastAPI routers)
    ↓
Service Layer (business logic)
    ↓
Model Layer (SQLAlchemy ORM, 18 entities)
    ↓
Integration Layer (LLM, Vault, S3, Webhooks, Analytics)
```

**Key patterns:**
- Multi-tenant: JWT → workspace_id → PostgreSQL RLS
- Async: All DB operations use SQLAlchemy async session
- Layered: Routers → Services → Models → Integrations
- Event-driven: Webhooks, audit logs, analytics on state changes

## Quick Start

```bash
cd pulse-api
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Set up environment
cp ../.env.example ../.env
# Edit ../.env with your database URL, Redis URL, API keys, etc.

# Run database migrations
alembic upgrade head

# Start the API server
uvicorn pulse.main:app --reload --port 8000
```

API docs available at http://localhost:8000/docs (Swagger UI) and http://localhost:8000/redoc (ReDoc).

## API Endpoints

All endpoints are under `/api/v1/`:

| Router | Key Endpoints |
|---|---|
| `auth` | `POST /register`, `POST /login`, `GET /me` |
| `generate` | `POST /generate` (single content), `POST /generate/bulk` |
| `content` | `GET /content`, `GET /content/{id}`, `PUT /content/{id}`, `DELETE /content/{id}`, `POST /content/{id}/review`, `POST /content/{id}/export`, `GET /content/{id}/versions` |
| `bulk_jobs` | `POST /bulk-jobs`, `GET /bulk-jobs`, `GET /bulk-jobs/{id}`, `GET /bulk-jobs/{id}/download` |
| `experiments` | `POST /experiments`, `GET /experiments`, `GET /experiments/{id}`, `GET /experiments/{id}/results`, `POST /experiments/{id}/promote-winner`, `POST /experiments/{id}/track`, `POST /experiments/{id}/tracking-urls` |
| `integrations` | `POST /integrations/vault/test`, `POST /integrations/storage/test`, `POST /integrations/webhooks/test`, `POST /integrations/analytics/test` |
| `health` | `GET /health/live`, `GET /health/ready` |

## Database Models

18 entities with PostgreSQL RLS for multi-tenant isolation:

| Entity | Description |
|---|---|
| `workspace` | Tenant workspace |
| `user` | User account (belongs to workspace) |
| `content` | Generated content item (partitioned by workspace) |
| `content_version` | Content version history |
| `brand_voice` | Brand voice configuration |
| `market_profile` | Cultural market profile (Hofstede dimensions) |
| `glossary` | Terminology glossary |
| `glossary_term` | Individual glossary term |
| `bulk_job` | Bulk generation job |
| `bulk_job_item` | Individual item in bulk job |
| `experiment` | A/B experiment |
| `experiment_variant` | Variant within an experiment |
| `performance_event` | Tracked performance metric |
| `prompt_version` | Prompt template version |
| `audit_log` | Audit trail (partitioned by date) |
| `webhook_config` | Webhook endpoint configuration |
| `api_key` | API key for programmatic access |
| `generation_cache` | LLM response cache |

## Environment Variables

Copy `../.env.example` to `../.env` and configure:

| Category | Variables |
|---|---|
| Application | `PULSE_ENV`, `PULSE_SECRET_KEY`, `PULSE_DEBUG`, `PULSE_LOG_LEVEL` |
| Database | `DATABASE_URL`, `DATABASE_POOL_SIZE`, `DATABASE_MAX_OVERFLOW` |
| Redis | `REDIS_URL` |
| JWT | `JWT_ALGORITHM`, `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` |
| LLM | `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `MISTRAL_API_KEY`, `OLLAMA_BASE_URL` |
| Storage | `STORAGE_ENDPOINT`, `STORAGE_ACCESS_KEY`, `STORAGE_SECRET_KEY`, `STORAGE_BUCKET` |
| Vault | `VAULT_API_URL`, `VAULT_API_KEY` |
| Analytics | `SEGMENT_WRITE_KEY`, `GA4_MEASUREMENT_ID`, `MIXPANEL_PROJECT_TOKEN` |
| Webhooks | `WEBHOOK_SIGNING_SECRET` |

## Tests

```bash
# Run all tests
pytest tests -v

# Run specific test file
pytest tests/test_auth.py -v

# Run with coverage
pytest tests -v --cov=pulse --cov-report=term-missing
```

Current test coverage: **57 tests across 10 files** covering auth, content, generation, experiments, bulk jobs, integrations, models, and health endpoints.

## Code Quality

```bash
# Lint
ruff check src tests

# Auto-fix lint issues
ruff check src tests --fix

# Type check (strict mode)
mypy src
```

Configuration:
- **ruff:** Python 3.11, line-length 100, rules `E F I N W UP B C4 SIM`
- **mpy:** Strict mode, Python 3.11

## Migrations

```bash
# Create a new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# View migration history
alembic history
```

## Project Structure

```
pulse-api/
├── src/pulse/
│   ├── main.py              # FastAPI app factory
│   ├── config.py            # Pydantic settings
│   ├── api/
│   │   ├── health.py        # Health check endpoints
│   │   ├── deps.py          # Shared dependencies
│   │   ├── schemas/         # Pydantic request/response schemas
│   │   └── v1/              # API v1 routers (7 routers)
│   ├── auth/                # JWT auth, password hashing
│   ├── core/                # Logging, experiment subsystem
│   ├── cultural/            # Cultural adaptation engine
│   ├── db/                  # SQLAlchemy session, Alembic
│   ├── generation/          # 8-step orchestrator
│   ├── integrations/        # Vault, S3, webhooks, analytics
│   ├── llm/                 # LLM abstraction layer
│   ├── middleware/          # Tenant middleware
│   ├── models/              # 18 ORM entities
│   ├── prompts/             # Prompt composer
│   ├── quality/             # Quality scoring engine
│   ├── services/            # Business logic
│   └── worker/              # Redis Streams worker
├── tests/                   # 57 tests (10 files)
├── pyproject.toml           # Dependencies and config
├── alembic.ini              # Alembic config
└── Dockerfile               # Container build
```

## Dependencies

**Runtime:** fastapi, uvicorn, sqlalchemy, asyncpg, redis, pydantic, alembic, httpx, python-jose, passlib, python-multipart, prometheus-client, structlog, opentelemetry

**Dev:** pytest, pytest-asyncio, httpx, aiosqlite, anyio, ruff, mypy
