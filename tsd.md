# Pulse — Technical Specification Document

**Product:** Pulse (ODW.ai Suite Module)
**Document Version:** 1.0
**Date:** 2026-06-23
**Status:** Draft
**Author:** Architecture Team

---

## 1. System Overview

### 1.1 Purpose

Pulse is a multilingual content generation and localization module within the ODW.ai suite. It produces culturally-adapted marketing and business content across 50+ languages, grounded in the customer's own knowledge base via Vault integration. The system supports self-hosted, model-agnostic deployment to ensure infrastructure sovereignty.

### 1.2 Architecture Components → Services/Modules

| SAD Component | Concrete Module | Deployment Unit |
|---|---|---|
| Pulse Application Server | `pulse-api` container | Stateless API server (2+ replicas) |
| Generation Orchestrator | Internal module within `pulse-api` | In-process |
| Cultural Adaptation Engine | Internal module within `pulse-api` | In-process |
| Quality Scoring Engine | Internal module within `pulse-api` | In-process |
| Bulk Job Manager | Worker processes in `pulse-worker` container | Horizontally scalable workers (1-10 replicas) |
| Content Management Module | Internal module within `pulse-api` | In-process |
| Review & Workflow Module | Internal module within `pulse-api` | In-process |
| Tenant Isolation Module | Middleware + PostgreSQL RLS | In-process + DB-level |
| LLM Abstraction Layer | Internal module within `pulse-api` | In-process |
| Prompt Composer | Internal module within `pulse-api` | In-process |
| Vault Connector | Internal module within `pulse-api` | In-process |
| Webhook Dispatcher | Async process in `pulse-scheduler` | Single replica |
| Analytics & Audit Module | Internal module + `pulse-scheduler` | In-process + scheduled tasks |
| Analytics Integration Module | Internal module within `pulse-api` | In-process |
| Experimentation Engine | Internal module within `pulse-api` | In-process |
| Job Scheduler | `pulse-scheduler` container | Single replica |

### 1.3 System Boundaries

**Included:**
- Content generation and cultural localization across 50+ languages
- Vault integration for knowledge grounding, brand voice, terminology
- Model-agnostic LLM backend (OpenAI, Anthropic, Mistral, Ollama, vLLM, Azure OpenAI, AWS Bedrock)
- Bulk generation with async job processing
- Multi-tenant architecture with workspace isolation
- Review workflows and quality scoring
- Self-hosted deployment (Docker Compose, Kubernetes, air-gapped)
- REST API and Web UI
- Webhook notifications

**Excluded:**
- Legal/medical/regulatory content localization (flagged for human review)
- Real-time translation (chat, live video)
- Document format preservation (InDesign, PDF layout)
- Audio/video localization (dubbing, subtitling)
- Translation memory management
- Fine-tuning custom models (v2.0+)
- Content distribution to CMS/social platforms (v2.0+)

---

## 2. Service & Module Breakdown

### 2.1 Content Management Module

- **Service Name:** `content-management`
- **Responsibility:** CRUD operations on content pieces, version control, content lifecycle state management (draft → review → approved/rejected/archived), export in multiple formats (Markdown, HTML, JSON, DOCX, PDF)
- **Inputs:** User requests (create, edit, approve, export), bulk import data (CSV/XLSX)
- **Outputs:** Persisted content records, version history, exported files (to S3/MinIO)
- **Internal Sub-components:**
  - Version controller (immutable version snapshots)
  - Export engine (format-specific renderers)
  - Content state machine (lifecycle transitions)
- **Dependencies:** PostgreSQL (persistence), Object Storage (exports), Vault Connector (source attribution)
- **Deployment Unit:** Internal module within `pulse-api` container

### 2.2 Generation Orchestrator

- **Service Name:** `generation-orchestrator`
- **Responsibility:** Coordinates end-to-end generation pipeline — retrieves Vault context, composes prompts, dispatches to LLM, applies post-processing, returns results
- **Inputs:** Generation request (content/brief, target markets, tone, parameters)
- **Outputs:** Generated content with metadata (confidence score, flags, Vault sources used, model used, latency metrics)
- **Internal Sub-components:**
  - Pipeline coordinator (sequential step execution)
  - Context aggregator (merges Vault data, market profiles, brand voice)
  - Post-processor (terminology enforcement, output formatting)
- **Dependencies:** Vault Connector, Cultural Adaptation Engine, Prompt Composer, LLM Abstraction Layer, Quality Scoring Engine
- **Deployment Unit:** Internal module within `pulse-api` container

### 2.3 Cultural Adaptation Engine

- **Service Name:** `cultural-adaptation`
- **Responsibility:** Applies market-specific cultural transformation rules to generation parameters. Encodes cultural dimensions (formality, directness, individualism, humor, persuasion style) per market profile. Transforms prompts to produce culturally-native output.
- **Inputs:** Target market code (ISO 639-1 + region), source content/brief, brand voice profile, cultural adaptation profile
- **Outputs:** Culturally-optimized prompt parameters and generation instructions (structured directive object)
- **Internal Sub-components:**
  - Market profile loader (retrieves and caches cultural profiles)
  - Dimension calculator (computes cultural transformation weights)
  - Directive generator (produces LLM-ready cultural instructions)
- **Dependencies:** PostgreSQL (market profiles), Redis (profile cache)
- **Deployment Unit:** Internal module within `pulse-api` container

### 2.4 Quality Scoring Engine

- **Service Name:** `quality-scoring`
- **Responsibility:** Evaluates generated output quality post-generation. Produces confidence scores (0-100%), flags content for human review, detects potential hallucinations (claims not grounded in Vault)
- **Inputs:** Generated content, Vault sources referenced, terminology glossary, market profile
- **Outputs:** Confidence score (0-100), flag list (array of {type, severity, message}), quality metadata
- **Internal Sub-components:**
  - Terminology compliance checker
  - Vault grounding verifier (claims vs. source material)
  - Length/format conformance checker
  - Optional LLM-as-judge evaluator (higher-tier deployments)
- **Dependencies:** Vault Connector (source verification), PostgreSQL (scoring rules)
- **Deployment Unit:** Internal module within `pulse-api` container

### 2.5 Bulk Job Manager

- **Service Name:** `bulk-job-manager`
- **Responsibility:** Manages long-running bulk generation jobs — accepts input (CSV/XLSX), decomposes into individual generation tasks, dispatches to worker pool, tracks progress, supports pause/resume/cancel, handles checkpointing
- **Inputs:** Bulk input file, generation configuration, target markets
- **Outputs:** Job status updates, progress events (WebSocket + webhook), completed content pieces, summary report
- **Internal Sub-components:**
  - Input parser (CSV/XLSX validation and decomposition)
  - Task dispatcher (pushes tasks to Redis Streams)
  - Progress tracker (atomic counter updates, checkpointing every 10 items)
  - Job controller (pause/resume/cancel state machine)
- **Dependencies:** Redis Streams (job queue), PostgreSQL (job state), Object Storage (input/output files)
- **Deployment Unit:** `pulse-worker` container (task execution), `pulse-api` (job management API)

### 2.6 Review & Workflow Module

- **Service Name:** `review-workflow`
- **Responsibility:** Manages content review workflows — side-by-side comparison, inline editing, annotation, approval chains, feedback collection
- **Inputs:** Reviewer actions (approve, reject, request changes, edit, feedback)
- **Outputs:** Updated content state, feedback records, audit entries
- **Internal Sub-components:**
  - Comparison renderer (source vs. localized diff view)
  - Approval chain manager (configurable multi-step approval)
  - Feedback collector (structured feedback with content references)
- **Dependencies:** PostgreSQL (state), WebSocket (real-time UI updates)
- **Deployment Unit:** Internal module within `pulse-api` container

### 2.7 Tenant Isolation Module

- **Service Name:** `tenant-isolation`
- **Responsibility:** Enforces strict data separation between workspaces. All data access scoped to authenticated workspace. Prevents cross-workspace data leakage at application and database level.
- **Inputs:** Authenticated request with workspace context (extracted from JWT)
- **Outputs:** Scoped data access, workspace-filtered queries
- **Internal Sub-components:**
  - Workspace context injector (middleware)
  - RLS policy enforcer (PostgreSQL session variables)
  - Cross-workspace access blocker (query validation)
- **Dependencies:** PostgreSQL (RLS policies), Auth middleware (JWT parsing)
- **Deployment Unit:** Middleware in `pulse-api` + PostgreSQL RLS policies

### 2.8 LLM Abstraction Layer

- **Service Name:** `llm-abstraction`
- **Responsibility:** Provides unified interface to multiple LLM backends. Handles adapter registration, request translation, response normalization, streaming support, error handling
- **Inputs:** Normalized generation request (prompt, parameters, model selection)
- **Outputs:** Normalized LLM response (generated text, token usage, latency metrics, finish reason)
- **Internal Sub-components:**
  - Adapter registry (provider-specific implementations)
  - Request translator (normalizes to provider-specific format)
  - Response normalizer (provider response → standard format)
  - Streaming handler (SSE token-by-token delivery)
- **Adapters:** OpenAI, Anthropic, Mistral, Ollama, vLLM, Azure OpenAI, AWS Bedrock
- **Dependencies:** External LLM provider APIs (HTTP/SSE)
- **Deployment Unit:** Internal module within `pulse-api` container

### 2.9 Prompt Composer

- **Service Name:** `prompt-composer`
- **Responsibility:** Constructs culturally-adapted prompts by combining: brand voice profile, market adaptation profile, terminology glossary, Vault-retrieved knowledge, content type template, tone controls, and user instructions. Core IP of Pulse.
- **Inputs:** All contextual inputs from Vault and configuration
- **Outputs:** Final prompt payload (system prompt + user prompt + parameters) ready for LLM consumption
- **Internal Sub-components:**
  - Template engine (variable substitution, conditional sections)
  - Prompt assembler (merges all context sources)
  - Token budget manager (ensures prompt fits model context window)
  - Prompt versioning (A/B testing support)
- **Dependencies:** Cultural Adaptation Engine, Vault Connector, PostgreSQL (templates)
- **Deployment Unit:** Internal module within `pulse-api` container

### 2.10 Fallback Router

- **Service Name:** `fallback-router`
- **Responsibility:** Manages model selection and failover. Routes generation requests to configured primary model; on failure or rate-limiting, automatically switches to secondary. Tracks model health and performance metrics.
- **Inputs:** Generation request, model configuration, model health status
- **Outputs:** Routed request to appropriate LLM adapter
- **Internal Sub-components:**
  - Circuit breaker (per-provider state tracking)
  - Health monitor (latency, error rate tracking)
  - Fallback chain resolver (ordered provider list)
  - Load balancer (weighted round-robin across healthy providers)
- **Dependencies:** LLM Abstraction Layer (adapters)
- **Deployment Unit:** Internal module within `pulse-api` container

### 2.11 Vault Connector

- **Service Name:** `vault-connector`
- **Responsibility:** Interfaces with ODW.ai Vault to retrieve knowledge (product info, brand voice, terminology, product catalogs), perform semantic search for relevant context, write approved content back to Vault
- **Inputs:** Query context (content type, product references, brand voice ID)
- **Outputs:** Relevant Vault content, brand voice profile, terminology entries, content lineage records
- **Internal Sub-components:**
  - REST API client (Vault HTTP interface)
  - Semantic search client (Vault embedding endpoint)
  - Local cache manager (Redis-backed, TTL-based)
  - Writeback handler (approved content → Vault)
- **Dependencies:** Vault API (external service), Redis (cache)
- **Deployment Unit:** Internal module within `pulse-api` container

### 2.12 Webhook Dispatcher

- **Service Name:** `webhook-dispatcher`
- **Responsibility:** Delivers event notifications to configured webhook URLs for content lifecycle events. Implements retry with exponential backoff.
- **Inputs:** Internal domain events (content.generated, content.approved, job.completed, etc.)
- **Outputs:** HTTP POST requests to configured endpoints with signed payloads
- **Internal Sub-components:**
  - Event processor (consumes from internal event queue)
  - Delivery executor (HTTP POST with retry)
  - Dead-letter handler (failed deliveries after max retries)
  - Delivery history tracker
- **Dependencies:** Redis (event queue), PostgreSQL (delivery history)
- **Deployment Unit:** `pulse-scheduler` container

### 2.13 Analytics & Audit Module

- **Service Name:** `analytics-audit`
- **Responsibility:** Tracks usage metrics, maintains immutable audit log, provides reporting dashboards
- **Inputs:** Domain events from all modules
- **Outputs:** Usage reports, audit trail, cost attribution data, Prometheus metrics
- **Internal Sub-components:**
  - Event collector (receives domain events)
  - Audit log writer (immutable, append-only)
  - Metrics aggregator (periodic rollup computation)
  - Report generator (dashboard data queries)
- **Dependencies:** PostgreSQL (storage), Prometheus (metrics export)
- **Deployment Unit:** Internal module within `pulse-api` + `pulse-scheduler` (aggregation)

### 2.14 Analytics Integration Module

- **Service Name:** `analytics-integration`
- **Responsibility:** Bidirectional integration with external analytics platforms. Receives performance events from external sources (GA4, Mixpanel, Segment) via webhooks or polling. Sends experiment metadata to external tools. Normalizes events into internal format.
- **Inputs:** Webhooks from analytics tools, API polling responses, internal experiment events
- **Outputs:** Normalized performance events, experiment metadata forwarded to analytics tools
- **Internal Sub-components:**
  - Segment connector (event routing hub — routes to 100+ destinations)
  - Google Analytics 4 connector (Measurement Protocol + Data API)
  - Mixpanel connector (HTTP API for ingestion + export)
  - Event normalizer (external format → internal PerformanceEvent)
  - Webhook receiver (signed payloads from external tools)
- **Dependencies:** PostgreSQL (event storage), Redis (event buffering), Experimentation Engine
- **Deployment Unit:** Internal module within `pulse-api` container

### 2.15 Experimentation Engine

- **Service Name:** `experimentation-engine`
- **Responsibility:** Manages full experiment lifecycle — creation, variant assignment, performance tracking, statistical analysis, winner determination. Coordinates with Generation Orchestrator for variant generation.
- **Inputs:** Experiment creation requests, performance events, variant assignment queries
- **Outputs:** Experiment configurations, variant assignments, statistical results, winner recommendations
- **Internal Sub-components:**
  - Assignment engine (deterministic hashing via SHA256(visitor_id + experiment_id))
  - Statistical analysis engine (chi-squared, Bayesian, effect size)
  - Results computation engine (hourly batch processing)
  - Tracking URL generator (UTM parameters)
  - Exposure tracker (separates assignments from actual views)
- **Dependencies:** PostgreSQL, Redis, Generation Orchestrator, Cultural Adaptation Engine
- **Deployment Unit:** Internal module within `pulse-api` container

---

## 3. Technical Stack Specification

### 3.1 Backend

| Layer | Technology | Version | Justification |
|---|---|---|---|
| Language | Python | 3.11+ | Ecosystem maturity for AI/ML, strong typing with Pydantic, async support |
| Framework | FastAPI | 0.110+ | Async-native, automatic OpenAPI docs, high performance, Pydantic integration |
| ORM | SQLAlchemy 2.0 | 2.0+ | Mature, supports async, excellent PostgreSQL integration, RLS support |
| Task Queue | Redis Streams (via `redis-py`) | redis-py 5.0+ | Already required for caching; consumer groups provide exactly-once semantics |
| Validation | Pydantic v2 | 2.6+ | Strict schema validation, JSON schema generation, fast parsing |
| HTTP Client | httpx | 0.27+ | Async-native, HTTP/2 support, connection pooling for LLM API calls |
| Migrations | Alembic | 1.13+ | Standard SQLAlchemy migration tool, auto-generation support |
| Authentication | python-jose + OIDC libs | 3.3+ | JWT handling; OIDC/SAML via authlib |
| Export | python-docx, WeasyPrint, markdown | latest | DOCX, PDF, HTML export formats |
| Testing | pytest + pytest-asyncio | 8.0+ | Async test support, fixtures, comprehensive plugin ecosystem |

### 3.2 Frontend

| Layer | Technology | Version | Justification |
|---|---|---|---|
| Framework | React | 18+ | Component model, ecosystem, team familiarity |
| Language | TypeScript | 5.3+ | Type safety, better IDE support |
| State Management | TanStack Query | 5.0+ | Server state caching, optimistic updates, background refetch |
| UI Components | shadcn/ui + Radix | latest | Accessible, customizable, no vendor lock-in |
| Real-time | Native WebSocket | — | Bulk job progress, streaming generation |
| Build Tool | Vite | 5.0+ | Fast HMR, optimized builds |
| HTTP Client | ky or axios | latest | Request/response interceptors, automatic retry |

### 3.3 AI/ML Stack

| Component | Technology | Notes |
|---|---|---|
| LLM Providers | OpenAI, Anthropic, Mistral, Ollama, vLLM, Azure OpenAI, AWS Bedrock | Adapter pattern; customer-configurable |
| Embedding Models | OpenAI `text-embedding-3-small`, Cohere `embed-multilingual-v3`, or local (sentence-transformers) | For Vault semantic search; configurable per deployment |
| Prompt Engineering | Template engine with variable substitution | Core IP; versioned templates with A/B testing |
| Cultural Adaptation | Rule-based engine with configurable market profiles | 50+ market profiles encoding cultural dimensions |
| Quality Scoring | Heuristic-based + optional LLM-as-judge | Terminology compliance, Vault grounding, format checks |
| Local Inference | Ollama (CPU/GPU) or vLLM (GPU) | For air-gapped and sovereignty-focused deployments |
| Vector Search | pgvector extension (PostgreSQL) | HNSW indexing; sufficient for <10M tokens per workspace |

### 3.4 Data Layer

| Component | Technology | Version | Purpose |
|---|---|---|---|
| Primary Database | PostgreSQL | 16+ | Content, jobs, workspaces, audit logs, configuration |
| Vector Extension | pgvector | 0.7+ | Semantic search for Vault knowledge retrieval |
| Cache | Redis | 7.2+ | Session state, rate limits, brand voice cache, generation cache |
| Job Queue | Redis Streams | 7.2+ | Bulk job task distribution, event processing |
| Object Storage | S3-compatible (AWS S3, MinIO) | — | Exports, bulk input files, generated content files |
| Connection Pool | PgBouncer | 1.21+ | PostgreSQL connection management for high concurrency |

### 3.5 DevOps Tooling

| Component | Technology | Purpose |
|---|---|---|
| Containerization | Docker | Application packaging |
| Orchestration | Kubernetes (Helm charts) | Production deployment, scaling |
| Simple Deploy | Docker Compose | SMB/self-hosted simple deployments |
| CI/CD | GitHub Actions (or customer's CI) | Build, test, deploy pipeline |
| GitOps | ArgoCD or Flux | Production deployment management |
| Monitoring | Prometheus + Grafana | Metrics collection and visualization |
| Tracing | OpenTelemetry | Distributed tracing (OTLP export) |
| Logging | Structured JSON → stdout | Customer's log infrastructure (ELK, Loki, CloudWatch) |
| Secret Management | HashiCorp Vault / AWS Secrets Manager / K8s Secrets | Credential storage |
| TLS | cert-manager + Let's Encrypt | Automated certificate management |

---

## 4. Data Modeling & Schema Definitions

### 4.1 Entity: Workspace

**Table:** `workspaces`

| Field | Type | Constraints | Description |
|---|---|---|---|
| id | UUID | PK, DEFAULT gen_random_uuid() | Workspace identifier |
| name | VARCHAR(255) | NOT NULL | Workspace display name |
| slug | VARCHAR(100) | NOT NULL, UNIQUE | URL-safe identifier |
| plan | VARCHAR(50) | NOT NULL, DEFAULT 'standard' | Subscription tier |
| config | JSONB | NOT NULL, DEFAULT '{}' | Workspace-level configuration |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Creation timestamp |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Last update timestamp |

**Indexes:** UNIQUE(slug), INDEX(name)

### 4.2 Entity: User

**Table:** `users`

| Field | Type | Constraints | Description |
|---|---|---|---|
| id | UUID | PK, DEFAULT gen_random_uuid() | User identifier |
| workspace_id | UUID | NOT NULL, FK → workspaces.id | Owning workspace |
| email | VARCHAR(255) | NOT NULL | User email |
| role | VARCHAR(20) | NOT NULL, DEFAULT 'editor' | RBAC role (admin/editor/approver/viewer) |
| display_name | VARCHAR(255) | NOT NULL | Display name |
| is_active | BOOLEAN | NOT NULL, DEFAULT true | Account status |
| last_login_at | TIMESTAMPTZ | NULL | Last login timestamp |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Creation timestamp |

**Indexes:** UNIQUE(workspace_id, email), INDEX(workspace_id), INDEX(role)

### 4.3 Entity: Content Piece

**Table:** `content_pieces`

| Field | Type | Constraints | Description |
|---|---|---|---|
| id | UUID | PK, DEFAULT gen_random_uuid() | Content identifier |
| workspace_id | UUID | NOT NULL, FK → workspaces.id | Owning workspace |
| title | VARCHAR(500) | NOT NULL | Content title |
| content_type | VARCHAR(50) | NOT NULL | Type (blog_post, social_post, email_campaign, product_description, ad_copy, landing_page, press_release, newsletter, video_script, podcast_outline) |
| source_language | VARCHAR(10) | NOT NULL | Source language (ISO 639-1) |
| target_market | VARCHAR(20) | NOT NULL | Target market code (e.g., 'ja-JP', 'de-DE') |
| source_text | TEXT | NULL | Original source content (if localizing existing content) |
| generated_text | TEXT | NULL | Generated/localized output |
| status | VARCHAR(20) | NOT NULL, DEFAULT 'draft' | Lifecycle state (draft/review/approved/rejected/archived) |
| confidence_score | SMALLINT | NULL | Quality score 0-100 |
| flags | JSONB | NOT NULL, DEFAULT '[]' | Quality flags [{type, severity, message}] |
| model_used | VARCHAR(100) | NULL | LLM model that generated content |
| prompt_hash | VARCHAR(64) | NULL | SHA-256 of prompt (for cache lookup) |
| vault_sources | JSONB | NOT NULL, DEFAULT '[]' | Vault knowledge sources referenced |
| metadata | JSONB | NOT NULL, DEFAULT '{}' | Flexible metadata (tone, keywords, SEO data) |
| brand_voice_id | UUID | NULL, FK → brand_voices.id | Brand voice profile used |
| bulk_job_id | UUID | NULL, FK → bulk_jobs.id | Parent bulk job (if generated via bulk) |
| created_by | UUID | NOT NULL, FK → users.id | Creator |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Creation timestamp |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Last update timestamp |

**Indexes:**
- COMPOSITE(workspace_id, status, created_at DESC) — dashboard queries
- GIN(metadata) — flexible JSON filtering
- INDEX(workspace_id, target_market) — market-specific queries
- INDEX(bulk_job_id) — bulk job content lookup
- FULLTEXT(generated_text) — in-app search

**Partitioning:** BY HASH(workspace_id) into 16 partitions

### 4.4 Entity: Content Version

**Table:** `content_versions`

| Field | Type | Constraints | Description |
|---|---|---|---|
| id | UUID | PK, DEFAULT gen_random_uuid() | Version identifier |
| content_id | UUID | NOT NULL, FK → content_pieces.id | Parent content |
| workspace_id | UUID | NOT NULL, FK → workspaces.id | Workspace (for RLS) |
| version_number | INTEGER | NOT NULL | Sequential version number |
| generated_text | TEXT | NOT NULL | Content at this version |
| change_summary | TEXT | NULL | Description of changes |
| created_by | UUID | NOT NULL, FK → users.id | Who made this version |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Version timestamp |

**Indexes:** UNIQUE(content_id, version_number), INDEX(workspace_id)

### 4.5 Entity: Bulk Job

**Table:** `bulk_jobs`

| Field | Type | Constraints | Description |
|---|---|---|---|
| id | UUID | PK, DEFAULT gen_random_uuid() | Job identifier |
| workspace_id | UUID | NOT NULL, FK → workspaces.id | Owning workspace |
| name | VARCHAR(255) | NOT NULL | Job display name |
| status | VARCHAR(20) | NOT NULL, DEFAULT 'pending' | State (pending/processing/paused/completed/failed/cancelled) |
| content_type | VARCHAR(50) | NOT NULL | Type of content being generated |
| target_markets | JSONB | NOT NULL | Array of target market codes |
| configuration | JSONB | NOT NULL | Generation parameters |
| input_file_key | VARCHAR(500) | NULL | S3 key for input file |
| total_items | INTEGER | NOT NULL, DEFAULT 0 | Total items to process |
| completed_items | INTEGER | NOT NULL, DEFAULT 0 | Items completed |
| failed_items | INTEGER | NOT NULL, DEFAULT 0 | Items failed |
| started_at | TIMESTAMPTZ | NULL | Processing start time |
| completed_at | TIMESTAMPTZ | NULL | Processing completion time |
| created_by | UUID | NOT NULL, FK → users.id | Creator |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Creation timestamp |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Last update timestamp |

**Indexes:** INDEX(workspace_id, status), INDEX(created_at DESC)

### 4.6 Entity: Brand Voice

**Table:** `brand_voices`

| Field | Type | Constraints | Description |
|---|---|---|---|
| id | UUID | PK, DEFAULT gen_random_uuid() | Brand voice identifier |
| workspace_id | UUID | NOT NULL, FK → workspaces.id | Owning workspace |
| name | VARCHAR(255) | NOT NULL | Brand voice name |
| tone_attributes | JSONB | NOT NULL | {formality, personality, vocabulary_preferences, ...} |
| guidelines_text | TEXT | NULL | Raw brand guidelines content |
| sample_content | JSONB | NOT NULL, DEFAULT '[]' | Sample content pieces for voice calibration |
| is_active | BOOLEAN | NOT NULL, DEFAULT true | Active status |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Creation timestamp |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Last update timestamp |

**Indexes:** INDEX(workspace_id, is_active)

### 4.7 Entity: Market Adaptation Profile

**Table:** `market_profiles`

| Field | Type | Constraints | Description |
|---|---|---|---|
| id | UUID | PK, DEFAULT gen_random_uuid() | Profile identifier |
| workspace_id | UUID | NOT NULL, FK → workspaces.id | Owning workspace (NULL for system defaults) |
| market_code | VARCHAR(20) | NOT NULL | Market code (e.g., 'ja-JP') |
| name | VARCHAR(255) | NOT NULL | Profile display name |
| cultural_dimensions | JSONB | NOT NULL | {formality_level, directness, individualism, humor_style, persuasion_style, ...} |
| adaptation_rules | JSONB | NOT NULL, DEFAULT '{}' | Market-specific transformation rules |
| sensitivities | JSONB | NOT NULL, DEFAULT '[]' | Cultural sensitivities and taboos |
| is_system_default | BOOLEAN | NOT NULL, DEFAULT false | System-provided vs. custom |
| version | INTEGER | NOT NULL, DEFAULT 1 | Profile version |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Creation timestamp |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Last update timestamp |

**Indexes:** UNIQUE(workspace_id, market_code) WHERE workspace_id IS NOT NULL, INDEX(market_code)

### 4.8 Entity: Terminology Glossary

**Table:** `glossaries`

| Field | Type | Constraints | Description |
|---|---|---|---|
| id | UUID | PK, DEFAULT gen_random_uuid() | Glossary identifier |
| workspace_id | UUID | NOT NULL, FK → workspaces.id | Owning workspace |
| name | VARCHAR(255) | NOT NULL | Glossary name |
| entries | JSONB | NOT NULL, DEFAULT '[]' | [{source_term, translations: {lang: term}, context, is_prohibited}] |
| is_active | BOOLEAN | NOT NULL, DEFAULT true | Active status |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Creation timestamp |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Last update timestamp |

**Indexes:** INDEX(workspace_id, is_active)

### 4.9 Entity: Audit Log

**Table:** `audit_logs`

| Field | Type | Constraints | Description |
|---|---|---|---|
| id | BIGSERIAL | PK | Log entry identifier |
| workspace_id | UUID | NOT NULL, FK → workspaces.id | Workspace context |
| user_id | UUID | NULL, FK → users.id | Acting user (NULL for system actions) |
| action | VARCHAR(100) | NOT NULL | Action performed (e.g., 'content.created', 'job.completed') |
| resource_type | VARCHAR(50) | NOT NULL | Type of resource affected |
| resource_id | UUID | NULL | ID of affected resource |
| details | JSONB | NOT NULL, DEFAULT '{}' | Action-specific details |
| ip_address | INET | NULL | Client IP address |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Event timestamp |

**Indexes:**
- INDEX(workspace_id, created_at DESC) — compliance queries
- INDEX(user_id, action) — user activity reports
- INDEX(resource_type, resource_id) — resource history

**Partitioning:** BY RANGE(created_at) — monthly partitions

### 4.10 Entity: API Key

**Table:** `api_keys`

| Field | Type | Constraints | Description |
|---|---|---|---|
| id | UUID | PK, DEFAULT gen_random_uuid() | Key identifier |
| workspace_id | UUID | NOT NULL, FK → workspaces.id | Owning workspace |
| name | VARCHAR(255) | NOT NULL | Key display name |
| key_hash | VARCHAR(255) | NOT NULL | Hashed API key (never store plaintext) |
| key_prefix | VARCHAR(10) | NOT NULL | First 8 chars for identification |
| scopes | JSONB | NOT NULL, DEFAULT '["generate","read"]' | Permission scopes |
| rate_limit_rpm | INTEGER | NOT NULL, DEFAULT 60 | Requests per minute limit |
| is_active | BOOLEAN | NOT NULL, DEFAULT true | Active status |
| expires_at | TIMESTAMPTZ | NULL | Expiration (NULL = never) |
| last_used_at | TIMESTAMPTZ | NULL | Last usage timestamp |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Creation timestamp |

**Indexes:** UNIQUE(key_hash), INDEX(workspace_id, is_active)

### 4.11 Entity: Webhook Configuration

**Table:** `webhook_configs`

| Field | Type | Constraints | Description |
|---|---|---|---|
| id | UUID | PK, DEFAULT gen_random_uuid() | Config identifier |
| workspace_id | UUID | NOT NULL, FK → workspaces.id | Owning workspace |
| url | VARCHAR(2000) | NOT NULL | Delivery URL |
| events | JSONB | NOT NULL | Array of event types to subscribe to |
| secret | VARCHAR(255) | NOT NULL | HMAC signing secret |
| is_active | BOOLEAN | NOT NULL, DEFAULT true | Active status |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Creation timestamp |

**Indexes:** INDEX(workspace_id, is_active)

### 4.12 Entity: Generation Cache

**Table:** `generation_cache`

| Field | Type | Constraints | Description |
|---|---|---|---|
| prompt_hash | VARCHAR(64) | PK | SHA-256 of (prompt + model + parameters) |
| model_id | VARCHAR(100) | PK | Model identifier |
| result | TEXT | NOT NULL | Cached generated text |
| token_usage | JSONB | NOT NULL | {prompt_tokens, completion_tokens, total_tokens} |
| expires_at | TIMESTAMPTZ | NOT NULL | Cache expiration (24h TTL) |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Cache entry creation |

**Note:** Also cached in Redis for hot access; PostgreSQL serves as durable fallback.

### 4.13 Entity: Experiment

**Table:** `experiments`

| Field | Type | Constraints | Description |
|---|---|---|---|
| id | UUID | PK, DEFAULT gen_random_uuid() | Experiment identifier |
| workspace_id | UUID | NOT NULL, FK → workspaces.id | Owning workspace |
| name | VARCHAR(255) | NOT NULL | Experiment display name |
| hypothesis | TEXT | NOT NULL | Experiment hypothesis |
| experiment_type | VARCHAR(30) | NOT NULL | Type: content_variant / model_comparison / prompt_version |
| status | VARCHAR(20) | NOT NULL, DEFAULT 'draft' | Lifecycle state (draft/active/paused/completed/cancelled) |
| target_market | VARCHAR(20) | NOT NULL | Primary target market |
| target_markets | JSONB | NULL | Multiple markets for cross-locale experiments |
| content_type | VARCHAR(50) | NOT NULL | Type of content being tested |
| source_content_id | UUID | NULL, FK → content_pieces.id | Source content being tested |
| traffic_allocation | JSONB | NOT NULL | {"variant_a": 0.33, ...} traffic split |
| success_metric | VARCHAR(50) | NOT NULL | Primary metric: ctr / conversion_rate / engagement |
| success_criteria | JSONB | NOT NULL | {"min_sample_size": 10000, "min_duration_days": 14, "confidence_threshold": 0.95} |
| started_at | TIMESTAMPTZ | NULL | When experiment was activated |
| completed_at | TIMESTAMPTZ | NULL | When experiment concluded |
| winner_variant_id | UUID | NULL | Winning variant (set after analysis) |
| confidence_level | FLOAT | NULL | Achieved statistical confidence |
| results_summary | JSONB | NULL | Full results snapshot at completion |
| created_by | UUID | NOT NULL, FK → users.id | Creator |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Creation timestamp |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Last update timestamp |

**Indexes:** INDEX(workspace_id, status), INDEX(workspace_id, target_market)

**RLS:** All rows scoped to workspace_id

### 4.14 Entity: Experiment Variant

**Table:** `experiment_variants`

| Field | Type | Constraints | Description |
|---|---|---|---|
| id | UUID | PK, DEFAULT gen_random_uuid() | Variant identifier |
| experiment_id | UUID | NOT NULL, FK → experiments.id | Parent experiment |
| workspace_id | UUID | NOT NULL, FK → workspaces.id | Owning workspace |
| name | VARCHAR(100) | NOT NULL | Variant name (Control, Variant A, etc.) |
| variant_type | VARCHAR(30) | NOT NULL | Type: control / treatment / model_a / model_b |
| content_piece_id | UUID | NULL, FK → content_pieces.id | Content for this variant |
| model_used | VARCHAR(100) | NULL | Model used (for model comparison experiments) |
| prompt_version_id | UUID | NULL | Prompt version used |
| cultural_overrides | JSONB | NULL | Cultural adaptation overrides for this variant |
| traffic_weight | FLOAT | NOT NULL, DEFAULT 0.0 | Traffic allocation (0.0-1.0) |
| tracking_url | VARCHAR(2000) | NULL | URL with UTM parameters |
| tracking_pixel_url | VARCHAR(2000) | NULL | Pixel URL for exposure tracking |
| assignments_count | INTEGER | NOT NULL, DEFAULT 0 | Rolling assignment counter |
| exposures_count | INTEGER | NOT NULL, DEFAULT 0 | Rolling exposure counter |
| metrics | JSONB | NOT NULL, DEFAULT '{}' | {ctr, conversions, engagement, sample_size} |
| is_winner | BOOLEAN | NOT NULL, DEFAULT false | Whether this variant won |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Creation timestamp |

**Indexes:** INDEX(experiment_id), UNIQUE(experiment_id, name)

### 4.15 Entity: Experiment Assignment

**Table:** `experiment_assignments` — PARTITIONED BY RANGE(assigned_at) monthly

| Field | Type | Constraints | Description |
|---|---|---|---|
| id | BIGSERIAL | PK | Assignment identifier |
| experiment_id | UUID | NOT NULL, FK → experiments.id | Experiment context |
| variant_id | UUID | NOT NULL, FK → experiment_variants.id | Assigned variant |
| workspace_id | UUID | NOT NULL, FK → workspaces.id | Owning workspace |
| visitor_hash | VARCHAR(64) | NOT NULL | SHA256 of visitor identifier |
| visitor_segment | JSONB | NULL | {locale, device, geo} |
| assigned_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Assignment timestamp |

**Indexes:** UNIQUE(experiment_id, visitor_hash), INDEX(experiment_id)

### 4.16 Entity: Experiment Exposure

**Table:** `experiment_exposures` — PARTITIONED BY RANGE(exposed_at) weekly

| Field | Type | Constraints | Description |
|---|---|---|---|
| id | BIGSERIAL | PK | Exposure identifier |
| experiment_id | UUID | NOT NULL, FK → experiments.id | Experiment context |
| variant_id | UUID | NOT NULL, FK → experiment_variants.id | Exposed variant |
| workspace_id | UUID | NOT NULL, FK → workspaces.id | Owning workspace |
| visitor_hash | VARCHAR(64) | NOT NULL | Matches assignment visitor_hash |
| exposed_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Exposure timestamp |
| page_url | VARCHAR(2000) | NULL | Page where exposure occurred |
| context | JSONB | NULL | {platform, device, country, locale} |

**Indexes:** INDEX(experiment_id, visitor_hash), INDEX(experiment_id)

### 4.17 Entity: Performance Event

**Table:** `performance_events` — PARTITIONED BY RANGE(received_at) weekly

| Field | Type | Constraints | Description |
|---|---|---|---|
| id | BIGSERIAL | PK | Event identifier |
| experiment_id | UUID | NOT NULL, FK → experiments.id | Experiment context |
| variant_id | UUID | NOT NULL, FK → experiment_variants.id | Variant context |
| workspace_id | UUID | NOT NULL, FK → workspaces.id | Owning workspace |
| event_type | VARCHAR(50) | NOT NULL | Type: page_view / click / conversion / engagement / scroll_depth |
| visitor_hash | VARCHAR(64) | NOT NULL | Visitor identifier |
| event_data | JSONB | NULL | Event-specific data payload |
| locale | VARCHAR(20) | NULL | Visitor locale |
| received_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Receipt timestamp |
| source | VARCHAR(30) | NOT NULL | Source: internal / segment / google_analytics / mixpanel / webhook |

**Indexes:** INDEX(experiment_id, event_type), INDEX(experiment_id, variant_id)

**Note:** High-volume table — weekly partitioning, batch inserts (100 per transaction), cold storage to S3 after 90 days.

### 4.18 Entity: Prompt Version

**Table:** `prompt_versions`

| Field | Type | Constraints | Description |
|---|---|---|---|
| id | UUID | PK, DEFAULT gen_random_uuid() | Version identifier |
| workspace_id | UUID | NOT NULL, FK → workspaces.id | Owning workspace |
| name | VARCHAR(255) | NOT NULL | Version display name |
| content_type | VARCHAR(50) | NOT NULL | Content type this version applies to |
| system_prompt_template | TEXT | NOT NULL | System prompt template |
| user_prompt_template | TEXT | NOT NULL | User prompt template |
| cultural_overrides | JSONB | NULL | Cultural adaptation overrides |
| is_active | BOOLEAN | NOT NULL, DEFAULT true | Whether this version is active |
| performance_stats | JSONB | NULL | Historical performance data |
| version_number | INTEGER | NOT NULL | Sequential version number |
| parent_version_id | UUID | NULL, FK → prompt_versions.id | Parent version (for lineage tracking) |
| created_by | UUID | NOT NULL, FK → users.id | Creator |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Creation timestamp |

**Indexes:** INDEX(workspace_id, content_type, is_active), UNIQUE(workspace_id, content_type, version_number)

### 4.19 Relationships Summary

- workspaces 1:N users
- workspaces 1:N content_pieces
- workspaces 1:N bulk_jobs
- workspaces 1:N brand_voices
- workspaces 1:N market_profiles
- workspaces 1:N glossaries
- workspaces 1:N audit_logs
- workspaces 1:N api_keys
- workspaces 1:N webhook_configs
- content_pieces 1:N content_versions
- content_pieces N:1 bulk_jobs (nullable)
- content_pieces N:1 brand_voices (nullable)
- content_pieces N:1 users (created_by)
- workspaces 1:N experiments
- experiments 1:N experiment_variants
- experiments 1:N experiment_assignments
- experiments 1:N experiment_exposures
- experiments 1:N performance_events
- experiment_variants 1:N experiment_assignments
- experiment_variants 1:N experiment_exposures
- experiment_variants 1:N performance_events
- experiment_variants N:1 content_pieces (nullable)
- workspaces 1:N prompt_versions
- prompt_versions N:1 prompt_versions (parent_version_id, self-referencing)
- prompt_versions N:1 users (created_by)

### 4.20 Migration Strategy

- **Tool:** Alembic with auto-generation from SQLAlchemy models
- **Approach:** All migrations are forward+reverse (reversible). Applied automatically before application deployment via migration job.
- **Versioning:** Migrations versioned in source control; applied in order; never modified after merge.
- **Zero-downtime:** New columns added as nullable or with defaults. Column removals done in two-phase (deprecate → remove in next release).
- **RLS policies:** Applied as part of migration; tested in CI with isolation verification queries.

---

## 5. API Contracts (Strict Specification)

### 5.1 Common Conventions

- **Base URL:** `/api/v1`
- **Authentication:** Bearer token (JWT for UI users) or API key header (`X-API-Key`)
- **Content-Type:** `application/json` (unless file upload)
- **Request ID:** All responses include `X-Request-ID` header
- **Pagination:** Cursor-based (`?cursor=<id>&limit=<n>`)
- **Rate Limiting Headers:** `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`

### 5.2 Error Response Format

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Human-readable description",
    "details": [
      {
        "field": "target_market",
        "message": "Invalid market code. Must be ISO 639-1 + region."
      }
    ]
  }
}
```

**HTTP Status Codes:**
- 200: Success
- 201: Created
- 202: Accepted (async operation started)
- 400: Validation error
- 401: Authentication required
- 403: Insufficient permissions
- 404: Resource not found
- 409: Conflict (state transition invalid)
- 429: Rate limit exceeded
- 500: Internal server error
- 503: Service unavailable (dependency down)

### 5.3 POST /api/v1/generate — Single Content Generation

**Authentication:** Required (JWT or API key with `generate` scope)

**Request Headers:**
```
Content-Type: application/json
Authorization: Bearer <jwt>
X-Request-ID: <uuid>
```

**Request Body Schema:**
```json
{
  "content_type": "blog_post",
  "source_language": "en",
  "target_markets": ["ja-JP", "de-DE", "pt-BR"],
  "source_text": "string (optional — provide for localization of existing content)",
  "brief": "string (optional — provide for generation from scratch)",
  "brand_voice_id": "uuid (optional — uses workspace default if omitted)",
  "tone": "string (optional — overrides brand voice tone)",
  "keywords": ["string"] (optional — SEO keywords),
  "max_length": "integer (optional — max words)",
  "model_preference": "string (optional — specific model)",
  "metadata": {} (optional — additional context)
}
```

**Example Request:**
```json
{
  "content_type": "product_description",
  "source_language": "en",
  "target_markets": ["ja-JP", "ko-KR"],
  "source_text": "Introducing the UltraWidget Pro — the most advanced widget on the market. With 50% more processing power and a sleek new design, it's perfect for professionals who demand the best.",
  "brand_voice_id": "550e8400-e29b-41d4-a716-446655440000",
  "tone": "authoritative",
  "keywords": ["advanced widget", "professional", "processing power"],
  "max_length": 150
}
```

**Success Response (200):**
```json
{
  "data": {
    "content_id": "uuid",
    "results": [
      {
        "market": "ja-JP",
        "generated_text": "...",
        "confidence_score": 87,
        "flags": [],
        "model_used": "gpt-4-turbo",
        "vault_sources": ["product_catalog/ultrawidget-pro"],
        "token_usage": {"prompt": 450, "completion": 180, "total": 630}
      },
      {
        "market": "ko-KR",
        "generated_text": "...",
        "confidence_score": 82,
        "flags": [{"type": "cultural_sensitivity", "severity": "info", "message": "Consider adjusting formality level for B2B context"}],
        "model_used": "claude-3.5-sonnet",
        "vault_sources": ["product_catalog/ultrawidget-pro"],
        "token_usage": {"prompt": 445, "completion": 175, "total": 620}
      }
    ],
    "generated_at": "2026-06-23T10:30:00Z"
  }
}
```

### 5.4 POST /api/v1/generate/bulk — Bulk Content Generation

**Authentication:** Required (JWT or API key with `generate` scope)

**Request:** `multipart/form-data`
- `file`: CSV or XLSX file (required)
- `configuration`: JSON string with generation parameters

**Configuration Schema:**
```json
{
  "content_type": "product_description",
  "source_language": "en",
  "target_markets": ["ja-JP", "de-DE", "pt-BR", "ko-KR"],
  "brand_voice_id": "uuid",
  "tone": "professional",
  "model_preference": "gpt-4-turbo",
  "max_concurrent": 10
}
```

**Success Response (202):**
```json
{
  "data": {
    "job_id": "uuid",
    "status": "pending",
    "total_items": 2000,
    "estimated_duration_seconds": 3600,
    "progress_url": "/api/v1/jobs/{job_id}"
  }
}
```

### 5.5 GET /api/v1/jobs/{id} — Job Status

**Authentication:** Required

**Success Response (200):**
```json
{
  "data": {
    "job_id": "uuid",
    "status": "processing",
    "total_items": 2000,
    "completed_items": 847,
    "failed_items": 3,
    "progress_percent": 42.35,
    "started_at": "2026-06-23T10:00:00Z",
    "estimated_completion": "2026-06-23T11:00:00Z",
    "content_url": "/api/v1/jobs/{id}/content"
  }
}
```

### 5.6 POST /api/v1/jobs/{id}/pause — Pause Job

**Authentication:** Required (admin or editor role)

**Success Response (200):**
```json
{
  "data": {
    "job_id": "uuid",
    "status": "paused",
    "completed_items": 847,
    "message": "Job paused. Remaining 1150 items will resume when job is unpaused."
  }
}
```

### 5.7 GET /api/v1/content/{id} — Get Content Piece

**Authentication:** Required

**Success Response (200):**
```json
{
  "data": {
    "id": "uuid",
    "title": "UltraWidget Pro — Japanese Market",
    "content_type": "product_description",
    "source_language": "en",
    "target_market": "ja-JP",
    "source_text": "...",
    "generated_text": "...",
    "status": "draft",
    "confidence_score": 87,
    "flags": [],
    "model_used": "gpt-4-turbo",
    "vault_sources": ["product_catalog/ultrawidget-pro"],
    "brand_voice_id": "uuid",
    "versions": [{"version_number": 1, "created_at": "...", "created_by": "..."}],
    "metadata": {},
    "created_at": "2026-06-23T10:30:00Z",
    "updated_at": "2026-06-23T10:30:00Z"
  }
}
```

### 5.8 PUT /api/v1/content/{id} — Update Content

**Authentication:** Required (editor or admin role)

**Request Body:**
```json
{
  "generated_text": "updated text...",
  "status": "review",
  "metadata": {"edited_by_human": true}
}
```

**Success Response (200):** Updated content object with new version.

### 5.9 POST /api/v1/content/{id}/approve — Approve Content

**Authentication:** Required (approver or admin role)

**Success Response (200):**
```json
{
  "data": {
    "id": "uuid",
    "status": "approved",
    "approved_by": "user-uuid",
    "approved_at": "2026-06-23T11:00:00Z"
  }
}
```

### 5.10 GET /api/v1/content — List Content (Paginated)

**Authentication:** Required

**Query Parameters:**
- `status`: filter by status
- `content_type`: filter by type
- `target_market`: filter by market
- `cursor`: pagination cursor
- `limit`: page size (default 20, max 100)

**Success Response (200):**
```json
{
  "data": [...],
  "pagination": {
    "next_cursor": "uuid",
    "has_more": true,
    "total_count": 1247
  }
}
```

### 5.11 POST /api/v1/content/{id}/export — Export Content

**Authentication:** Required

**Request Body:**
```json
{
  "format": "docx"
}
```

**Supported formats:** markdown, html, json, docx, pdf

**Success Response (200):** Binary file with `Content-Disposition: attachment` header.

### 5.12 GET /api/v1/brand-voices — List Brand Voices

**Authentication:** Required

**Success Response (200):**
```json
{
  "data": [
    {
      "id": "uuid",
      "name": "Corporate Professional",
      "tone_attributes": {"formality": "high", "personality": "authoritative"},
      "is_active": true,
      "created_at": "..."
    }
  ]
}
```

### 5.13 POST /api/v1/brand-voices — Create Brand Voice

**Authentication:** Required (admin role)

**Request Body:**
```json
{
  "name": "Playful & Approachable",
  "tone_attributes": {
    "formality": "low",
    "personality": "friendly",
    "vocabulary_preferences": "simple, conversational",
    "humor": "light, inclusive"
  },
  "guidelines_text": "We speak like a knowledgeable friend...",
  "sample_content": ["Sample 1 text...", "Sample 2 text..."]
}
```

### 5.14 GET /api/v1/market-profiles — List Market Profiles

**Authentication:** Required

**Query Parameters:**
- `market_code`: filter by market
- `include_system_defaults`: boolean (default true)

### 5.15 GET /api/v1/analytics/usage — Usage Analytics

**Authentication:** Required (admin role)

**Query Parameters:**
- `period`: 7d, 30d, 90d
- `group_by`: day, week, month

**Success Response (200):**
```json
{
  "data": {
    "total_generated": 12450,
    "by_market": {"ja-JP": 3200, "de-DE": 2800, "pt-BR": 2100, "...": "..."},
    "by_content_type": {"product_description": 8000, "blog_post": 2000, "...": "..."},
    "avg_confidence_score": 84.3,
    "total_tokens_used": 15000000,
    "estimated_cost_usd": 125.50,
    "period": "30d"
  }
}
```

### 5.16 WebSocket /ws/jobs/{id}/progress — Real-time Job Progress

**Authentication:** JWT token via query parameter or first message

**Server pushes:**
```json
{
  "type": "progress",
  "job_id": "uuid",
  "completed_items": 848,
  "total_items": 2000,
  "failed_items": 3,
  "timestamp": "2026-06-23T10:35:00Z"
}
```

```json
{
  "type": "completed",
  "job_id": "uuid",
  "summary": {
    "total": 2000,
    "succeeded": 1997,
    "failed": 3,
    "duration_seconds": 3540
  }
}
```

### 5.17 POST /api/v1/experiments — Create Experiment

**Authentication:** Required (JWT or API key with `experiments:write` scope)

**Request Body Schema:**
```json
{
  "name": "German B2B Blog: Data-Driven vs Emotional",
  "hypothesis": "Data-driven content will outperform emotional for German B2B",
  "experiment_type": "content_variant",
  "target_market": "de-DE",
  "content_type": "blog_post",
  "source_content_id": "uuid",
  "variants": [
    {"name": "Control", "variant_type": "control", "content_piece_id": "uuid", "traffic_weight": 0.34},
    {"name": "Data-Driven", "variant_type": "treatment", "cultural_overrides": {"persuasion_style": "evidence", "emotional_expression": "low"}, "traffic_weight": 0.33},
    {"name": "Trust-Building", "variant_type": "treatment", "cultural_overrides": {"persuasion_style": "trust", "uncertainty_avoidance": "high"}, "traffic_weight": 0.33}
  ],
  "success_metric": "ctr",
  "success_criteria": {"min_sample_size": 10000, "min_duration_days": 14, "confidence_threshold": 0.95}
}
```

**Success Response (201):** Experiment object with tracking_urls per variant.

### 5.18 GET /api/v1/experiments — List Experiments

**Authentication:** Required

**Query Parameters:**
- `status`: filter by status (draft/active/paused/completed/cancelled)
- `experiment_type`: filter by type
- `target_market`: filter by market
- `cursor`: pagination cursor
- `limit`: page size (default 20, max 100)

**Success Response (200):** Paginated list of experiment objects.

### 5.19 GET /api/v1/experiments/{id} — Get Experiment Detail

**Authentication:** Required

**Success Response (200):** Full experiment object with variants, assignments count, exposures count, and current metrics.

### 5.20 PUT /api/v1/experiments/{id} — Update Experiment

**Authentication:** Required (editor or admin role)

**Constraint:** Only allowed when experiment status is `draft`.

**Success Response (200):** Updated experiment object.

### 5.21 POST /api/v1/experiments/{id}/start — Start Experiment

**Authentication:** Required (admin role)

**Behavior:** Validates all variants approved, sets status=active, activates assignment engine, emits `experiment.started` webhook.

**Success Response (200):**
```json
{
  "data": {
    "id": "uuid",
    "status": "active",
    "started_at": "2026-06-24T10:00:00Z"
  }
}
```

### 5.22 POST /api/v1/experiments/{id}/pause — Pause Experiment

**Authentication:** Required (admin role)

**Success Response (200):** Updated experiment object with status `paused`.

### 5.23 POST /api/v1/experiments/{id}/stop — Stop Experiment

**Authentication:** Required (admin role)

**Success Response (200):** Updated experiment object with status `completed`.

### 5.24 GET /api/v1/experiments/{id}/results — Get Results

**Authentication:** Required

**Success Response (200):**
```json
{
  "data": {
    "experiment_id": "uuid",
    "status": "active",
    "per_variant_metrics": [
      {
        "variant_id": "uuid",
        "variant_name": "Control",
        "assignments_count": 5200,
        "exposures_count": 4800,
        "ctr": 0.042,
        "conversion_rate": 0.012,
        "engagement_score": 0.65
      }
    ],
    "statistical_analysis": {
      "test_used": "chi-squared",
      "p_value": 0.003,
      "confidence_level": 0.997,
      "effect_size": 0.15,
      "recommendation": "Variant A (Data-Driven) shows statistically significant improvement over Control"
    },
    "per_locale_breakdown": {
      "de-DE": {"variant_a_ctr": 0.045, "variant_b_ctr": 0.038},
      "de-AT": {"variant_a_ctr": 0.041, "variant_b_ctr": 0.035}
    },
    "winner_recommendation": "variant-a-uuid"
  }
}
```

### 5.25 POST /api/v1/experiments/{id}/promote-winner — Promote Winner

**Authentication:** Required (admin role)

**Behavior:** Sets winner variant traffic_weight to 1.0, all others to 0.0, archives losing variants, stores winning cultural_overrides as feedback for future generation per market.

**Success Response (200):** Updated experiment object.

### 5.26 POST /api/v1/performance-events — Ingest Performance Event

**Authentication:** Required (JWT or API key with `events:write` scope)

**Request Body Schema:**
```json
{
  "experiment_id": "uuid",
  "variant_id": "uuid",
  "event_type": "click",
  "visitor_hash": "sha256-hash",
  "event_data": {"element": "cta-button", "position": "above-fold"},
  "locale": "de-DE",
  "source": "internal"
}
```

**Success Response (201):** Event acknowledgment.

### 5.27 POST /api/v1/performance-events/batch — Ingest Batch of Events

**Authentication:** Required (JWT or API key with `events:write` scope)

**Request Body:**
```json
{
  "events": [
    {"experiment_id": "uuid", "variant_id": "uuid", "event_type": "page_view", "visitor_hash": "...", "source": "internal"},
    {"experiment_id": "uuid", "variant_id": "uuid", "event_type": "click", "visitor_hash": "...", "source": "internal"}
  ]
}
```

**Constraint:** Maximum 100 events per batch.

**Success Response (201):** Batch acknowledgment with count of accepted events.

### 5.28 POST /api/v1/performance-events/webhook/{connector} — Webhook Receiver

**Authentication:** Signed payload verification (HMAC)

**Path Parameter:** `connector` — one of `segment`, `google_analytics`, `mixpanel`

**Behavior:** Receives signed webhook payloads from external analytics tools, validates signature, normalizes events, and stores as performance events.

**Success Response (200):** Acknowledgment with count of processed events.

### 5.29 POST /api/v1/experiments/model-comparison — Create Model Comparison Experiment

**Authentication:** Required (JWT or API key with `experiments:write` scope)

**Request Body:**
```json
{
  "name": "German Blog: GPT-4 vs Claude 3.5 Quality",
  "hypothesis": "Claude 3.5 produces higher engagement for German blog content",
  "experiment_type": "model_comparison",
  "target_market": "de-DE",
  "content_type": "blog_post",
  "source_content_id": "uuid",
  "variants": [
    {"name": "GPT-4", "variant_type": "model_a", "model_used": "gpt-4-turbo", "traffic_weight": 0.5},
    {"name": "Claude 3.5", "variant_type": "model_b", "model_used": "claude-3.5-sonnet", "traffic_weight": 0.5}
  ],
  "success_metric": "engagement",
  "success_criteria": {"min_sample_size": 5000, "min_duration_days": 7, "confidence_threshold": 0.95}
}
```

**Success Response (201):** Experiment object with model comparison variants.

### 5.30 GET /api/v1/prompt-versions — List Prompt Versions

**Authentication:** Required

**Query Parameters:**
- `content_type`: filter by content type
- `is_active`: filter by active status
- `cursor`: pagination cursor
- `limit`: page size (default 20, max 100)

**Success Response (200):** Paginated list of prompt version objects.

### 5.31 POST /api/v1/prompt-versions — Create Prompt Version

**Authentication:** Required (editor or admin role)

**Request Body:**
```json
{
  "name": "Data-Driven German B2B v2",
  "content_type": "blog_post",
  "system_prompt_template": "You are a B2B content writer specializing in data-driven...",
  "user_prompt_template": "Write a blog post about {{topic}} for the German market...",
  "cultural_overrides": {"persuasion_style": "evidence", "formality_level": 5}
}
```

**Success Response (201):** Created prompt version object.

---

## 6. Business Logic Specification

### 6.1 Single Content Generation Pipeline

**Trigger:** User submits generation request via API or UI.

**Step-by-step execution:**

```
1. REQUEST VALIDATION
   ├─ Validate required fields (content_type, source_language, target_markets)
   ├─ Validate market codes against supported markets list
   ├─ Validate content_type against supported types
   ├─ Check workspace quota/limits
   └─ Return 400 if validation fails

2. CONTEXT RETRIEVAL (parallel where possible)
   ├─ 2a. Vault Connector → retrieve brand voice profile (or workspace default)
   ├─ 2b. Vault Connector → retrieve terminology glossary for workspace
   ├─ 2c. Vault Connector → semantic search for relevant product knowledge
   ├─ 2d. Cultural Adaptation Engine → load market profiles for each target market
   └─ Timeout: 500ms for Vault; proceed with cache on timeout

3. PROMPT COMPOSITION (per target market)
   ├─ 3a. Cultural Adaptation Engine → compute cultural transformation parameters
   │       Input: market_code, brand_voice, source content
   │       Output: {formality_weight, directness_weight, humor_weight, 
   │                persuasion_style, structural_preferences, taboos_to_avoid}
   ├─ 3b. Prompt Composer → assemble final prompt
   │       Components:
   │       - System prompt: role definition + cultural directives
   │       - Brand voice section: tone, personality, vocabulary rules
   │       - Terminology section: required terms, prohibited terms
   │       - Knowledge context: relevant Vault content (RAG results)
   │       - Content type template: structure requirements
   │       - Source content/brief: what to generate/localize
   │       - Output constraints: length, format, keywords
   ├─ 3c. Token budget check → trim if exceeds model context window
   └─ 3d. Compute prompt_hash (SHA-256) for cache lookup

4. CACHE CHECK
   ├─ Compute hash = SHA256(prompt + model_id + parameters)
   ├─ Check Redis cache for hash hit
   ├─ If HIT: return cached result immediately (skip to step 7)
   └─ If MISS: proceed to generation

5. LLM DISPATCH
   ├─ 5a. Fallback Router → select model (primary or fallback based on health)
   ├─ 5b. LLM Abstraction Layer → translate request to provider format
   ├─ 5c. Dispatch to model adapter (HTTP request with streaming SSE)
   ├─ 5d. Receive response (or stream tokens)
   ├─ 5e. On failure: retry with exponential backoff (max 3 attempts)
   ├─ 5f. On persistent failure: circuit breaker opens, route to fallback model
   └─ 5g. Normalize response to standard format

6. POST-PROCESSING
   ├─ 6a. Terminology enforcement → verify required terms present, prohibited absent
   ├─ 6b. Quality Scoring Engine → compute confidence score
   │       Components:
   │       - Terminology compliance (0-30 points)
   │       - Vault grounding verification (0-30 points)
   │       - Length/format conformance (0-20 points)
   │       - Cultural coherence heuristic (0-20 points)
   ├─ 6c. Flag generation → identify content needing human review
   │       Triggers: score < 60, terminology violations, sensitive topics,
   │                 ungrounded claims, cultural sensitivity warnings
   └─ 6d. Store result in generation cache (Redis + PostgreSQL)

7. PERSISTENCE
   ├─ Create content_pieces record (status: draft)
   ├─ Create initial content_version record
   ├─ Record generation metadata (model, latency, prompt_hash, vault_sources)
   └─ Emit domain event: content.generated

8. RESPONSE
   ├─ Return generated content with metadata
   ├─ Async: emit audit event
   └─ Async: update analytics counters
```

**Edge cases:**
- Source text is empty and brief is empty → 400 error
- Target market not supported → 400 with list of supported markets
- Brand voice not found → use workspace default; if none, generate without brand voice (flag in output)
- Vault completely unavailable → proceed with cached data, flag output
- All LLM providers unavailable → return 503 with retry-after header
- Prompt exceeds context window → truncate knowledge context (preserve brand voice + cultural directives)

### 6.2 Bulk Job Processing Pipeline

**Trigger:** User uploads bulk input file via API.

**Step-by-step execution:**

```
1. INPUT VALIDATION
   ├─ Parse uploaded file (CSV/XLSX)
   ├─ Validate structure: required columns present
   ├─ Validate row count (max 100,000 per job)
   ├─ Calculate total_items = rows × target_markets count
   └─ Return 400 if invalid

2. JOB CREATION
   ├─ Create bulk_jobs record (status: pending)
   ├─ Upload input file to object storage
   ├─ Decompose into individual generation tasks
   │       Each task = {source_row_data, target_market, configuration}
   └─ Push tasks to Redis Streams job queue

3. WORKER CONSUMPTION
   ├─ Worker pool consumes tasks from Redis Streams consumer group
   ├─ Each worker:
   │   ├─ Acknowledge task (visibility timeout)
   │   ├─ Run full generation pipeline (steps 2-7 from single generation)
   │   ├─ Write result to content_pieces table
   │   ├─ Increment completed_items atomically (PostgreSQL)
   │   ├─ Every 10 items: checkpoint job progress to PostgreSQL
   │   └─ Emit progress event (WebSocket + webhook if configured)
   └─ On task failure:
       ├─ Retry within worker (max 2 attempts)
       ├─ If persistent failure: mark task as failed, increment failed_items
       └─ Redis consumer group redelivers unacknowledged tasks on worker crash

4. JOB COMPLETION
   ├─ When completed_items + failed_items == total_items:
   │   ├─ Update job status to "completed"
   │   ├─ Compute summary statistics
   │   ├─ Generate summary report
   │   └─ Emit job.completed event
   └─ User notified via WebSocket + webhook

5. PAUSE/RESUME/CANCEL
   ├─ PAUSE: Set job status to "paused"; workers stop consuming this job's tasks
   ├─ RESUME: Set status back to "processing"; workers resume consumption
   └─ CANCEL: Discard remaining tasks from queue; preserve partial results;
              set status to "cancelled"
```

**Failure handling:**
- Worker crash: Redis consumer group redelivers unacknowledged tasks to another worker
- PostgreSQL connection loss: workers retry; job state preserved in Redis
- Redis failure: bulk jobs cannot proceed; existing results safe in PostgreSQL
- Individual task failure: logged, counted, remaining tasks continue

### 6.3 Content Lifecycle State Machine

```
States: draft → review → approved | rejected
                         ↓
                      archived

Transitions:
  draft → review:     Editor submits for review
  review → approved:  Approver approves content
  review → rejected:  Approver rejects (returns to draft with feedback)
  review → draft:     Editor withdraws from review
  approved → archived: Admin archives content
  draft → archived:   Admin archives content
  
Rules:
  - Only editors/admins can create content (initial state: draft)
  - Only approvers/admins can approve/reject
  - Rejected content returns to draft with feedback attached
  - Archived content is read-only
  - All transitions logged to audit_logs
```

### 6.4 Cultural Adaptation Logic

```
INPUT: market_code (e.g., 'ja-JP'), source_content, brand_voice

1. LOAD MARKET PROFILE
   - Retrieve cultural_dimensions for market_code
   - Dimensions: formality_level (1-5), directness (1-5), individualism (1-5),
     humor_appropriateness (1-5), persuasion_style (relationship/direct/evidence/emotional),
     structural_preference (linear/circular/hierarchical)

2. COMPUTE TRANSFORMATION DIRECTIVES
   - Map dimensions to LLM instructions:
     formality_level=5 (Japan) → "Use keigo (honorific speech). Avoid casual expressions."
     directness=2 (Japan) → "Be indirect. Use hedging language. Avoid blunt statements."
     persuasion_style=relationship → "Lead with relationship-building. Establish trust before pitch."
   
3. GENERATE CULTURAL CONTEXT BLOCK
   - Combine market directives with brand voice constraints
   - Resolve conflicts: brand voice takes precedence unless cultural taboo
   - Add taboos/sensitivities list as hard constraints
   
4. OUTPUT: Structured directive object for Prompt Composer
```

### 6.5 Quality Scoring Algorithm

```
INPUT: generated_text, vault_sources, glossary, market_profile

SCORE COMPONENTS (total = 100):

1. TERMINOLOGY COMPLIANCE (0-30 points)
   - Check all required terms present: +5 per term (max 15)
   - Check no prohibited terms present: +15 if clean, -5 per violation
   - Normalize: score = max(0, computed)

2. VAULT GROUNDING (0-30 points)
   - Extract claims from generated text
   - Verify each claim against vault_sources
   - Grounded claims: +5 each (max 25)
   - Ungrounded claims (potential hallucination): -10 each
   - Base score: 10 (for having any Vault context)

3. LENGTH/FORMAT CONFORMANCE (0-20 points)
   - Within requested length range: +20
   - Slightly over/under (±20%): +10
   - Significantly off (>±50%): +0
   - Correct format structure: +5 bonus (if template specified)

4. CULTURAL COHERENCE HEURISTIC (0-20 points)
   - Formality level matches market expectation: +10
   - No obvious cultural violations (taboo words/phrases): +10
   - Structural preference followed: +5 bonus

TOTAL: sum of components, clamped to [0, 100]

FLAG THRESHOLDS:
  score < 60 → flag for human review (high priority)
  score 60-75 → flag for human review (medium priority)
  score > 75 → no flag (acceptable quality)
  Any terminology violation → flag regardless of score
  Any ungrounded claim → flag as "potential hallucination"
```

### 6.6 Experiment Management Pipeline

**Trigger:** User creates experiment via API or UI.

**Step-by-step execution:**

```
1. CREATION
   ├─ Validate variants (2-5 variants required)
   ├─ Validate traffic allocation (weights must sum to 1.0)
   ├─ Create experiment record (status: draft)
   ├─ Create variant records with cultural_overrides
   ├─ For each variant:
   │   ├─ Generate content using cultural_overrides via Generation Orchestrator
   │   ├─ Create content_piece for variant (if not provided)
   │   └─ Generate tracking URLs with UTM parameters
   │       Format: {base_url}?utm_source=pulse&utm_medium=experiment&utm_campaign={experiment_id}&utm_variant={variant_id}
   └─ Return experiment object with tracking_urls

2. START
   ├─ Validate all variant content_pieces are approved
   ├─ Set experiment status to active
   ├─ Set started_at timestamp
   ├─ Activate assignment engine (enable Redis cache for assignments)
   └─ Emit experiment.started webhook

3. VARIANT ASSIGNMENT
   ├─ Compute visitor_hash = SHA256(visitor_id + experiment_id)
   ├─ Lookup existing assignment in Redis cache
   ├─ If assignment exists:
   │   └─ Return assigned variant content immediately
   ├─ If no assignment:
   │   ├─ Allocate variant by traffic_weight (deterministic based on visitor_hash)
   │   ├─ Create assignment record in experiment_assignments table
   │   ├─ Cache assignment in Redis (TTL: 24 hours)
   │   ├─ Increment variant assignments_count
   │   └─ Return variant content
   └─ Variant content includes: generated_text, tracking_pixel_url, metadata

4. EXPOSURE TRACKING
   ├─ When content actually viewed (tracking pixel fires or explicit API call)
   ├─ Create exposure record in experiment_exposures table
   ├─ Increment variant exposures_count
   ├─ Exposure tracking separates assignments from actual views
   └─ Enables treatment-on-treated analysis (only count users who actually saw content)

5. EVENT INGESTION
   ├─ Receive events via webhook (Segment/GA4/Mixpanel) or direct API
   ├─ Validate event signature (for webhooks)
   ├─ Normalize external event format to internal PerformanceEvent
   ├─ Correlate event with assignment via visitor_hash
   ├─ Store in performance_events table (partitioned by week)
   ├─ Update variant rolling metrics (ctr, conversions, engagement)
   └─ Emit performance.event_received domain event

6. RESULTS COMPUTATION (hourly batch)
   ├─ For each active experiment:
   │   ├─ Check if min_duration (days since started_at) met
   │   ├─ Check if min_sample_size met for all variants
   │   ├─ If criteria met:
   │   │   ├─ Compute chi-squared test for success_metric
   │   │   ├─ Calculate p-value and confidence_level
   │   │   ├─ Compute effect_size (Cohen's h for proportions)
   │   │   ├─ Optional: run Bayesian analysis (posterior probability)
   │   │   ├─ Compare confidence_level to success_criteria.confidence_threshold
   │   │   ├─ If confidence > threshold:
   │   │   │   ├─ Determine winner (variant with highest metric)
   │   │   │   ├─ Set winner_variant_id
   │   │   │   ├─ Set status to completed
   │   │   │   ├─ Set completed_at timestamp
   │   │   │   ├─ Store results_summary
   │   │   │   └─ Emit experiment.completed webhook
   │   │   └─ If confidence < threshold:
   │   │       └─ Continue experiment (no action)
   │   └─ If criteria not met:
   │       └─ Continue experiment (no action)
   └─ Log computation results for observability

7. WINNER PROMOTION
   ├─ Set winner variant traffic_weight to 1.0
   ├─ Set all other variants traffic_weight to 0.0
   ├─ Archive losing variants (set is_active = false)
   ├─ Store winning cultural_overrides as feedback for future generation:
   │   ├─ Update market profile with successful adaptation parameters
   │   └─ Tag content metadata with winning variant cultural_overrides
   └─ Emit experiment.winner_promoted webhook
```

**Edge cases:**
- Variant generation fails → experiment remains in draft, error reported to user
- Traffic allocation doesn't sum to 1.0 → 400 error at creation
- Experiment started with unapproved variants → 409 error
- Performance events received for non-existent experiment → 404 error, event logged for debugging
- Statistical computation fails → retry with exponential backoff, alert on persistent failure
- Winner promotion on inactive experiment → 409 error

#### 6.6.1 Event Tracking Schema

**Standard exposure event schema (Segment-compatible):**

```json
{
  "event_type": "experiment_exposure",
  "entity_id": "visitor_hash",
  "experiment_id": "uuid",
  "variant_key": "treatment_a",
  "timestamp": "ISO8601",
  "context": {
    "platform": "web",
    "device_type": "mobile",
    "country": "DE",
    "locale": "de-DE"
  },
  "properties": {
    "content_id": "uuid",
    "content_type": "blog_post"
  }
}
```

**Schema notes:**
- `event_type`: Fixed value `experiment_exposure` for exposure events. Other event types use corresponding values (e.g., `experiment_click`, `experiment_conversion`).
- `entity_id`: SHA256 hash of visitor identifier — matches `visitor_hash` in assignment and performance_events tables.
- `variant_key`: Human-readable variant identifier (e.g., `treatment_a`, `control`) — maps to `experiment_variants.name`.
- `context.platform`: One of `web`, `mobile`, `email`, `social`, `ads`.
- `context.device_type`: One of `desktop`, `mobile`, `tablet`.
- `context.country`: ISO 3166-1 alpha-2 country code.
- `context.locale`: ISO 639-1 language + region code (e.g., `de-DE`, `ja-JP`).
- `properties.content_id`: UUID of the content_piece shown to the visitor.
- `properties.content_type`: Type of content (matches `content_pieces.content_type`).
- This schema is compatible with Segment's `track` API, enabling direct ingestion from Segment-connected sources.

---

## 7. State Management & Data Flow

### 7.1 Stateless vs Stateful Components

- **Stateless:** `pulse-api` instances (all session state in Redis, all persistent state in PostgreSQL), `pulse-worker` processes (stateless between tasks; job progress checkpointed to PostgreSQL)
- **Stateful:** PostgreSQL (primary data store), Redis (cache + job queue), Object Storage (files)

### 7.2 Caching Layers

- **Redis — Brand Voice Cache:** Active brand voice profiles per workspace, TTL 5 minutes, invalidated on Vault update event
- **Redis — Glossary Cache:** Active terminology glossaries per workspace, TTL 5 minutes, invalidated on glossary update
- **Redis — Market Profiles Cache:** Cultural adaptation profiles, TTL 1 hour, invalidated on profile update
- **Redis — Generation Cache:** Hash of (prompt + model + parameters) → result, TTL 24 hours, content-based invalidation
- **Redis — Rate Limit Counters:** Per-API-key request counts, TTL = window duration (1 minute)
- **Application Memory — Prompt Templates:** Compiled prompt templates, process lifetime, invalidated on deployment

### 7.3 Data Flow Map

```
Request → API Gateway → Auth Middleware → Tenant Isolation (workspace injection)
  → Module Handler → [Vault retrieval (cached)] → [Prompt composition]
  → [LLM dispatch (with fallback)] → [Quality scoring] → [Persistence]
  → Response → [Async: audit log, analytics, webhook dispatch]
```

---

## 8. Background Jobs & Asynchronous Processing

### 8.1 Job Types

| Job Name | Trigger | Queue | Retry Logic | Idempotency |
|---|---|---|---|---|
| Bulk Generation Task | Bulk job submission | Redis Streams (`pulse:jobs:{job_id}`) | 3 retries, immediate redelivery via consumer group | Task IDempotency key = (job_id, row_index, market) |
| Webhook Delivery | Domain event emitted | Redis Streams (`pulse:webhooks`) | 5 retries: 1min, 5min, 30min, 2hr, 12hr backoff | Delivery ID ensures no duplicate sends |
| Analytics Aggregation | Scheduled (every 5 min) | `pulse-scheduler` cron | 2 retries on failure | Aggregation keyed by time window |
| Cache Cleanup | Scheduled (hourly) | `pulse-scheduler` cron | No retry needed | Deletes expired entries only |
| Vault Writeback | Content approved | Redis Streams (`pulse:vault-writeback`) | 3 retries, 500ms/1s/2s backoff | Content ID + version ensures no duplicate writes |
| Experiment Results Computation | Hourly cron | `pulse-scheduler` cron | 2 retries on failure | Computation keyed by experiment_id + time window |
| Performance Event Aggregation | Every 5 min | `pulse-scheduler` cron | 2 retries on failure | Aggregation keyed by experiment_id + variant_id + time window |
| Analytics Sync | Every 15 min | `pulse-scheduler` cron | 3 retries, 1min/5min/30min backoff | Sync cursor per connector prevents duplicate pulls |

### 8.2 Queue System

- **Technology:** Redis Streams with consumer groups
- **Streams:** `pulse:jobs:{job_id}` (per-job task queue), `pulse:webhooks` (webhook delivery), `pulse:vault-writeback` (Vault sync)
- **Consumer Groups:** One group per worker pool; exactly-once semantics via ACK-based consumption
- **Durability:** Redis AOF + RDB persistence; Sentinel for HA

### 8.3 Failure Handling Strategy

- **Task failure:** Logged, marked failed in job progress, remaining tasks continue
- **Worker crash:** Consumer group redelivers unacknowledged tasks to surviving workers
- **Queue persistence loss:** Job state in PostgreSQL allows reconstruction; tasks re-decomposed from input file
- **Dead letter:** After max retries, webhook deliveries moved to dead-letter table for manual inspection

---

## 9. External Integrations

### 9.1 LLM Providers

| Provider | Endpoint | Auth | Rate Limits | Fallback |
|---|---|---|---|---|
| OpenAI | `https://api.openai.com/v1/chat/completions` | Bearer token (API key) | Per-model TPM/RPM limits | Route to next provider in chain |
| Anthropic | `https://api.anthropic.com/v1/messages` | x-api-key header | Per-org RPM limits | Route to next provider |
| Mistral | `https://api.mistral.ai/v1/chat/completions` | Bearer token | Per-key limits | Route to next provider |
| Azure OpenAI | Customer's Azure endpoint | API key or AAD token | Deployment-specific TPM | Route to next provider |
| AWS Bedrock | AWS SDK (InvokeModel) | AWS IAM credentials | Account-level TPM | Route to next provider |
| Ollama (local) | `http://localhost:11434/api/generate` | None (local) | Hardware-limited | Route to cloud provider |
| vLLM (local) | `http://localhost:8000/v1/chat/completions` | None (local) | Hardware-limited | Route to cloud provider |

**Fallback Strategy:** Configurable ordered chain per workspace. Circuit breaker per provider (opens after 3 failures in 60s). If all providers fail, jobs queue until recovery.

### 9.2 Vault (ODW.ai)

- **Endpoint:** Customer's Vault instance URL (configured per workspace)
- **Auth:** mTLS or shared JWT audience (service-to-service)
- **Key APIs:** `GET /api/v1/knowledge/search` (semantic search), `GET /api/v1/brand-voices/{id}`, `GET /api/v1/glossaries/{id}`, `POST /api/v1/content` (writeback)
- **Rate Limits:** Configured per deployment; Pulse caches aggressively to minimize calls
- **Fallback:** Local cache (Redis) provides degraded-but-functional mode when Vault unavailable

### 9.3 Object Storage (S3/MinIO)

- **Endpoint:** S3 API endpoint (AWS or MinIO URL)
- **Auth:** AWS credentials (access key/secret) or MinIO credentials
- **Usage:** Bulk job input files, content exports, generated content archives
- **Fallback:** Generation continues without storage; exports unavailable until storage recovers

---

## 10. Configuration & Environment Variables

### 10.1 Required Environment Variables

| Variable | Purpose | Example (Dev) | Example (Prod) |
|---|---|---|---|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://pulse:dev@localhost:5432/pulse` | `postgresql://pulse:${DB_PASS}@db-primary:5432/pulse` |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379/0` | `redis://:${REDIS_PASS}@redis-primary:6379/0` |
| `VAULT_BASE_URL` | Vault API base URL | `http://localhost:8080` | `https://vault.customer.com` |
| `VAULT_API_TOKEN` | Vault service authentication | `dev-vault-token` | `${VAULT_TOKEN}` (from secrets manager) |
| `OBJECT_STORAGE_ENDPOINT` | S3-compatible endpoint | `http://localhost:9000` | `https://s3.amazonaws.com` |
| `OBJECT_STORAGE_BUCKET` | Storage bucket name | `pulse-dev` | `pulse-prod-${workspace}` |
| `OBJECT_STORAGE_ACCESS_KEY` | Storage auth | `minioadmin` | `${S3_ACCESS_KEY}` |
| `OBJECT_STORAGE_SECRET_KEY` | Storage auth | `minioadmin` | `${S3_SECRET_KEY}` |
| `JWT_SECRET` | JWT signing key | `dev-secret-change-me` | `${JWT_SECRET}` (64+ char random) |
| `API_HOST` | Listen address | `0.0.0.0` | `0.0.0.0` |
| `API_PORT` | Listen port | `8000` | `8000` |
| `LOG_LEVEL` | Logging verbosity | `DEBUG` | `INFO` |
| `ENVIRONMENT` | Environment identifier | `development` | `production` |

### 10.2 LLM Provider Configuration (per workspace, stored in DB)

| Variable | Purpose | Example |
|---|---|---|
| `OPENAI_API_KEY` | OpenAI authentication | `sk-...` |
| `ANTHROPIC_API_KEY` | Anthropic authentication | `sk-ant-...` |
| `MISTRAL_API_KEY` | Mistral authentication | `...` |
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI deployment URL | `https://{instance}.openai.azure.com` |
| `AWS_ACCESS_KEY_ID` | Bedrock authentication | `AKIA...` |
| `AWS_SECRET_ACCESS_KEY` | Bedrock authentication | `...` |
| `OLLAMA_BASE_URL` | Local Ollama endpoint | `http://localhost:11434` |
| `VLLM_BASE_URL` | Local vLLM endpoint | `http://localhost:8000` |

### 10.3 Operational Configuration

| Variable | Purpose | Default |
|---|---|---|
| `WORKER_CONCURRENCY` | Tasks per worker process | `5` |
| `MAX_BULK_JOB_SIZE` | Maximum items per bulk job | `100000` |
| `GENERATION_CACHE_TTL` | Cache TTL in seconds | `86400` (24h) |
| `VAULT_CACHE_TTL` | Vault data cache TTL | `300` (5min) |
| `MAX_GENERATION_TIMEOUT` | LLM call timeout in seconds | `60` |
| `WEBHOOK_MAX_RETRIES` | Webhook delivery retries | `5` |
| `RATE_LIMIT_RPM` | Default API rate limit (per key) | `60` |
| `TRACING_ENABLED` | OpenTelemetry tracing | `true` |
| `TRACING_SAMPLE_RATE` | Trace sampling rate (success) | `0.01` (1%) |

---

## 11. Security Implementation Details

### 11.1 Authentication Flow

1. **UI Users:** OIDC/SAML SSO → IdP returns auth code → Pulse exchanges for JWT → JWT contains `workspace_id`, `user_id`, `role`, `scopes`
2. **API Consumers:** API key in `X-API-Key` header → Pulse hashes and looks up in `api_keys` table → Validates scopes and rate limits
3. **Inter-service (Pulse ↔ Vault):** mTLS certificate authentication or shared JWT audience claim

**JWT Claims:**
```json
{
  "sub": "user-uuid",
  "workspace_id": "workspace-uuid",
  "role": "editor",
  "scopes": ["generate", "read", "write"],
  "iat": 1719100000,
  "exp": 1719103600,
  "iss": "pulse.odw.ai"
}
```

**Token Expiry:** Access tokens: 1 hour. Refresh tokens: 7 days (rotatable).

### 11.2 Authorization Model (RBAC)

| Role | Generate | Read | Write | Approve | Admin |
|---|---|---|---|---|---|
| Admin | ✓ | ✓ | ✓ | ✓ | ✓ |
| Editor | ✓ | ✓ | ✓ | ✗ | ✗ |
| Approver | ✗ | ✓ | ✗ | ✓ | ✗ |
| Viewer | ✗ | ✓ | ✗ | ✗ | ✗ |

### 11.3 Data Encryption

- **At rest:** AES-256 (PostgreSQL TDE or encrypted volumes, Redis encrypted volumes, S3 SSE-S3/SSE-KMS)
- **In transit:** TLS 1.3 for all external and internal communication
- **Secrets:** Never logged; stored in memory only; HashiCorp Vault / AWS Secrets Manager / K8s Secrets

### 11.4 Input Validation

- All API inputs validated against Pydantic schemas before processing
- Content length limits (max 50,000 characters per generation request)
- File upload size limits (max 50MB), type validation (CSV/XLSX only)
- Prompt injection defense: system/user prompt separation; input sanitization; output scanning for prompt leakage
- SQL injection prevention: parameterized queries via SQLAlchemy ORM

---

## 12. Error Handling & Logging

### 12.1 Error Categories

| Category | HTTP Code | Error Code Prefix | Example |
|---|---|---|---|
| Validation | 400 | `VALIDATION_*` | `VALIDATION_INVALID_MARKET` |
| Authentication | 401 | `AUTH_*` | `AUTH_TOKEN_EXPIRED` |
| Authorization | 403 | `PERMISSION_*` | `PERMISSION_INSUFFICIENT_ROLE` |
| Not Found | 404 | `NOT_FOUND_*` | `NOT_FOUND_CONTENT` |
| Conflict | 409 | `CONFLICT_*` | `CONFLICT_INVALID_STATE_TRANSITION` |
| Rate Limit | 429 | `RATE_LIMIT_*` | `RATE_LIMIT_EXCEEDED` |
| External Dependency | 502/503 | `DEPENDENCY_*` | `DEPENDENCY_LLM_UNAVAILABLE` |
| Internal | 500 | `INTERNAL_*` | `INTERNAL_UNEXPECTED_ERROR` |

### 12.2 Logging Format

```json
{
  "timestamp": "2026-06-23T10:30:00.123Z",
  "level": "INFO",
  "service": "pulse-api",
  "module": "generation-orchestrator",
  "request_id": "req-uuid",
  "workspace_id": "ws-uuid",
  "message": "Generation completed",
  "context": {
    "content_id": "content-uuid",
    "model": "gpt-4-turbo",
    "market": "ja-JP",
    "latency_ms": 4200,
    "confidence_score": 87
  }
}
```

**Rules:**
- API keys, tokens, customer content NEVER logged at INFO or above
- Prompt content logged only at DEBUG with PII redaction
- All errors logged with full stack trace at ERROR level
- Correlation via `request_id` (generated at API gateway, propagated through all components)

---

## 13. Performance Considerations

### 13.1 Expected Load

- **API tier:** 500 concurrent users, ~200 requests/second at peak
- **Generation throughput:** ~50 content pieces/minute per worker (depends on LLM latency)
- **Bulk jobs:** Up to 100,000 items per job, processed by 10-20 workers
- **Data volume:** 10M+ content pieces across all workspaces within 12 months

### 13.2 Bottleneck Analysis & Optimization

| Bottleneck | Impact | Optimization |
|---|---|---|
| LLM API latency (5-25s per call) | Limits generation throughput | Streaming responses; generation caching; multi-model routing; batch API pricing |
| PostgreSQL writes during bulk jobs | High write volume | Batch inserts (100 per transaction); PgBouncer; partitioned tables |
| Vault retrieval latency (up to 500ms) | Adds to per-request latency | Redis cache (5min TTL); pre-warming on workspace activation |
| Prompt composition (CPU-bound) | Minor per-request cost | Pre-compiled templates; cached market profiles; O(1) assembly |

### 13.3 Latency Budget (Single Generation)

| Step | Target | Max |
|---|---|---|
| Auth + validation | 10ms | 50ms |
| Vault retrieval | 100ms (cached) | 500ms |
| Cultural adaptation | 5ms | 20ms |
| Prompt composition | 10ms | 50ms |
| LLM generation | 5-15s | 25s |
| Quality scoring | 50ms | 200ms |
| Persistence | 20ms | 100ms |
| **Total** | **6-16s** | **<30s** |

---

## 14. Testing Strategy

### 14.1 Unit Tests

- **Coverage target:** >80% line coverage across all modules
- **Focus areas:** Prompt composition logic, cultural adaptation calculations, quality scoring algorithm, state machine transitions, input validation
- **Framework:** pytest + pytest-asyncio
- **Mocking:** All external dependencies (LLM providers, Vault, S3) mocked via fixture-based mocks

### 14.2 Integration Tests

- **Scope:** API endpoint testing (full request/response cycle), database operations (including RLS enforcement), Redis operations (caching, job queue), Vault connector (against test Vault instance)
- **Environment:** Docker Compose with test PostgreSQL, Redis, MinIO
- **Key scenarios:** Multi-tenant isolation verification (cross-workspace queries must fail), job lifecycle (create → process → complete), fallback routing (primary fails → secondary succeeds)

### 14.3 End-to-End Tests

- **Scenario 1:** Full generation flow (API → generation → quality check → persistence → retrieval)
- **Scenario 2:** Bulk job lifecycle (upload → process → progress tracking → completion → export)
- **Scenario 3:** Cultural adaptation validation (generate for 5+ markets, verify cultural directives applied)
- **Scenario 4:** Failure recovery (LLM provider down → fallback activates → generation succeeds)
- **Scenario 5:** Air-gapped mode (no outbound network → local models → generation succeeds)

### 14.4 Mocking Strategy

- **LLM providers:** Mock adapter returning deterministic responses for testing; separate "smoke test" suite hitting real APIs (gated, not in CI)
- **Vault:** Test Vault instance with synthetic knowledge base
- **Time:** Freeze time via pytest-freezer for deterministic timestamp testing

---

## 15. Deployment & Build Instructions

### 15.1 Build Steps

```bash
# Backend
cd pulse-api
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest tests/                          # Run tests
alembic upgrade head                   # Apply migrations
uvicorn pulse.main:app --host 0.0.0.0 --port 8000

# Frontend
cd pulse-ui
npm install
npm run build                          # Production build → dist/

# Docker
docker build -t pulse-api:latest -f Dockerfile.api .
docker build -t pulse-worker:latest -f Dockerfile.worker .
docker build -t pulse-scheduler:latest -f Dockerfile.scheduler .
docker build -t pulse-ui:latest -f Dockerfile.ui .
```

### 15.2 Dockerfile Requirements

- **Base image:** `python:3.11-slim` (API/worker/scheduler), `node:20-alpine` (UI build) → `nginx:alpine` (UI serve)
- **Security:** Non-root user, minimal packages, no secrets in image layers
- **Health checks:** `HEALTHCHECK CMD curl -f http://localhost:8000/health/live`
- **Multi-stage builds:** Separate build and runtime stages

### 15.3 Service Startup Sequence

```
1. PostgreSQL (primary) — wait for ready
2. Redis — wait for ready
3. pulse-scheduler — starts after DB + Redis
4. pulse-api (2+ replicas) — starts after DB + Redis + Vault connectivity confirmed
5. pulse-worker (1+ replicas) — starts after pulse-api (needs job queue available)
6. pulse-ui — starts after pulse-api (needs API availability)
```

### 15.4 CI/CD Pipeline

```
PR → Lint + Type Check → Unit Tests → Build Image → Security Scan → Integration Tests
  → Merge to main → Build + Tag → Deploy to Staging → Performance Benchmark
  → Manual approval → Deploy to Production (rolling update + canary analysis)
```

---

## 16. Observability Hooks

### 16.1 Metrics (Prometheus `/metrics` endpoint)

- `pulse_generation_total{model, market, status}` — generation count by model/market/status
- `pulse_generation_duration_seconds{model, market}` — generation latency histogram
- `pulse_confidence_score{market, content_type}` — quality score distribution
- `pulse_bulk_jobs_active` — currently processing bulk jobs
- `pulse_bulk_job_items_total{status}` — bulk job item counts
- `pulse_llm_request_total{provider, model, status}` — LLM API calls
- `pulse_llm_request_duration_seconds{provider, model}` — LLM latency
- `pulse_llm_tokens_total{provider, model, type}` — token consumption
- `pulse_vault_retrieval_duration_seconds` — Vault query latency
- `pulse_vault_cache_hit_total` — cache hit rate
- `pulse_active_workspaces` — active workspace count
- `pulse_queue_depth` — job queue depth
- `pulse_experiments_active` — currently active experiment count
- `pulse_experiment_assignments_total{experiment_id, variant_id}` — total assignments per experiment/variant
- `pulse_experiment_exposures_total{experiment_id, variant_id}` — total exposures per experiment/variant
- `pulse_experiment_events_total{experiment_id, variant_id, event_type}` — performance events ingested
- `pulse_experiment_results_computation_duration_seconds` — statistical computation latency histogram
- `pulse_analytics_connector_events_total{connector, direction}` — external analytics events (direction: inbound/outbound)
- `pulse_analytics_connector_errors_total{connector}` — analytics connector errors

### 16.2 Logs

- Structured JSON to stdout (see Section 12.2 for format)
- Levels: ERROR (actionable), WARN (degraded), INFO (lifecycle), DEBUG (internals)
- Sensitive data never logged above DEBUG

### 16.3 Traces (OpenTelemetry)

- **Key spans:** API request → Vault retrieval → Prompt composition → LLM call → Quality scoring → Response
- **Propagation:** W3C Trace Context headers
- **Export:** OTLP to customer's backend (Jaeger, Tempo, etc.)
- **Sampling:** 100% for errors; 1% for successful requests (configurable)

### 16.4 Health Checks

- `GET /health/live` — Process running (liveness probe)
- `GET /health/ready` — All dependencies reachable (readiness probe)
- `GET /health/detailed` — Per-dependency status (diagnostics, not externally exposed)

---

## 17. File & Folder Structure

```
pulse/
├── pulse-api/
│   ├── src/
│   │   ├── pulse/
│   │   │   ├── __init__.py
│   │   │   ├── main.py                    # FastAPI app, lifespan, middleware
│   │   │   ├── config.py                  # Settings (pydantic-settings)
│   │   │   ├── api/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── router.py              # Top-level router
│   │   │   │   ├── v1/
│   │   │   │   │   ├── generate.py        # POST /generate, POST /generate/bulk
│   │   │   │   │   ├── content.py         # Content CRUD endpoints
│   │   │   │   │   ├── jobs.py            # Job management endpoints
│   │   │   │   │   ├── brand_voices.py    # Brand voice CRUD
│   │   │   │   │   ├── market_profiles.py # Market profile endpoints
│   │   │   │   │   ├── analytics.py       # Usage analytics
│   │   │   │   │   ├── webhooks.py        # Webhook config CRUD
│   │   │   │   │   ├── experiments.py     # Experiment CRUD + lifecycle
│   │   │   │   │   ├── performance.py     # Performance event ingestion
│   │   │   │   │   └── prompt_versions.py # Prompt version CRUD
│   │   │   │   ├── middleware/
│   │   │   │   │   ├── auth.py            # JWT + API key auth
│   │   │   │   │   ├── tenant.py          # Workspace context injection
│   │   │   │   │   ├── rate_limit.py      # Rate limiting
│   │   │   │   │   └── request_id.py      # X-Request-ID propagation
│   │   │   │   └── schemas/               # Pydantic request/response models
│   │   │   │       ├── generate.py
│   │   │   │       ├── content.py
│   │   │   │       ├── jobs.py
│   │   │   │       ├── experiment.py      # Experiment + variant schemas
│   │   │   │       ├── performance.py     # Performance event schemas
│   │   │   │       └── common.py          # Error schemas, pagination
│   │   │   ├── core/
│   │   │   │   ├── experiment/
│   │   │   │   │   ├── assignment.py    # Variant assignment engine
│   │   │   │   │   ├── statistics.py    # Statistical analysis (chi-squared, Bayesian)
│   │   │   │   │   ├── results.py       # Results computation engine
│   │   │   │   │   └── tracking.py      # Tracking URL + exposure tracker
│   │   │   │   ├── generation/
│   │   │   │   │   ├── orchestrator.py    # Generation pipeline coordinator
│   │   │   │   │   ├── prompt_composer.py # Prompt assembly logic
│   │   │   │   │   └── cache.py           # Generation cache logic
│   │   │   │   ├── cultural/
│   │   │   │   │   ├── engine.py          # Cultural adaptation engine
│   │   │   │   │   ├── profiles.py        # Market profile loader
│   │   │   │   │   └── dimensions.py      # Cultural dimension calculations
│   │   │   │   ├── quality/
│   │   │   │   │   ├── scorer.py          # Quality scoring algorithm
│   │   │   │   │   ├── terminology.py     # Terminology enforcement
│   │   │   │   │   └── grounding.py       # Vault grounding verification
│   │   │   │   └── llm/
│   │   │   │       ├── abstraction.py     # LLM abstraction layer
│   │   │   │       ├── router.py          # Fallback router + circuit breaker
│   │   │   │       └── adapters/
│   │   │   │           ├── base.py        # Abstract adapter interface
│   │   │   │           ├── openai.py
│   │   │   │           ├── anthropic.py
│   │   │   │           ├── mistral.py
│   │   │   │           ├── ollama.py
│   │   │   │           ├── vllm.py
│   │   │   │           ├── azure_openai.py
│   │   │   │           └── bedrock.py
│   │   │   ├── integrations/
│   │   │   │   ├── analytics/
│   │   │   │   │   ├── base.py          # Abstract analytics connector
│   │   │   │   │   ├── segment.py       # Segment connector
│   │   │   │   │   ├── ga4.py           # Google Analytics 4 connector
│   │   │   │   │   └── mixpanel.py      # Mixpanel connector
│   │   │   │   ├── vault/
│   │   │   │   │   ├── client.py          # Vault REST API client
│   │   │   │   │   ├── search.py          # Semantic search client
│   │   │   │   │   └── cache.py           # Vault data cache manager
│   │   │   │   ├── storage/
│   │   │   │   │   └── s3.py              # S3/MinIO client wrapper
│   │   │   │   └── webhooks/
│   │   │   │       └── dispatcher.py      # Webhook delivery engine
│   │   │   ├── models/                    # SQLAlchemy ORM models
│   │   │   │   ├── workspace.py
│   │   │   │   ├── user.py
│   │   │   │   ├── content.py
│   │   │   │   ├── bulk_job.py
│   │   │   │   ├── brand_voice.py
│   │   │   │   ├── market_profile.py
│   │   │   │   ├── glossary.py
│   │   │   │   ├── audit_log.py
│   │   │   │   ├── api_key.py
│   │   │   │   ├── webhook_config.py
│   │   │   │   ├── experiment.py          # Experiment + ExperimentVariant models
│   │   │   │   ├── performance_event.py   # PerformanceEvent model
│   │   │   │   └── prompt_version.py      # PromptVersion model
│   │   │   ├── services/                  # Business logic layer
│   │   │   │   ├── content_service.py
│   │   │   │   ├── job_service.py
│   │   │   │   ├── brand_voice_service.py
│   │   │   │   ├── analytics_service.py
│   │   │   │   ├── experiment_service.py  # Experiment lifecycle management
│   │   │   │   └── analytics_integration_service.py  # External analytics connectors
│   │   │   └── db/
│   │   │       ├── session.py             # DB session factory
│   │   │       ├── rls.py                 # RLS policy setup
│   │   │       └── migrations/            # Alembic migrations
│   │   │           ├── env.py
│   │   │           └── versions/
│   │   └── alembic.ini
│   ├── tests/
│   │   ├── unit/
│   │   ├── integration/
│   │   └── conftest.py
│   ├── Dockerfile
│   └── pyproject.toml
├── pulse-worker/
│   ├── src/
│   │   └── pulse_worker/
│   │       ├── __init__.py
│   │       ├── main.py                    # Worker entry point
│   │       ├── consumer.py                # Redis Streams consumer
│   │       └── tasks/
│   │           ├── generation_task.py     # Single generation task handler
│   │           └── webhook_task.py        # Webhook delivery task
│   ├── Dockerfile
│   └── pyproject.toml
├── pulse-scheduler/
│   ├── src/
│   │   └── pulse_scheduler/
│   │       ├── __init__.py
│   │       ├── main.py                    # Scheduler entry point
│   │       ├── jobs/
│   │       │   ├── analytics_aggregation.py
│   │       │   ├── cache_cleanup.py
│   │       │   ├── vault_writeback.py
│   │       │   ├── experiment_results.py         # Hourly experiment results computation
│   │       │   ├── performance_aggregation.py    # Rolling metrics aggregation (5 min)
│   │       │   └── analytics_sync.py             # External analytics sync (15 min)
│   │       └── webhook_dispatcher.py
│   ├── Dockerfile
│   └── pyproject.toml
├── pulse-ui/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── main.tsx
│   │   ├── pages/
│   │   │   ├── Dashboard.tsx
│   │   │   ├── Generate.tsx
│   │   │   ├── ContentList.tsx
│   │   │   ├── ContentDetail.tsx
│   │   │   ├── BulkJobs.tsx
│   │   │   ├── BrandVoices.tsx
│   │   │   ├── Settings.tsx
│   │   │   └── Analytics.tsx
│   │   ├── components/
│   │   ├── hooks/
│   │   ├── api/                           # API client functions
│   │   └── types/                         # TypeScript type definitions
│   ├── Dockerfile
│   ├── package.json
│   └── vite.config.ts
├── deploy/
│   ├── docker-compose.yml                 # Simple self-hosted deployment
│   ├── docker-compose.airgap.yml          # Air-gapped deployment
│   ├── helm/                              # Kubernetes Helm chart
│   │   ├── Chart.yaml
│   │   ├── values.yaml
│   │   └── templates/
│   └── k8s/                               # Raw K8s manifests (alternative)
├── docs/
│   ├── api-reference.md
│   ├── deployment-guide.md
│   └── cultural-profiles.md
└── README.md
```

---

## 18. Coding Standards & Conventions

### 18.1 Naming Conventions

- **Python:** snake_case for functions/variables, PascalCase for classes, UPPER_SNAKE for constants
- **TypeScript:** camelCase for functions/variables, PascalCase for components/types/interfaces
- **Database:** snake_case for tables/columns, plural table names
- **API paths:** kebab-case, plural nouns (`/brand-voices`, `/market-profiles`)
- **Environment variables:** UPPER_SNAKE_CASE with `PULSE_` prefix for app-specific vars

### 18.2 API Naming Rules

- RESTful resource naming: `/api/v1/{resource}` and `/api/v1/{resource}/{id}`
- Actions that aren't CRUD: `/api/v1/{resource}/{id}/{action}` (e.g., `/content/{id}/approve`)
- Consistent response envelope: `{ "data": ... }` for success, `{ "error": { ... } }` for errors
- Pagination: cursor-based with `next_cursor` and `has_more`

### 18.3 Error Format Standard

All errors follow the structure defined in Section 5.2. Error codes are uppercase with underscores, prefixed by category. Always include human-readable `message` and optional `details` array for field-level errors.

### 18.4 Code Organization Principles

- **Layered architecture:** API → Service → Core → Integration → Database
- **Dependency injection:** Services receive dependencies via constructor; no global state
- **Single responsibility:** Each module has one clear purpose (see Section 2)
- **Interface segregation:** LLM adapters implement common interface; new providers require no core changes
- **Fail-fast:** Validate inputs at API boundary; never pass invalid state to core logic
- **Immutable records:** Content versions are append-only; never modify historical versions

---

## 19. Assumptions & Constraints

### 19.1 Assumptions

- **A1:** Frontier LLMs (GPT-4, Claude 3.5, Llama 3, Mistral Large) produce localization-quality output with proper cultural context prompting — validated by ≥85% native-speaker approval rate in pre-GA benchmarks
- **A2:** Vault provides sufficient knowledge grounding to prevent hallucination of product information — enforced via confidence scoring and human review workflows
- **A3:** Self-hosted customers have basic Docker/Kubernetes expertise (or choose managed cloud option)
- **A4:** Cultural adaptation profiles generalize sufficiently per market without per-customer customization for Tier 1 languages
- **A5:** Vault API will remain stable throughout development — versioned contract with integration tests in CI
- **A6:** Redis Streams provides sufficient durability and throughput for v1.0 scale (100K items per job) — load tested in staging
- **A7:** pgvector performance acceptable for knowledge bases up to 10M tokens per workspace
- **A8:** Generation caching at 24h TTL provides meaningful cost reduction (est. 15-25%) without quality staleness
- **A9:** Prompt engineering (without fine-tuning) achieves sufficient cultural adaptation quality for Tier 1 and Tier 2 languages
- **A10:** Multi-tenant RLS isolation is sufficient for agency use cases — validated via security review

### 19.2 Constraints

- **C1:** LLM capability ceiling — output quality cannot exceed what the underlying model produces for a given language
- **C2:** Cultural knowledge completeness — profiles encode generalized knowledge, not every customer-specific nuance
- **C3:** Self-hosted infrastructure variability — must work across diverse customer environments without custom engineering
- **C4:** Model-agnostic abstraction cost — unified interface prevents deep optimization for any single model (~2-5ms overhead per call)
- **C5:** Vault coupling — Pulse cannot be deployed without at least minimal Vault functionality
- **C6:** Localization quality subjectivity — no automated metric fully captures quality; human review is essential
- **C7:** LLM cost scaling — API costs scale linearly with usage; high-volume customers face significant ongoing costs
- **C8:** Regulatory evolution — AI regulation (EU AI Act, regional laws) may require post-GA changes
- **C9:** 50+ language quality consistency — some languages will have lower quality; transparent tier system required
- **C10:** Air-gapped model freshness — local models may fall behind cloud-hosted alternatives; accepted sovereignty trade-off

---

*End of Document*
