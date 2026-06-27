# ODW Pulse

ODW Pulse is a multilingual content generation platform that produces culturally-adapted marketing content across 50+ languages. Unlike simple translation tools, Pulse adapts tone, idiom, and cultural context for each target market.

## Status

⚠️ **Early release.** ODW [Name] is an early, functional release — core features work, but it is not yet hardened for production. We are refining every module toward a first full public release in **Q3 2026**. Until then, it is best used as a foundation to build on with AI coding agents (see below).

## Build Status

| Check | Status |
|---|---|
| Backend Tests (57) | ✅ Passing |
| Backend Lint (ruff, 90 files) | ✅ Clean |
| Backend Types (mypy strict, 90 files) | ✅ Clean |
| Frontend Types (TypeScript) | ✅ Clean |
| Frontend Build (Vite) | ✅ Clean |

## Key Differentiators

1. **Cultural Adaptation Engine** — Not literal translation. Adapts tone, formality, idioms per market using Hofstede cultural dimensions across 10 market archetypes.
2. **Vault Integration** — Content is grounded in the business's own knowledge, products, and brand voice via the Vault connector.
3. **Infrastructure Sovereignty** — Fully self-hosted, model-agnostic, no data leaves the customer's deployment. Air-gapped environments supported.
4. **A/B Experimentation** — Built-in A/B testing with deterministic variant assignment, chi-squared statistical significance, and winner promotion.
5. **Bulk Generation** — Redis Streams-based job queue for high-volume content generation with CSV import/export.

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI + SQLAlchemy 2.0 (async) + Pydantic v2 |
| Database | PostgreSQL 16 (with RLS for multi-tenancy) |
| Cache/Queue | Redis 7 (caching + Streams for job queue) |
| LLM Integration | Model-agnostic adapters (OpenAI, Anthropic, Ollama via httpx) |
| Frontend | React 18 + TypeScript + Vite + TanStack Query + Tailwind CSS |
| Migrations | Alembic (with partitioned table support) |
| Deployment | Docker Compose (dev) + Kubernetes manifests (prod) |
| Object Storage | S3/MinIO |
| Observability | Prometheus metrics, OpenTelemetry, structlog |

## Architecture

Pulse uses a **modular monolith with async job processing**:

```
┌─────────────────────────────────────────────────────┐
│                    React SPA                         │
│  (Dashboard, Generate, Content, Bulk Jobs,          │
│   Experiments, Settings)                            │
└──────────────────┬──────────────────────────────────┘
                   │ REST API
┌──────────────────▼──────────────────────────────────┐
│              FastAPI Monolith                         │
│  ┌─────────┐ ┌──────────┐ ┌────────────────────┐   │
│  │  Auth   │ │ Generate │ │ Content Management │   │
│  │  (JWT)  │ │ Pipeline │ │  (CRUD + Review)   │   │
│  └─────────┘ └────┬─────┘ └────────────────────┘   │
│  ┌─────────┐ ┌────┴─────┐ ┌────────────────────┐   │
│  │  Bulk   │ │Experiment│ │   Integrations     │   │
│  │  Jobs   │ │ Engine   │ │ (Vault, S3,        │   │
│  │         │ │ (A/B)    │ │  Webhooks,         │   │
│  └─────────┘ └──────────┘ │  Analytics)        │   │
│                           └────────────────────┘   │
│  LLM Layer: OpenAI / Anthropic / Ollama adapters   │
│  Cultural Engine: 10 market profiles, Hofstede     │
│  Quality Engine: Heuristic scoring + flags         │
└──────┬──────────────┬───────────────┬──────────────┘
       │              │               │
┌──────▼───┐   ┌─────▼─────┐   ┌────▼─────┐
│PostgreSQL│   │   Redis   │   │  S3/MinIO│
│  (RLS)   │   │ (Streams) │   │          │
└──────────┘   └───────────┘   └──────────┘
```

**Key design decisions:**
- Multi-tenant workspace isolation via JWT + PostgreSQL Row-Level Security
- Deterministic A/B variant assignment (SHA256 hashing by entity_id + experiment_id)
- Circuit breaker pattern for LLM provider failover
- Prompt versioning with automatic version tracking
- Event-driven: webhooks, audit logging, analytics connectors

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- Docker & Docker Compose (for full-stack development)

### Full Stack (Docker Compose)

```bash
# Clone the repository
git clone git@github.com:OnDemandWorld/odw-pulse.git
cd odw-pulse

# Copy environment template and configure
cp .env.example .env
# Edit .env with your API keys and settings

# Start all services
make dev
```

This starts: PostgreSQL, Redis, MinIO, pulse-api, pulse-worker, pulse-scheduler, pulse-ui.

### Individual Services

```bash
# Backend API
cd pulse-api
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
uvicorn pulse.main:app --reload --port 8000

# Frontend
cd pulse-ui
npm install
npm run dev
```

### Environment Configuration

Copy `.env.example` to `.env` and configure:

| Category | Variables |
|---|---|
| Application | `PULSE_ENV`, `PULSE_SECRET_KEY`, `PULSE_DEBUG`, `PULSE_LOG_LEVEL` |
| Database | `DATABASE_URL`, `DATABASE_POOL_SIZE` |
| Redis | `REDIS_URL` |
| LLM Providers | `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `OLLAMA_BASE_URL`, + more |
| Storage | `STORAGE_ENDPOINT`, `STORAGE_ACCESS_KEY`, `STORAGE_BUCKET` |
| Vault | `VAULT_API_URL`, `VAULT_API_KEY` |
| Analytics | `SEGMENT_WRITE_KEY`, `GA4_MEASUREMENT_ID`, `MIXPANEL_PROJECT_TOKEN` |
| Webhooks | `WEBHOOK_SIGNING_SECRET` |

## Project Structure

```
odw-pulse/
├── pulse-api/            # FastAPI backend (90 source files)
│   ├── src/pulse/
│   │   ├── api/          # HTTP endpoints (7 routers)
│   │   ├── auth/         # JWT auth, password hashing
│   │   ├── core/         # Logging, experiment subsystem
│   │   ├── cultural/     # Cultural adaptation engine
│   │   ├── db/           # SQLAlchemy session, Alembic migrations
│   │   ├── generation/   # 8-step generation orchestrator
│   │   ├── integrations/ # Vault, S3, webhooks, analytics
│   │   ├── llm/          # LLM abstraction layer
│   │   ├── middleware/   # Tenant isolation
│   │   ├── models/       # 18 ORM entities
│   │   ├── prompts/      # Prompt composer
│   │   ├── quality/      # Quality scoring engine
│   │   ├── services/     # Business logic layer
│   │   └── worker/       # Redis Streams worker
│   └── tests/            # 57 tests (10 files)
├── pulse-ui/             # React SPA (13 source files)
│   └── src/
│       ├── api/          # Axios HTTP client
│       ├── components/   # Layout, NavLink
│       ├── pages/        # 7 pages
│       └── types/        # TypeScript type definitions
├── pulse-worker/         # Standalone worker package
├── pulse-scheduler/      # Standalone scheduler package
├── k8s/                  # Kubernetes manifests (9 YAML files)
├── docker-compose.yml    # Full dev stack
├── Makefile              # Development commands
├── .env.example          # Environment template
├── prd.md                # Product Requirements Document
├── tsd.md                # Technical Specification Document
├── sad.md                # System Architecture Document
├── tbk.md                # Task Breakdown Knowledge
├── research.md           # Competitive landscape analysis
├── DEVELOPMENT.md        # Implementation status & roadmap
└── CLAUDE.md             # AI agent instructions
```

## Development Commands

| Command | Description |
|---|---|
| `make dev` | Start full Docker Compose stack |
| `make api` | Run API server locally (with reload) |
| `make worker` | Run async worker locally |
| `make scheduler` | Run scheduler locally |
| `make ui` | Run UI dev server (Vite) |
| `make test` | Run backend tests (pytest) |
| `make lint` | Run ruff on backend |
| `make typecheck` | Run mypy strict on backend |
| `make build` | Build all Docker images |

## API Endpoints

All endpoints are under `/api/v1/`:

| Router | Key Endpoints |
|---|---|
| `auth` | `POST /register`, `POST /login`, `GET /me` |
| `generate` | `POST /generate` (single content), `POST /generate/bulk` |
| `content` | `GET/PUT/DELETE /content`, `POST /:id/review`, `POST /:id/export` |
| `bulk_jobs` | `POST /bulk-jobs`, `GET /bulk-jobs/:id`, `GET /:id/download` |
| `experiments` | `POST /experiments`, `GET /:id/results`, `POST /:id/promote-winner` |
| `integrations` | `POST /integrations/vault/test`, `POST /integrations/storage/test`, etc. |

## Deployment

### Docker Compose (Development)

```bash
make dev
```

### Kubernetes (Production)

```bash
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/secrets.yaml  # Copy from k8s/secrets.example.yaml
kubectl apply -f k8s/postgres.yaml
kubectl apply -f k8s/redis.yaml
kubectl apply -f k8s/pulse-api.yaml
kubectl apply -f k8s/pulse-worker.yaml
kubectl apply -f k8s/pulse-scheduler.yaml
kubectl apply -f k8s/pulse-ui.yaml
kubectl apply -f k8s/ingress.yaml
```

## Positioning

Pulse is a **value-adding suite module** within the ODW.ai platform, not a standalone lead product. Defensibility comes from:
- Genuine cultural adaptation quality (not just translation)
- Suite integration (Vault grounding, brand voice consistency)
- Infrastructure sovereignty (self-hosted, model-agnostic)

Content generation itself is increasingly commoditized — Pulse's value is in the localization quality layer and the data flywheel from experimentation.

## Working with AI agents
This repository is built to be extended with AI coding agents. Rather than a turnkey product, ODW [Name] is a working, well-structured codebase you can clone and adapt to your own needs with an agent like Claude Code. The repo includes agent context files (e.g. `CLAUDE.md`) and clear architecture docs so an agent can quickly understand the structure and help you customise, integrate, and extend it. To get started: clone the repo, open it with your coding agent, point it at this README and the docs, and describe what you want to build.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

