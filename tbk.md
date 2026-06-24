# Pulse — Task Breakdown Knowledge (TBK)

**Product:** Pulse (ODW.ai Suite Module)
**Document Version:** 1.1
**Date:** 2026-06-24
**Status:** Ready for Execution
**Based on:** TSD v1.0 (2026-06-23)
**Changes:** Added EPIC-6 (Experimentation & Performance Tracking) with 8 new tasks (EXP-001 through EXP-008)

---

## 1. Execution Overview

### 1.1 Implementation Strategy

Pulse is a multilingual content generation and localization engine built on a Django/FastAPI monolith with PostgreSQL, Redis, and Vault integration. The system generates culturally-adapted marketing content across 50+ languages using model-agnostic LLM backends.

The implementation follows a **layered build strategy** — foundation first (infrastructure, auth, data models), then core intelligence (generation pipeline, cultural adaptation), then workflows (content management, bulk jobs), then integrations (Vault, webhooks, analytics connectors), then experimentation (A/B testing, performance tracking), and finally the frontend and deployment artifacts.

### 1.2 Major Phases

| Phase | Description | Duration Estimate |
|---|---|---|
| Phase 1 | Environment & Project Setup | 2 days |
| Phase 2 | Core Infrastructure (DB, Auth, Tenant Isolation) | 4 days |
| Phase 3 | Core Business Logic (Generation Pipeline, Cultural Engine, Quality Scoring) | 8 days |
| Phase 4 | API Layer (All REST endpoints, WebSocket) | 5 days |
| Phase 5 | Integrations (Vault, S3, Webhooks, LLM Providers, Analytics Connectors) | 6 days |
| Phase 6 | Frontend & Experimentation (React UI, A/B Testing UI) | 7 days |
| Phase 7 | Experimentation & Performance Tracking (A/B Testing, Statistical Analysis, Analytics Integration) | 8 days |
| Phase 8 | Testing & Deployment Preparation | 4 days |

**Total estimated duration:** 44 working days (single developer/agent)

### 1.3 Parallelizable vs Sequential Workstreams

**Sequential (Critical Path):**
- Database schema → ORM models → Migrations → Auth middleware → API endpoints
- LLM abstraction layer → LLM adapters → Generation orchestrator → Quality scoring
- Cultural adaptation engine → Prompt composer → Generation pipeline
- Experiment data models → Assignment engine → Statistics engine → Experiment service → Experiment API

**Parallelizable Workstreams:**
- Frontend development (after API contracts are defined) can proceed in parallel with backend integrations
- LLM adapter implementations (OpenAI, Anthropic, Mistral, etc.) are independent of each other
- Analytics connectors (Segment, GA4, Mixpanel) are independent of each other
- Experimentation UI can proceed in parallel once experiment API contracts defined
- Scheduler jobs (results computation, analytics sync) independent of core experiment logic
- Unit tests can be written alongside each module implementation
- Docker/deployment configuration can proceed once service structure is defined
- Webhook dispatcher and analytics module are independent of core generation

### 1.4 Critical Path Components

1. **LLM Abstraction Layer** — All generation depends on this; must be built first among core logic
2. **Cultural Adaptation Engine** — Core IP differentiator; feeds into Prompt Composer
3. **Generation Orchestrator** — Central pipeline that ties all core components together
4. **Experimentation Engine** — All A/B testing depends on this; must be built after core generation pipeline
5. **PostgreSQL Schema + RLS** — Foundation for all data operations; tenant isolation is non-negotiable
6. **Vault Connector** — Knowledge grounding is essential for quality; blocks end-to-end testing

### 1.5 Key Technical Decisions

- **Framework:** FastAPI (not Django REST Framework) for async-native performance with LLM streaming
- **Task Queue:** Redis Streams (not Celery) for exactly-once semantics and lower operational complexity
- **ORM:** SQLAlchemy 2.0 async with Alembic migrations
- **Validation:** Pydantic v2 for all API schemas and configuration
- **Multi-tenancy:** PostgreSQL Row-Level Security (RLS) as defense-in-depth alongside application-level workspace scoping
- **Caching:** Multi-layer (Redis hot cache + PostgreSQL durable fallback for generation cache)

---

## 2. Task Breakdown Structure

### Epic Overview

| Epic ID | Epic Name | Tasks | Estimated Effort |
|---|---|---|---|
| EPIC-1 | Infrastructure & Foundation | 7 tasks | 12 days |
| EPIC-2 | Core Generation Engine | 7 tasks | 14 days |
| EPIC-3 | Content & Workflow Management | 6 tasks | 10 days |
| EPIC-4 | Integrations & External Services | 5 tasks | 8 days |
| EPIC-5 | Frontend & Deployment | 5 tasks | 10 days |
| EPIC-6 | Experimentation & Performance Tracking | 8 tasks | 10 days |

**Total: 38 tasks across 6 epics**

---

## 3. Task Definitions

---

### EPIC-1: Infrastructure & Foundation

---

#### Task INFRA-001: Project Scaffolding & Configuration

**ID:** INFRA-001
**Title:** Project Scaffolding, Dependencies, and Configuration System
**Description:** Initialize the monorepo structure with all four deployment units (pulse-api, pulse-worker, pulse-scheduler, pulse-ui). Set up Python virtual environments, dependency management (pyproject.toml), and the pydantic-settings configuration system that reads from environment variables. Create the base FastAPI application entry point with lifespan management, CORS configuration, and structured JSON logging.
**Inputs:** TSD Sections 3.1, 3.5, 10, 17, 18
**Output:**
- `pulse/pulse-api/pyproject.toml` with all dependencies (fastapi, sqlalchemy, redis-py, httpx, pydantic, alembic, python-jose, python-docx, weasyprint, prometheus-client, opentelemetry-*)
- `pulse/pulse-api/src/pulse/__init__.py`
- `pulse/pulse-api/src/pulse/main.py` — FastAPI app with lifespan, CORS, middleware stack
- `pulse/pulse-api/src/pulse/config.py` — Pydantic Settings class with all env vars from TSD §10
- `pulse/pulse-worker/pyproject.toml` and entry point
- `pulse/pulse-scheduler/pyproject.toml` and entry point
- `pulse/pulse-ui/package.json` with React 18, TypeScript, TanStack Query, shadcn/ui, Vite
- `pulse/README.md` with setup instructions

**Acceptance Criteria:**
- `uvicorn pulse.main:app` starts without errors on port 8000
- `GET /health/live` returns 200
- All environment variables from TSD §10.1 are defined in config.py with defaults
- Structured JSON logging outputs to stdout with request_id correlation
- All four project directories exist with valid pyproject.toml / package.json
- `npm run dev` starts the UI dev server on port 5173

**Dependencies:** None (root task)
**Execution Type:** AI-Agent
**Priority:** Critical
**Estimated Effort:** L (4-6 hours)
**Context Window:** Minimal (single file per artifact)
**Risk Level:** Low (deterministic scaffolding)
**File Mapping:**
- `pulse/pulse-api/pyproject.toml` (.toml)
- `pulse/pulse-api/src/pulse/__init__.py` (.py)
- `pulse/pulse-api/src/pulse/main.py` (.py)
- `pulse/pulse-api/src/pulse/config.py` (.py)
- `pulse/pulse-worker/pyproject.toml` (.toml)
- `pulse/pulse-worker/src/pulse_worker/__init__.py` (.py)
- `pulse/pulse-worker/src/pulse_worker/main.py` (.py)
- `pulse/pulse-scheduler/pyproject.toml` (.toml)
- `pulse/pulse-scheduler/src/pulse_scheduler/__init__.py` (.py)
- `pulse/pulse-scheduler/src/pulse_scheduler/main.py` (.py)
- `pulse/pulse-ui/package.json` (.json)
- `pulse/pulse-ui/vite.config.ts` (.ts)
- `pulse/pulse-ui/src/main.tsx` (.tsx)
- `pulse/pulse-ui/src/App.tsx` (.tsx)
- `pulse/README.md` (.md)

---

#### Task INFRA-002: Database Schema & ORM Models

**ID:** INFRA-002
**Title:** PostgreSQL Schema, SQLAlchemy ORM Models, and Alembic Migrations
**Description:** Implement all 12 database entities from TSD §4 as SQLAlchemy 2.0 ORM models with proper relationships, indexes, constraints, and partitioning hints. Create the initial Alembic migration that generates all tables, indexes, RLS policies, and partitioned tables. Implement the database session factory with async connection pooling via PgBouncer-compatible configuration.
**Inputs:** TSD Sections 4.1-4.14
**Output:**
- `pulse/pulse-api/src/pulse/models/workspace.py` — Workspace model
- `pulse/pulse-api/src/pulse/models/user.py` — User model with RBAC role enum
- `pulse/pulse-api/src/pulse/models/content.py` — ContentPiece + ContentVersion models
- `pulse/pulse-api/src/pulse/models/bulk_job.py` — BulkJob model
- `pulse/pulse-api/src/pulse/models/brand_voice.py` — BrandVoice model
- `pulse/pulse-api/src/pulse/models/market_profile.py` — MarketProfile model
- `pulse/pulse-api/src/pulse/models/glossary.py` — Glossary model
- `pulse/pulse-api/src/pulse/models/audit_log.py` — AuditLog model (partitioned by month)
- `pulse/pulse-api/src/pulse/models/api_key.py` — APIKey model
- `pulse/pulse-api/src/pulse/models/webhook_config.py` — WebhookConfig model
- `pulse/pulse-api/src/pulse/models/generation_cache.py` — GenerationCache model
- `pulse/pulse-api/src/pulse/db/session.py` — Async session factory with connection pooling
- `pulse/pulse-api/src/pulse/db/rls.py` — RLS policy setup functions
- `pulse/pulse-api/src/pulse/db/migrations/env.py` — Alembic environment config
- `pulse/pulse-api/src/pulse/db/migrations/versions/001_initial_schema.py` — Initial migration
- `pulse/pulse-api/src/alembic.ini` — Alembic configuration

**Acceptance Criteria:**
- `alembic upgrade head` creates all 12 tables in PostgreSQL 16+
- All indexes from TSD §4 are present (verified via `\di` in psql)
- RLS policies applied to all workspace-scoped tables
- `content_pieces` table is partitioned by HASH(workspace_id) into 16 partitions
- `audit_logs` table is partitioned by RANGE(created_at) monthly
- All foreign key constraints are valid
- Async session factory creates connections via asyncpg
- Model relationships match TSD §4.13 (1:N mappings verified)
- Reverse migration (`alembic downgrade base`) drops all tables cleanly

**Dependencies:** INFRA-001
**Execution Type:** AI-Agent
**Priority:** Critical
**Estimated Effort:** L (5-7 hours)
**Context Window:** Medium (module-level, cross-references between models)
**Risk Level:** Medium (schema design has long-term implications)
**File Mapping:**
- `pulse/pulse-api/src/pulse/models/*.py` (11 .py files)
- `pulse/pulse-api/src/pulse/db/session.py` (.py)
- `pulse/pulse-api/src/pulse/db/rls.py` (.py)
- `pulse/pulse-api/src/pulse/db/migrations/env.py` (.py)
- `pulse/pulse-api/src/pulse/db/migrations/versions/001_initial_schema.py` (.py)
- `pulse/pulse-api/src/alembic.ini` (.ini)

---

#### Task INFRA-003: Authentication & Authorization Middleware

**ID:** INFRA-003
**Title:** JWT Authentication, API Key Auth, and RBAC Middleware
**Description:** Implement the dual authentication system (JWT for UI users, API key for programmatic access) with RBAC enforcement. JWT validation extracts workspace_id, user_id, role, and scopes from token claims. API key authentication hashes the provided key and looks it up in the api_keys table. Rate limiting middleware enforces per-key RPM limits using Redis sliding window counters. All middleware propagates request_id and workspace context.
**Inputs:** TSD Sections 5.1, 11.1, 11.2
**Output:**
- `pulse/pulse-api/src/pulse/api/middleware/auth.py` — JWT + API key auth middleware
- `pulse/pulse-api/src/pulse/api/middleware/rate_limit.py` — Redis-based rate limiting
- `pulse/pulse-api/src/pulse/api/middleware/request_id.py` — X-Request-ID propagation
- `pulse/pulse-api/src/pulse/api/middleware/tenant.py` — Workspace context injection + RLS variable setting
- `pulse/pulse-api/src/pulse/core/auth/jwt_utils.py` — JWT encode/decode/verify functions
- `pulse/pulse-api/src/pulse/core/auth/api_key_utils.py` — API key hashing and verification
- `pulse/pulse-api/src/pulse/core/auth/rbac.py` — Role-based permission checker decorator

**Acceptance Criteria:**
- Valid JWT with correct claims passes authentication; expired JWT returns 401 AUTH_TOKEN_EXPIRED
- Valid API key (X-API-Key header) passes authentication; invalid key returns 401
- Rate limit exceeded returns 429 with X-RateLimit-* headers
- RBAC decorator blocks editor from approve action (returns 403 PERMISSION_INSUFFICIENT_ROLE)
- Tenant middleware sets PostgreSQL session variable `app.workspace_id` for RLS
- request_id middleware generates UUID if not present in headers; propagates through all logs
- Cross-workspace access blocked at DB level (RLS verified with test queries)

**Dependencies:** INFRA-001, INFRA-002
**Execution Type:** AI-Agent
**Priority:** Critical
**Estimated Effort:** L (5-6 hours)
**Context Window:** Medium (auth flow spans multiple files)
**Risk Level:** Medium (security-critical; must be correct)
**File Mapping:**
- `pulse/pulse-api/src/pulse/api/middleware/auth.py` (.py)
- `pulse/pulse-api/src/pulse/api/middleware/rate_limit.py` (.py)
- `pulse/pulse-api/src/pulse/api/middleware/request_id.py` (.py)
- `pulse/pulse-api/src/pulse/api/middleware/tenant.py` (.py)
- `pulse/pulse-api/src/pulse/core/auth/jwt_utils.py` (.py)
- `pulse/pulse-api/src/pulse/core/auth/api_key_utils.py` (.py)
- `pulse/pulse-api/src/pulse/core/auth/rbac.py` (.py)

---

#### Task INFRA-004: Redis Connection Layer & Caching Infrastructure

**ID:** INFRA-004
**Title:** Redis Client Setup, Cache Manager, and Stream Utilities
**Description:** Implement the Redis connection layer supporting both caching operations and Redis Streams for job queuing. Create a cache manager with TTL-based expiration, namespace isolation per workspace, and cache invalidation hooks. Implement Redis Streams utilities for consumer group creation, message acknowledgment, and dead-letter handling.
**Inputs:** TSD Sections 3.4, 7.2, 8.2
**Output:**
- `pulse/pulse-api/src/pulse/core/cache/redis_client.py` — Async Redis connection pool
- `pulse/pulse-api/src/pulse/core/cache/cache_manager.py` — Generic cache with TTL, namespace, invalidation
- `pulse/pulse-api/src/pulse/core/cache/streams.py` — Redis Streams producer/consumer utilities
- `pulse/pulse-api/src/pulse/core/cache/rate_limit.py` — Sliding window rate limit counter

**Acceptance Criteria:**
- Redis connection pool initializes with async redis-py 5.0+
- Cache manager supports get/set/delete with per-key TTL
- Cache namespaces isolate data by workspace_id prefix
- Redis Streams consumer group creation is idempotent
- Message acknowledgment works with visibility timeout
- Rate limit counter implements sliding window (not fixed window)
- Connection failure raises appropriate exception with retry hint
- All cache operations are async (non-blocking)

**Dependencies:** INFRA-001
**Execution Type:** AI-Agent
**Priority:** High
**Estimated Effort:** M (3-4 hours)
**Context Window:** Minimal (single module)
**Risk Level:** Low (well-understood patterns)
**File Mapping:**
- `pulse/pulse-api/src/pulse/core/cache/redis_client.py` (.py)
- `pulse/pulse-api/src/pulse/core/cache/cache_manager.py` (.py)
- `pulse/pulse-api/src/pulse/core/cache/streams.py` (.py)
- `pulse/pulse-api/src/pulse/core/cache/rate_limit.py` (.py)

---

#### Task INFRA-005: Error Handling Framework & Logging System

**ID:** INFRA-005
**Title:** Structured Error Handling, Exception Hierarchy, and Logging Configuration
**Description:** Create the exception hierarchy matching TSD §12.1 error categories. Implement global exception handlers that convert domain exceptions to proper HTTP responses with the standard error envelope. Configure structured JSON logging with PII redaction, request correlation, and sensitive data filtering.
**Inputs:** TSD Sections 5.2, 12.1, 12.2
**Output:**
- `pulse/pulse-api/src/pulse/core/exceptions.py` — Exception hierarchy (ValidationError, AuthError, PermissionError, NotFoundError, ConflictError, RateLimitError, DependencyError, InternalError)
- `pulse/pulse-api/src/pulse/core/error_handlers.py` — FastAPI exception handlers → standard error envelope
- `pulse/pulse-api/src/pulse/core/logging_config.py` — Structured JSON logging with PII redaction
- `pulse/pulse-api/src/pulse/core/middleware/error_handler.py` — Catch-all error handler middleware

**Acceptance Criteria:**
- Raising `NotFoundError(resource_type='content')` returns 404 with code `NOT_FOUND_CONTENT`
- Raising `ValidationError` with field details returns 400 with details array
- All error responses follow `{ "error": { "code": "...", "message": "...", "details": [...] } }` format
- API keys and tokens are NEVER present in logs at INFO level or above
- All log entries include timestamp, level, service, module, request_id, workspace_id
- Stack traces logged at ERROR level only
- Log output is valid JSON parseable by jq

**Dependencies:** INFRA-001
**Execution Type:** AI-Agent
**Priority:** High
**Estimated Effort:** M (2-3 hours)
**Context Window:** Minimal
**Risk Level:** Low
**File Mapping:**
- `pulse/pulse-api/src/pulse/core/exceptions.py` (.py)
- `pulse/pulse-api/src/pulse/core/error_handlers.py` (.py)
- `pulse/pulse-api/src/pulse/core/logging_config.py` (.py)
- `pulse/pulse-api/src/pulse/core/middleware/error_handler.py` (.py)

---

#### Task INFRA-006: Health Check Endpoints & Dependency Monitoring

**ID:** INFRA-006
**Title:** Health Check System (Liveness, Readiness, Detailed Diagnostics)
**Description:** Implement the three-tier health check system for Kubernetes/container orchestration. Liveness probe verifies process is running. Readiness probe checks all dependencies (PostgreSQL, Redis, Vault connectivity). Detailed endpoint provides per-dependency status for diagnostics.
**Inputs:** TSD Section 16.4
**Output:**
- `pulse/pulse-api/src/pulse/api/health.py` — Health check route handlers
- `pulse/pulse-api/src/pulse/core/health/dependency_checker.py` — Per-dependency connectivity checks

**Acceptance Criteria:**
- `GET /health/live` returns 200 when process is running (no dependency checks)
- `GET /health/ready` returns 200 only when PostgreSQL + Redis are reachable; 503 otherwise
- `GET /health/detailed` returns JSON with status of each dependency (postgres, redis, vault, s3)
- Readiness probe has 3-second timeout (doesn't hang on slow dependencies)
- Health endpoints are excluded from authentication middleware

**Dependencies:** INFRA-001, INFRA-002, INFRA-004
**Execution Type:** AI-Agent
**Priority:** High
**Estimated Effort:** S (1-2 hours)
**Context Window:** Minimal
**Risk Level:** Low
**File Mapping:**
- `pulse/pulse-api/src/pulse/api/health.py` (.py)
- `pulse/pulse-api/src/pulse/core/health/dependency_checker.py` (.py)

---

#### Task INFRA-007: Infrastructure Integration Tests

**ID:** INFRA-007
**Title:** Infrastructure Layer Integration Tests (DB, Redis, Auth, Health)
**Description:** Write comprehensive integration tests for all infrastructure components. Test database operations with real PostgreSQL (via Docker), Redis caching and streams, authentication flows (JWT + API key), RBAC enforcement, tenant isolation (RLS), and health checks.
**Inputs:** TSD Sections 4, 11, 14.2, 16.4
**Output:**
- `pulse/pulse-api/tests/conftest.py` — Shared fixtures (async DB session, Redis client, test app, factory functions)
- `pulse/pulse-api/tests/integration/test_database.py` — Schema, migrations, RLS tests
- `pulse/pulse-api/tests/integration/test_auth.py` — JWT + API key auth flow tests
- `pulse/pulse-api/tests/integration/test_rbac.py` — Role permission matrix tests
- `pulse/pulse-api/tests/integration/test_tenant_isolation.py` — Cross-workspace access blocked
- `pulse/pulse-api/tests/integration/test_health.py` — Health endpoint tests
- `pulse/pulse-api/tests/integration/test_rate_limiting.py` — Rate limit enforcement tests
- `pulse/pulse-api/tests/docker-compose.test.yml` — Test infrastructure (PostgreSQL, Redis, MinIO)

**Acceptance Criteria:**
- All tests pass with `pytest tests/integration/` against Docker Compose test stack
- RLS test: User from workspace A cannot read content from workspace B (query returns empty)
- Auth test: Expired JWT returns 401; valid JWT returns 200
- RBAC test: Viewer role cannot create content (403); Editor cannot approve (403)
- Rate limit test: 61st request within 1 minute returns 429
- Health test: /health/ready returns 503 when Redis is stopped
- Test coverage for infrastructure layer > 90%

**Dependencies:** INFRA-001 through INFRA-006
**Execution Type:** AI-Agent
**Priority:** High
**Estimated Effort:** L (4-5 hours)
**Context Window:** Medium (test fixtures reference multiple modules)
**Risk Level:** Low
**File Mapping:**
- `pulse/pulse-api/tests/conftest.py` (.py)
- `pulse/pulse-api/tests/integration/test_database.py` (.py)
- `pulse/pulse-api/tests/integration/test_auth.py` (.py)
- `pulse/pulse-api/tests/integration/test_rbac.py` (.py)
- `pulse/pulse-api/tests/integration/test_tenant_isolation.py` (.py)
- `pulse/pulse-api/tests/integration/test_health.py` (.py)
- `pulse/pulse-api/tests/integration/test_rate_limiting.py` (.py)
- `pulse/pulse-api/tests/docker-compose.test.yml` (.yml)

---

### EPIC-2: Core Generation Engine

---

#### Task GEN-001: LLM Abstraction Layer — Base Interface & Adapter Registry

**ID:** GEN-001
**Title:** LLM Abstraction Layer — Abstract Base, Registry, and Response Normalization
**Description:** Design and implement the LLM abstraction layer that provides a unified interface across all LLM providers. Create the abstract adapter interface defining the contract (generate, stream, get_capabilities). Implement the adapter registry for dynamic provider registration. Create the response normalizer that converts provider-specific responses into a standard format.
**Inputs:** TSD Sections 2.8, 9.1
**Output:**
- `pulse/pulse-api/src/pulse/core/llm/adapters/base.py` — AbstractLLMAdapter with generate(), stream(), get_capabilities() methods
- `pulse/pulse-api/src/pulse/core/llm/adapters/registry.py` — AdapterRegistry with register/get/list methods
- `pulse/pulse-api/src/pulse/core/llm/types.py` — LLMRequest, LLMResponse, LLMStreamChunk, TokenUsage, FinishReason dataclasses
- `pulse/pulse-api/src/pulse/core/llm/normalizer.py` — Response normalizer (provider-specific → standard format)

**Acceptance Criteria:**
- AbstractLLMAdapter cannot be instantiated directly (ABC enforcement)
- AdapterRegistry.register() accepts a provider name + adapter class
- AdapterRegistry.get("openai") returns the registered OpenAI adapter instance
- LLMResponse standard format includes: text, token_usage (prompt/completion/total), latency_ms, finish_reason, model_id, provider
- Response normalizer converts OpenAI response format to standard LLMResponse
- Response normalizer converts Anthropic response format to standard LLMResponse
- Streaming interface yields LLMStreamChunk objects with incremental text + usage data

**Dependencies:** INFRA-001
**Execution Type:** AI-Agent
**Priority:** Critical
**Estimated Effort:** M (3-4 hours)
**Context Window:** Medium (interface design affects all adapters)
**Risk Level:** Medium (core abstraction; design errors cascade)
**File Mapping:**
- `pulse/pulse-api/src/pulse/core/llm/adapters/base.py` (.py)
- `pulse/pulse-api/src/pulse/core/llm/adapters/registry.py` (.py)
- `pulse/pulse-api/src/pulse/core/llm/types.py` (.py)
- `pulse/pulse-api/src/pulse/core/llm/normalizer.py` (.py)

---

#### Task GEN-002: LLM Provider Adapters (OpenAI, Anthropic, Mistral, Ollama, vLLM, Azure, Bedrock)

**ID:** GEN-002
**Title:** Implement All Seven LLM Provider Adapters
**Description:** Implement concrete adapter classes for each supported LLM provider. Each adapter translates the standard LLMRequest into the provider's specific API format, makes the HTTP request (with streaming SSE support), and normalizes the response. Handle provider-specific authentication, error formats, rate limit headers, and model name mappings.
**Inputs:** TSD Sections 2.8, 9.1
**Output:**
- `pulse/pulse-api/src/pulse/core/llm/adapters/openai.py` — OpenAI adapter (chat completions API)
- `pulse/pulse-api/src/pulse/core/llm/adapters/anthropic.py` — Anthropic adapter (messages API)
- `pulse/pulse-api/src/pulse/core/llm/adapters/mistral.py` — Mistral adapter (OpenAI-compatible)
- `pulse/pulse-api/src/pulse/core/llm/adapters/ollama.py` — Ollama adapter (local inference)
- `pulse/pulse-api/src/pulse/core/llm/adapters/vllm.py` — vLLM adapter (local GPU inference)
- `pulse/pulse-api/src/pulse/core/llm/adapters/azure_openai.py` — Azure OpenAI adapter
- `pulse/pulse-api/src/pulse/core/llm/adapters/bedrock.py` — AWS Bedrock adapter (via boto3)

**Acceptance Criteria:**
- Each adapter implements generate() returning standard LLMResponse
- Each adapter implements stream() yielding LLMStreamChunk objects
- OpenAI adapter correctly formats messages array with system/user roles
- Anthropic adapter uses x-api-key header and system parameter
- Azure OpenAI adapter uses deployment-specific endpoint URL
- Bedrock adapter uses boto3 InvokeModel with correct model ID format
- Ollama adapter handles connection refused gracefully (local model not loaded)
- All adapters respect timeout configuration (MAX_GENERATION_TIMEOUT)
- All adapters handle HTTP 429 (rate limit) with retry-after parsing
- Streaming works end-to-end for at least OpenAI and Anthropic adapters

**Dependencies:** GEN-001
**Execution Type:** AI-Agent
**Priority:** Critical
**Estimated Effort:** L (6-8 hours)
**Context Window:** Medium (each adapter is independent but follows same interface)
**Risk Level:** Medium (external API formats may change; mock for testing)
**File Mapping:**
- `pulse/pulse-api/src/pulse/core/llm/adapters/openai.py` (.py)
- `pulse/pulse-api/src/pulse/core/llm/adapters/anthropic.py` (.py)
- `pulse/pulse-api/src/pulse/core/llm/adapters/mistral.py` (.py)
- `pulse/pulse-api/src/pulse/core/llm/adapters/ollama.py` (.py)
- `pulse/pulse-api/src/pulse/core/llm/adapters/vllm.py` (.py)
- `pulse/pulse-api/src/pulse/core/llm/adapters/azure_openai.py` (.py)
- `pulse/pulse-api/src/pulse/core/llm/adapters/bedrock.py` (.py)

---

#### Task GEN-003: Fallback Router & Circuit Breaker

**ID:** GEN-003
**Title:** Fallback Router with Circuit Breaker and Health Monitoring
**Description:** Implement the fallback router that manages model selection and automatic failover. Includes per-provider circuit breaker (opens after 3 failures in 60s), health monitoring (latency/error rate tracking), weighted round-robin load balancing across healthy providers, and configurable fallback chains per workspace.
**Inputs:** TSD Sections 2.10, 9.1
**Output:**
- `pulse/pulse-api/src/pulse/core/llm/router.py` — FallbackRouter with select_provider(), record_success(), record_failure()
- `pulse/pulse-api/src/pulse/core/llm/circuit_breaker.py` — CircuitBreaker per provider (closed/open/half-open states)
- `pulse/pulse-api/src/pulse/core/llm/health_monitor.py` — Latency/error rate tracker with sliding window

**Acceptance Criteria:**
- Router selects primary provider from workspace configuration
- On primary failure (exception or 5xx), router automatically tries next provider in chain
- Circuit breaker opens after 3 failures within 60 seconds; routes around that provider
- Circuit breaker transitions to half-open after cooldown; allows one test request
- Health monitor tracks p50/p95 latency and error rate per provider
- Weighted round-robin distributes load across healthy providers based on configured weights
- If ALL providers fail, raises DependencyError with retry-after suggestion
- Router configuration is per-workspace (stored in workspace config JSONB)

**Dependencies:** GEN-001, GEN-002
**Execution Type:** AI-Agent
**Priority:** Critical
**Estimated Effort:** M (3-4 hours)
**Context Window:** Medium (router coordinates multiple adapters)
**Risk Level:** Medium (failure handling is complex; needs thorough testing)
**File Mapping:**
- `pulse/pulse-api/src/pulse/core/llm/router.py` (.py)
- `pulse/pulse-api/src/pulse/core/llm/circuit_breaker.py` (.py)
- `pulse/pulse-api/src/pulse/core/llm/health_monitor.py` (.py)

---

#### Task GEN-004: Cultural Adaptation Engine

**ID:** GEN-004
**Title:** Cultural Adaptation Engine — Market Profiles, Dimension Calculator, Directive Generator
**Description:** Implement the cultural adaptation engine that transforms generation parameters based on target market cultural characteristics. Load and cache market profiles encoding cultural dimensions (formality, directness, individualism, humor, persuasion style). Compute transformation weights and generate LLM-ready cultural directives. Include 50+ pre-built market profiles as seed data.
**Inputs:** TSD Sections 2.3, 6.4
**Output:**
- `pulse/pulse-api/src/pulse/core/cultural/engine.py` — CulturalAdaptationEngine with adapt() method
- `pulse/pulse-api/src/pulse/core/cultural/profiles.py` — MarketProfileLoader with cache integration
- `pulse/pulse-api/src/pulse/core/cultural/dimensions.py` — DimensionCalculator (maps dimensions → LLM instructions)
- `pulse/pulse-api/src/pulse/core/cultural/directives.py` — DirectiveGenerator (produces structured cultural context block)
- `pulse/pulse-api/src/pulse/core/cultural/seed_profiles.py` — 50+ market profile definitions (JSON data)
- `pulse/pulse-api/src/pulse/db/migrations/versions/002_seed_market_profiles.py` — Migration to seed profiles

**Acceptance Criteria:**
- adapt("ja-JP", source_content, brand_voice) returns cultural directive object with:
  - formality_weight: 5 (keigo/honorific speech directive)
  - directness_weight: 2 (indirect/hedging directive)
  - persuasion_style: "relationship"
  - taboos_to_avoid: [list of Japanese cultural sensitivities]
- adapt("de-DE", ...) returns different directives (direct, evidence-based, formal but not honorific)
- Market profiles cached in Redis with 1-hour TTL
- System default profiles loadable without workspace context
- Workspace-specific profile overrides system default for same market_code
- 50+ market profiles seeded covering: all G20 languages, major Asian/European/Middle Eastern markets
- Dimension calculator maps numeric dimensions (1-5) to natural language LLM instructions
- Directive generator resolves conflicts between brand voice and cultural norms (cultural taboo wins)

**Dependencies:** INFRA-002, INFRA-004
**Execution Type:** Either
**Priority:** Critical
**Estimated Effort:** L (6-8 hours)
**Context Window:** Large (cross-service: cultural logic + market data + cache)
**Risk Level:** High (core IP; cultural accuracy is subjective and critical)
**File Mapping:**
- `pulse/pulse-api/src/pulse/core/cultural/engine.py` (.py)
- `pulse/pulse-api/src/pulse/core/cultural/profiles.py` (.py)
- `pulse/pulse-api/src/pulse/core/cultural/dimensions.py` (.py)
- `pulse/pulse-api/src/pulse/core/cultural/directives.py` (.py)
- `pulse/pulse-api/src/pulse/core/cultural/seed_profiles.py` (.py)
- `pulse/pulse-api/src/pulse/db/migrations/versions/002_seed_market_profiles.py` (.py)

---

#### Task GEN-005: Prompt Composer

**ID:** GEN-005
**Title:** Prompt Composer — Template Engine, Assembler, Token Budget Manager
**Description:** Implement the prompt composer — the core IP of Pulse. Combines brand voice profile, cultural adaptation directives, terminology glossary, Vault-retrieved knowledge, content type templates, tone controls, and user instructions into a final prompt payload. Includes template engine with variable substitution, token budget management (ensures prompt fits model context window), and prompt versioning for A/B testing.
**Inputs:** TSD Sections 2.9, 6.1 (Step 3)
**Output:**
- `pulse/pulse-api/src/pulse/core/generation/prompt_composer.py` — PromptComposer with compose() method
- `pulse/pulse-api/src/pulse/core/generation/templates/` — Content type prompt templates (blog_post, social_post, email_campaign, product_description, ad_copy, landing_page, press_release, newsletter, video_script, podcast_outline)
- `pulse/pulse-api/src/pulse/core/generation/token_budget.py` — TokenBudgetManager (tiktoken-based counting, truncation strategy)
- `pulse/pulse-api/src/pulse/core/generation/template_engine.py` — Variable substitution + conditional sections

**Acceptance Criteria:**
- compose() accepts all context inputs and returns final prompt payload (system_prompt + user_prompt + parameters)
- System prompt includes: role definition, cultural directives, brand voice rules
- User prompt includes: source content/brief, knowledge context, output constraints
- Terminology section includes required terms and prohibited terms from glossary
- Token budget manager uses tiktoken to count tokens; truncates knowledge context first if over budget
- Token budget preserves brand voice + cultural directives (never truncated)
- Template engine supports {{variable}} substitution and {% if condition %} blocks
- 10 content type templates exist, each with appropriate structure requirements
- Prompt hash (SHA-256) is deterministic for same inputs (enables caching)
- A/B testing: prompt version parameter selects between template variants

**Dependencies:** GEN-001, GEN-004
**Execution Type:** AI-Agent
**Priority:** Critical
**Estimated Effort:** L (5-7 hours)
**Context Window:** Large (combines outputs from cultural engine + Vault + templates)
**Risk Level:** High (core IP; prompt quality directly affects output quality)
**File Mapping:**
- `pulse/pulse-api/src/pulse/core/generation/prompt_composer.py` (.py)
- `pulse/pulse-api/src/pulse/core/generation/templates/*.py` (10 template files)
- `pulse/pulse-api/src/pulse/core/generation/token_budget.py` (.py)
- `pulse/pulse-api/src/pulse/core/generation/template_engine.py` (.py)

---

#### Task GEN-006: Quality Scoring Engine

**ID:** GEN-006
**Title:** Quality Scoring Engine — Terminology Compliance, Vault Grounding, Format Checks
**Description:** Implement post-generation quality evaluation. Score generated content on four dimensions: terminology compliance (0-30), Vault grounding verification (0-30), length/format conformance (0-20), and cultural coherence heuristic (0-20). Generate flags for content needing human review based on score thresholds and specific violations.
**Inputs:** TSD Sections 2.4, 6.5
**Output:**
- `pulse/pulse-api/src/pulse/core/quality/scorer.py` — QualityScorer with score() method returning (score: int, flags: list)
- `pulse/pulse-api/src/pulse/core/quality/terminology.py` — TerminologyChecker (required terms present, prohibited absent)
- `pulse/pulse-api/src/pulse/core/quality/grounding.py` — VaultGroundingVerifier (claims vs. source material)
- `pulse/pulse-api/src/pulse/core/quality/format_checker.py` — Length/format conformance checker
- `pulse/pulse-api/src/pulse/core/quality/cultural_coherence.py` — Cultural coherence heuristic scorer

**Acceptance Criteria:**
- score() returns tuple (confidence_score: 0-100, flags: [{type, severity, message}])
- Terminology compliance: all required terms present → +5 each (max 15); no prohibited terms → +15; each violation → -5
- Vault grounding: extract claims from text, verify against vault_sources; grounded +5 each (max 25); ungrounded -10 each; base 10 for having context
- Length conformance: within range → +20; ±20% → +10; >±50% → +0
- Cultural coherence: formality matches → +10; no taboo violations → +10; structural preference → +5
- Score < 60 → flag "high_priority_review"
- Score 60-75 → flag "medium_priority_review"
- Any terminology violation → flag "terminology_violation" regardless of score
- Any ungrounded claim → flag "potential_hallucination"
- Scoring completes in < 200ms (no LLM calls in basic scoring)

**Dependencies:** GEN-004, GEN-005
**Execution Type:** AI-Agent
**Priority:** Critical
**Estimated Effort:** L (5-6 hours)
**Context Window:** Medium (scoring logic is self-contained but references cultural dimensions)
**Risk Level:** High (scoring accuracy affects user trust; hallucination detection is hard)
**File Mapping:**
- `pulse/pulse-api/src/pulse/core/quality/scorer.py` (.py)
- `pulse/pulse-api/src/pulse/core/quality/terminology.py` (.py)
- `pulse/pulse-api/src/pulse/core/quality/grounding.py` (.py)
- `pulse/pulse-api/src/pulse/core/quality/format_checker.py` (.py)
- `pulse/pulse-api/src/pulse/core/quality/cultural_coherence.py` (.py)

---

#### Task GEN-007: Generation Orchestrator — End-to-End Pipeline

**ID:** GEN-007
**Title:** Generation Orchestrator — Full Pipeline Coordination
**Description:** Implement the generation orchestrator that coordinates the complete generation pipeline: request validation → context retrieval (Vault) → cultural adaptation → prompt composition → cache check → LLM dispatch → post-processing (quality scoring) → persistence → response. Handles parallel context retrieval, timeout management, and all edge cases defined in TSD §6.1.
**Inputs:** TSD Sections 2.2, 6.1, 7.3
**Output:**
- `pulse/pulse-api/src/pulse/core/generation/orchestrator.py` — GenerationOrchestrator with execute() method
- `pulse/pulse-api/src/pulse/core/generation/cache.py` — Generation cache (Redis + PostgreSQL dual-layer)
- `pulse/pulse-api/src/pulse/core/generation/context_aggregator.py` — Parallel Vault context retrieval
- `pulse/pulse-api/src/pulse/core/generation/post_processor.py` — Post-processing pipeline

**Acceptance Criteria:**
- execute() runs full pipeline: validate → retrieve context → adapt → compose → cache check → generate → score → persist → respond
- Context retrieval runs in parallel (Vault brand voice + glossary + semantic search + market profiles)
- Vault retrieval has 500ms timeout; proceeds with cache on timeout
- Cache check: SHA-256(prompt + model + params) → Redis lookup; hit returns cached result immediately
- Cache miss: dispatches to LLM via Fallback Router; stores result in cache (24h TTL)
- Multi-market generation: iterates target_markets, generates one piece per market
- On all LLM providers unavailable: returns 503 DEPENDENCY_LLM_UNAVAILABLE
- On empty source_text AND empty brief: returns 400 VALIDATION_NO_INPUT
- On unsupported market: returns 400 VALIDATION_INVALID_MARKET with supported markets list
- Domain event `content.generated` emitted after successful persistence
- Latency within budget: total < 30s for single generation (TSD §13.3)

**Dependencies:** GEN-001 through GEN-006
**Execution Type:** AI-Agent
**Priority:** Critical
**Estimated Effort:** L (6-8 hours)
**Context Window:** Large (orchestrator coordinates all core components)
**Risk Level:** High (integration point; bugs here affect everything)
**File Mapping:**
- `pulse/pulse-api/src/pulse/core/generation/orchestrator.py` (.py)
- `pulse/pulse-api/src/pulse/core/generation/cache.py` (.py)
- `pulse/pulse-api/src/pulse/core/generation/context_aggregator.py` (.py)
- `pulse/pulse-api/src/pulse/core/generation/post_processor.py` (.py)

---

### EPIC-3: Content & Workflow Management

---

#### Task CONTENT-001: Content Management Service & State Machine

**ID:** CONTENT-001
**Title:** Content Service — CRUD Operations, Version Control, Lifecycle State Machine
**Description:** Implement the content management service handling all content CRUD operations, immutable version snapshots, and the content lifecycle state machine (draft → review → approved/rejected → archived). Enforce role-based transition rules and emit domain events on state changes.
**Inputs:** TSD Sections 2.1, 6.3
**Output:**
- `pulse/pulse-api/src/pulse/services/content_service.py` — ContentService with create/get/update/list/archive methods
- `pulse/pulse-api/src/pulse/core/content/state_machine.py` — ContentStateMachine with transition validation
- `pulse/pulse-api/src/pulse/core/content/version_controller.py` — Immutable version snapshot creator
- `pulse/pulse-api/src/pulse/core/events.py` — Domain event emitter (content.generated, content.approved, etc.)

**Acceptance Criteria:**
- create() persists content_piece with status='draft' and creates initial content_version
- update() creates new content_version snapshot before applying changes
- State transitions enforced: draft→review (editor), review→approved (approver), review→rejected (approver)
- Invalid transitions raise ConflictError (409 CONFLICT_INVALID_STATE_TRANSITION)
- Rejected content returns to draft with feedback attached in metadata
- Archived content is read-only (update raises 409)
- All transitions logged to audit_logs with user_id and details
- Domain events emitted: content.created, content.updated, content.status_changed, content.archived
- List supports cursor-based pagination with filters (status, content_type, target_market)

**Dependencies:** INFRA-002, INFRA-003
**Execution Type:** AI-Agent
**Priority:** High
**Estimated Effort:** L (5-6 hours)
**Context Window:** Medium (state machine + service + events)
**Risk Level:** Medium (state transitions must be airtight)
**File Mapping:**
- `pulse/pulse-api/src/pulse/services/content_service.py` (.py)
- `pulse/pulse-api/src/pulse/core/content/state_machine.py` (.py)
- `pulse/pulse-api/src/pulse/core/content/version_controller.py` (.py)
- `pulse/pulse-api/src/pulse/core/events.py` (.py)

---

#### Task CONTENT-002: Content Export Engine

**ID:** CONTENT-002
**Title:** Content Export Engine — Multi-Format Rendering (Markdown, HTML, JSON, DOCX, PDF)
**Description:** Implement the export engine that renders content pieces into multiple output formats. Support Markdown, HTML, JSON, DOCX (via python-docx), and PDF (via WeasyPrint). Exports include metadata headers, brand voice attribution, and Vault source references.
**Inputs:** TSD Sections 2.1, 5.11
**Output:**
- `pulse/pulse-api/src/pulse/core/content/export_engine.py` — ExportEngine with render(content, format) method
- `pulse/pulse-api/src/pulse/core/content/renderers/markdown.py` — Markdown renderer
- `pulse/pulse-api/src/pulse/core/content/renderers/html.py` — HTML renderer
- `pulse/pulse-api/src/pulse/core/content/renderers/json_renderer.py` — JSON renderer
- `pulse/pulse-api/src/pulse/core/content/renderers/docx.py` — DOCX renderer (python-docx)
- `pulse/pulse-api/src/pulse/core/content/renderers/pdf.py` — PDF renderer (WeasyPrint from HTML)

**Acceptance Criteria:**
- render(content, "markdown") returns valid Markdown with title header and body
- render(content, "html") returns styled HTML with metadata section
- render(content, "json") returns JSON with all content fields + metadata
- render(content, "docx") returns valid .docx binary with title, body, and metadata page
- render(content, "pdf") returns valid PDF binary (rendered from HTML via WeasyPrint)
- Unsupported format raises ValidationError
- Export includes: title, generated_text, target_market, brand_voice_name, confidence_score, vault_sources
- DOCX and PDF exports complete in < 5 seconds for typical content (< 5000 words)

**Dependencies:** CONTENT-001
**Execution Type:** AI-Agent
**Priority:** Medium
**Estimated Effort:** M (3-4 hours)
**Context Window:** Minimal (each renderer is independent)
**Risk Level:** Low
**File Mapping:**
- `pulse/pulse-api/src/pulse/core/content/export_engine.py` (.py)
- `pulse/pulse-api/src/pulse/core/content/renderers/markdown.py` (.py)
- `pulse/pulse-api/src/pulse/core/content/renderers/html.py` (.py)
- `pulse/pulse-api/src/pulse/core/content/renderers/json_renderer.py` (.py)
- `pulse/pulse-api/src/pulse/core/content/renderers/docx.py` (.py)
- `pulse/pulse-api/src/pulse/core/content/renderers/pdf.py` (.py)

---

#### Task CONTENT-003: Bulk Job Manager — Input Parsing, Task Dispatch, Progress Tracking

**ID:** CONTENT-003
**Title:** Bulk Job Manager — CSV/XLSX Parsing, Redis Streams Dispatch, Progress Tracking
**Description:** Implement the bulk job manager that handles large-scale content generation. Parse uploaded CSV/XLSX files, decompose into individual generation tasks, push to Redis Streams, track progress with atomic counters, support pause/resume/cancel, and handle checkpointing every 10 items.
**Inputs:** TSD Sections 2.5, 5.4, 5.5, 5.6, 6.2
**Output:**
- `pulse/pulse-api/src/pulse/services/job_service.py` — JobService with create/get/pause/resume/cancel methods
- `pulse/pulse-api/src/pulse/core/jobs/input_parser.py` — CSV/XLSX parser with validation (max 100K rows)
- `pulse/pulse-api/src/pulse/core/jobs/task_dispatcher.py` — Pushes tasks to Redis Streams per-job queue
- `pulse/pulse-api/src/pulse/core/jobs/progress_tracker.py` — Atomic counter updates, checkpointing
- `pulse/pulse-worker/src/pulse_worker/consumer.py` — Redis Streams consumer group worker
- `pulse/pulse-worker/src/pulse_worker/tasks/generation_task.py` — Single generation task handler

**Acceptance Criteria:**
- CSV/XLSX parsing validates required columns; returns 400 on invalid structure
- Row count > 100,000 returns 400 with error message
- total_items = rows × len(target_markets) calculated correctly
- Tasks pushed to Redis Stream `pulse:jobs:{job_id}` with idempotency key (job_id, row_index, market)
- Worker consumes tasks, runs generation pipeline, writes to content_pieces
- Progress tracked atomically: completed_items and failed_items updated per item
- Checkpoint to PostgreSQL every 10 items (not every item — reduces DB load)
- Pause: sets job status to "paused"; workers stop consuming this job's tasks
- Resume: sets status to "processing"; workers resume
- Cancel: discards remaining tasks from queue; preserves partial results
- Worker crash: consumer group redelivers unacknowledged tasks to surviving workers
- Job completion: when completed + failed == total, status → "completed", summary generated

**Dependencies:** GEN-007, INFRA-004
**Execution Type:** AI-Agent
**Priority:** High
**Estimated Effort:** L (6-8 hours)
**Context Window:** Large (spans API + worker + Redis + PostgreSQL)
**Risk Level:** High (distributed system; failure modes are complex)
**File Mapping:**
- `pulse/pulse-api/src/pulse/services/job_service.py` (.py)
- `pulse/pulse-api/src/pulse/core/jobs/input_parser.py` (.py)
- `pulse/pulse-api/src/pulse/core/jobs/task_dispatcher.py` (.py)
- `pulse/pulse-api/src/pulse/core/jobs/progress_tracker.py` (.py)
- `pulse/pulse-worker/src/pulse_worker/consumer.py` (.py)
- `pulse/pulse-worker/src/pulse_worker/tasks/generation_task.py` (.py)

---

#### Task CONTENT-004: Review & Workflow Module

**ID:** CONTENT-004
**Title:** Review & Workflow Module — Approval Chains, Feedback, Side-by-Side Comparison
**Description:** Implement the review workflow system supporting configurable multi-step approval chains, inline feedback collection, and side-by-side source vs. localized comparison. Track approval history and support feedback attachment to content pieces.
**Inputs:** TSD Section 2.6
**Output:**
- `pulse/pulse-api/src/pulse/services/review_service.py` — ReviewService with submit_for_review/approve/reject/add_feedback
- `pulse/pulse-api/src/pulse/core/workflow/approval_chain.py` — Configurable multi-step approval chain manager
- `pulse/pulse-api/src/pulse/core/workflow/feedback.py` — Feedback collector with content reference support
- `pulse/pulse-api/src/pulse/core/workflow/comparison.py` — Source vs. localized diff generator

**Acceptance Criteria:**
- submit_for_review() transitions content from draft to review; emits content.submitted_for_review event
- approve() transitions from review to approved (only approver/admin role); emits content.approved
- reject() transitions from review to draft with feedback; emits content.rejected
- Approval chain supports configurable steps (e.g., editor → senior editor → legal)
- Feedback includes: user_id, comment, content_reference (specific text span), created_at
- Comparison generator produces structured diff between source_text and generated_text
- All review actions logged to audit_logs

**Dependencies:** CONTENT-001, INFRA-003
**Execution Type:** AI-Agent
**Priority:** Medium
**Estimated Effort:** M (3-4 hours)
**Context Window:** Medium
**Risk Level:** Medium
**File Mapping:**
- `pulse/pulse-api/src/pulse/services/review_service.py` (.py)
- `pulse/pulse-api/src/pulse/core/workflow/approval_chain.py` (.py)
- `pulse/pulse-api/src/pulse/core/workflow/feedback.py` (.py)
- `pulse/pulse-api/src/pulse/core/workflow/comparison.py` (.py)

---

#### Task CONTENT-005: Brand Voice & Glossary Management Services

**ID:** CONTENT-005
**Title:** Brand Voice and Terminology Glossary CRUD Services
**Description:** Implement services for managing brand voice profiles and terminology glossaries. Brand voices define tone, personality, vocabulary preferences, and include sample content for calibration. Glossaries define required/prohibited terms with per-language translations. Both are workspace-scoped and cached in Redis.
**Inputs:** TSD Sections 4.6, 4.8, 5.12, 5.13
**Output:**
- `pulse/pulse-api/src/pulse/services/brand_voice_service.py` — BrandVoiceService with CRUD + activation
- `pulse/pulse-api/src/pulse/services/glossary_service.py` — GlossaryService with CRUD + entry management
- `pulse/pulse-api/src/pulse/core/cache/brand_voice_cache.py` — Brand voice Redis cache (5min TTL)
- `pulse/pulse-api/src/pulse/core/cache/glossary_cache.py` — Glossary Redis cache (5min TTL)

**Acceptance Criteria:**
- Brand voice CRUD: create, get, list (workspace-scoped), update, deactivate
- Brand voice includes tone_attributes (JSONB), guidelines_text, sample_content array
- Glossary CRUD: create, get, list, update, add/remove entries
- Glossary entries include: source_term, translations (per-language), context, is_prohibited flag
- Both cached in Redis with 5-minute TTL; invalidated on update
- Workspace default brand voice configurable (one per workspace)
- List endpoints support cursor-based pagination

**Dependencies:** INFRA-002, INFRA-004
**Execution Type:** AI-Agent
**Priority:** High
**Estimated Effort:** M (3-4 hours)
**Context Window:** Minimal
**Risk Level:** Low
**File Mapping:**
- `pulse/pulse-api/src/pulse/services/brand_voice_service.py` (.py)
- `pulse/pulse-api/src/pulse/services/glossary_service.py` (.py)
- `pulse/pulse-api/src/pulse/core/cache/brand_voice_cache.py` (.py)
- `pulse/pulse-api/src/pulse/core/cache/glossary_cache.py` (.py)

---

#### Task CONTENT-006: API Endpoints — Content, Jobs, Brand Voices, Market Profiles, Analytics

**ID:** CONTENT-006
**Title:** Complete REST API Layer — All Endpoints per TSD §5
**Description:** Implement all REST API endpoints defined in TSD §5 as FastAPI routers. Each endpoint validates input via Pydantic schemas, delegates to the appropriate service, and returns responses in the standard envelope format. Includes cursor-based pagination, proper HTTP status codes, and rate limit headers.
**Inputs:** TSD Sections 5.3-5.16
**Output:**
- `pulse/pulse-api/src/pulse/api/router.py` — Top-level router aggregating all v1 sub-routers
- `pulse/pulse-api/src/pulse/api/v1/generate.py` — POST /generate, POST /generate/bulk
- `pulse/pulse-api/src/pulse/api/v1/content.py` — GET/PUT /content, POST /content/{id}/approve, POST /content/{id}/export
- `pulse/pulse-api/src/pulse/api/v1/jobs.py` — GET /jobs/{id}, POST /jobs/{id}/pause, POST /jobs/{id}/resume, POST /jobs/{id}/cancel
- `pulse/pulse-api/src/pulse/api/v1/brand_voices.py` — CRUD /brand-voices
- `pulse/pulse-api/src/pulse/api/v1/market_profiles.py` — GET /market-profiles
- `pulse/pulse-api/src/pulse/api/v1/analytics.py` — GET /analytics/usage
- `pulse/pulse-api/src/pulse/api/v1/webhooks.py` — CRUD /webhooks
- `pulse/pulse-api/src/pulse/api/schemas/generate.py` — Generation request/response Pydantic models
- `pulse/pulse-api/src/pulse/api/schemas/content.py` — Content CRUD schemas
- `pulse/pulse-api/src/pulse/api/schemas/jobs.py` — Job schemas
- `pulse/pulse-api/src/pulse/api/schemas/common.py` — Error schemas, pagination, common types
- `pulse/pulse-api/src/pulse/api/ws/progress.py` — WebSocket /ws/jobs/{id}/progress

**Acceptance Criteria:**
- POST /api/v1/generate returns 200 with generated content for valid request
- POST /api/v1/generate returns 400 for invalid market code
- POST /api/v1/generate/bulk returns 202 with job_id for valid file upload
- GET /api/v1/jobs/{id} returns progress with completed_items, failed_items, progress_percent
- POST /api/v1/jobs/{id}/pause returns 200 with paused status
- GET /api/v1/content returns paginated list with cursor and has_more
- PUT /api/v1/content/{id} creates new version and returns updated content
- POST /api/v1/content/{id}/approve returns 200 with approved status (approver role only)
- POST /api/v1/content/{id}/export returns binary file with Content-Disposition header
- WebSocket /ws/jobs/{id}/progress pushes progress updates in real-time
- All responses follow `{ "data": ... }` envelope
- All errors follow `{ "error": { "code": "...", "message": "...", "details": [...] } }` envelope
- Rate limit headers present on all responses

**Dependencies:** GEN-007, CONTENT-001, CONTENT-003, CONTENT-005
**Execution Type:** AI-Agent
**Priority:** Critical
**Estimated Effort:** L (6-8 hours)
**Context Window:** Large (all endpoints + schemas)
**Risk Level:** Medium (many endpoints but each is straightforward)
**File Mapping:**
- `pulse/pulse-api/src/pulse/api/router.py` (.py)
- `pulse/pulse-api/src/pulse/api/v1/generate.py` (.py)
- `pulse/pulse-api/src/pulse/api/v1/content.py` (.py)
- `pulse/pulse-api/src/pulse/api/v1/jobs.py` (.py)
- `pulse/pulse-api/src/pulse/api/v1/brand_voices.py` (.py)
- `pulse/pulse-api/src/pulse/api/v1/market_profiles.py` (.py)
- `pulse/pulse-api/src/pulse/api/v1/analytics.py` (.py)
- `pulse/pulse-api/src/pulse/api/v1/webhooks.py` (.py)
- `pulse/pulse-api/src/pulse/api/schemas/generate.py` (.py)
- `pulse/pulse-api/src/pulse/api/schemas/content.py` (.py)
- `pulse/pulse-api/src/pulse/api/schemas/jobs.py` (.py)
- `pulse/pulse-api/src/pulse/api/schemas/common.py` (.py)
- `pulse/pulse-api/src/pulse/api/ws/progress.py` (.py)

---

### EPIC-4: Integrations & External Services

---

#### Task INT-001: Vault Connector — REST Client, Semantic Search, Cache Manager

**ID:** INT-001
**Title:** Vault Connector — Knowledge Retrieval, Semantic Search, Writeback
**Description:** Implement the Vault connector module that interfaces with ODW.ai Vault for knowledge grounding. Includes REST API client for brand voice and glossary retrieval, semantic search client for relevant product knowledge, local Redis cache manager with TTL, and writeback handler for pushing approved content back to Vault.
**Inputs:** TSD Sections 2.11, 9.2
**Output:**
- `pulse/pulse-api/src/pulse/integrations/vault/client.py` — Vault REST API client (httpx-based)
- `pulse/pulse-api/src/pulse/integrations/vault/search.py` — Semantic search client (embedding endpoint)
- `pulse/pulse-api/src/pulse/integrations/vault/cache.py` — Vault data cache manager (Redis-backed, TTL)
- `pulse/pulse-api/src/pulse/integrations/vault/writeback.py` — Approved content writeback handler

**Acceptance Criteria:**
- Vault client retrieves brand voice profile by ID (GET /api/v1/brand-voices/{id})
- Vault client retrieves glossary by ID (GET /api/v1/glossaries/{id})
- Semantic search returns relevant knowledge chunks for a query (GET /api/v1/knowledge/search)
- Search results include relevance scores and source document references
- Cache manager stores Vault responses in Redis with configurable TTL (5min default)
- Cache invalidation on Vault update event (webhook from Vault)
- Writeback handler posts approved content to Vault (POST /api/v1/content)
- Vault unavailable: client falls back to cached data; flags output as "degraded"
- mTLS authentication supported (certificate paths from config)
- All Vault calls logged with latency metrics

**Dependencies:** INFRA-001, INFRA-004
**Execution Type:** AI-Agent
**Priority:** Critical
**Estimated Effort:** L (5-6 hours)
**Context Window:** Medium
**Risk Level:** High (external dependency; integration must be robust)
**File Mapping:**
- `pulse/pulse-api/src/pulse/integrations/vault/client.py` (.py)
- `pulse/pulse-api/src/pulse/integrations/vault/search.py` (.py)
- `pulse/pulse-api/src/pulse/integrations/vault/cache.py` (.py)
- `pulse/pulse-api/src/pulse/integrations/vault/writeback.py` (.py)

---

#### Task INT-002: Object Storage (S3/MinIO) Integration

**ID:** INT-002
**Title:** S3/MinIO Object Storage Client — Upload, Download, Presigned URLs
**Description:** Implement the object storage integration for file operations. Support upload (bulk job input files, exports), download (retrieving stored files), presigned URL generation (temporary access), and bucket management. Works with both AWS S3 and MinIO (air-gapped deployments).
**Inputs:** TSD Sections 3.4, 9.3
**Output:**
- `pulse/pulse-api/src/pulse/integrations/storage/s3.py` — S3Client wrapper (boto3-based)
- `pulse/pulse-api/src/pulse/integrations/storage/config.py` — Storage configuration (endpoint, credentials, bucket)

**Acceptance Criteria:**
- upload(key, data) stores file in configured bucket; returns storage key
- download(key) retrieves file content as bytes
- generate_presigned_url(key, expiry_seconds) returns temporary access URL
- Works with AWS S3 (standard endpoint) and MinIO (custom endpoint)
- Upload handles files up to 50MB (bulk input file limit)
- Connection failure raises DependencyError with clear message
- Bucket auto-creation in development mode (configurable)

**Dependencies:** INFRA-001
**Execution Type:** AI-Agent
**Priority:** High
**Estimated Effort:** M (2-3 hours)
**Context Window:** Minimal
**Risk Level:** Low
**File Mapping:**
- `pulse/pulse-api/src/pulse/integrations/storage/s3.py` (.py)
- `pulse/pulse-api/src/pulse/integrations/storage/config.py` (.py)

---

#### Task INT-003: Webhook Dispatcher — Event Delivery with Retry

**ID:** INT-003
**Title:** Webhook Dispatcher — Event Processing, HTTP Delivery, Retry with Backoff
**Description:** Implement the webhook dispatcher that delivers event notifications to configured webhook URLs. Consumes events from Redis Streams, signs payloads with HMAC, delivers via HTTP POST with exponential backoff retry (5 attempts: 1min, 5min, 30min, 2hr, 12hr), and handles dead-letter for permanently failed deliveries.
**Inputs:** TSD Sections 2.12, 8.1
**Output:**
- `pulse/pulse-scheduler/src/pulse_scheduler/webhook_dispatcher.py` — WebhookDispatcher main loop
- `pulse/pulse-api/src/pulse/integrations/webhooks/dispatcher.py` — Delivery executor (HTTP POST + retry)
- `pulse/pulse-api/src/pulse/integrations/webhooks/signing.py` — HMAC payload signing
- `pulse/pulse-api/src/pulse/integrations/webhooks/dead_letter.py` — Dead-letter handler

**Acceptance Criteria:**
- Dispatcher consumes from `pulse:webhooks` Redis Stream
- Each delivery: HTTP POST with JSON body + X-Webhook-Signature header (HMAC-SHA256)
- Retry schedule: 1min, 5min, 30min, 2hr, 12hr (5 attempts total)
- After max retries: moved to dead-letter table (webhook_dead_letters) for manual inspection
- Delivery history tracked in webhook_delivery_logs table
- Supports multiple webhook configs per workspace (filtered by event type subscription)
- Delivery timeout: 10 seconds per attempt
- Idempotency: delivery ID ensures no duplicate sends

**Dependencies:** INFRA-004, CONTENT-001
**Execution Type:** AI-Agent
**Priority:** Medium
**Estimated Effort:** M (3-4 hours)
**Context Window:** Minimal
**Risk Level:** Low
**File Mapping:**
- `pulse/pulse-scheduler/src/pulse_scheduler/webhook_dispatcher.py` (.py)
- `pulse/pulse-api/src/pulse/integrations/webhooks/dispatcher.py` (.py)
- `pulse/pulse-api/src/pulse/integrations/webhooks/signing.py` (.py)
- `pulse/pulse-api/src/pulse/integrations/webhooks/dead_letter.py` (.py)

---

#### Task INT-004: Analytics & Audit Module

**ID:** INT-004
**Title:** Analytics & Audit Module — Usage Tracking, Immutable Audit Log, Prometheus Metrics
**Description:** Implement the analytics and audit system. Track all domain events for usage reporting. Maintain immutable append-only audit log. Expose Prometheus metrics for monitoring. Provide usage analytics API (total generated, by market, by content type, avg confidence, token usage, cost estimation).
**Inputs:** TSD Sections 2.13, 5.15, 16.1
**Output:**
- `pulse/pulse-api/src/pulse/services/analytics_service.py` — AnalyticsService with get_usage_report()
- `pulse/pulse-api/src/pulse/core/audit/audit_writer.py` — Immutable audit log writer
- `pulse/pulse-api/src/pulse/core/audit/event_collector.py` — Domain event collector
- `pulse/pulse-scheduler/src/pulse_scheduler/jobs/analytics_aggregation.py` — Periodic rollup computation
- `pulse/pulse-api/src/pulse/core/metrics/prometheus.py` — Prometheus metrics definitions and exporter

**Acceptance Criteria:**
- Every domain event (content.generated, content.approved, job.completed, etc.) written to audit_logs
- Audit log entries are immutable (no UPDATE/DELETE allowed; enforced by DB permissions)
- GET /api/v1/analytics/usage returns: total_generated, by_market, by_content_type, avg_confidence_score, total_tokens_used, estimated_cost_usd
- Prometheus /metrics endpoint exposes all metrics from TSD §16.1
- Metrics include: pulse_generation_total, pulse_generation_duration_seconds, pulse_confidence_score, pulse_bulk_jobs_active, pulse_llm_request_total, pulse_llm_tokens_total, pulse_vault_cache_hit_total
- Analytics aggregation job runs every 5 minutes (via pulse-scheduler cron)
- Cost estimation based on token counts × per-model pricing table

**Dependencies:** CONTENT-001, INFRA-002
**Execution Type:** AI-Agent
**Priority:** Medium
**Estimated Effort:** M (4-5 hours)
**Context Window:** Medium
**Risk Level:** Low
**File Mapping:**
- `pulse/pulse-api/src/pulse/services/analytics_service.py` (.py)
- `pulse/pulse-api/src/pulse/core/audit/audit_writer.py` (.py)
- `pulse/pulse-api/src/pulse/core/audit/event_collector.py` (.py)
- `pulse/pulse-scheduler/src/pulse_scheduler/jobs/analytics_aggregation.py` (.py)
- `pulse/pulse-api/src/pulse/core/metrics/prometheus.py` (.py)

---

#### Task INT-005: Scheduler Jobs — Cache Cleanup, Vault Writeback, Analytics Aggregation

**ID:** INT-005
**Title:** Pulse Scheduler — Periodic Jobs (Cache Cleanup, Vault Writeback, Analytics)
**Description:** Implement the pulse-scheduler service that runs periodic background jobs: generation cache cleanup (hourly, expired entries), Vault writeback processing (approved content → Vault), and analytics aggregation (every 5 minutes). Uses asyncio-based scheduling (no external cron dependency).
**Inputs:** TSD Sections 8.1, 8.2
**Output:**
- `pulse/pulse-scheduler/src/pulse_scheduler/main.py` — Scheduler entry point with job registration
- `pulse/pulse-scheduler/src/pulse_scheduler/jobs/cache_cleanup.py` — Expired cache entry cleanup
- `pulse/pulse-scheduler/src/pulse_scheduler/jobs/vault_writeback.py` — Vault writeback consumer
- `pulse/pulse-scheduler/src/pulse_scheduler/jobs/analytics_aggregation.py` — (already in INT-004, referenced here)
- `pulse/pulse-scheduler/Dockerfile` — Scheduler container definition

**Acceptance Criteria:**
- Scheduler starts and registers all periodic jobs
- Cache cleanup runs hourly; deletes expired entries from generation_cache table and Redis
- Vault writeback consumes from `pulse:vault-writeback` stream; retries 3x with 500ms/1s/2s backoff
- Analytics aggregation runs every 5 minutes; computes rollups for current window
- All jobs log execution status (success/failure/duration)
- Scheduler gracefully handles PostgreSQL/Redis connection loss (retry with backoff)
- Dockerfile builds successfully; health check passes

**Dependencies:** INT-001, INT-004, INFRA-004
**Execution Type:** AI-Agent
**Priority:** Medium
**Estimated Effort:** M (3-4 hours)
**Context Window:** Medium
**Risk Level:** Low
**File Mapping:**
- `pulse/pulse-scheduler/src/pulse_scheduler/main.py` (.py)
- `pulse/pulse-scheduler/src/pulse_scheduler/jobs/cache_cleanup.py` (.py)
- `pulse/pulse-scheduler/src/pulse_scheduler/jobs/vault_writeback.py` (.py)
- `pulse/pulse-scheduler/Dockerfile` (.dockerfile)

---

### EPIC-5: Frontend & Deployment

---

#### Task UI-001: React Application Shell — Layout, Routing, Auth Flow

**ID:** UI-001
**Title:** React UI Shell — Layout, Routing, Authentication Flow, API Client
**Description:** Build the React application shell with layout components (sidebar navigation, header, main content area), client-side routing (React Router), authentication flow (OIDC redirect + JWT storage), and the API client layer (ky/axios with interceptors for auth headers and error handling).
**Inputs:** TSD Sections 3.2, 11.1
**Output:**
- `pulse/pulse-ui/src/App.tsx` — Root component with routing
- `pulse/pulse-ui/src/layouts/MainLayout.tsx` — Sidebar + header + content layout
- `pulse/pulse-ui/src/components/Sidebar.tsx` — Navigation sidebar
- `pulse/pulse-ui/src/components/Header.tsx` — Top header with user info
- `pulse/pulse-ui/src/auth/AuthProvider.tsx` — Auth context + OIDC flow
- `pulse/pulse-ui/src/auth/ProtectedRoute.tsx` — Route guard component
- `pulse/pulse-ui/src/api/client.ts` — API client with auth interceptors
- `pulse/pulse-ui/src/api/endpoints.ts` — Typed API endpoint functions
- `pulse/pulse-ui/src/types/index.ts` — TypeScript type definitions matching API schemas
- `pulse/pulse-ui/src/hooks/useAuth.ts` — Auth hook
- `pulse/pulse-ui/src/hooks/useApi.ts` — API hook with TanStack Query integration

**Acceptance Criteria:**
- App renders with sidebar navigation (Dashboard, Generate, Content, Bulk Jobs, Brand Voices, Settings, Analytics)
- Unauthenticated users redirected to login/OIDC provider
- After OIDC callback, JWT stored in memory (not localStorage for security); refresh token in httpOnly cookie
- Protected routes redirect to login if JWT expired
- API client automatically attaches Authorization: Bearer header
- API client handles 401 responses by triggering token refresh
- TypeScript types match all API request/response schemas from TSD §5
- TanStack Query configured with staleTime, retry, and error handling

**Dependencies:** INFRA-001
**Execution Type:** AI-Agent
**Priority:** High
**Estimated Effort:** L (5-6 hours)
**Context Window:** Medium (app shell spans multiple components)
**Risk Level:** Low
**File Mapping:**
- `pulse/pulse-ui/src/App.tsx` (.tsx)
- `pulse/pulse-ui/src/layouts/MainLayout.tsx` (.tsx)
- `pulse/pulse-ui/src/components/Sidebar.tsx` (.tsx)
- `pulse/pulse-ui/src/components/Header.tsx` (.tsx)
- `pulse/pulse-ui/src/auth/AuthProvider.tsx` (.tsx)
- `pulse/pulse-ui/src/auth/ProtectedRoute.tsx` (.tsx)
- `pulse/pulse-ui/src/api/client.ts` (.ts)
- `pulse/pulse-ui/src/api/endpoints.ts` (.ts)
- `pulse/pulse-ui/src/types/index.ts` (.ts)
- `pulse/pulse-ui/src/hooks/useAuth.ts` (.ts)
- `pulse/pulse-ui/src/hooks/useApi.ts` (.ts)

---

#### Task UI-002: Dashboard & Generation Pages

**ID:** UI-002
**Title:** Dashboard Page and Content Generation Interface
**Description:** Build the main dashboard showing recent content, active jobs, usage stats, and quick actions. Build the generation interface with form for content type selection, source text/brief input, target market multi-select, brand voice selection, tone controls, and real-time streaming display of generated output.
**Inputs:** TSD Sections 5.3, 5.7
**Output:**
- `pulse/pulse-ui/src/pages/Dashboard.tsx` — Dashboard with stats cards, recent content, active jobs
- `pulse/pulse-ui/src/pages/Generate.tsx` — Generation form + results display
- `pulse/pulse-ui/src/components/GenerationForm.tsx` — Form component with all generation parameters
- `pulse/pulse-ui/src/components/MarketSelector.tsx` — Multi-select for 50+ target markets
- `pulse/pulse-ui/src/components/StreamingOutput.tsx` — Real-time token-by-token display
- `pulse/pulse-ui/src/components/ContentCard.tsx` — Content preview card for dashboard/list
- `pulse/pulse-ui/src/components/ConfidenceBadge.tsx` — Score badge with color coding

**Acceptance Criteria:**
- Dashboard shows: total content count, active jobs, avg confidence score, recent 5 content pieces
- Generation form validates required fields (content_type, source_language, target_markets)
- Market selector shows searchable list of 50+ markets with flags/codes
- Submitting generation shows streaming output (token-by-token via SSE/WebSocket)
- After generation: shows generated text, confidence score badge, flags list, Vault sources
- Multi-market generation shows tabs/accordion for each market result
- Form supports both "generate from brief" and "localize existing content" modes
- All components use shadcn/ui primitives; accessible (keyboard navigation, ARIA labels)

**Dependencies:** UI-001, CONTENT-006
**Execution Type:** AI-Agent
**Priority:** High
**Estimated Effort:** L (5-7 hours)
**Context Window:** Medium
**Risk Level:** Low
**File Mapping:**
- `pulse/pulse-ui/src/pages/Dashboard.tsx` (.tsx)
- `pulse/pulse-ui/src/pages/Generate.tsx` (.tsx)
- `pulse/pulse-ui/src/components/GenerationForm.tsx` (.tsx)
- `pulse/pulse-ui/src/components/MarketSelector.tsx` (.tsx)
- `pulse/pulse-ui/src/components/StreamingOutput.tsx` (.tsx)
- `pulse/pulse-ui/src/components/ContentCard.tsx` (.tsx)
- `pulse/pulse-ui/src/components/ConfidenceBadge.tsx` (.tsx)

---

#### Task UI-003: Content Management & Bulk Jobs Pages

**ID:** UI-003
**Title:** Content List, Content Detail, Review Interface, and Bulk Jobs Page
**Description:** Build the content management pages: paginated content list with filters, content detail view with version history, side-by-side review interface with approve/reject actions, and bulk jobs page with progress tracking (WebSocket), pause/resume/cancel controls, and result download.
**Inputs:** TSD Sections 5.5-5.11, 5.16
**Output:**
- `pulse/pulse-ui/src/pages/ContentList.tsx` — Paginated content list with filters
- `pulse/pulse-ui/src/pages/ContentDetail.tsx` — Content detail with version history
- `pulse/pulse-ui/src/pages/BulkJobs.tsx` — Bulk jobs list + detail with progress
- `pulse/pulse-ui/src/components/ContentFilters.tsx` — Filter bar (status, type, market)
- `pulse/pulse-ui/src/components/VersionHistory.tsx` — Version timeline component
- `pulse/pulse-ui/src/components/ReviewPanel.tsx` — Side-by-side comparison + approve/reject
- `pulse/pulse-ui/src/components/JobProgress.tsx` — Real-time progress bar via WebSocket
- `pulse/pulse-ui/src/components/FileUpload.tsx` — CSV/XLSX upload component for bulk jobs

**Acceptance Criteria:**
- Content list: cursor-based pagination, filters (status, content_type, target_market), search
- Content detail: shows generated_text, metadata, confidence score, flags, Vault sources, version history
- Version history: timeline of versions with diff view between consecutive versions
- Review panel: side-by-side source vs. generated; approve/reject buttons with feedback textarea
- Bulk jobs: list all jobs with status badges; click into job shows real-time progress
- Job progress: WebSocket connection updates progress bar every second
- Pause/resume/cancel buttons functional with confirmation dialogs
- File upload: drag-and-drop CSV/XLSX with validation (file type, size < 50MB)
- Export button on content detail: downloads in selected format (markdown/html/docx/pdf)

**Dependencies:** UI-001, CONTENT-006
**Execution Type:** AI-Agent
**Priority:** High
**Estimated Effort:** L (6-8 hours)
**Context Window:** Medium
**Risk Level:** Low
**File Mapping:**
- `pulse/pulse-ui/src/pages/ContentList.tsx` (.tsx)
- `pulse/pulse-ui/src/pages/ContentDetail.tsx` (.tsx)
- `pulse/pulse-ui/src/pages/BulkJobs.tsx` (.tsx)
- `pulse/pulse-ui/src/components/ContentFilters.tsx` (.tsx)
- `pulse/pulse-ui/src/components/VersionHistory.tsx` (.tsx)
- `pulse/pulse-ui/src/components/ReviewPanel.tsx` (.tsx)
- `pulse/pulse-ui/src/components/JobProgress.tsx` (.tsx)
- `pulse/pulse-ui/src/components/FileUpload.tsx` (.tsx)

---

#### Task UI-004: Settings, Analytics, and Brand Voice Management Pages

**ID:** UI-004
**Title:** Settings, Analytics Dashboard, and Brand Voice Management UI
**Description:** Build the remaining UI pages: Settings (workspace config, API key management, webhook configuration, LLM provider setup), Analytics (usage charts, cost breakdown, market distribution), and Brand Voice management (CRUD with tone attribute editor).
**Inputs:** TSD Sections 5.12, 5.13, 5.15
**Output:**
- `pulse/pulse-ui/src/pages/Settings.tsx` — Settings page with tabs (General, API Keys, Webhooks, LLM Providers)
- `pulse/pulse-ui/src/pages/Analytics.tsx` — Analytics dashboard with charts
- `pulse/pulse-ui/src/pages/BrandVoices.tsx` — Brand voice list + editor
- `pulse/pulse-ui/src/components/ApiKeyManager.tsx` — API key CRUD with scope selection
- `pulse/pulse-ui/src/components/WebhookConfig.tsx` — Webhook URL + event subscription editor
- `pulse/pulse-ui/src/components/LLMProviderConfig.tsx` — Provider credentials + fallback chain editor
- `pulse/pulse-ui/src/components/UsageChart.tsx` — Recharts-based usage visualization
- `pulse/pulse-ui/src/components/BrandVoiceEditor.tsx` — Tone attributes form + sample content

**Acceptance Criteria:**
- Settings: API key creation with scope checkboxes; key shown once then hashed
- Settings: Webhook config with URL, event type multi-select, test delivery button
- Settings: LLM provider config with credential fields; fallback chain drag-to-reorder
- Analytics: line chart of generations over time (7d/30d/90d toggle)
- Analytics: bar chart of generations by market; pie chart by content type
- Analytics: summary cards (total generated, avg confidence, total tokens, estimated cost)
- Brand Voices: list with active/inactive toggle; create/edit form with tone sliders
- Brand Voices: sample content upload (paste text or upload file)
- All pages responsive (mobile-friendly layout)

**Dependencies:** UI-001, CONTENT-006
**Execution Type:** AI-Agent
**Priority:** Medium
**Estimated Effort:** L (5-7 hours)
**Context Window:** Medium
**Risk Level:** Low
**File Mapping:**
- `pulse/pulse-ui/src/pages/Settings.tsx` (.tsx)
- `pulse/pulse-ui/src/pages/Analytics.tsx` (.tsx)
- `pulse/pulse-ui/src/pages/BrandVoices.tsx` (.tsx)
- `pulse/pulse-ui/src/components/ApiKeyManager.tsx` (.tsx)
- `pulse/pulse-ui/src/components/WebhookConfig.tsx` (.tsx)
- `pulse/pulse-ui/src/components/LLMProviderConfig.tsx` (.tsx)
- `pulse/pulse-ui/src/components/UsageChart.tsx` (.tsx)
- `pulse/pulse-ui/src/components/BrandVoiceEditor.tsx` (.tsx)

---

#### Task UI-005: Docker Configuration, Helm Charts, and Deployment Artifacts

**ID:** UI-005
**Title:** Dockerfiles, Docker Compose, Helm Charts, and CI/CD Pipeline
**Description:** Create all deployment artifacts: multi-stage Dockerfiles for all four services, Docker Compose for simple self-hosted deployment, Docker Compose for air-gapped deployment, Kubernetes Helm chart with configurable values, and GitHub Actions CI/CD pipeline.
**Inputs:** TSD Sections 15, 17
**Output:**
- `pulse/pulse-api/Dockerfile` — Multi-stage Python build (python:3.11-slim, non-root, health check)
- `pulse/pulse-worker/Dockerfile` — Worker container
- `pulse/pulse-scheduler/Dockerfile` — Scheduler container
- `pulse/pulse-ui/Dockerfile` — Node build → nginx serve
- `pulse/deploy/docker-compose.yml` — Full stack (api, worker, scheduler, ui, postgres, redis, minio)
- `pulse/deploy/docker-compose.airgap.yml` — Air-gapped variant (local LLM via Ollama)
- `pulse/deploy/helm/Chart.yaml` — Helm chart metadata
- `pulse/deploy/helm/values.yaml` — Configurable values (replicas, resources, env vars, ingress)
- `pulse/deploy/helm/templates/deployment-api.yaml` — API deployment
- `pulse/deploy/helm/templates/deployment-worker.yaml` — Worker deployment
- `pulse/deploy/helm/templates/deployment-scheduler.yaml` — Scheduler deployment
- `pulse/deploy/helm/templates/deployment-ui.yaml` — UI deployment
- `pulse/deploy/helm/templates/service.yaml` — Services
- `pulse/deploy/helm/templates/ingress.yaml` — Ingress with TLS
- `pulse/deploy/helm/templates/configmap.yaml` — ConfigMap for env vars
- `pulse/deploy/helm/templates/secret.yaml` — Secret for credentials
- `pulse/.github/workflows/ci.yml` — CI pipeline (lint, test, build, scan)
- `pulse/.github/workflows/deploy.yml` — Deploy pipeline (staging → production)

**Acceptance Criteria:**
- `docker compose up` starts full stack; all services healthy
- `docker compose -f docker-compose.airgap.yml up` starts with Ollama for local LLM
- API Dockerfile: multi-stage build, non-root user, < 500MB image size
- UI Dockerfile: Node build stage → nginx serve stage; < 50MB final image
- Helm chart: `helm install pulse deploy/helm/` deploys to Kubernetes cluster
- Helm values configurable: replica counts, resource limits, image tags, env vars
- Ingress configured with TLS (cert-manager annotation)
- CI pipeline: lint → type check → unit tests → build image → security scan → integration tests
- Deploy pipeline: build+tag → deploy staging → performance benchmark → manual approval → deploy production
- Health checks configured in all Dockerfiles and K8s deployments

**Dependencies:** All previous tasks (needs all services implemented)
**Execution Type:** Developer
**Priority:** High
**Estimated Effort:** L (6-8 hours)
**Context Window:** Large (deployment spans all services)
**Risk Level:** Medium (deployment configuration must work across environments)
**File Mapping:**
- `pulse/pulse-api/Dockerfile` (.dockerfile)
- `pulse/pulse-worker/Dockerfile` (.dockerfile)
- `pulse/pulse-scheduler/Dockerfile` (.dockerfile)
- `pulse/pulse-ui/Dockerfile` (.dockerfile)
- `pulse/deploy/docker-compose.yml` (.yml)
- `pulse/deploy/docker-compose.airgap.yml` (.yml)
- `pulse/deploy/helm/Chart.yaml` (.yaml)
- `pulse/deploy/helm/values.yaml` (.yaml)
- `pulse/deploy/helm/templates/*.yaml` (8 template files)
- `pulse/.github/workflows/ci.yml` (.yml)
- `pulse/.github/workflows/deploy.yml` (.yml)

---

### EPIC-6: Experimentation & Performance Tracking

---

#### Task EXP-001: Experiment Data Models & Migrations

**ID:** EXP-001
**Title:** Experiment, Variant, Assignment, Exposure, Performance Event, and Prompt Version ORM Models
**Description:** Implement all 6 new database entities as SQLAlchemy 2.0 ORM models. Create migration with proper partitioning: experiment_assignments (monthly), experiment_exposures (weekly), performance_events (weekly). Add RLS policies for workspace isolation on all new tables.
**Inputs:** TSD §4.14-4.19
**Output:**
- `pulse-api/src/pulse/models/experiment.py` (Experiment + ExperimentVariant)
- `pulse-api/src/pulse/models/performance_event.py` (PerformanceEvent, partitioned)
- `pulse-api/src/pulse/models/prompt_version.py` (PromptVersion)
- `pulse-api/src/pulse/db/migrations/versions/003_add_experimentation_schema.py`

**Acceptance Criteria:**
- `alembic upgrade head` creates 6 new tables
- `experiment_assignments` partitioned by month
- `experiment_exposures` and `performance_events` partitioned by week
- RLS policies on all new tables
- All indexes created per TSD spec
- Reverse migration drops all tables cleanly

**Dependencies:** INFRA-002
**Execution Type:** AI-Agent
**Priority:** Critical
**Estimated Effort:** L (5-6 hours)
**Context Window:** Medium (new models reference existing workspace/content tables)
**Risk Level:** Medium (partitioning must be correct for performance)
**File Mapping:**
- `pulse-api/src/pulse/models/experiment.py` (.py)
- `pulse-api/src/pulse/models/performance_event.py` (.py)
- `pulse-api/src/pulse/models/prompt_version.py` (.py)
- `pulse-api/src/pulse/db/migrations/versions/003_add_experimentation_schema.py` (.py)

---

#### Task EXP-002: Experiment Assignment Engine

**ID:** EXP-002
**Title:** Deterministic Hashing Variant Assignment with Redis Cache
**Description:** Implement deterministic variant assignment using SHA256(visitor_id + experiment_id) % 100 bucketing. Cache assignments in Redis (TTL = experiment duration). Handle returning visitors (same assignment) and new visitors (allocate by traffic_weight). Support weighted allocation (e.g., 33/33/34 split).
**Inputs:** TSD §6.6 (experiment pipeline step 3)
**Output:**
- `pulse-api/src/pulse/core/experiment/assignment.py`

**Acceptance Criteria:**
- Same visitor_hash + experiment_id always returns same variant
- Traffic allocation matches configured weights within 1% over 10,000 assignments
- Redis cache lookup: <5ms
- Cache miss computation: <10ms
- Supports 2-5 variants per experiment

**Dependencies:** EXP-001, INFRA-004
**Execution Type:** AI-Agent
**Priority:** Critical
**Estimated Effort:** M (3-4 hours)
**Context Window:** Minimal (single module with clear interface)
**Risk Level:** Medium (determinism is critical for experiment validity)
**File Mapping:**
- `pulse-api/src/pulse/core/experiment/assignment.py` (.py)

---

#### Task EXP-003: Statistical Analysis Engine

**ID:** EXP-003
**Title:** Statistical Significance — Chi-Squared, Effect Size, Bayesian Analysis, Per-Locale
**Description:** Implement statistical analysis: chi-squared test for comparing conversion rates, Cohen's h effect size, confidence intervals, optional Bayesian Beta-Binomial analysis, per-locale analysis for multilingual experiments.
**Inputs:** TSD §6.6 (experiment pipeline step 5-6)
**Output:**
- `pulse-api/src/pulse/core/experiment/statistics.py`

**Acceptance Criteria:**
- `chi_squared_test` returns (p_value, confidence_level, effect_size)
- Results match scipy.stats chi2_contingency within 0.001
- `bayesian_analysis` returns probability treatment > control
- Per-locale analysis works for multi-market experiments
- Computation <100ms for 10,000 events
- Edge cases: zero events, single variant, equal rates

**Dependencies:** EXP-001
**Execution Type:** AI-Agent
**Priority:** High
**Estimated Effort:** M (3-4 hours)
**Context Window:** Minimal (self-contained statistical module)
**Risk Level:** High (statistical correctness is critical for experiment validity)
**File Mapping:**
- `pulse-api/src/pulse/core/experiment/statistics.py` (.py)

---

#### Task EXP-004: Experiment Service & Lifecycle Management

**ID:** EXP-004
**Title:** Experiment Service — CRUD, State Machine, Variant Generation, Results, Winner Promotion
**Description:** Full experiment lifecycle: create → generate variants → start → track → ingest events → compute results → determine winner → promote. Integrates with Generation Orchestrator for variant generation using cultural_overrides. Includes sample size calculator and duration estimation.
**Inputs:** TSD §6.6
**Output:**
- `pulse-api/src/pulse/services/experiment_service.py`
- `pulse-api/src/pulse/core/experiment/results.py`
- `pulse-api/src/pulse/core/experiment/tracking.py` (UTM URL generation)

**Acceptance Criteria:**
- `create()` validates traffic allocation sums to 1.0, 2-5 variants
- Variant generation uses `cultural_overrides` from variant config
- State transitions: draft → active → paused → active → completed
- `start()` validates all variants approved
- Results computation callable by scheduler
- Winner: confidence > threshold → winner set
- `promote_winner()` sets winner to 100%, others to 0%
- Sample size calculator returns required visitors per locale
- Domain events emitted: `experiment.created`, `experiment.started`, `experiment.completed`

**Dependencies:** EXP-001, EXP-002, EXP-003, GEN-007
**Execution Type:** AI-Agent
**Priority:** Critical
**Estimated Effort:** L (6-8 hours)
**Context Window:** Large (integrates generation pipeline, assignment, statistics)
**Risk Level:** High (orchestrates entire experiment lifecycle)
**File Mapping:**
- `pulse-api/src/pulse/services/experiment_service.py` (.py)
- `pulse-api/src/pulse/core/experiment/results.py` (.py)
- `pulse-api/src/pulse/core/experiment/tracking.py` (.py)

---

#### Task EXP-005: Analytics Integration Connectors

**ID:** EXP-005
**Title:** Segment, GA4, and Mixpanel Connectors — Bidirectional Event Routing
**Description:** Implement analytics connectors. Segment as P0 (central event router, 100+ destinations). GA4 (Measurement Protocol + Data API). Mixpanel (HTTP API). All connectors: send experiment metadata out, receive performance events back, normalize to internal PerformanceEvent format. Webhook receiver for signed payloads.
**Inputs:** TSD §2.14
**Output:**
- `pulse-api/src/pulse/integrations/analytics/base.py`
- `pulse-api/src/pulse/integrations/analytics/segment.py`
- `pulse-api/src/pulse/integrations/analytics/ga4.py`
- `pulse-api/src/pulse/integrations/analytics/mixpanel.py`
- `pulse-api/src/pulse/services/analytics_integration_service.py`

**Acceptance Criteria:**
- Segment connector sends experiment metadata and receives events
- GA4 connector sends via Measurement Protocol, reads via Data API
- Mixpanel connector sends/receives via HTTP API
- All connectors normalize → internal PerformanceEvent format
- Webhook receiver at `/api/v1/performance-events/webhook/{connector}`
- Connector failures don't block experiments (graceful degradation)
- Internal tracking fallback for air-gapped deployments (JS snippet → Pulse API)

**Dependencies:** EXP-001, INFRA-001
**Execution Type:** AI-Agent
**Priority:** High (Segment P0, GA4 P1, Mixpanel P2)
**Estimated Effort:** L (6-8 hours)
**Context Window:** Medium (each connector independent but follows common interface)
**Risk Level:** High (external API dependencies; must handle failures gracefully)
**File Mapping:**
- `pulse-api/src/pulse/integrations/analytics/base.py` (.py)
- `pulse-api/src/pulse/integrations/analytics/segment.py` (.py)
- `pulse-api/src/pulse/integrations/analytics/ga4.py` (.py)
- `pulse-api/src/pulse/integrations/analytics/mixpanel.py` (.py)
- `pulse-api/src/pulse/services/analytics_integration_service.py` (.py)

---

#### Task EXP-006: Experiment API Endpoints

**ID:** EXP-006
**Title:** REST API — Experiment CRUD, Lifecycle, Results, Performance Events, Prompt Versions
**Description:** All experiment REST endpoints per TSD §5.17-5.31. Experiment CRUD, lifecycle actions (start/pause/stop/promote), results with statistical analysis, performance event ingestion (single + batch + webhook), prompt version management, model comparison.
**Inputs:** TSD §5.17-5.31
**Output:**
- `pulse-api/src/pulse/api/v1/experiments.py`
- `pulse-api/src/pulse/api/v1/performance.py`
- `pulse-api/src/pulse/api/v1/prompt_versions.py`
- `pulse-api/src/pulse/api/schemas/experiment.py`
- `pulse-api/src/pulse/api/schemas/performance.py`

**Acceptance Criteria:**
- All 15 endpoints functional per TSD
- Workspace-scoped with RLS
- Standard response envelope format
- Results endpoint includes statistical analysis + per-locale breakdown
- Batch event ingestion handles 100 events per request

**Dependencies:** EXP-004, EXP-005
**Execution Type:** AI-Agent
**Priority:** Critical
**Estimated Effort:** L (6-8 hours)
**Context Window:** Large (many endpoints + schemas)
**Risk Level:** Medium (many endpoints but each is straightforward)
**File Mapping:**
- `pulse-api/src/pulse/api/v1/experiments.py` (.py)
- `pulse-api/src/pulse/api/v1/performance.py` (.py)
- `pulse-api/src/pulse/api/v1/prompt_versions.py` (.py)
- `pulse-api/src/pulse/api/schemas/experiment.py` (.py)
- `pulse-api/src/pulse/api/schemas/performance.py` (.py)

---

#### Task EXP-007: Scheduler Jobs — Results, Aggregation, Analytics Sync

**ID:** EXP-007
**Title:** Scheduled Jobs — Hourly Results, 5-min Aggregation, 15-min Analytics Sync
**Description:** Three scheduled jobs: (1) Hourly — compute statistical significance for all active experiments, determine winners. (2) Every 5 min — aggregate raw performance events into rolling variant metrics. (3) Every 15 min — pull latest events from Segment/GA4/Mixpanel APIs.
**Inputs:** TSD §8 (background jobs)
**Output:**
- `pulse-scheduler/src/pulse_scheduler/jobs/experiment_results.py`
- `pulse-scheduler/src/pulse_scheduler/jobs/performance_aggregation.py`
- `pulse-scheduler/src/pulse_scheduler/jobs/analytics_sync.py`

**Acceptance Criteria:**
- Results job processes all active experiments within 60 seconds
- Aggregation job updates metrics every 5 minutes
- Analytics sync pulls from external APIs every 15 minutes
- All jobs handle errors gracefully (log and continue)
- Jobs respect workspace isolation

**Dependencies:** EXP-004, EXP-005, INT-005
**Execution Type:** AI-Agent
**Priority:** High
**Estimated Effort:** M (4-5 hours)
**Context Window:** Medium (scheduler jobs reference experiment service + connectors)
**Risk Level:** Medium (must handle failures gracefully without corrupting data)
**File Mapping:**
- `pulse-scheduler/src/pulse_scheduler/jobs/experiment_results.py` (.py)
- `pulse-scheduler/src/pulse_scheduler/jobs/performance_aggregation.py` (.py)
- `pulse-scheduler/src/pulse_scheduler/jobs/analytics_sync.py` (.py)

---

#### Task EXP-008: Experimentation UI

**ID:** EXP-008
**Title:** React UI — Experiment Creation, Results Dashboard, Model Comparison, Performance Analytics
**Description:** Full experimentation UI: experiment list, creation form (variant editor with cultural override controls), detail page with real-time results charts, statistical confidence badges (green >95%, yellow 80-95%, red <80%), model comparison interface (blind evaluation), performance dashboard with per-locale breakdown, sample size estimator display.
**Inputs:** TSD §5.17-5.31
**Output:**
- `pulse-ui/src/pages/Experiments.tsx`
- `pulse-ui/src/pages/ExperimentDetail.tsx`
- `pulse-ui/src/pages/ModelComparison.tsx`
- `pulse-ui/src/components/ExperimentForm.tsx`
- `pulse-ui/src/components/VariantEditor.tsx`
- `pulse-ui/src/components/ResultsChart.tsx`
- `pulse-ui/src/components/StatisticalBadge.tsx`
- `pulse-ui/src/components/SampleSizeEstimator.tsx`

**Acceptance Criteria:**
- Experiment list with status badges
- Create form: name, hypothesis, variant count (2-5), traffic allocation slider, success metric, min sample, min duration
- Variant editor with cultural override controls (persuasion_style, formality, emotional_expression)
- Results: real-time bar chart per variant, updating every 30 seconds
- Statistical badge with color coding
- Model comparison: blind evaluation (model names hidden until rated)
- Per-locale breakdown toggle
- Sample size estimator shows estimated duration based on traffic
- Accessible and responsive

**Dependencies:** EXP-006, UI-001
**Execution Type:** AI-Agent
**Priority:** High
**Estimated Effort:** L (6-8 hours)
**Context Window:** Medium (UI components reference experiment API types)
**Risk Level:** Medium (many components but follow established UI patterns)
**File Mapping:**
- `pulse-ui/src/pages/Experiments.tsx` (.tsx)
- `pulse-ui/src/pages/ExperimentDetail.tsx` (.tsx)
- `pulse-ui/src/pages/ModelComparison.tsx` (.tsx)
- `pulse-ui/src/components/ExperimentForm.tsx` (.tsx)
- `pulse-ui/src/components/VariantEditor.tsx` (.tsx)
- `pulse-ui/src/components/ResultsChart.tsx` (.tsx)
- `pulse-ui/src/components/StatisticalBadge.tsx` (.tsx)
- `pulse-ui/src/components/SampleSizeEstimator.tsx` (.tsx)

---

## 4. Dependency Graph

### 4.1 Blocking Dependencies (Sequential)

```
INFRA-001 (Scaffolding)
  ├── INFRA-002 (DB Schema) ──→ INFRA-003 (Auth) ──→ CONTENT-001 (Content Service)
  │       │                                              ├── CONTENT-004 (Review)
  │       │                                              └── CONTENT-006 (API Endpoints)
  │       └──→ EXP-001 (Experiment Models) ──→ EXP-002 (Assignment) ──→ EXP-004 (Experiment Service)
  │                                                                          ├── EXP-006 (Experiment API) ──→ EXP-008 (Experimentation UI)
  │                                                                          └── EXP-007 (Scheduler Jobs)
  │       EXP-003 (Statistics) ──────────────────→ EXP-004
  │       EXP-005 (Analytics Connectors) ────────→ EXP-006
  ├── INFRA-004 (Redis) ──→ GEN-004 (Cultural Engine) ──→ GEN-005 (Prompt Composer)
  │       │                                                  └── GEN-006 (Quality Scoring)
  │       │                                                        └── GEN-007 (Orchestrator) ──→ EXP-004
  │       │                                                              ├── CONTENT-003 (Bulk Jobs)
  │       │                                                              └── CONTENT-006 (API Endpoints)
  │       └──→ EXP-002 (Assignment Engine)
  ├── GEN-001 (LLM Base) ──→ GEN-002 (Adapters) ──→ GEN-003 (Router)
  │                                                      └── GEN-007 (Orchestrator)
  └── INT-001 (Vault) ──→ GEN-007 (Orchestrator)
```

### 4.2 Parallelizable Groups

**Group A (can start after INFRA-001):**
- INFRA-002 (DB Schema)
- INFRA-004 (Redis)
- INFRA-005 (Error Handling)
- GEN-001 (LLM Base Interface)
- INT-002 (S3 Storage)
- UI-001 (React Shell)

**Group B (can start after INFRA-002 + INFRA-003):**
- CONTENT-001 (Content Service)
- CONTENT-005 (Brand Voice/Glossary)
- GEN-004 (Cultural Engine)
- EXP-001 (Experiment Data Models)

**Group C (LLM adapters — all independent of each other):**
- OpenAI adapter
- Anthropic adapter
- Mistral adapter
- Ollama adapter
- vLLM adapter
- Azure OpenAI adapter
- Bedrock adapter

**Group D (after API contracts defined — parallel with backend):**
- UI-002 (Dashboard + Generate)
- UI-003 (Content + Bulk Jobs)
- UI-004 (Settings + Analytics)

**Group E (experimentation — after EXP-001):**
- EXP-002 (Assignment Engine) — depends on EXP-001 + INFRA-004
- EXP-003 (Statistics Engine) — depends on EXP-001
- EXP-005 (Analytics Connectors) — depends on EXP-001 + INFRA-001

**Group F (after experiment API contracts defined — parallel with backend):**
- EXP-008 (Experimentation UI) — depends on EXP-006 + UI-001

### 4.3 No Circular Dependencies

Verified: All dependency arrows flow from infrastructure → core → services → API → UI. No backward references.

---

## 5. Execution Phases

### Phase 1: Environment & Project Setup (Days 1-2)

| Order | Task | Verification |
|---|---|---|
| 1 | INFRA-001: Project Scaffolding | `uvicorn` starts, `npm run dev` starts |
| 2 | INFRA-005: Error Handling Framework | Exception → proper HTTP response |
| 3 | INFRA-004: Redis Connection Layer | Cache get/set/delete works |

### Phase 2: Core Infrastructure (Days 3-6)

| Order | Task | Verification |
|---|---|---|
| 4 | INFRA-002: Database Schema & ORM | `alembic upgrade head` creates all tables |
| 5 | INFRA-003: Authentication & RBAC | JWT auth + RBAC enforcement verified |
| 6 | INFRA-006: Health Check Endpoints | /health/live, /health/ready return correct codes |
| 7 | INFRA-007: Infrastructure Tests | All integration tests pass |

### Phase 3: Core Business Logic (Days 7-14)

| Order | Task | Verification |
|---|---|---|
| 8 | GEN-001: LLM Abstraction Base | Abstract interface + registry works |
| 9 | GEN-002: LLM Provider Adapters | Each adapter returns normalized response |
| 10 | GEN-003: Fallback Router | Failover works when primary fails |
| 11 | GEN-004: Cultural Adaptation Engine | Different markets produce different directives |
| 12 | GEN-005: Prompt Composer | Composed prompt includes all context sources |
| 13 | GEN-006: Quality Scoring Engine | Score computed correctly for test content |
| 14 | GEN-007: Generation Orchestrator | End-to-end generation pipeline works |

### Phase 4: Content & Workflow (Days 15-20)

| Order | Task | Verification |
|---|---|---|
| 15 | CONTENT-001: Content Service & State Machine | CRUD + state transitions work |
| 16 | CONTENT-002: Export Engine | All 5 formats render correctly |
| 17 | CONTENT-005: Brand Voice & Glossary | CRUD + caching works |
| 18 | CONTENT-004: Review & Workflow | Approval chain + feedback works |
| 19 | CONTENT-003: Bulk Job Manager | Bulk job lifecycle (create → process → complete) |
| 20 | CONTENT-006: API Endpoints | All endpoints return correct responses |

### Phase 5: Integrations (Days 21-27)

| Order | Task | Verification |
|---|---|---|
| 21 | INT-001: Vault Connector | Knowledge retrieval + semantic search works |
| 22 | INT-002: S3 Storage | Upload/download/presigned URLs work |
| 23 | INT-003: Webhook Dispatcher | Events delivered with retry |
| 24 | INT-004: Analytics & Audit | Metrics exposed, audit log immutable |
| 25 | INT-005: Scheduler Jobs | Periodic jobs execute on schedule |
| 26 | EXP-005: Analytics Integration Connectors | Segment/GA4/Mixpanel bidirectional routing works |

### Phase 6: Frontend & Experimentation (Days 22-35, parallel with Phase 5)

| Order | Task | Verification |
|---|---|---|
| 27 | UI-001: React Shell | Auth flow + routing works |
| 28 | UI-002: Dashboard & Generation | Generation form submits, streaming works |
| 29 | UI-003: Content & Bulk Jobs | Content list, review, job progress work |
| 30 | UI-004: Settings & Analytics | All settings pages functional |
| 31 | EXP-001: Experiment Data Models | 6 new tables created with partitioning |
| 32 | EXP-002: Experiment Assignment Engine | Deterministic assignment with Redis cache |
| 33 | EXP-003: Statistical Analysis Engine | Chi-squared + Bayesian analysis validated |
| 34 | EXP-004: Experiment Service & Lifecycle | Full experiment lifecycle works |
| 35 | EXP-006: Experiment API Endpoints | All 15 endpoints functional |
| 36 | EXP-007: Scheduler Jobs (Results/Aggregation) | Hourly results + 5-min aggregation work |
| 37 | EXP-008: Experimentation UI | Experiment dashboard + model comparison work |

### Phase 7: Deployment & Testing (Days 36-44)

| Order | Task | Verification |
|---|---|---|
| 38 | UI-005: Docker & Deployment | `docker compose up` runs full stack |

---

## 6. AI-Agent Optimization Layer

### 6.1 Task Suitability Matrix

| Task ID | Single-Shot | Iterative | Context Window | Risk |
|---|---|---|---|---|
| INFRA-001 | ✓ | | Minimal | Low |
| INFRA-002 | | ✓ | Medium | Medium |
| INFRA-003 | | ✓ | Medium | Medium |
| INFRA-004 | ✓ | | Minimal | Low |
| INFRA-005 | ✓ | | Minimal | Low |
| INFRA-006 | ✓ | | Minimal | Low |
| INFRA-007 | | ✓ | Medium | Low |
| GEN-001 | ✓ | | Medium | Medium |
| GEN-002 | ✓ (per adapter) | | Minimal | Medium |
| GEN-003 | | ✓ | Medium | Medium |
| GEN-004 | | ✓ | Large | High |
| GEN-005 | | ✓ | Large | High |
| GEN-006 | | ✓ | Medium | High |
| GEN-007 | | ✓ | Large | High |
| CONTENT-001 | | ✓ | Medium | Medium |
| CONTENT-002 | ✓ (per renderer) | | Minimal | Low |
| CONTENT-003 | | ✓ | Large | High |
| CONTENT-004 | | ✓ | Medium | Medium |
| CONTENT-005 | ✓ | | Minimal | Low |
| CONTENT-006 | | ✓ | Large | Medium |
| INT-001 | | ✓ | Medium | High |
| INT-002 | ✓ | | Minimal | Low |
| INT-003 | | ✓ | Minimal | Low |
| INT-004 | | ✓ | Medium | Low |
| INT-005 | | ✓ | Medium | Low |
| UI-001 | | ✓ | Medium | Low |
| UI-002 | | ✓ | Medium | Low |
| UI-003 | | ✓ | Medium | Low |
| UI-004 | | ✓ | Medium | Low |
| UI-005 | | ✓ | Large | Medium |
| EXP-001 | | ✓ | Medium | Medium |
| EXP-002 | ✓ | | Minimal | Medium |
| EXP-003 | ✓ | | Minimal | High |
| EXP-004 | | ✓ | Large | High |
| EXP-005 | | ✓ | Medium | High |
| EXP-006 | | ✓ | Large | Medium |
| EXP-007 | | ✓ | Medium | Medium |
| EXP-008 | | ✓ | Medium | Medium |

### 6.2 Agent Execution Guidelines

**For Single-Shot tasks:** Provide complete TSD section references and schema definitions. Agent can generate complete file in one pass.

**For Iterative tasks:** Start with skeleton/structure, then fill in logic. Review output after each iteration. These tasks benefit from test-driven development — write tests first, then implement.

**For High-Risk tasks (GEN-004, GEN-005, GEN-006, GEN-007, CONTENT-003, INT-001):**
- Require human review of design before implementation
- Implement with extensive inline documentation
- Write comprehensive tests alongside implementation
- Consider pair programming (agent + human) for initial design

**Context Window Management:**
- **Minimal:** Single file, no cross-references needed. Agent works autonomously.
- **Medium:** Module-level, 2-5 files with clear interfaces. Agent needs interface definitions.
- **Large:** Cross-service, 5+ files. Agent needs architecture overview + interface contracts.

---

## 7. File-Level Mapping

### 7.1 Complete File Inventory

**Backend — pulse-api (Python)**

| File Path | Type | Owner Task |
|---|---|---|
| `pulse-api/pyproject.toml` | .toml | INFRA-001 |
| `pulse-api/src/pulse/__init__.py` | .py | INFRA-001 |
| `pulse-api/src/pulse/main.py` | .py | INFRA-001 |
| `pulse-api/src/pulse/config.py` | .py | INFRA-001 |
| `pulse-api/src/alembic.ini` | .ini | INFRA-002 |
| `pulse-api/src/pulse/models/workspace.py` | .py | INFRA-002 |
| `pulse-api/src/pulse/models/user.py` | .py | INFRA-002 |
| `pulse-api/src/pulse/models/content.py` | .py | INFRA-002 |
| `pulse-api/src/pulse/models/bulk_job.py` | .py | INFRA-002 |
| `pulse-api/src/pulse/models/brand_voice.py` | .py | INFRA-002 |
| `pulse-api/src/pulse/models/market_profile.py` | .py | INFRA-002 |
| `pulse-api/src/pulse/models/glossary.py` | .py | INFRA-002 |
| `pulse-api/src/pulse/models/audit_log.py` | .py | INFRA-002 |
| `pulse-api/src/pulse/models/api_key.py` | .py | INFRA-002 |
| `pulse-api/src/pulse/models/webhook_config.py` | .py | INFRA-002 |
| `pulse-api/src/pulse/models/generation_cache.py` | .py | INFRA-002 |
| `pulse-api/src/pulse/db/session.py` | .py | INFRA-002 |
| `pulse-api/src/pulse/db/rls.py` | .py | INFRA-002 |
| `pulse-api/src/pulse/db/migrations/env.py` | .py | INFRA-002 |
| `pulse-api/src/pulse/db/migrations/versions/001_initial_schema.py` | .py | INFRA-002 |
| `pulse-api/src/pulse/db/migrations/versions/002_seed_market_profiles.py` | .py | GEN-004 |
| `pulse-api/src/pulse/api/middleware/auth.py` | .py | INFRA-003 |
| `pulse-api/src/pulse/api/middleware/rate_limit.py` | .py | INFRA-003 |
| `pulse-api/src/pulse/api/middleware/request_id.py` | .py | INFRA-003 |
| `pulse-api/src/pulse/api/middleware/tenant.py` | .py | INFRA-003 |
| `pulse-api/src/pulse/core/auth/jwt_utils.py` | .py | INFRA-003 |
| `pulse-api/src/pulse/core/auth/api_key_utils.py` | .py | INFRA-003 |
| `pulse-api/src/pulse/core/auth/rbac.py` | .py | INFRA-003 |
| `pulse-api/src/pulse/core/cache/redis_client.py` | .py | INFRA-004 |
| `pulse-api/src/pulse/core/cache/cache_manager.py` | .py | INFRA-004 |
| `pulse-api/src/pulse/core/cache/streams.py` | .py | INFRA-004 |
| `pulse-api/src/pulse/core/cache/rate_limit.py` | .py | INFRA-004 |
| `pulse-api/src/pulse/core/cache/brand_voice_cache.py` | .py | CONTENT-005 |
| `pulse-api/src/pulse/core/cache/glossary_cache.py` | .py | CONTENT-005 |
| `pulse-api/src/pulse/core/exceptions.py` | .py | INFRA-005 |
| `pulse-api/src/pulse/core/error_handlers.py` | .py | INFRA-005 |
| `pulse-api/src/pulse/core/logging_config.py` | .py | INFRA-005 |
| `pulse-api/src/pulse/core/middleware/error_handler.py` | .py | INFRA-005 |
| `pulse-api/src/pulse/api/health.py` | .py | INFRA-006 |
| `pulse-api/src/pulse/core/health/dependency_checker.py` | .py | INFRA-006 |
| `pulse-api/src/pulse/core/llm/types.py` | .py | GEN-001 |
| `pulse-api/src/pulse/core/llm/adapters/base.py` | .py | GEN-001 |
| `pulse-api/src/pulse/core/llm/adapters/registry.py` | .py | GEN-001 |
| `pulse-api/src/pulse/core/llm/normalizer.py` | .py | GEN-001 |
| `pulse-api/src/pulse/core/llm/adapters/openai.py` | .py | GEN-002 |
| `pulse-api/src/pulse/core/llm/adapters/anthropic.py` | .py | GEN-002 |
| `pulse-api/src/pulse/core/llm/adapters/mistral.py` | .py | GEN-002 |
| `pulse-api/src/pulse/core/llm/adapters/ollama.py` | .py | GEN-002 |
| `pulse-api/src/pulse/core/llm/adapters/vllm.py` | .py | GEN-002 |
| `pulse-api/src/pulse/core/llm/adapters/azure_openai.py` | .py | GEN-002 |
| `pulse-api/src/pulse/core/llm/adapters/bedrock.py` | .py | GEN-002 |
| `pulse-api/src/pulse/core/llm/router.py` | .py | GEN-003 |
| `pulse-api/src/pulse/core/llm/circuit_breaker.py` | .py | GEN-003 |
| `pulse-api/src/pulse/core/llm/health_monitor.py` | .py | GEN-003 |
| `pulse-api/src/pulse/core/cultural/engine.py` | .py | GEN-004 |
| `pulse-api/src/pulse/core/cultural/profiles.py` | .py | GEN-004 |
| `pulse-api/src/pulse/core/cultural/dimensions.py` | .py | GEN-004 |
| `pulse-api/src/pulse/core/cultural/directives.py` | .py | GEN-004 |
| `pulse-api/src/pulse/core/cultural/seed_profiles.py` | .py | GEN-004 |
| `pulse-api/src/pulse/core/generation/prompt_composer.py` | .py | GEN-005 |
| `pulse-api/src/pulse/core/generation/token_budget.py` | .py | GEN-005 |
| `pulse-api/src/pulse/core/generation/template_engine.py` | .py | GEN-005 |
| `pulse-api/src/pulse/core/generation/templates/*.py` | .py (×10) | GEN-005 |
| `pulse-api/src/pulse/core/quality/scorer.py` | .py | GEN-006 |
| `pulse-api/src/pulse/core/quality/terminology.py` | .py | GEN-006 |
| `pulse-api/src/pulse/core/quality/grounding.py` | .py | GEN-006 |
| `pulse-api/src/pulse/core/quality/format_checker.py` | .py | GEN-006 |
| `pulse-api/src/pulse/core/quality/cultural_coherence.py` | .py | GEN-006 |
| `pulse-api/src/pulse/core/generation/orchestrator.py` | .py | GEN-007 |
| `pulse-api/src/pulse/core/generation/cache.py` | .py | GEN-007 |
| `pulse-api/src/pulse/core/generation/context_aggregator.py` | .py | GEN-007 |
| `pulse-api/src/pulse/core/generation/post_processor.py` | .py | GEN-007 |
| `pulse-api/src/pulse/services/content_service.py` | .py | CONTENT-001 |
| `pulse-api/src/pulse/core/content/state_machine.py` | .py | CONTENT-001 |
| `pulse-api/src/pulse/core/content/version_controller.py` | .py | CONTENT-001 |
| `pulse-api/src/pulse/core/events.py` | .py | CONTENT-001 |
| `pulse-api/src/pulse/core/content/export_engine.py` | .py | CONTENT-002 |
| `pulse-api/src/pulse/core/content/renderers/markdown.py` | .py | CONTENT-002 |
| `pulse-api/src/pulse/core/content/renderers/html.py` | .py | CONTENT-002 |
| `pulse-api/src/pulse/core/content/renderers/json_renderer.py` | .py | CONTENT-002 |
| `pulse-api/src/pulse/core/content/renderers/docx.py` | .py | CONTENT-002 |
| `pulse-api/src/pulse/core/content/renderers/pdf.py` | .py | CONTENT-002 |
| `pulse-api/src/pulse/services/job_service.py` | .py | CONTENT-003 |
| `pulse-api/src/pulse/core/jobs/input_parser.py` | .py | CONTENT-003 |
| `pulse-api/src/pulse/core/jobs/task_dispatcher.py` | .py | CONTENT-003 |
| `pulse-api/src/pulse/core/jobs/progress_tracker.py` | .py | CONTENT-003 |
| `pulse-api/src/pulse/services/review_service.py` | .py | CONTENT-004 |
| `pulse-api/src/pulse/core/workflow/approval_chain.py` | .py | CONTENT-004 |
| `pulse-api/src/pulse/core/workflow/feedback.py` | .py | CONTENT-004 |
| `pulse-api/src/pulse/core/workflow/comparison.py` | .py | CONTENT-004 |
| `pulse-api/src/pulse/services/brand_voice_service.py` | .py | CONTENT-005 |
| `pulse-api/src/pulse/services/glossary_service.py` | .py | CONTENT-005 |
| `pulse-api/src/pulse/api/router.py` | .py | CONTENT-006 |
| `pulse-api/src/pulse/api/v1/generate.py` | .py | CONTENT-006 |
| `pulse-api/src/pulse/api/v1/content.py` | .py | CONTENT-006 |
| `pulse-api/src/pulse/api/v1/jobs.py` | .py | CONTENT-006 |
| `pulse-api/src/pulse/api/v1/brand_voices.py` | .py | CONTENT-006 |
| `pulse-api/src/pulse/api/v1/market_profiles.py` | .py | CONTENT-006 |
| `pulse-api/src/pulse/api/v1/analytics.py` | .py | CONTENT-006 |
| `pulse-api/src/pulse/api/v1/webhooks.py` | .py | CONTENT-006 |
| `pulse-api/src/pulse/api/schemas/generate.py` | .py | CONTENT-006 |
| `pulse-api/src/pulse/api/schemas/content.py` | .py | CONTENT-006 |
| `pulse-api/src/pulse/api/schemas/jobs.py` | .py | CONTENT-006 |
| `pulse-api/src/pulse/api/schemas/common.py` | .py | CONTENT-006 |
| `pulse-api/src/pulse/api/ws/progress.py` | .py | CONTENT-006 |
| `pulse-api/src/pulse/integrations/vault/client.py` | .py | INT-001 |
| `pulse-api/src/pulse/integrations/vault/search.py` | .py | INT-001 |
| `pulse-api/src/pulse/integrations/vault/cache.py` | .py | INT-001 |
| `pulse-api/src/pulse/integrations/vault/writeback.py` | .py | INT-001 |
| `pulse-api/src/pulse/integrations/storage/s3.py` | .py | INT-002 |
| `pulse-api/src/pulse/integrations/storage/config.py` | .py | INT-002 |
| `pulse-api/src/pulse/integrations/webhooks/dispatcher.py` | .py | INT-003 |
| `pulse-api/src/pulse/integrations/webhooks/signing.py` | .py | INT-003 |
| `pulse-api/src/pulse/integrations/webhooks/dead_letter.py` | .py | INT-003 |
| `pulse-api/src/pulse/services/analytics_service.py` | .py | INT-004 |
| `pulse-api/src/pulse/core/audit/audit_writer.py` | .py | INT-004 |
| `pulse-api/src/pulse/core/audit/event_collector.py` | .py | INT-004 |
| `pulse-api/src/pulse/core/metrics/prometheus.py` | .py | INT-004 |
| `pulse-api/src/pulse/models/experiment.py` | .py | EXP-001 |
| `pulse-api/src/pulse/models/performance_event.py` | .py | EXP-001 |
| `pulse-api/src/pulse/models/prompt_version.py` | .py | EXP-001 |
| `pulse-api/src/pulse/db/migrations/versions/003_add_experimentation_schema.py` | .py | EXP-001 |
| `pulse-api/src/pulse/core/experiment/assignment.py` | .py | EXP-002 |
| `pulse-api/src/pulse/core/experiment/statistics.py` | .py | EXP-003 |
| `pulse-api/src/pulse/services/experiment_service.py` | .py | EXP-004 |
| `pulse-api/src/pulse/core/experiment/results.py` | .py | EXP-004 |
| `pulse-api/src/pulse/core/experiment/tracking.py` | .py | EXP-004 |
| `pulse-api/src/pulse/integrations/analytics/base.py` | .py | EXP-005 |
| `pulse-api/src/pulse/integrations/analytics/segment.py` | .py | EXP-005 |
| `pulse-api/src/pulse/integrations/analytics/ga4.py` | .py | EXP-005 |
| `pulse-api/src/pulse/integrations/analytics/mixpanel.py` | .py | EXP-005 |
| `pulse-api/src/pulse/services/analytics_integration_service.py` | .py | EXP-005 |
| `pulse-api/src/pulse/api/v1/experiments.py` | .py | EXP-006 |
| `pulse-api/src/pulse/api/v1/performance.py` | .py | EXP-006 |
| `pulse-api/src/pulse/api/v1/prompt_versions.py` | .py | EXP-006 |
| `pulse-api/src/pulse/api/schemas/experiment.py` | .py | EXP-006 |
| `pulse-api/src/pulse/api/schemas/performance.py` | .py | EXP-006 |

**Backend — pulse-worker (Python)**

| File Path | Type | Owner Task |
|---|---|---|
| `pulse-worker/pyproject.toml` | .toml | INFRA-001 |
| `pulse-worker/src/pulse_worker/__init__.py` | .py | INFRA-001 |
| `pulse-worker/src/pulse_worker/main.py` | .py | INFRA-001 |
| `pulse-worker/src/pulse_worker/consumer.py` | .py | CONTENT-003 |
| `pulse-worker/src/pulse_worker/tasks/generation_task.py` | .py | CONTENT-003 |

**Backend — pulse-scheduler (Python)**

| File Path | Type | Owner Task |
|---|---|---|
| `pulse-scheduler/pyproject.toml` | .toml | INFRA-001 |
| `pulse-scheduler/src/pulse_scheduler/__init__.py` | .py | INFRA-001 |
| `pulse-scheduler/src/pulse_scheduler/main.py` | .py | INT-005 |
| `pulse-scheduler/src/pulse_scheduler/webhook_dispatcher.py` | .py | INT-003 |
| `pulse-scheduler/src/pulse_scheduler/jobs/cache_cleanup.py` | .py | INT-005 |
| `pulse-scheduler/src/pulse_scheduler/jobs/vault_writeback.py` | .py | INT-005 |
| `pulse-scheduler/src/pulse_scheduler/jobs/analytics_aggregation.py` | .py | INT-004 |
| `pulse-scheduler/src/pulse_scheduler/jobs/experiment_results.py` | .py | EXP-007 |
| `pulse-scheduler/src/pulse_scheduler/jobs/performance_aggregation.py` | .py | EXP-007 |
| `pulse-scheduler/src/pulse_scheduler/jobs/analytics_sync.py` | .py | EXP-007 |

**Frontend — pulse-ui (TypeScript/React)**

| File Path | Type | Owner Task |
|---|---|---|
| `pulse-ui/package.json` | .json | INFRA-001 |
| `pulse-ui/vite.config.ts` | .ts | INFRA-001 |
| `pulse-ui/src/main.tsx` | .tsx | INFRA-001 |
| `pulse-ui/src/App.tsx` | .tsx | UI-001 |
| `pulse-ui/src/layouts/MainLayout.tsx` | .tsx | UI-001 |
| `pulse-ui/src/components/Sidebar.tsx` | .tsx | UI-001 |
| `pulse-ui/src/components/Header.tsx` | .tsx | UI-001 |
| `pulse-ui/src/auth/AuthProvider.tsx` | .tsx | UI-001 |
| `pulse-ui/src/auth/ProtectedRoute.tsx` | .tsx | UI-001 |
| `pulse-ui/src/api/client.ts` | .ts | UI-001 |
| `pulse-ui/src/api/endpoints.ts` | .ts | UI-001 |
| `pulse-ui/src/types/index.ts` | .ts | UI-001 |
| `pulse-ui/src/hooks/useAuth.ts` | .ts | UI-001 |
| `pulse-ui/src/hooks/useApi.ts` | .ts | UI-001 |
| `pulse-ui/src/pages/Dashboard.tsx` | .tsx | UI-002 |
| `pulse-ui/src/pages/Generate.tsx` | .tsx | UI-002 |
| `pulse-ui/src/components/GenerationForm.tsx` | .tsx | UI-002 |
| `pulse-ui/src/components/MarketSelector.tsx` | .tsx | UI-002 |
| `pulse-ui/src/components/StreamingOutput.tsx` | .tsx | UI-002 |
| `pulse-ui/src/components/ContentCard.tsx` | .tsx | UI-002 |
| `pulse-ui/src/components/ConfidenceBadge.tsx` | .tsx | UI-002 |
| `pulse-ui/src/pages/ContentList.tsx` | .tsx | UI-003 |
| `pulse-ui/src/pages/ContentDetail.tsx` | .tsx | UI-003 |
| `pulse-ui/src/pages/BulkJobs.tsx` | .tsx | UI-003 |
| `pulse-ui/src/components/ContentFilters.tsx` | .tsx | UI-003 |
| `pulse-ui/src/components/VersionHistory.tsx` | .tsx | UI-003 |
| `pulse-ui/src/components/ReviewPanel.tsx` | .tsx | UI-003 |
| `pulse-ui/src/components/JobProgress.tsx` | .tsx | UI-003 |
| `pulse-ui/src/components/FileUpload.tsx` | .tsx | UI-003 |
| `pulse-ui/src/pages/Settings.tsx` | .tsx | UI-004 |
| `pulse-ui/src/pages/Analytics.tsx` | .tsx | UI-004 |
| `pulse-ui/src/pages/BrandVoices.tsx` | .tsx | UI-004 |
| `pulse-ui/src/components/ApiKeyManager.tsx` | .tsx | UI-004 |
| `pulse-ui/src/components/WebhookConfig.tsx` | .tsx | UI-004 |
| `pulse-ui/src/components/LLMProviderConfig.tsx` | .tsx | UI-004 |
| `pulse-ui/src/components/UsageChart.tsx` | .tsx | UI-004 |
| `pulse-ui/src/components/BrandVoiceEditor.tsx` | .tsx | UI-004 |
| `pulse-ui/src/pages/Experiments.tsx` | .tsx | EXP-008 |
| `pulse-ui/src/pages/ExperimentDetail.tsx` | .tsx | EXP-008 |
| `pulse-ui/src/pages/ModelComparison.tsx` | .tsx | EXP-008 |
| `pulse-ui/src/components/ExperimentForm.tsx` | .tsx | EXP-008 |
| `pulse-ui/src/components/VariantEditor.tsx` | .tsx | EXP-008 |
| `pulse-ui/src/components/ResultsChart.tsx` | .tsx | EXP-008 |
| `pulse-ui/src/components/StatisticalBadge.tsx` | .tsx | EXP-008 |
| `pulse-ui/src/components/SampleSizeEstimator.tsx` | .tsx | EXP-008 |

**Deployment & Configuration**

| File Path | Type | Owner Task |
|---|---|---|
| `pulse-api/Dockerfile` | .dockerfile | UI-005 |
| `pulse-worker/Dockerfile` | .dockerfile | UI-005 |
| `pulse-scheduler/Dockerfile` | .dockerfile | UI-005 |
| `pulse-ui/Dockerfile` | .dockerfile | UI-005 |
| `deploy/docker-compose.yml` | .yml | UI-005 |
| `deploy/docker-compose.airgap.yml` | .yml | UI-005 |
| `deploy/helm/Chart.yaml` | .yaml | UI-005 |
| `deploy/helm/values.yaml` | .yaml | UI-005 |
| `deploy/helm/templates/deployment-api.yaml` | .yaml | UI-005 |
| `deploy/helm/templates/deployment-worker.yaml` | .yaml | UI-005 |
| `deploy/helm/templates/deployment-scheduler.yaml` | .yaml | UI-005 |
| `deploy/helm/templates/deployment-ui.yaml` | .yaml | UI-005 |
| `deploy/helm/templates/service.yaml` | .yaml | UI-005 |
| `deploy/helm/templates/ingress.yaml` | .yaml | UI-005 |
| `deploy/helm/templates/configmap.yaml` | .yaml | UI-005 |
| `deploy/helm/templates/secret.yaml` | .yaml | UI-005 |
| `.github/workflows/ci.yml` | .yml | UI-005 |
| `.github/workflows/deploy.yml` | .yml | UI-005 |

**Tests**

| File Path | Type | Owner Task |
|---|---|---|
| `pulse-api/tests/conftest.py` | .py | INFRA-007 |
| `pulse-api/tests/integration/test_database.py` | .py | INFRA-007 |
| `pulse-api/tests/integration/test_auth.py` | .py | INFRA-007 |
| `pulse-api/tests/integration/test_rbac.py` | .py | INFRA-007 |
| `pulse-api/tests/integration/test_tenant_isolation.py` | .py | INFRA-007 |
| `pulse-api/tests/integration/test_health.py` | .py | INFRA-007 |
| `pulse-api/tests/integration/test_rate_limiting.py` | .py | INFRA-007 |
| `pulse-api/tests/docker-compose.test.yml` | .yml | INFRA-007 |

### 7.2 File Ownership Rules

- **No file is created by multiple tasks.** Each file has exactly one owner task.
- **Shared modules** (e.g., config.py, events.py) are created once by the earliest task that needs them; later tasks import but don't modify.
- **Test files** are owned by the test task (INFRA-007 for infrastructure; each epic should add its own test files as follow-up).

---

## 8. Test Task Mapping

### 8.1 Unit Tests (per functional task)

| Functional Task | Unit Test File | Key Test Cases |
|---|---|---|
| INFRA-003 (Auth) | `tests/unit/test_auth.py` | JWT decode valid/expired/malformed; API key hash match; RBAC matrix |
| INFRA-004 (Redis) | `tests/unit/test_cache.py` | Cache hit/miss; TTL expiration; namespace isolation |
| GEN-001 (LLM Base) | `tests/unit/test_llm_types.py` | LLMResponse construction; normalizer for each provider format |
| GEN-002 (Adapters) | `tests/unit/test_adapters.py` | Each adapter: request formatting, response parsing, error handling |
| GEN-003 (Router) | `tests/unit/test_router.py` | Circuit breaker states; fallback chain; health tracking |
| GEN-004 (Cultural) | `tests/unit/test_cultural.py` | Dimension calculation for 5+ markets; directive generation; conflict resolution |
| GEN-005 (Prompt) | `tests/unit/test_prompt_composer.py` | Template substitution; token budget truncation; prompt hash determinism |
| GEN-006 (Quality) | `tests/unit/test_quality.py` | Score components; flag thresholds; terminology check; grounding check |
| GEN-007 (Orchestrator) | `tests/unit/test_orchestrator.py` | Pipeline step execution; cache hit path; error paths |
| CONTENT-001 (Content) | `tests/unit/test_content_service.py` | CRUD operations; state machine transitions; version creation |
| CONTENT-002 (Export) | `tests/unit/test_export.py` | Each format renderer output validation |
| CONTENT-003 (Bulk) | `tests/unit/test_bulk.py` | CSV parsing; task decomposition; progress tracking |
| INT-001 (Vault) | `tests/unit/test_vault.py` | Client request formatting; cache behavior; fallback on timeout |
| INT-003 (Webhooks) | `tests/unit/test_webhooks.py` | HMAC signing; retry schedule; dead-letter handling |
| EXP-001 (Experiment Models) | `tests/unit/test_experiment_models.py` | ORM model creation; partitioning; RLS policies |
| EXP-002 (Assignment) | `tests/unit/test_assignment.py` | Deterministic hashing; cache hit/miss; traffic allocation within 1% |
| EXP-003 (Statistics) | `tests/unit/test_statistics.py` | Chi-squared results match scipy; effect size; Bayesian probability |
| EXP-004 (Experiment Service) | `tests/unit/test_experiment_service.py` | Lifecycle state machine; variant generation; winner promotion |
| EXP-005 (Analytics Connectors) | `tests/unit/test_analytics_connectors.py` | Each connector normalize; webhook signature verification |
| EXP-006 (Experiment API) | `tests/unit/test_experiment_api.py` | All 15 endpoints; workspace scoping; batch ingestion |

### 8.2 Integration Tests

| Test File | Scope | Inputs | Expected Outputs |
|---|---|---|---|
| `test_database.py` | Schema + RLS | Apply migrations; run cross-workspace queries | Tables created; cross-workspace queries return empty |
| `test_auth.py` | Auth flows | JWT + API key requests | Correct 200/401/403 responses |
| `test_rbac.py` | Permission matrix | Each role × each action | Correct allow/deny per TSD §11.2 |
| `test_tenant_isolation.py` | Multi-tenancy | Two workspaces, cross-access attempts | Blocked at DB level |
| `test_generation_e2e.py` | Full pipeline | Generation request → LLM mock → response | Content created with correct metadata |
| `test_bulk_job_e2e.py` | Bulk lifecycle | Upload CSV → process → complete | All items generated; progress tracked |
| `test_fallback_e2e.py` | LLM failover | Primary fails → secondary succeeds | Generation succeeds via fallback |
| `test_cultural_e2e.py` | Cultural adaptation | Generate for 5 markets | Different cultural directives applied |
| `test_vault_integration.py` | Vault connector | Retrieve knowledge; semantic search | Correct content returned; cache populated |
| `test_experiment_e2e.py` | Full experiment lifecycle | Create → start → ingest events → compute results → promote | Winner determined with statistical confidence |
| `test_analytics_sync_e2e.py` | Analytics connector sync | Push experiment metadata to Segment; receive events back | PerformanceEvents ingested and correlated |

### 8.3 End-to-End Tests

| Scenario | Steps | Success Criteria |
|---|---|---|
| Full generation flow | API request → generation → quality → persist → retrieve | Content retrievable via GET with correct metadata |
| Bulk job lifecycle | Upload → process → progress → complete → export | All items generated; export downloadable |
| Cultural adaptation | Generate for ja-JP, de-DE, pt-BR, ko-KR, ar-SA | Each output reflects market-specific directives |
| Failure recovery | Kill primary LLM provider → generation continues | Fallback activates; no data loss |
| Air-gapped mode | No outbound network → local Ollama → generation | Content generated using local model |
| Multi-tenant isolation | Two workspaces; verify no cross-access | RLS blocks all cross-workspace queries |
| Experiment lifecycle | Create experiment → generate variants → start → ingest events → compute results | Winner determined with >95% confidence; promote_winner() sets 100% allocation |
| A/B test variant assignment | Same visitor returns same variant; 10,000 assignments match traffic allocation within 1% | Deterministic hashing; Redis cache hit <5ms |
| Analytics integration | Push experiment metadata to Segment → receive performance events | Events normalized to internal format; correlated with experiment |
| Per-locale analysis | Run experiment across 3 markets → compute per-locale statistics | Each locale has independent conversion rate and significance |

---

## 9. Definition of Done (Global)

### 9.1 System-Wide Completion Criteria

The Pulse system is considered **complete** when ALL of the following are true:

**API Completeness:**
- [ ] All 15+ API endpoints from TSD §5 implemented and returning correct responses
- [ ] All endpoints authenticated (JWT or API key)
- [ ] All endpoints workspace-scoped (tenant isolation verified)
- [ ] Rate limiting enforced on all endpoints
- [ ] Error responses follow standard envelope format
- [ ] OpenAPI documentation auto-generated and accurate

**Data Model Consistency:**
- [ ] All 12 entities from TSD §4 implemented as SQLAlchemy models
- [ ] All indexes, constraints, and partitioning match TSD specification
- [ ] RLS policies applied and verified (no cross-workspace data leakage)
- [ ] Alembic migrations apply cleanly from scratch and are reversible
- [ ] Seed data (market profiles) loaded correctly

**Core Logic:**
- [ ] Generation pipeline executes end-to-end (request → LLM → quality → persist)
- [ ] Cultural adaptation produces different directives for different markets
- [ ] Quality scoring algorithm matches TSD §6.5 specification
- [ ] Generation caching works (Redis + PostgreSQL dual-layer)
- [ ] Fallback routing activates on provider failure
- [ ] Bulk jobs process correctly with pause/resume/cancel support

**Integrations:**
- [ ] Vault connector retrieves knowledge and performs semantic search
- [ ] Vault writeback pushes approved content back to Vault
- [ ] S3/MinIO storage handles file upload/download
- [ ] Webhook dispatcher delivers events with retry
- [ ] All 7 LLM provider adapters functional (at least mocked for testing)

**Frontend:**
- [ ] All pages render correctly with real API data
- [ ] Authentication flow works (OIDC → JWT → protected routes)
- [ ] Generation form submits and shows streaming output
- [ ] Content list with pagination and filters works
- [ ] Bulk job progress updates in real-time via WebSocket
- [ ] All settings pages functional (API keys, webhooks, LLM providers)

**Testing:**
- [ ] Unit test coverage > 80% line coverage
- [ ] All integration tests pass against Docker Compose test stack
- [ ] All 6 E2E scenarios pass
- [ ] No unresolved TODO or FIXME comments in production code

**Deployment:**
- [ ] `docker compose up` starts full stack successfully
- [ ] All containers pass health checks
- [ ] Helm chart deploys to Kubernetes cluster
- [ ] CI/CD pipeline runs (lint → test → build → deploy)
- [ ] Air-gapped deployment variant works with local LLM

**Experimentation Completeness:**
- [ ] All experiment API endpoints implemented and tested
- [ ] Variant assignment deterministic, matches traffic allocation within 1%
- [ ] Statistical analysis validated against scipy
- [ ] At least one analytics connector (Segment) working end-to-end
- [ ] Experiment results dashboard displays correct data
- [ ] Performance events ingested and correlated with experiments
- [ ] Exposure tracking separate from assignments
- [ ] Scheduled jobs compute results hourly
- [ ] Sample size calculator functional per locale

**Observability:**
- [ ] Prometheus metrics exposed at /metrics
- [ ] Structured JSON logging with request correlation
- [ ] OpenTelemetry traces exported
- [ ] Health checks (live/ready/detailed) functional

**Security:**
- [ ] No secrets in source code or Docker images
- [ ] API keys hashed (never stored plaintext)
- [ ] TLS configured for all external communication
- [ ] Input validation on all API endpoints (Pydantic schemas)
- [ ] Prompt injection defenses in place

---

## 10. Risk & Bottleneck Identification

### 10.1 High-Complexity Tasks

| Task | Risk | Impact | Mitigation |
|---|---|---|---|
| GEN-004 (Cultural Engine) | High — Cultural accuracy is subjective; 50+ markets need correct profiles | Core IP differentiator; incorrect cultural adaptation produces unusable output | Start with 10 Tier-1 markets; validate with native speakers; iterate profiles; make profiles configurable per workspace |
| GEN-005 (Prompt Composer) | High — Prompt quality directly determines output quality | Poor prompts → poor generation → low confidence scores → user churn | Version prompts with A/B testing; build evaluation harness; iterate based on quality scores |
| GEN-007 (Orchestrator) | High — Integration point for all core components; complex error handling | Bugs here break the entire generation pipeline | Implement incrementally (single market first, then multi-market); extensive logging; comprehensive error paths |
| CONTENT-003 (Bulk Jobs) | High — Distributed system with Redis Streams, workers, checkpointing | Data loss or stuck jobs at scale | Start with small batches; test worker crash recovery; implement monitoring alerts |
| INT-001 (Vault Connector) | High — External dependency; Vault API may change or be unavailable | Generation degrades without Vault knowledge grounding | Aggressive caching; degraded mode with cached data; mock Vault for testing; contract tests in CI |
| EXP-003 (Statistical Analysis) | High — Statistical correctness is critical for experiment validity | Incorrect statistics lead to wrong business decisions | Validate against scipy; extensive edge case testing; optional Bayesian analysis for robustness |
| EXP-004 (Experiment Service) | High — Orchestrates entire experiment lifecycle integrating generation pipeline | Bugs break experiment lifecycle | Implement incrementally; extensive state machine testing; mock LLM calls in tests |
| EXP-005 (Analytics Connectors) | High — External API dependencies with different auth and payload formats | Connector failures could block performance tracking | Graceful degradation; internal tracking fallback; connector failures don't block experiments |

### 10.2 External System Dependencies

| Dependency | Risk | Mitigation |
|---|---|---|
| LLM Providers (OpenAI, Anthropic, etc.) | API changes, rate limits, outages, cost spikes | Adapter pattern isolates changes; fallback routing; generation caching reduces calls; monitor costs |
| Vault (ODW.ai) | API instability, latency, availability | Cache aggressively (5min TTL); degraded mode; contract tests; versioned API |
| PostgreSQL | Connection limits, slow queries at scale | PgBouncer; partitioned tables; query optimization; read replicas for analytics |
| Redis | Memory pressure, durability concerns | Redis Sentinel for HA; AOF + RDB persistence; monitor memory usage; fallback to PostgreSQL cache |
| S3/MinIO | Availability, credential rotation | Generation continues without storage; exports unavailable until recovery; credential rotation support |
| Analytics Platforms (Segment, GA4, Mixpanel) | API changes, rate limits, payload format changes | Connector abstraction; graceful degradation; internal tracking fallback; webhook receivers with signature verification |

### 10.3 Bottleneck Analysis

| Bottleneck | Impact | Mitigation Strategy |
|---|---|---|
| LLM API latency (5-25s) | Limits single-request throughput | Streaming responses; generation caching (est. 15-25% cost reduction); multi-model routing |
| Cultural profile maintenance | 50+ profiles need ongoing curation | Start with 10 Tier-1; make profiles workspace-customizable; community contributions |
| Bulk job processing at scale | 100K items × 5 markets = 500K LLM calls | Worker pool scaling (1-10 replicas); checkpointing; parallel market processing |
| Prompt composition CPU cost | Minor per-request but adds up at 200 rps | Pre-compiled templates; cached market profiles; O(1) assembly |
| Database writes during bulk jobs | High write volume | Batch inserts (100/transaction); partitioned tables; PgBouncer connection pooling |
| Statistical analysis computation | Computation time grows with event volume | Partitioned performance_events; efficient chi-squared implementation; <100ms for 10K events; pre-aggregated metrics |
| Analytics sync latency | External API rate limits | 15-minute sync interval; batch event ingestion (100/request); exponential backoff; graceful degradation |

### 10.4 Incremental Delivery Strategy

To mitigate risk, deliver in vertical slices:

1. **Slice 1 (MVP):** Single market generation (en-US) with one LLM provider (OpenAI), no Vault, basic quality scoring → validates core pipeline
2. **Slice 2:** Add cultural adaptation for 5 Tier-1 markets + Vault integration → validates core IP
3. **Slice 3:** Add bulk jobs + remaining LLM adapters + full quality scoring → validates scale
4. **Slice 4:** Add review workflows + webhooks + analytics → validates enterprise features
5. **Slice 5:** Add remaining 45+ market profiles + air-gapped deployment → validates completeness
6. **Slice 6:** Add experimentation (data models, assignment engine, statistics, Segment connector, experiment UI) → validates A/B testing and performance tracking

---

## 11. Output Requirements

### 11.1 Exhaustiveness Checklist

- [x] All TSD sections mapped to at least one task
- [x] All 12+ database entities have corresponding ORM model tasks (12 original + 6 experimentation)
- [x] All 15+ API endpoints have corresponding implementation tasks
- [x] All 7 LLM providers have adapter implementation tasks
- [x] All 5 export formats have renderer tasks
- [x] All 4 deployment units have Dockerfile tasks
- [x] All background job types have implementation tasks
- [x] All middleware components have implementation tasks
- [x] All caching layers have implementation tasks
- [x] All 6 experimentation entities have corresponding ORM model tasks
- [x] All experiment API endpoints (§5.17-5.31) have corresponding implementation tasks
- [x] All analytics connectors (Segment, GA4, Mixpanel) have implementation tasks
- [x] All scheduled jobs (results, aggregation, sync) have implementation tasks
- [x] Experimentation UI components have implementation tasks

### 11.2 Explicitness Standards

Every task in this TBK:
- Has a **unique hierarchical ID** (e.g., GEN-004)
- Has a **specific title** (no vague "implement X system")
- Has a **clear description** referencing TSD sections
- Has **concrete inputs** (TSD section numbers)
- Has **exact expected outputs** (file paths + descriptions)
- Has **testable acceptance criteria** (not "works correctly" but "returns 400 for invalid input")
- Has **explicit dependencies** (task IDs, not "previous tasks")
- Has **execution type** (AI-Agent, Developer, or Either)
- Has **priority** (Critical/High/Medium/Low)
- Has **effort estimate** (S/M/L)
- Has **file-level mapping** (exact paths + file types)

### 11.3 Optimization for Parallel Execution

- 6 tasks can start immediately after INFRA-001 (no other dependencies)
- 7 LLM adapters are fully independent and can be built in parallel
- Frontend tasks (UI-002 through UI-004) can proceed once API contracts (CONTENT-006 schemas) are defined
- Analytics connectors (Segment, GA4, Mixpanel) are independent of each other and can be built in parallel
- Experimentation UI (EXP-008) can proceed in parallel once experiment API contracts (EXP-006) defined
- Scheduler jobs (EXP-007) are independent of core experiment logic and can be built after service/connector completion
- Test tasks can be written alongside implementation tasks
- Deployment artifacts (UI-005) can be scaffolded early and refined as services are completed

### 11.4 Optimization for AI-Agent Autonomy

- Single-shot tasks (INFRA-001, INFRA-004, INFRA-005, INFRA-006, GEN-001, INT-002, EXP-002, EXP-003) require minimal context and can be executed fully autonomously
- Each task includes all necessary TSD section references so the agent doesn't need to search for requirements
- File paths are explicit — no ambiguity about where to create files
- Acceptance criteria are testable — agent can verify its own work by running tests
- Dependencies are explicit — agent knows exactly what must exist before starting
- Experiment tasks follow same interface-first pattern: EXP-001 (models) before EXP-002/003 (engines) before EXP-004 (service) before EXP-006 (API)

### 11.5 Minimal Rework Guarantees

- Interface-first design: GEN-001 (LLM base interface) is built before adapters, ensuring all adapters conform
- Schema-first: INFRA-002 (DB models) before services, ensuring consistent data access patterns
- Contract-first: API schemas (CONTENT-006) defined before endpoint implementation
- Test-first: Integration tests (INFRA-007) written after infrastructure, before business logic, catching issues early
- No task modifies files owned by another task (clear file ownership in §7)

---

## Appendix A: Glossary

| Term | Definition |
|---|---|
| TBK | Task Breakdown Knowledge — this document |
| TSD | Technical Specification Document — the source requirements |
| Epic | Major system area grouping related tasks |
| Vault | ODW.ai knowledge base service providing brand voice, terminology, and product knowledge |
| RLS | Row-Level Security — PostgreSQL feature for multi-tenant data isolation |
| Cultural Adaptation | Process of transforming content generation parameters based on target market cultural characteristics |
| Prompt Composer | Core IP module that assembles all context into a final LLM prompt |
| Generation Cache | Dual-layer cache (Redis + PostgreSQL) for avoiding duplicate LLM calls |
| Circuit Breaker | Pattern that prevents cascading failures by routing around unhealthy providers |
| Consumer Group | Redis Streams feature for distributed task consumption with exactly-once semantics |
| Experiment | A/B test comparing 2-5 content variants to determine statistical winner based on performance metrics |
| Variant | A single version of content within an experiment, with configurable traffic allocation |
| Assignment | Mapping of visitor to variant using deterministic hashing (SHA256) |
| Exposure | Record of when a visitor was exposed to a variant (distinct from assignment) |
| Performance Event | Metric event (conversion, engagement) correlated with experiment variants |
| Statistical Significance | Probability that observed differences between variants are not due to chance (typically >95%) |
| Effect Size | Quantitative measure of the magnitude of difference between variants (Cohen's h) |
| Bayesian Analysis | Probabilistic statistical approach using Beta-Binomial distribution for experiment analysis |
| Sample Size Calculator | Tool that computes minimum required visitors per variant to achieve statistical significance |

## Appendix B: Environment Variable Quick Reference

| Variable | Required | Default | Used By |
|---|---|---|---|
| DATABASE_URL | Yes | — | pulse-api, pulse-worker, pulse-scheduler |
| REDIS_URL | Yes | — | pulse-api, pulse-worker, pulse-scheduler |
| VAULT_BASE_URL | Yes | — | pulse-api |
| VAULT_API_TOKEN | Yes | — | pulse-api |
| OBJECT_STORAGE_ENDPOINT | Yes | — | pulse-api |
| OBJECT_STORAGE_BUCKET | Yes | — | pulse-api |
| OBJECT_STORAGE_ACCESS_KEY | Yes | — | pulse-api |
| OBJECT_STORAGE_SECRET_KEY | Yes | — | pulse-api |
| JWT_SECRET | Yes | — | pulse-api |
| API_HOST | No | 0.0.0.0 | pulse-api |
| API_PORT | No | 8000 | pulse-api |
| LOG_LEVEL | No | INFO | all services |
| ENVIRONMENT | No | development | all services |
| WORKER_CONCURRENCY | No | 5 | pulse-worker |
| MAX_BULK_JOB_SIZE | No | 100000 | pulse-api |
| GENERATION_CACHE_TTL | No | 86400 | pulse-api |
| VAULT_CACHE_TTL | No | 300 | pulse-api |
| MAX_GENERATION_TIMEOUT | No | 60 | pulse-api |
| WEBHOOK_MAX_RETRIES | No | 5 | pulse-scheduler |
| RATE_LIMIT_RPM | No | 60 | pulse-api |
| TRACING_ENABLED | No | true | pulse-api |
| TRACING_SAMPLE_RATE | No | 0.01 | pulse-api |

## Appendix C: Supported Content Types

| Content Type | Description | Template |
|---|---|---|
| blog_post | Long-form article (500-3000 words) | blog_post.py |
| social_post | Short social media post (50-300 words) | social_post.py |
| email_campaign | Marketing email with CTA (200-1000 words) | email_campaign.py |
| product_description | E-commerce product copy (50-300 words) | product_description.py |
| ad_copy | Advertisement text (20-100 words) | ad_copy.py |
| landing_page | Web page copy (500-2000 words) | landing_page.py |
| press_release | Formal press announcement (300-800 words) | press_release.py |
| newsletter | Periodic update email (300-1500 words) | newsletter.py |
| video_script | Video narration script (200-1000 words) | video_script.py |
| podcast_outline | Podcast episode structure (300-1000 words) | podcast_outline.py |

## Appendix D: Supported LLM Providers

| Provider | Adapter File | Auth Method | Streaming | Local/Cloud |
|---|---|---|---|---|
| OpenAI | openai.py | Bearer token | ✓ (SSE) | Cloud |
| Anthropic | anthropic.py | x-api-key header | ✓ (SSE) | Cloud |
| Mistral | mistral.py | Bearer token | ✓ (SSE) | Cloud |
| Ollama | ollama.py | None (local) | ✓ (streaming) | Local |
| vLLM | vllm.py | None (local) | ✓ (SSE) | Local |
| Azure OpenAI | azure_openai.py | API key / AAD | ✓ (SSE) | Cloud |
| AWS Bedrock | bedrock.py | AWS IAM | ✓ (event stream) | Cloud |

---

*End of Task Breakdown Knowledge Document*
