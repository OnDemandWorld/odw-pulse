# Pulse — System Architecture Document

**Product:** Pulse (ODW.ai Suite Module)
**Document Version:** 1.0
**Date:** 2026-06-23
**Status:** Draft
**Author:** Architecture Team

---

## 1. Architecture Overview

### 1.1 Purpose

Pulse is a multilingual content generation and localization module within the ODW.ai suite. It produces culturally-adapted marketing and business content across 50+ languages, grounded in the customer's own knowledge base via Vault integration. The system supports self-hosted, model-agnostic deployment to ensure infrastructure sovereignty.

### 1.2 Architectural Style

Pulse adopts a **modular monolith with asynchronous job processing** — a deliberate hybrid that balances operational simplicity for self-hosted deployments against the scalability requirements of bulk generation workloads.

The architecture decomposes into:

- **Synchronous request path** — single content generation, API calls, UI interactions (REST API → service → response)
- **Asynchronous job path** — bulk generation, long-running operations (API → job queue → worker pool → results)
- **Event-driven side effects** — webhooks, audit logging, analytics, Vault synchronization

### 1.3 Justification & Trade-offs

| Decision | Rationale | Trade-off Accepted |
|---|---|---|
| Modular monolith over microservices | Self-hosted customers need simple deployment (single Docker Compose or Helm chart). Microservices add operational complexity (service mesh, distributed tracing overhead, multiple deployment units) that contradicts the sovereignty and simplicity goals. | Monolith limits independent scaling of individual components. Mitigated by internal module boundaries that allow future extraction if needed. |
| Async job queue for bulk operations | Bulk jobs (100K+ content pieces) must support pause/resume/cancel, progress tracking, and checkpointing. Synchronous processing cannot meet these requirements. | Adds infrastructure dependency (message queue). Mitigated by using Redis Streams (already required for caching) rather than a separate Kafka deployment for v1.0. |
| Adapter pattern for LLM backends | Model-agnostic requirement demands clean abstraction. Adapters allow adding new providers without modifying core generation logic. | Abstraction layer adds latency (~2-5ms per call) and prevents deep optimization for any single model. Accepted as necessary cost of flexibility. |
| Vault as external dependency rather than embedded | Pulse is a suite module by design. Embedding knowledge management would duplicate Vault's capabilities and create maintenance burden. | Creates hard dependency on Vault availability. Mitigated by defining a clear Vault API contract with a minimal fallback mode (local brand voice config) for evaluation scenarios. |
| PostgreSQL as primary data store | Mature, well-supported, excellent multi-tenancy support via row-level security, strong JSON support for flexible metadata, and customers are comfortable operating it. | Not purpose-built for vector search (needed for Vault RAG). Mitigated by using pgvector extension for v1.0; dedicated vector DB considered for v2.0 if scale demands it. |

---

## 2. High-Level System Components

### 2.1 Component Map

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          CLIENT LAYER                                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────────┐  │
│  │   Web UI     │  │  REST API    │  │  SDK (Python, JS/TS)         │  │
│  │  (React SPA) │  │  Consumers   │  │  (Thin wrappers over REST)   │  │
│  └──────┬───────┘  └──────┬───────┘  └──────────────┬───────────────┘  │
└─────────┼──────────────────┼─────────────────────────┼──────────────────┘
          │                  │                         │
┌─────────┼──────────────────┼─────────────────────────┼──────────────────┐
│         ▼                  ▼                         ▼    PLATFORM LAYER │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                    API Gateway (Platform)                         │   │
│  │         Auth · Rate Limiting · Routing · TLS Termination          │   │
│  └─────────────────────────────┬────────────────────────────────────┘   │
└────────────────────────────────┼────────────────────────────────────────┘
                                 │
┌────────────────────────────────┼────────────────────────────────────────┐
│                                ▼                    PULSE CORE           │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                     Pulse Application Server                      │   │
│  │  ┌─────────────┐ ┌──────────────┐ ┌────────────┐ ┌───────────┐  │   │
│  │  │  Content    │ │  Generation  │ │  Cultural  │ │  Quality  │  │   │
│  │  │  Management │ │  Orchestrator│ │  Adaptation│ │  Scoring  │  │   │
│  │  │  Module     │ │              │ │  Engine    │ │  Engine   │  │   │
│  │  └─────────────┘ └──────────────┘ └────────────┘ └───────────┘  │   │
│  │  ┌─────────────┐ ┌──────────────┐ ┌────────────┐ ┌───────────┐  │   │
│  │  │  Bulk Job   │ │  Review &    │ │  Tenant    │ │  Analytics│  │   │
│  │  │  Manager    │ │  Workflow    │ │  Isolation │ │  & Audit  │  │   │
│  │  └─────────────┘ └──────────────┘ └────────────┘ └───────────┘  │   │
│  │  ┌─────────────┐ ┌──────────────┐                                │   │
│  │  │Experimentat.│ │  Analytics   │                                │   │
│  │  │   Engine    │ │ Integration  │                                │   │
│  │  └─────────────┘ └──────────────┘                                │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                        │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                    LLM Abstraction Layer                          │   │
│  │  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌─────────────────┐  │   │
│  │  │  Model    │ │  Prompt   │ │  Fallback │ │  Multi-Model    │  │   │
│  │  │  Adapters │ │  Composer │ │  Router   │ │  Routing        │  │   │
│  │  └───────────┘ └───────────┘ └───────────┘ └─────────────────┘  │   │
│  └──────────────────────────────────────────────────────────────────┘   │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
┌────────────────────────────────┼────────────────────────────────────────┐
│                                ▼              INTEGRATION LAYER         │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────────────┐   │
│  │   Vault    │ │  LLM       │ │  Object    │ │  Webhook           │   │
│  │  Connector │ │  Providers │ │  Storage   │ │  Dispatcher        │   │
│  │            │ │  (OpenAI,  │ │  (S3/      │ │                    │   │
│  │            │ │  Anthropic,│ │   MinIO)   │ │                    │   │
│  │            │ │  Mistral,  │ │            │ │                    │   │
│  │            │ │  Ollama,   │ │            │ │                    │   │
│  │            │ │  vLLM)     │ │            │ │                    │   │
│  └────────────┘ └────────────┘ └────────────┘ └────────────────────┘   │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐                          │
│  │  Segment   │ │  Google    │ │  Mixpanel  │                          │
│  │  Connector │ │  Analytics │ │  Connector │                          │
│  │ (P0: event │ │  Connector │ │            │                          │
│  │  router →  │ │  (GA4)     │ │            │                          │
│  │  100+ dest)│ │            │ │            │                          │
│  └────────────┘ └────────────┘ └────────────┘                          │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
┌────────────────────────────────┼────────────────────────────────────────┐
│                                ▼               DATA LAYER               │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────────────┐   │
│  │ PostgreSQL │ │   Redis    │ │  Job Queue │ │  Vector Index      │   │
│  │ (+pgvector)│ │  (Cache +  │ │  (Redis    │ │  (pgvector ext.)   │   │
│  │            │ │   Streams) │ │   Streams) │ │                    │   │
│  └────────────┘ └────────────┘ └────────────┘ └────────────────────┘   │
│  ┌────────────┐                                                        │
│  │ Experiment │                                                        │
│  │ Tables     │                                                        │
│  │(partitioned│                                                        │
│  │  tables)   │                                                        │
│  └────────────┘                                                        │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Component Definitions

#### Content Management Module
- **Responsibility:** CRUD operations on content pieces, version control, content lifecycle state management (draft → review → approved/rejected/archived), export in multiple formats.
- **Inputs:** User requests (create, edit, approve, export), bulk import data.
- **Outputs:** Persisted content records, version history, exported files.
- **Technology:** Internal module within the application server; PostgreSQL for persistence.

#### Generation Orchestrator
- **Responsibility:** Coordinates the end-to-end generation pipeline — retrieves Vault context, composes prompts, dispatches to LLM, applies post-processing (terminology enforcement, confidence scoring), returns results.
- **Inputs:** Generation request (content/brief, target markets, tone, parameters).
- **Outputs:** Generated content with metadata (confidence score, flags, Vault sources used, model used).
- **Technology:** Internal module; coordinates across Cultural Adaptation Engine, LLM Abstraction Layer, and Vault Connector.

#### Cultural Adaptation Engine
- **Responsibility:** Applies market-specific cultural transformation rules to generation parameters. Encodes cultural dimensions (formality, directness, individualism, humor, persuasion style) per market profile. Transforms prompts to produce culturally-native output rather than translated output.
- **Inputs:** Target market code, source content/brief, brand voice profile, cultural adaptation profile.
- **Outputs:** Culturally-optimized prompt parameters and generation instructions.
- **Technology:** Rule-based engine with configurable market profiles stored in PostgreSQL; profiles are versioned and editable.

#### Quality Scoring Engine
- **Responsibility:** Evaluates generated output quality post-generation. Produces confidence scores (0-100%), flags content for human review (sensitive topics, terminology violations, low confidence), and detects potential hallucinations (claims not grounded in Vault).
- **Inputs:** Generated content, Vault sources referenced, terminology glossary, market profile.
- **Outputs:** Confidence score, flag list, quality metadata.
- **Technology:** Heuristic-based scoring (terminology compliance, length conformance, Vault grounding verification) combined with optional LLM-as-judge evaluation for higher-tier deployments.

#### Bulk Job Manager
- **Responsibility:** Manages long-running bulk generation jobs — accepts input (CSV/XLSX), decomposes into individual generation tasks, dispatches to worker pool, tracks progress, supports pause/resume/cancel, handles checkpointing for durability.
- **Inputs:** Bulk input file, generation configuration, target markets.
- **Outputs:** Job status updates, progress events, completed content pieces, summary report.
- **Technology:** Redis Streams for job queue; PostgreSQL for job state; worker pool pattern with configurable concurrency.

#### Review & Workflow Module
- **Responsibility:** Manages content review workflows — side-by-side comparison, inline editing, annotation, approval chains, feedback collection.
- **Inputs:** Reviewer actions (approve, reject, request changes, edit, feedback).
- **Outputs:** Updated content state, feedback records, audit entries.
- **Technology:** Internal module; PostgreSQL for state; WebSocket for real-time UI updates.

#### Tenant Isolation Module
- **Responsibility:** Enforces strict data separation between workspaces. All data access is scoped to the authenticated workspace. Prevents cross-workspace data leakage at the application and database level.
- **Inputs:** Authenticated request with workspace context.
- **Outputs:** Scoped data access, workspace-filtered queries.
- **Technology:** PostgreSQL row-level security (RLS) policies; application-level workspace context injection on every query.

#### LLM Abstraction Layer
- **Responsibility:** Provides a unified interface to multiple LLM backends. Handles adapter registration, request translation, response normalization, streaming support, and error handling.
- **Inputs:** Normalized generation request (prompt, parameters, model selection).
- **Outputs:** Normalized LLM response (generated text, token usage, latency metrics).
- **Technology:** Adapter pattern with provider-specific implementations (OpenAI, Anthropic, Mistral, Ollama, vLLM, Azure OpenAI, AWS Bedrock).

#### Prompt Composer
- **Responsibility:** Constructs culturally-adapted prompts by combining: brand voice profile, market adaptation profile, terminology glossary, Vault-retrieved knowledge, content type template, tone controls, and user instructions. This is the core IP of Pulse.
- **Inputs:** All contextual inputs from Vault and configuration.
- **Outputs:** Final prompt payload ready for LLM consumption.
- **Technology:** Template engine with variable substitution; prompt versioning and A/B testing support.

#### Fallback Router
- **Responsibility:** Manages model selection and failover. Routes generation requests to configured primary model; on failure or rate-limiting, automatically switches to secondary. Tracks model health and performance metrics.
- **Inputs:** Generation request, model configuration, model health status.
- **Outputs:** Routed request to appropriate LLM adapter.
- **Technology:** Circuit breaker pattern; health check polling; configurable fallback chains.

#### Vault Connector
- **Responsibility:** Interfaces with ODW.ai Vault to retrieve knowledge (product info, brand voice, terminology, product catalogs), perform semantic search for relevant context, and write approved content back to Vault.
- **Inputs:** Query context (content type, product references, brand voice ID).
- **Outputs:** Relevant Vault content, brand voice profile, terminology entries, content lineage records.
- **Technology:** REST API client for Vault; semantic search via Vault's embedding endpoint; local caching for frequently-accessed knowledge.

#### Webhook Dispatcher
- **Responsibility:** Delivers event notifications to configured webhook URLs for content lifecycle events (generated, reviewed, approved, exported). Implements retry with exponential backoff.
- **Inputs:** Internal domain events.
- **Outputs:** HTTP POST requests to configured endpoints.
- **Technology:** Async event processor; dead-letter queue for failed deliveries; delivery history tracking.

#### Analytics & Audit Module
- **Responsibility:** Tracks usage metrics (content volume, languages, models, confidence scores), maintains immutable audit log of all user actions, provides reporting dashboards.
- **Inputs:** Domain events from all modules.
- **Outputs:** Usage reports, audit trail, cost attribution data.
- **Technology:** Event collection → PostgreSQL (structured); Prometheus metrics export for operational monitoring.

#### Experimentation Engine
- **Responsibility:** Manages the full experiment lifecycle — creation, variant assignment (deterministic hashing), performance tracking, statistical analysis (chi-squared + Bayesian), and winner determination. Coordinates with Generation Orchestrator for variant generation and with Analytics Integration for performance data.
- **Inputs:** Experiment creation requests, performance events (internal + external), variant assignment queries, exposure events.
- **Outputs:** Experiment configurations, variant assignments, exposure tracking, statistical results, winner recommendations.
- **Technology:** Internal module within pulse-api; PostgreSQL for experiment state; statistical computation in Python (scipy/numpy); Redis for real-time assignment caching.
- **Key Design Principle:** Three-layer architecture (Assignment Service + Event Pipeline + Analysis Engine) following patterns from Netflix XP, Uber XP, and Airbnb Minerva.

#### Analytics Integration Layer
- **Responsibility:** Bidirectional bridge between Pulse and external analytics platforms. Segment acts as central event router (write once, send to 100+ destinations). Direct connectors for GA4, Mixpanel. Receives performance events, normalizes to internal format, correlates with experiments.
- **Inputs:** Webhooks from analytics tools, API polling responses, internal experiment events.
- **Outputs:** Normalized performance events, experiment metadata forwarded to analytics tools.
- **Technology:** Connector pattern (similar to LLM adapters); webhook receiver in API server; polling jobs in scheduler; Redis for event buffering.
- **Key Integration:** Segment as P0 — gives access to 100+ downstream destinations with one integration.

---

## 3. Component Interaction & Data Flow

### 3.1 Single Content Generation Flow (Synchronous)

```
User → Web UI → API Gateway → Pulse Application Server
  │
  ├─ 1. Auth middleware validates JWT, extracts workspace context
  ├─ 2. Content Management Module creates draft content record
  ├─ 3. Generation Orchestrator activated:
  │     ├─ 3a. Vault Connector retrieves: brand voice profile, terminology
  │     │       glossary, relevant product knowledge (semantic search)
  │     ├─ 3b. Cultural Adaptation Engine loads market profile, computes
  │     │       cultural transformation parameters
  │     ├─ 3c. Prompt Composer assembles final prompt from all inputs
  │     ├─ 3d. Fallback Router selects model per configuration
  │     ├─ 3e. LLM Abstraction Layer dispatches to model adapter
  │     ├─ 3f. Response received → Quality Scoring Engine evaluates
  │     ├─ 3g. Terminology enforcement pass (post-processing)
  │     └─ 3h. Content record updated with generated text, score, flags
  ├─ 4. Response returned to UI (streaming or complete)
  └─ 5. Async: Audit event emitted, analytics updated
```

**Latency budget:** Vault retrieval (<500ms) + Prompt composition (<100ms) + LLM generation (<25s for API models) + Quality scoring (<500ms) = <30s total target.

### 3.2 Bulk Generation Flow (Asynchronous)

```
User → Web UI → API Gateway → Pulse Application Server
  │
  ├─ 1. Bulk Job Manager receives input file, validates structure
  ├─ 2. Job record created (status: pending), total items calculated
  ├─ 3. Input decomposed into individual generation tasks
  ├─ 4. Tasks pushed to Redis Streams job queue
  ├─ 5. Job status transitions to "processing"
  ├─ 6. Worker pool consumes tasks:
  │     ├─ Each worker runs the full generation pipeline (3a-3h above)
  │     ├─ Completed pieces written to PostgreSQL
  │     ├─ Progress counter incremented atomically
  │     └─ Progress events emitted (WebSocket to UI, webhook if configured)
  ├─ 7. On completion: job status → "completed", summary computed
  ├─ 8. User notified; results available for review/export
  └─ 9. Pause: workers stop consuming; Resume: consumption continues
       Cancel: remaining tasks discarded; partial results preserved
```

**Checkpointing:** Every 10 completed items, job progress is persisted to PostgreSQL. On worker failure, unacknowledged tasks are redelivered by Redis Streams consumer group.

### 3.3 Failure Scenarios

| Failure | Detection | Response |
|---|---|---|
| LLM API timeout (>60s) | Adapter-level timeout | Retry once with backoff; if fails, fallback router switches to secondary model |
| LLM provider outage | Circuit breaker opens (3 failures in 60s) | All requests routed to fallback model; alert emitted; user notified if no fallback configured |
| Vault unavailable | Health check failure | Generation proceeds with cached brand voice + glossary (stale but functional); alert emitted; content flagged as "generated without live Vault context" |
| Worker crash during bulk job | Redis consumer group detects unacknowledged task | Task redelivered to another worker; job progress reflects last checkpoint |
| PostgreSQL connection loss | Connection pool health check | Application returns 503; queued jobs remain in Redis; automatic reconnection with backoff |
| Object storage unavailable | S3 SDK error | Export operations fail gracefully; generated content remains in PostgreSQL; alert emitted |

### 3.4 Async vs Sync Boundaries

| Operation | Pattern | Rationale |
|---|---|---|
| Single content generation | Synchronous (with optional streaming) | User expects immediate result; <30s latency acceptable |
| Bulk generation | Asynchronous (job queue) | May take hours; user needs progress tracking and control |
| Webhook delivery | Asynchronous (event queue) | Must not block generation pipeline; retry semantics required |
| Analytics aggregation | Asynchronous (event collection) | Non-critical path; eventual consistency acceptable |
| Audit logging | Synchronous write, async aggregation | Audit entries must be durable before request completes |
| Vault synchronization | Asynchronous (eventual) | Content written back to Vault after approval; slight delay acceptable |

### 3.5 Performance Event Data Flow (3 Ingestion Paths)

**Path A: Webhook Push (Primary)**

```
External Analytics (Segment/GA4/Mixpanel) → Webhook →
  Pulse API /api/v1/performance-events/webhook/{connector} →
  Event normalizer →
  Correlate with assignment via visitor_hash →
  Store performance_event →
  Update experiment_variant rolling metrics →
  Emit metric_updated event
```

**Path B: API Polling (Supplementary)**

```
pulse-scheduler (every 15 min) →
  Query Segment/GA4/Mixpanel API →
  Fetch events since last sync →
  Normalize → Store performance_event →
  Correlate with assignments
```

**Path C: Internal Tracking (Air-gapped / Self-hosted)**

```
JavaScript snippet on customer's website →
  Posts exposure + event data to Pulse API →
  Pulse correlates via visitor_hash (no external dependencies)
```

**All paths converge:**

```
→ Store in performance_events table (partitioned weekly for write scale)
→ Update experiment_variant metrics (rolling aggregation every 5 min)
→ Hourly results computation checks for statistical significance
→ Cold storage: events older than 90 days archived to S3 (Parquet format)
```

### 3.6 The Pulse Feedback Loop Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    THE PULSE FEEDBACK LOOP                       │
│                                                                  │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐  │
│  │ GENERATE │───>│ PUBLISH  │───>│  MEASURE │───>│  LEARN   │  │
│  │          │    │          │    │          │    │          │  │
│  │ Content  │    │ Export/  │    │ Track    │    │ Update   │  │
│  │ variants │    │ API/     │    │ CTR,     │    │ cultural │  │
│  │ with     │    │ Segment  │    │ conv,    │    │ profiles │  │
│  │ different│    │ routing  │    │ engage.  │    │ + model  │  │
│  │ cultural │    │ to GA4/  │    │ per      │    │ routing  │  │
│  │ params   │    │ Mixpanel │    │ locale   │    │ per      │  │
│  │          │    │          │    │          │    │ market   │  │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘  │
│       ^                                               │          │
│       └───────────────────────────────────────────────┘          │
│                    (continuous improvement)                       │
└─────────────────────────────────────────────────────────────────┘
```

**Key principle:** This is what differentiates Pulse from every competitor. Current architecture is open-loop (content goes out, nothing comes back). The feedback loop closes this: winning variant characteristics are stored per market and influence future generation — Pulse gets better with every experiment.

---

## 4. API & Service Boundaries

### 4.1 Service Boundaries

Pulse exposes three API surfaces:

1. **Platform API** — consumed by Web UI and SDKs. Exposed through ODW.ai API Gateway. Handles content generation, management, review, and administration.
2. **Internal Vault API** — consumed by Pulse from Vault. Handles knowledge retrieval, brand voice access, terminology lookup, and content writeback.
3. **Webhook API** — emitted by Pulse to customer-configured endpoints. Handles content lifecycle event notifications.

### 4.2 Communication Patterns

| Boundary | Protocol | Pattern | Rationale |
|---|---|---|---|
| UI ↔ Pulse | REST + WebSocket | Request/response + real-time push | REST for CRUD; WebSocket for bulk job progress and streaming generation |
| SDK ↔ Pulse | REST | Request/response | Simple, universal compatibility |
| Pulse ↔ Vault | REST | Request/response | Vault is an independent service; clean API contract |
| Pulse ↔ LLM Providers | REST (HTTP) | Request/response + streaming (SSE) | All major providers support HTTP; SSE for streaming tokens |
| Pulse ↔ Job Queue | Redis protocol | Pub/sub + consumer groups | Low-latency, already required for caching |
| Pulse → Webhooks | HTTP POST | Fire-and-forget with retry | Standard webhook pattern; customer endpoints may be unreliable |
| Internal module ↔ module | In-process function calls | Synchronous | Modular monolith; no network overhead between modules |

### 4.3 API Contract Expectations

**Generation API (core endpoint):**
- `POST /api/v1/generate` — accepts content/brief, target markets, parameters; returns generated content with metadata
- `POST /api/v1/generate/bulk` — accepts file upload + configuration; returns job ID for tracking
- `GET /api/v1/jobs/{id}` — returns job status, progress, results
- `GET /api/v1/content/{id}` — returns content piece with full metadata
- `PUT /api/v1/content/{id}` — updates content (edit, status change)

**Contract principles:**
- All responses include `X-Request-ID` for tracing
- Error responses follow consistent structure: `{ error: { code, message, details } }`
- Pagination via cursor-based approach for list endpoints
- API versioning via URL path (`/api/v1/`, `/api/v2/`)
- Rate limiting headers included: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`

### 4.4 Service Decoupling Opportunities

The modular monolith design maintains clear internal boundaries that allow future extraction:

- **Cultural Adaptation Engine** could become an independent service if cultural profiles grow complex enough to warrant separate scaling and update cycles.
- **Quality Scoring Engine** could be extracted for use by other ODW.ai modules.
- **LLM Abstraction Layer** is already designed as an independent concern and could serve as shared infrastructure across the suite.
- **Bulk Job Manager** could be separated if job processing demands dedicated infrastructure distinct from the API-serving tier.

---

## 5. Data Architecture

### 5.1 Storage Strategy

| Data Type | Storage | Rationale |
|---|---|---|
| Content pieces, jobs, workspaces, users, audit logs | PostgreSQL | Relational integrity, complex queries, row-level security for multi-tenancy, JSON columns for flexible metadata |
| Brand voice profiles, market adaptation profiles, glossaries | PostgreSQL (JSON columns) | Structured enough for relational storage; JSON provides flexibility for per-market overrides |
| Vault knowledge embeddings (local cache) | pgvector extension | Avoids separate vector DB dependency for v1.0; sufficient for <10M tokens per workspace |
| Session state, rate limit counters | Redis | Sub-millisecond access; TTL-based expiration |
| Job queue, task distribution | Redis Streams | Consumer groups provide exactly-once processing semantics; durable within Redis |
| Generated content files (exports, bulk input) | S3-compatible object storage | Large binary objects; lifecycle policies for retention |
| Prompt templates, cultural adaptation rules | PostgreSQL (versioned) | Must be auditable and versioned; relatively static with periodic updates |
| Performance events (clicks, views, conversions) | PostgreSQL partitioned weekly | High write volume, time-series pattern. After 90 days → S3 Parquet for cold storage |
| Experiment assignments | PostgreSQL partitioned monthly | Immutable records, deterministic hashing means cache miss is cheap |
| Experiment exposures | PostgreSQL partitioned weekly | Separated from assignments for treatment-on-treated analysis |
| Experiment state (config, status) | PostgreSQL standard | Low volume, high consistency required |
| Real-time assignment cache | Redis (TTL = experiment duration) | Fast lookup, <5ms target |
| Rolling variant metrics | PostgreSQL materialized views | Pre-computed aggregations refreshed every 5 min |
| Statistical results | PostgreSQL JSONB | Cached results per experiment, avoids re-computation |

### 5.2 Data Ownership

| Module | Owned Data | Access Pattern |
|---|---|---|
| Content Management | Content pieces, versions, exports | Read/write by this module; read-only by Review, Analytics |
| Generation Orchestrator | Generation metadata (model used, latency, prompt hash) | Write during generation; read by Analytics |
| Bulk Job Manager | Job records, task state, progress | Write during processing; read by UI and API |
| Tenant Isolation | Workspace configuration, RLS policies | Write by Admin; enforced on all queries |
| Quality Scoring | Confidence scores, flags | Write during generation; read by Review, UI |
| Analytics & Audit | Usage metrics, audit entries | Write by event emission; read by dashboards |

### 5.3 Consistency Model

- **Strong consistency** for: content lifecycle state transitions, workspace isolation, audit log writes. These use synchronous database writes within transactions.
- **Eventual consistency** for: analytics aggregation, webhook delivery, Vault writeback, progress counters during bulk jobs. These use asynchronous event processing with acceptable delay (seconds to minutes).

### 5.4 Indexing Strategy

- **Content pieces:** Composite index on (workspace_id, status, created_at) for dashboard queries; GIN index on metadata JSON for flexible filtering; full-text search index on generated content for in-app search.
- **Bulk jobs:** Index on (workspace_id, status) for job listing; index on created_at for chronological ordering.
- **Audit logs:** Index on (workspace_id, timestamp) for compliance queries; index on (user_id, action) for user activity reports.
- **Vector embeddings:** HNSW index via pgvector for semantic similarity search during Vault retrieval.

### 5.5 Data Partitioning

- **Workspace-based partitioning** for content pieces and audit logs (partition by workspace_id hash). This ensures workspace isolation at the storage level and improves query performance for single-workspace operations.
- **Time-based partitioning** for audit logs (monthly partitions) to support retention policies and efficient pruning of expired data.
- Bulk job task data stored separately from job metadata to allow independent scaling and cleanup.

---

## 6. Scalability & Performance Design

### 6.1 Scaling Strategy

| Component | Scaling Approach | Mechanism |
|---|---|---|
| Application Server (API tier) | Horizontal | Stateless; multiple behind load balancer. Scaled based on CPU/memory and request latency. |
| Generation Workers | Horizontal | Worker pool size configurable; each worker is an independent process consuming from job queue. Scaled based on queue depth and LLM throughput. |
| PostgreSQL | Vertical (primary) + Read replicas | Vertical scaling for write throughput (generation is write-heavy). Read replicas for dashboard queries and analytics. |
| Redis | Vertical (single instance) | Sufficient for v1.0 scale. Redis Cluster considered for v2.0 if job queue volume demands it. |
| Object Storage | Horizontal (inherent) | S3-compatible storage scales inherently. No action required. |

### 6.2 Statelessness

- Application server instances are fully stateless. All session state is in Redis; all persistent state is in PostgreSQL.
- Worker processes are stateless between tasks. Job progress is checkpointed to PostgreSQL, allowing any worker to pick up any task.
- This enables zero-downtime deployments (rolling updates) and horizontal scaling without session affinity.

### 6.3 Bottleneck Identification & Mitigation

| Bottleneck | Impact | Mitigation |
|---|---|---|
| LLM API rate limits | Limits concurrent generation throughput | Multi-model routing distributes load across providers; request queuing with backpressure; customer-configurable concurrency limits |
| PostgreSQL write throughput during bulk jobs | High write volume from 100K+ content pieces | Batch inserts (100 pieces per transaction); connection pooling (PgBouncer); partitioned tables reduce index write amplification |
| Vault retrieval latency | Adds to generation latency on every request | Local cache (Redis) for frequently-accessed brand voice and glossary data; cache invalidation on Vault update events; pre-warming on workspace activation |
| Prompt composition complexity | CPU-bound prompt assembly for culturally-adapted generation | Prompt templates pre-compiled; market profiles cached in memory; composition is O(1) lookup + string assembly |
| Object storage for bulk exports | Large file generation and download | Streaming uploads to S3; presigned URLs for direct download; multipart upload for large exports |
| Performance event ingestion at scale | Millions of events/day for high-traffic experiments | Batch inserts (100 per transaction); write-ahead buffering in Redis; weekly partitioning; S3 cold storage after 90 days |
| Statistical computation for many experiments | CPU-intensive for 100+ concurrent experiments | Hourly batch (not real-time); compute only for experiments past minimum sample size; cache results in Redis |
| Variant assignment at scale | Every page view requires assignment lookup | Redis cache with deterministic hashing; cache miss falls back to recompute (<10ms) |
| Cross-locale analysis | Querying experiments across multiple markets | Pre-computed per-locale aggregations; materialized views for dashboard queries |

### 6.4 Caching Layers

| Cache | Contents | TTL | Invalidation |
|---|---|---|---|
| Redis — Brand Voice | Active brand voice profiles per workspace | 5 minutes | Vault update event; manual refresh |
| Redis — Glossary | Active terminology glossaries per workspace | 5 minutes | Glossary update event |
| Redis — Market Profiles | Cultural adaptation profiles | 1 hour | Profile update (rare) |
| Redis — Generation Cache | Hash of (prompt + model + parameters) → result | 24 hours | Content-based; identical requests served from cache |
| Redis — Rate Limit Counters | Per-API-key request counts | Window duration (1 minute) | Automatic expiration |
| Application Memory — Prompt Templates | Compiled prompt templates | Process lifetime | Deployment (new version) |

### 6.5 Load Balancing

- **API tier:** Round-robin with health checks. Sticky sessions not required (stateless).
- **Worker pool:** Pull-based (workers consume from queue). Natural load distribution — faster workers consume more tasks.
- **LLM providers:** Weighted round-robin across configured models; health-aware routing avoids degraded providers.

### 6.6 Rate Limiting & Throttling

- **Per-API-key limits:** Configurable requests per minute; separate limits for generation vs. management endpoints.
- **Per-workspace concurrency limits:** Maximum simultaneous generation requests per workspace (prevents single tenant from monopolizing workers).
- **Bulk job throttling:** Maximum concurrent bulk jobs per workspace; queue depth limits with backpressure.
- **LLM provider rate limiting:** Client-side token bucket per provider; request queuing when limits approached.

---

## 7. Reliability & Fault Tolerance

### 7.1 Failover Strategy

| Component | Failover Mechanism | RTO | RPO |
|---|---|---|---|
| Application Server | Multiple instances behind LB; failed instance removed from pool | <30s (health check interval) | Zero (stateless) |
| PostgreSQL | Streaming replication to standby; automatic failover via Patroni or cloud-managed HA | <60s | Zero (synchronous replication) or <1s (async) |
| Redis | Redis Sentinel for automatic failover to replica | <30s | <1s (async replication) |
| LLM Provider | Circuit breaker + fallback model chain; if all providers fail, jobs queue until recovery | Immediate (fallback) / Minutes (full recovery) | Zero (jobs persist in queue) |
| Object Storage | S3 provides 99.99% availability inherently; MinIO cluster for self-hosted | N/A (service-level durability) | N/A |

### 7.2 Retry Mechanisms

| Operation | Retry Strategy | Max Retries | Backoff |
|---|---|---|---|
| LLM API calls | Exponential backoff with jitter | 3 | 1s, 2s, 4s (+ jitter) |
| Vault API calls | Exponential backoff | 3 | 500ms, 1s, 2s |
| Webhook delivery | Exponential backoff | 5 | 1min, 5min, 30min, 2hr, 12hr |
| Database connections | Immediate retry with connection pool | 5 | 100ms, 200ms, 400ms, 800ms, 1.6s |
| Bulk job tasks | Re-queue on failure (Redis consumer group) | 3 | Immediate redelivery |

### 7.3 Circuit Breakers

- **LLM Provider Circuit Breaker:** Opens after 3 consecutive failures within 60 seconds. Half-open state after 30 seconds (single probe request). Closed on successful probe. Per-provider state.
- **Vault Circuit Breaker:** Opens after 5 consecutive failures within 2 minutes. Half-open after 60 seconds. When open, generation proceeds with cached context and flags output accordingly.
- **Object Storage Circuit Breaker:** Opens after 3 failures. Export operations return error; generation continues (content stored in PostgreSQL).

### 7.4 Graceful Degradation

| Scenario | Degraded Behavior |
|---|---|
| Vault unavailable | Generation proceeds with last-cached brand voice and glossary. Output flagged: "Generated without live Vault context — review recommended." |
| All LLM providers unavailable | Generation queued; user notified of delay. Bulk jobs paused with progress preserved. |
| Single LLM provider unavailable | Automatic fallback to secondary model. User notified in output metadata. |
| Quality scoring unavailable | Content generated without confidence scores. All output flagged for manual review. |
| Object storage unavailable | Generation continues; export operations unavailable until storage recovers. |
| Redis unavailable | Application falls back to direct database queries (slower); job queue unavailable (bulk jobs cannot start until Redis recovers). |

### 7.5 Single Points of Failure & Mitigation

| SPOF | Mitigation |
|---|---|
| PostgreSQL primary | Streaming replica with automatic failover (Patroni or cloud HA). Regular backups with tested restore procedure. |
| Redis primary | Sentinel-managed replica. If Redis is fully lost: API continues with degraded caching; bulk jobs require Redis restart to resume. |
| Single LLM provider | Multi-provider architecture with fallback chains. No single provider is required. |
| Application server | Horizontal scaling; no single instance is critical. |

---

## 8. Security Architecture

### 8.1 Authentication & Authorization

**Authentication:**
- **UI users:** OIDC or SAML SSO via ODW.ai platform identity provider. MFA enforced for admin roles.
- **API consumers:** API key authentication with scope-based permissions. Keys are workspace-scoped and rotatable.
- **Inter-service (Pulse ↔ Vault):** mTLS or shared JWT audience for service-to-service authentication.
- **Self-hosted deployments:** Customer configures identity provider (OIDC, SAML, LDAP). Pulse integrates via standard protocols.

**Authorization (RBAC):**

| Role | Permissions |
|---|---|
| Admin | Full workspace management, user management, configuration, all content operations |
| Editor | Create, edit, generate content; submit for review |
| Approver | Review, approve, reject content; cannot modify workspace configuration |
| Viewer | Read-only access to content and analytics |

**Multi-tenant isolation:**
- PostgreSQL row-level security (RLS) policies enforce workspace scoping on every query.
- Application middleware injects workspace_id from authenticated session into every database operation.
- Cross-workspace queries are architecturally impossible (no query path exists without workspace context).

### 8.2 Data Protection

**Encryption at rest:**
- PostgreSQL: TDE (Transparent Data Encryption) or encrypted EBS volumes (cloud) / LUKS (self-hosted).
- Redis: Encrypted at rest via encrypted volumes; in-memory by nature.
- Object storage: Server-side encryption (SSE-S3 or SSE-KMS for AWS; MinIO encryption for self-hosted).
- All encryption: AES-256.

**Encryption in transit:**
- All external communication: TLS 1.3 (API, webhooks, LLM provider calls).
- Internal communication: TLS 1.3 between all components (including Pulse ↔ Vault, Pulse ↔ PostgreSQL, Pulse ↔ Redis).
- Self-hosted: Customer provides TLS certificates; Pulse ships with Let's Encrypt automation for convenience.

### 8.3 Secrets Management

| Secret | Storage | Rotation |
|---|---|---|
| LLM API keys | HashiCorp Vault, AWS Secrets Manager, or encrypted config file (self-hosted) | Customer-managed rotation; Pulse supports hot-reload without restart |
| Database credentials | Kubernetes Secrets or environment variables | Rotation requires brief maintenance window |
| TLS certificates | cert-manager (K8s) or customer-managed | Automated renewal via ACME/Let's Encrypt |
| API keys (consumer) | PostgreSQL (hashed) | User-initiated rotation; old keys invalidated immediately |
| OIDC/SAML credentials | Kubernetes Secrets or environment variables | Rotation during IdP maintenance window |

### 8.4 API Security

- **Rate limiting:** Per-key and per-workspace limits; DDoS protection via request throttling.
- **Input validation:** All API inputs validated against schemas; content length limits; file upload size limits and type validation.
- **Prompt injection defense:** User-provided instructions are sanitized and isolated within prompt structure; system prompts are not user-modifiable; content generation does not execute arbitrary instructions from generated content.
- **Output filtering:** Generated content passes through safety filters before delivery (configurable per workspace for air-gapped deployments).

### 8.5 Threat Considerations

| Threat | Mitigation |
|---|---|
| Prompt injection (user tries to extract system prompts or bypass controls) | System/user prompt separation; input sanitization; output scanning for prompt leakage patterns |
| Data exfiltration via generated content | Content length limits; no external data fetching during generation; air-gapped mode prevents all outbound connections |
| Cross-workspace data leakage | RLS enforcement; automated isolation testing in CI; penetration testing before GA |
| LLM provider training on customer data | Contractual zero-retention guarantees; technical verification where possible; self-hosted model option eliminates risk entirely |
| Supply chain attack (compromised dependency) | Dependency scanning in CI/CD; locked dependency versions; minimal base images; signed container images |
| Credential theft (API keys, database passwords) | Secrets never logged; secrets in memory only (not persisted to disk in plaintext); short-lived tokens where possible |

---

## 9. Infrastructure & Deployment Architecture

### 9.1 Deployment Models

| Model | Target Customer | Infrastructure |
|---|---|---|
| **Self-hosted (Docker Compose)** | SMBs, small teams, simple setups | Single VM or small cluster; Docker + Docker Compose |
| **Self-hosted (Kubernetes)** | Enterprises, agencies, regulated industries | Customer's Kubernetes cluster; Helm chart deployment |
| **Self-hosted (Air-gapped)** | Highly regulated (defense, finance, government) | Isolated network; no outbound internet; local models only |
| **Cloud-hosted (ODW.ai managed)** | Customers who want sovereignty guarantees without operational burden | ODW.ai-operated dedicated infrastructure per customer |

### 9.2 Container Architecture

```
┌─────────────────────────────────────────────────────────┐
│                  Kubernetes Cluster / Docker Host        │
│                                                         │
│  ┌─────────────────────────────────────────────────┐    │
│  │  pulse-api (2+ replicas)                        │    │
│  │  - API server, content management, generation   │    │
│  │  - Resource: 2 CPU, 4GB RAM per replica         │    │
│  └─────────────────────────────────────────────────┘    │
│                                                         │
│  ┌─────────────────────────────────────────────────┐    │
│  │  pulse-worker (1-10 replicas, auto-scaled)      │    │
│  │  - Bulk job processing, background tasks        │    │
│  │  - Resource: 2 CPU, 4GB RAM per replica         │    │
│  └─────────────────────────────────────────────────┘    │
│                                                         │
│  ┌─────────────────────────────────────────────────┐    │
│  │  pulse-scheduler (1 replica)                    │    │
│  │  - Job scheduling, cleanup, maintenance tasks   │    │
│  │  - Resource: 0.5 CPU, 1GB RAM                   │    │
│  └─────────────────────────────────────────────────┘    │
│                                                         │
│  ┌──────────────┐  ┌──────────────┐                    │
│  │  PostgreSQL  │  │    Redis     │                    │
│  │  (primary +  │  │  (primary +  │                    │
│  │   replica)   │  │   replica)   │                    │
│  └──────────────┘  └──────────────┘                    │
│                                                         │
│  ┌─────────────────────────────────────────────────┐    │
│  │  Local Model Server (optional, GPU nodes)       │    │
│  │  - Ollama or vLLM serving local LLMs            │    │
│  │  - Resource: GPU instances (A100/H100/L40S)     │    │
│  └─────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
```

### 9.3 Environment Strategy

| Environment | Purpose | Infrastructure | Data |
|---|---|---|---|
| Development | Feature development, unit testing | Local Docker Compose | Synthetic test data |
| Staging | Integration testing, acceptance testing, performance testing | Mirrors production topology | Anonymized production-like data |
| Production | Customer-facing | Full HA topology | Real customer data |

### 9.4 CI/CD Approach

- **Source:** Git monorepo for Pulse; feature branches → PR → main.
- **Build:** Container images built on every merge to main. Tagged with semantic version + git SHA.
- **Test gates:** Unit tests (>80% coverage) → Integration tests → Security scan (dependency + container) → Performance benchmark (staging).
- **Deployment:** GitOps model (ArgoCD or Flux). Production deployments via rolling update with automated canary analysis (error rate, latency regression).
- **Database migrations:** Applied automatically before application deployment (migration job runs first). All migrations reversible.
- **Rollback:** Automated rollback on error rate spike (>1% 5xx) within first 5 minutes of deployment. Manual rollback available at any time.

### 9.5 Air-Gapped Deployment Specifics

- All container images provided as tarballs for offline loading.
- License validation via pre-loaded license file (cryptographically signed); no phone-home.
- Model artifacts (weights) delivered via secure download + offline transfer.
- Updates delivered as signed artifact bundles; customer applies at their cadence.
- No outbound network rules enforced at deployment validation stage.

---

## 10. Observability & Operations

### 10.1 Logging Strategy

- **Structured JSON logging** from all components. Every log entry includes: timestamp, level, service, module, request_id, workspace_id (where applicable), message, and structured context fields.
- **Log levels:** ERROR (actionable failures), WARN (degraded behavior, fallbacks triggered), INFO (request lifecycle, job state transitions), DEBUG (detailed internals, disabled in production by default).
- **Sensitive data:** API keys, tokens, and customer content are never logged. Prompt content logged only at DEBUG level with PII redaction.
- **Log aggregation:** stdout → container runtime → customer's log infrastructure (ELK, Loki, CloudWatch, etc.). Pulse provides no built-in log storage.

### 10.2 Metrics Collection

**Prometheus-compatible metrics endpoint** (`/metrics`) exposing:

| Metric Category | Examples |
|---|---|
| Generation throughput | `pulse_generation_total{model, market, status}`, `pulse_generation_duration_seconds{model, market}` |
| Quality metrics | `pulse_confidence_score{market, content_type}`, `pulse_flagged_content_total{flag_type}` |
| Job metrics | `pulse_bulk_jobs_active`, `pulse_bulk_job_items_total{status}`, `pulse_bulk_job_duration_seconds` |
| LLM provider metrics | `pulse_llm_request_total{provider, model, status}`, `pulse_llm_request_duration_seconds{provider, model}`, `pulse_llm_tokens_total{provider, model, type}` |
| Vault metrics | `pulse_vault_retrieval_duration_seconds`, `pulse_vault_cache_hit_total`, `pulse_vault_errors_total` |
| System health | `pulse_active_workspaces`, `pulse_connected_workers`, `pulse_queue_depth` |

### 10.3 Distributed Tracing

- **OpenTelemetry** instrumentation across all components.
- **Trace context propagation** via W3C Trace Context headers.
- **Key spans:** API request → Vault retrieval → Prompt composition → LLM call → Quality scoring → Response.
- **Trace export:** OTLP to customer's tracing backend (Jaeger, Tempo, Zipkin, etc.).
- **Sampling:** 100% for errors; configurable sampling rate for successful requests (default 1%).

### 10.4 Alerting & Monitoring

| Alert | Condition | Severity | Action |
|---|---|---|---|
| High error rate | >1% 5xx responses over 5 minutes | Critical | Page on-call; investigate application logs |
| LLM provider degradation | >10% failures to single provider over 5 minutes | Warning | Verify fallback is active; contact provider if persistent |
| Queue depth growing | Job queue depth >1000 for >10 minutes | Warning | Scale workers; investigate processing bottleneck |
| Vault connectivity lost | Vault health check failing for >2 minutes | Warning | Verify Vault deployment; generation running on cache |
| Database replication lag | Replica lag >5 seconds | Warning | Investigate database performance; risk of failover |
| Worker count below target | Active workers < configured minimum | Warning | Check worker health; auto-scaler may have failed |
| Disk space low | Any volume >85% utilization | Warning | Expand storage; investigate growth |
| Certificate expiry | TLS certificate expires within 14 days | Info | Renew certificate |

### 10.5 Health Checks

- **Liveness probe:** `/health/live` — process is running and responsive.
- **Readiness probe:** `/health/ready` — all dependencies reachable (PostgreSQL, Redis, Vault).
- **Detailed health:** `/health/detailed` — per-dependency status (for diagnostics; not exposed externally).

---

## 11. Cost & Resource Considerations

### 11.1 Major Cost Drivers

| Driver | Description | Optimization |
|---|---|---|
| **LLM API costs** | Dominant cost for cloud-model deployments. Scales linearly with content volume and token count. | Generation caching (identical requests); model tiering (cheaper models for simple content); prompt efficiency (minimize input tokens); batch API pricing where available |
| **GPU compute (local models)** | Significant for air-gapped or sovereignty-focused deployments running local LLMs. | Model quantization (GPTQ/AWQ); batch inference; right-sizing GPU instances; shared GPU across workspaces |
| **PostgreSQL** | Scales with content volume and workspace count. | Read replicas for query load; partitioned tables for large workspaces; connection pooling (PgBouncer) |
| **Object storage** | Grows with generated content, exports, and bulk job inputs. | Lifecycle policies (archive old exports); configurable retention; compression for text content |
| **Bandwidth** | LLM API calls, Vault retrieval, content delivery. | Caching reduces redundant API calls; compression for API responses; CDN for static assets |

### 11.2 Cost Optimization Strategies

1. **Generation caching:** Hash-based cache (prompt + model + parameters → result). 24-hour TTL. Eliminates redundant generation for identical or near-identical requests. Estimated 15-25% cost reduction for repeat-heavy workloads.

2. **Model tiering:** Route simple content (social posts, short descriptions) to smaller/cheaper models; reserve expensive models for complex content (long-form blog posts, nuanced cultural adaptation). Configurable per workspace.

3. **Prompt efficiency:** Minimize system prompt size; use structured output formats to reduce output tokens; cache common prompt prefixes (KV-cache optimization for compatible providers).

4. **Batch processing:** For bulk jobs, batch API calls where supported (OpenAI batch API offers 50% discount). Group generation tasks to maximize throughput per API connection.

5. **Right-sized infrastructure:** Auto-scaling workers based on queue depth (scale down during off-hours). Recommended instance types documented per deployment size.

### 11.3 Resource Sizing Guide

| Deployment Size | Workspaces | API Replicas | Workers | PostgreSQL | Redis |
|---|---|---|---|---|---|
| Small (SMB) | 1-5 | 2 | 2-4 | 4 CPU, 16GB RAM, 500GB SSD | 2 CPU, 4GB RAM |
| Medium (Agency) | 10-50 | 3-5 | 5-10 | 8 CPU, 32GB RAM, 1TB SSD | 4 CPU, 8GB RAM |
| Large (Enterprise) | 50+ | 5-10 | 10-20+ | 16+ CPU, 64GB+ RAM, 2TB+ SSD | 8 CPU, 16GB RAM |

---

## 12. Trade-offs & Design Decisions

### 12.1 Modular Monolith vs. Microservices

**Options considered:** Full microservices, modular monolith, serverless.

**Chosen:** Modular monolith with async job processing.

| Pros | Cons |
|---|---|
| Single deployment unit — simple for self-hosted customers | Cannot scale individual modules independently |
| No network overhead between modules | Codebase coupling requires discipline to maintain boundaries |
| Simpler debugging and observability | Large codebase may slow onboarding |
| Docker Compose deployment feasible | Future extraction to microservices requires effort |

**Why not microservices:** Self-hosted deployment is a core differentiator. Operating 10+ microservices on customer infrastructure creates unacceptable operational burden. The modular monolith maintains internal boundaries that allow future extraction if scale demands it.

**Why not serverless:** Air-gapped deployment requirement eliminates serverless. Also, long-running generation tasks (30s+ per piece) are poor fits for serverless execution time limits.

### 12.2 PostgreSQL + pgvector vs. Dedicated Vector Database

**Options considered:** PostgreSQL + pgvector, Pinecone/Weaviate/Qdrant alongside PostgreSQL, dedicated vector DB only.

**Chosen:** PostgreSQL with pgvector extension.

| Pros | Cons |
|---|---|
| Single database to operate (reduces self-hosted complexity) | pgvector performance degrades at very large scale (>50M vectors) |
| Transactions span content + embeddings atomically | Fewer vector-specific optimizations than dedicated solutions |
| Customer already comfortable operating PostgreSQL | Limited to HNSW/IVF indexing (no learned indexes) |
| Eliminates network hop for vector search | |

**Why not dedicated vector DB:** Adds operational complexity for self-hosted customers (another service to deploy, monitor, and back up). pgvector is sufficient for v1.0 scale (<10M tokens per workspace). Migration path to dedicated vector DB documented for v2.0 if needed.

### 12.3 Redis Streams vs. Kafka for Job Queue

**Options considered:** Redis Streams, Apache Kafka, RabbitMQ, PostgreSQL-based queue.

**Chosen:** Redis Streams.

| Pros | Cons |
|---|---|
| Redis already required for caching — no new infrastructure | Not designed for long-term message retention |
| Consumer groups provide exactly-once semantics | Limited message replay compared to Kafka |
| Low latency, simple operations | Single-node durability (mitigated by Sentinel) |
| Lightweight for self-hosted deployments | |

**Why not Kafka:** Kafka requires ZooKeeper (or KRaft) and significant operational expertise. Overkill for v1.0 job queue requirements. Redis Streams provides adequate semantics with zero additional infrastructure.

**Why not PostgreSQL queue:** Polling-based queues create unnecessary database load at bulk generation scale. Redis Streams provides push-based consumption with better throughput.

### 12.4 Generation Caching Strategy

**Options considered:** No caching, exact-match caching, semantic similarity caching.

**Chosen:** Exact-match caching (content hash → result).

| Pros | Cons |
|---|---|
| Simple to implement and reason about | Only eliminates truly identical requests |
| Zero quality risk (cached result is exact) | Does not help with near-duplicate requests |
| Significant cost reduction for repeat-heavy workloads | Cache invalidation complexity for Vault updates |
| | Storage cost for cached results |

**Why not semantic caching:** Semantic similarity caching (cache hits for "similar" prompts) introduces quality risk — similar ≠ identical in localization. A cached result for a "similar" prompt may not be appropriate for the actual request. Exact-match caching is safe and still provides meaningful cost reduction.

### 12.5 Row-Level Security vs. Separate Databases for Multi-Tenancy

**Options considered:** Shared database with RLS, separate database per workspace, separate schema per workspace.

**Chosen:** Shared database with row-level security.

| Pros | Cons |
|---|---|
| Single database to operate and back up | Requires discipline in RLS policy enforcement |
| Cross-workspace analytics queries are simple | Bug in RLS policy = data leakage |
| Scales to hundreds of workspaces without schema proliferation | Noisy neighbor risk (mitigated by per-workspace resource limits) |
| Simple migration and upgrade path | |

**Why not separate databases:** Operational complexity explodes with hundreds of workspaces. Backup, migration, and connection management become unmanageable. RLS provides equivalent isolation with dramatically simpler operations.

---

## 13. Risks & Mitigations

### 13.1 Technical Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| **LLM quality inconsistency across languages** — Tier 3 languages produce noticeably worse output than Tier 1 | High | Medium | Transparent language tier system; per-language model selection guidance; quality benchmarks published per tier; customer expectation management |
| **Prompt injection or cultural safety failure** — Generated content is offensive or inappropriate for target market | Medium | High | Cultural sensitivity lists in adaptation profiles; content safety filters; mandatory human review flagging for sensitive markets; incident response process |
| **Vault dependency creates single point of failure** — Vault outage blocks all knowledge-grounded generation | Medium | Medium | Local cache provides degraded-but-functional mode; generation continues with cached context; clear user notification when operating without live Vault |
| **Bulk job processing creates resource exhaustion** — Large jobs (100K+ pieces) consume all workers, starving single-piece generation | Medium | Medium | Separate worker pools for bulk vs. single generation; configurable concurrency limits per job type; priority queuing |
| **pgvector performance degradation at scale** — Vector search becomes slow as knowledge bases grow | Low | Medium | Monitoring query latency; documented migration path to dedicated vector DB; HNSW parameter tuning; knowledge base size limits per workspace |
| **Self-hosted deployment support burden** — Diverse customer infrastructure creates unpredictable support load | Medium | Medium | Comprehensive documentation; automated deployment validation; diagnostic tooling; managed cloud option to reduce support load |

### 13.2 External Dependency Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| **LLM provider pricing increase** — OpenAI/Anthropic raise prices significantly | Medium | Medium | Model-agnostic architecture allows switching; local model option eliminates API costs entirely; cost transparency tools help customers optimize |
| **LLM provider model discontinuation** — Provider deprecates a model Pulse relies on | Medium | Medium | Adapter architecture isolates model changes; migration guides for model transitions; multi-model support means no single model is critical |
| **Vault API contract changes** — Vault team changes API in breaking way | Low | High | Versioned API contract; Pulse pins to specific Vault API version; change notification process between teams; integration tests catch breaks early |
| **Open-source model quality regression** — Llama/Mistral updates degrade quality for specific languages | Low | Medium | Model version pinning (customer chooses when to upgrade); quality regression detection via benchmarks; fallback to previous model version |

### 13.3 Data & Compliance Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| **Cross-workspace data leakage** — Bug exposes one workspace's content to another | Low | Critical | RLS policy testing in CI; automated isolation verification; penetration testing before GA; immutable audit trail for forensic analysis |
| **Regulatory change invalidates compliance posture** — New AI regulation requires changes Pulse doesn't support | Medium | Medium | Content labeling feature (for disclosure requirements); modular compliance framework; legal monitoring of regulatory landscape; rapid response process |
| **LLM provider uses customer content for training** — Violates sovereignty guarantees | Low | Critical | Contractual zero-retention agreements; technical verification (API audit logs); self-hosted model option eliminates risk entirely; customer communication on provider policies |
| **Performance tracking collects visitor PII via analytics** — Experimentation requires tracking visitor behavior across sessions | Medium | High | Visitor hashing (SHA256, no raw PII stored); GDPR-compliant consent mechanism required; data minimization (only experiment-relevant events); privacy documentation for customers |
| **Insufficient traffic for multilingual experiments** — Per-locale experiments need significant visitor volume to reach statistical significance | High | Medium | Sample size calculator warns users before experiment start; automatic duration estimation based on traffic; recommended minimum 10,000 visitors + 300 conversions per variant per locale |
| **External analytics dependency (Segment/GA4 unavailable)** — Outage in analytics platform breaks performance data ingestion | Low | Medium | Internal tracking fallback (JavaScript snippet → Pulse API); air-gapped mode with no external dependencies |

---

## 14. Assumptions & Constraints

### 14.1 Assumptions

| # | Assumption | Validation Approach |
|---|---|---|
| A1 | Frontier LLMs (GPT-4, Claude 3.5, Llama 3, Mistral Large) produce localization-quality output with proper cultural context prompting | Pre-GA quality benchmarking across Tier 1 languages with native speaker evaluation; ≥85% approval rate required for GA |
| A2 | Vault provides knowledge grounding sufficient to prevent hallucination of product information | Hallucination detection heuristics; confidence scoring; human review workflows; Vault source attribution |
| A3 | Customers deploying self-hosted have basic Kubernetes or Docker expertise (or choose managed option) | Deployment documentation quality validated via beta customer feedback; <2 hour setup target for self-hosted |
| A4 | Cultural adaptation profiles generalize sufficiently per market (not requiring per-customer customization) | Beta testing with customers in target markets; community contribution program for profile refinement |
| A5 | Vault API will be stable and available for Pulse integration throughout development | Early API contract finalization; integration tests in CI; dedicated Vault liaison from platform team |
| A6 | Redis Streams provides sufficient job queue durability and throughput for v1.0 scale (100K+ items per job) | Load testing in staging; monitoring queue depth and processing latency; documented migration path to Kafka if needed |
| A7 | pgvector performance is acceptable for knowledge bases up to 10M tokens per workspace | Performance benchmarking at target scale; HNSW index tuning; documented scale limits |
| A8 | Generation caching at 24-hour TTL provides meaningful cost reduction without quality staleness | Cache hit rate monitoring; customer feedback on cached result freshness; configurable TTL |
| A9 | Prompt engineering (without fine-tuning) achieves sufficient cultural adaptation quality for Tier 1 and Tier 2 languages | Quality benchmarks per language tier; feedback loop from customer corrections; prompt version A/B testing |
| A10 | Multi-tenant RLS isolation is sufficient for agency use cases (no customer requires physical data separation) | Validation via security review and customer requirements gathering; separate database option documented as escape hatch |

### 14.2 Constraints

| # | Constraint | Impact |
|---|---|---|
| C1 | **LLM capability ceiling** — Output quality cannot exceed what the underlying model can produce. Prompt engineering and cultural context improve results but cannot overcome fundamental model limitations for specific languages. | Some languages will have lower quality; must be transparent about tier limitations. |
| C2 | **Cultural knowledge completeness** — Cultural adaptation profiles encode generalized knowledge. They cannot capture every customer-specific cultural nuance or emerging cultural shifts. | Profiles require ongoing maintenance; customer customization supported; community contribution encouraged. |
| C3 | **Self-hosted infrastructure variability** — Customer hardware, network, and expertise vary enormously. Pulse must work across this diversity without custom engineering per customer. | Deployment documentation must be comprehensive; automated validation required; managed option for those who need it. |
| C4 | **Model-agnostic abstraction cost** — Unified interface prevents deep optimization for any single model. Peak performance on one model is sacrificed for flexibility. | Accepted trade-off; customers who want peak performance on one model can configure model-specific routing. |
| C5 | **Vault coupling** — Pulse depends on Vault being available and functional. Pulse cannot be sold or deployed without at least minimal Vault functionality. | By design (suite module); minimal Vault mode documented for evaluation; clear API contract reduces coupling risk. |
| C6 | **Localization quality subjectivity** — "Good localization" is subjective and market-dependent. No automated metric fully captures localization quality. | Human review workflows are essential; confidence scores guide (not replace) human judgment; feedback loops drive improvement. |
| C7 | **LLM cost scaling** — API costs scale linearly with usage. High-volume customers face significant ongoing costs. | Cost optimization tools (caching, model tiering, batch discounts); transparent cost reporting; local model option for cost-sensitive deployments. |
| C8 | **Regulatory evolution** — AI regulation is evolving rapidly (EU AI Act, regional laws). Compliance requirements may change post-GA. | Modular compliance framework; content labeling feature; legal monitoring; rapid response capability. |
| C9 | **50+ language quality consistency** — Maintaining consistent quality across 50+ languages with diverse LLM support levels is inherently challenging. | Language tier system; per-language model selection; transparent quality documentation; phased rollout (Tier 1 first, then expand). |
| C10 | **Air-gapped model freshness** — Air-gapped deployments cannot receive real-time model updates. Local models may fall behind cloud-hosted alternatives. | Accepted trade-off for sovereignty; periodic model update delivery mechanism; customer chooses freshness vs. sovereignty. |

---

## 15. Future Evolution & Extensibility

### 15.1 Architectural Extension Points

| Extension Point | Current State | Future Evolution |
|---|---|---|
| **LLM Adapters** | Adapter pattern supports adding providers without core changes | New providers (Google Gemini, Cohere, custom fine-tuned models) added via adapter implementation. No core code modification required. |
| **Cultural Adaptation Profiles** | Rule-based engine with configurable market profiles | Community-contributed profiles; ML-enhanced adaptation (learn from customer feedback patterns); per-customer profile customization. |
| **Content Types** | Template-based generation for 10 defined content types | New content types added via template registration. Custom template support for enterprise customers. |
| **Quality Scoring** | Heuristic-based + optional LLM-as-judge | Dedicated evaluation model; customer-specific quality calibration; automated regression detection. |
| **Vault Integration** | REST API client with caching | Deeper integration (real-time sync, bidirectional content flow); support for multiple Vault instances per workspace. |
| **Vector Search** | pgvector extension within PostgreSQL | Migration path to dedicated vector DB (Qdrant, Weaviate) if scale demands. Abstracted behind retrieval interface. |
| **Job Queue** | Redis Streams | Migration path to Kafka or dedicated job scheduler (Temporal) if job complexity increases. Abstracted behind queue interface. |
| **Multi-tenancy** | RLS-based workspace isolation | Escape hatch: separate database per workspace for customers requiring physical isolation. Abstracted behind tenant context interface. |
| **Export Formats** | Markdown, HTML, JSON, DOCX, PDF | New formats added via exporter plugin interface. Custom format support for enterprise integrations. |
| **Webhook Events** | Content lifecycle events | Extensible event system; custom event types; event filtering and transformation. |
| **Experimentation Engine** | Fixed-traffic A/B testing with chi-squared + Bayesian analysis | Multi-armed bandit for adaptive traffic allocation; Bayesian optimization for automatic variant generation; cross-market learning (results in one market inform variant generation for similar markets). |
| **Analytics Integration** | Segment + GA4 + Mixpanel connectors | Plugin interface for custom connectors; real-time event streaming via Kafka; BI tool integrations (Looker, Tableau, PowerBI). |
| **Feedback Loop** | Winning cultural_overrides stored per market, suggested for future generation | Automated cultural profile refinement based on aggregate results; model auto-selection per market based on performance evidence; prompt self-optimization. |
| **Statistical Engine** | Chi-squared + Bayesian Beta-Binomial | Sequential testing (no fixed sample size); CUPED variance reduction; causal inference methods. |
| **Data Storage** | PostgreSQL with partitioning + S3 cold storage | Warehouse-native option (query customer's Snowflake/BigQuery directly); data lake integration. |

### 15.2 Planned v2.0 Evolutions

1. **Dedicated vector database** — If knowledge bases exceed pgvector performance thresholds, migrate to Qdrant or Weaviate behind the existing retrieval interface.

2. **Real-time localization** — Streaming generation for live content (chat, video subtitles). Requires WebSocket-based generation pipeline and sub-second latency optimization.

3. **Custom model fine-tuning** — Per-customer model fine-tuning on brand voice and cultural preferences. Requires training pipeline infrastructure and model registry.

4. **Content distribution integrations** — Direct publishing to CMS (WordPress, Contentful), social platforms, ad networks. Requires integration framework with OAuth-based authentication.

5. **Collaborative editing** — Real-time multi-user editing of generated content. Requires CRDT-based conflict resolution or operational transform.

6. **Temporal workflow engine** — If job orchestration complexity grows (multi-step workflows, human-in-the-loop, long-running processes), migrate from Redis Streams to Temporal for durable execution.

7. **Marketplace for cultural profiles** — Community-contributed and expert-curated cultural adaptation profiles. Requires review/approval workflow and quality validation.

8. **Predictive localization** — Automatic detection of content that needs re-localization (cultural shifts, regulatory changes, brand updates). Requires change detection pipeline and notification system.

### 15.3 Scaling Evolution Path

| Current Scale Target | Scaling Limit | Evolution Trigger | Next Step |
|---|---|---|---|
| 500 concurrent users | ~2,000 with current architecture | User growth beyond 2,000 | Extract high-load modules (generation, job processing) into independent services |
| 100K items per bulk job | ~1M with Redis Streams | Jobs exceeding 1M items | Migrate to Kafka for durable, high-throughput job queue |
| 10M tokens per workspace | ~50M with pgvector | Knowledge bases exceeding 50M tokens | Migrate to dedicated vector database |
| 100 workspaces | ~500 with RLS | Workspace count exceeding 500 | Evaluate separate-schema or separate-database tenancy for large agencies |
| 50+ languages | No architectural limit | Quality inconsistency in long-tail languages | Per-language model specialization; dedicated evaluation models per language family |

### 15.4 Suite Integration Evolution

Pulse is designed as a suite module. Future integration points:

- **Vault ↔ Pulse bidirectional sync** — Approved content automatically updates Vault knowledge base; Vault changes trigger content refresh notifications.
- **Cross-module content reuse** — Content generated in Pulse available to other ODW.ai modules (e.g., campaign management, analytics).
- **Unified analytics** — Pulse usage and quality metrics aggregated into suite-wide dashboard.
- **Shared LLM infrastructure** — LLM Abstraction Layer potentially becomes suite-wide shared service, reducing per-module provider management.

---

## 16. Competitive Architecture Differentiation

Pulse occupies a unique position in the market by combining three capabilities that competitors offer only in isolation:

**Localization Platforms (Phrase, Lokalise, Crowdin):**
- Generate and export content with no performance feedback
- Static translation workflows with no experimentation
- Content goes out, nothing comes back — open-loop architecture

**Experimentation Platforms (Optimizely, VWO):**
- Provide A/B testing and statistical analysis
- Require external content creation and manual setup per locale
- No content generation capability

**Pulse — The Unified Approach:**
- **Generates** culturally-adapted variants across 50+ languages
- **Tests** them with built-in A/B experimentation (chi-squared + Bayesian analysis)
- **Learns** via the feedback loop — winning characteristics influence future generation

This closed-loop architecture (Generate → Publish → Measure → Learn → Generate) is what differentiates Pulse. While competitors operate in isolation, Pulse is the only system that automatically improves cultural adaptation based on real-world performance data. Every experiment makes Pulse smarter, creating a compounding advantage that neither pure localization platforms nor pure experimentation platforms can match.

---

*End of Document*
