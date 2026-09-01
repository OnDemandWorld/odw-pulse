# Pulse — Technical Audit Plan

**Document ID:** `BUILD_REPORT_20260901.md`
**Auditor Role:** Senior Software Architect
**Audit Date:** 2026-09-01
**Repository:** `git@github.com:OnDemandWorld/odw-pulse.git`
**Head Commit:** `1a0f1d4` (master)
**Scope:** Full codebase — backend (pulse-api, pulse-worker, pulse-scheduler), frontend (pulse-ui), deployment (docker-compose, k8s), CI/CD, documentation.

---

## 1. Current State Assessment

### 1.1 Repository Composition

| Component | Files | Lines (approx.) | Notes |
|---|---|---|---|
| `pulse-api/src/pulse/` | 94 Python modules | ~10,857 LOC | FastAPI monolith |
| `pulse-api/tests/` | 11 test files | ~2,500 LOC | pytest-asyncio |
| `pulse-ui/src/` | 18 TS/TSX files | ~2,100 LOC | React 18 + Vite |
| `pulse-worker/src/` | 2 modules | ~600 LOC | Redis Streams consumer |
| `pulse-scheduler/src/` | 1 module | ~70 LOC | APScheduler |
| `k8s/` | 10 YAML manifests | ~850 LOC | Deployment + ConfigMap |
| `docker-compose.yml` | 1 | ~100 LOC | Dev stack |
| `.github/workflows/` | 1 | ~80 LOC | CI only |
| **Total** | **~150 source files** | **~15,000 LOC** | |

### 1.2 Test Coverage (measured 2026-09-01)

```
pytest --cov=pulse → 89 passed, 75% total coverage

Per-module highlights:
  ✓ models/*              94-100%  (ORM definitions)
  ✓ api/v1/*              85-95%   (endpoints)
  ✓ services/*            85-92%   (business logic)
  ✓ worker/dispatch.py    100%
  ⚠ worker/maintenance.py  89%
  ⚠ worker/redis_client.py 62%     (claim/XAUTOCLAIM paths uncovered)
  ✗ worker/tasks.py         22%    (generation pipeline barely exercised)
  ✗ llm/providers/*          0%    (OpenAI/Anthropic/Ollama adapters UNTESTED)
  ✗ llm/registry.py         40%
  ⚠ quality/engine.py       70%
```

**Estimated production-grade coverage: 55–60%** (excluding generated code, mocks, and `__init__.py` modules).

### 1.3 Architectural Integrity

**Strengths:**
- Clean layered architecture: `api → services → models` with well-defined boundaries.
- Multi-tenancy modeled consistently (workspace-scoped tables, JWT-derived context, RLS policies).
- Dependency injection via FastAPI's `Depends()` is used uniformly; no global mutable state outside of engine factories.
- Auth flow is now real (bcrypt password hashes, proper JWT lifecycle, audit log on impersonation).
- Durable job pipeline with XREADGROUP/XACK/XAUTOCLAIM, dead-lettering after 5 attempts, reconnect-with-backoff.
- SSRF guard on webhook URLs with defense-in-depth (scheme + IP-range validation at both registration and dispatch).
- CI runs backend tests, lint, typecheck, frontend build, manifest validation, and Docker builds on every push.

**Weaknesses:**
- **Frontend is currently broken against the new backend auth.** Login page references a hardcoded mock credential that no longer exists; there is no registration UI; first-time users cannot onboard.
- **`DATABASE_ADMIN_URL` is defined in `config.py` but is not propagated through any deployment artifact** (`.env.example`, `docker-compose.yml`, `k8s/*`). Login/register will silently use the scoped `DATABASE_URL`, which will fail once RLS is actually enforced by a non-owner role.
- **RLS policies exist but are not enforced in practice.** Migration 002 runs `FORCE ROW LEVEL SECURITY` on every workspace-scoped table, but in `docker-compose.yml` the application connects as `pulse`, which is the table-owning superuser (`POSTGRES_USER=pulse`). PostgreSQL silently bypasses RLS for superusers and table owners — so the policies are inert. Actual isolation currently relies on service-layer `workspace_id` filters, which is correct but defeats the purpose of RLS.
- **Zero test coverage for the LLM provider adapters** (`pulse/llm/providers/{anthropic,ollama,openai}.py`, `registry.py` at 40%). These are the cost center and the integration boundary — untested.
- **Worker generation pipeline at 22% coverage.** `worker/tasks.py` drives the actual content generation; only the happy path is tested.
- **No rate limiting anywhere.** `/auth/login`, `/auth/register`, `/generate`, and all bulk endpoints have no throttle. `/auth/login` is brute-forceable.
- **No JWT revocation.** Logout is purely client-side (removing `localStorage.pulse_token`). A compromised access token works until expiry (default 30 minutes).
- **Webhook SSRF guard is bypassable via DNS rebinding.** The validation runs immediately before dispatch, but between the `getaddrinfo()` call and the actual HTTP connect, an attacker-controlled DNS record can change the resolution. This is a known limitation, documented in `url_guard.py`, but not mitigated (e.g., with pinned resolution or egress proxy).
- **Migration 001 was edited in place** to add the `review_annotations` table. Any developer who already ran `alembic upgrade head` on the original 001 has a divergent schema. This is acknowledged in `PLAN.md` but no migration-rewrite tooling or guard exists.
- **No k8s probes for pulse-worker or pulse-scheduler.** The other four workloads have `readinessProbe`/`livenessProbe`; these two do not. K8s cannot detect stuck or dead worker pods.
- **Integration connectors (Vault, Segment, GA4, Mixpanel) are stubs.** They log but make no outbound calls. Documented but unmitigated.
- **CORS in dev mode echoes any origin with credentials** (`allow_origin_regex=r".*"` + `allow_credentials=True`). Safe only because dev isn't exposed to the internet.

### 1.4 Quantitative Health Summary

| Metric | Value | Grade |
|---|---|---|
| Tests passing | 89 | ✅ |
| Estimated production coverage | 55–60% | ⚠️ (target: 75%+) |
| Backend lint/typecheck | Clean | ✅ |
| Frontend lint/typecheck | Clean | ✅ |
| Critical bugs (broken flows) | 1 (frontend auth) | ❌ |
| High-severity security gaps | 4 | ❌ |
| Deployment artifacts consistent | Partially (admin URL gap) | ⚠️ |
| CI pipeline coverage | Build + test + lint | ⚠️ (no integration test) |
| Documentation currency | Synchronized | ✅ |

---

## 2. Immediate Remediation Plan

All tasks are ordered within their severity band by descending impact. Each task is actionable within the scope of the current codebase without external system changes unless noted.

### Critical (fix within 1 week)

**C-1. Frontend registration flow.**
The UI currently references a hardcoded mock user (`test@example.com / testpassword`) in `pulse-ui/src/pages/Login.tsx:87-89`, and there is no UI path to `POST /api/v1/auth/register`. First-time users cannot onboard.
**Remediation:**
- Remove mock-credential hint from `Login.tsx`.
- Add a "Create workspace" tab/toggle on the login page that POSTs to `/auth/register` with `{workspace_name, email, password}`.
- On success, store the returned `access_token` and redirect to `/`.
- Update the `Login` and `Register` TypeScript types in `pulse-ui/src/types/index.ts` to reflect `TokenResponse` (which now returns `workspace_id` and `email`).
- Add Playwright E2E test for the full register → login → authenticated-flow loop.

**C-2. Propagate `DATABASE_ADMIN_URL` through all deployment artifacts.**
Currently defined only in `pulse-api/src/pulse/config.py:33`. Without it, the pre-auth paths (login, register) use the scoped role, which will be denied under actual RLS enforcement.
**Remediation:**
- Add `DATABASE_ADMIN_URL` to `.env.example` with comment explaining its purpose (privileged pre-auth connection; typically points to a `BYPASSRLS` role).
- Add `DATABASE_ADMIN_URL: postgresql+asyncpg://pulse_admin:...@postgres:5432/pulse` to `docker-compose.yml` `pulse-api` environment. Add a `pulse_admin` role to the compose Postgres bootstrap.
- Add `POSTGRES_ADMIN_PASSWORD` to `k8s/secrets.example.yaml`. Reference it in `k8s/pulse-api.yaml` via `$(POSTGRES_ADMIN_PASSWORD)` and set `DATABASE_ADMIN_URL` accordingly.
- Create the admin role in the Postgres init script (to be added in C-7).

**C-3. Rate-limit authentication endpoints.**
`/auth/login` and `/auth/register` are unthrottled. A single attacker can brute-force passwords or enumerate accounts.
**Remediation:**
- Add `slowapi` (or equivalent) as a dependency.
- Apply a limiter to `/auth/login` (e.g., 5 attempts / IP / minute) and `/auth/register` (e.g., 3 / IP / minute).
- Store limiter state in Redis (already wired).
- Return `429 Too Many Requests` with `Retry-After` header on throttle.
- Add tests that assert 429 on burst attempts.

**C-4. Implement JWT revocation / logout.**
Compromised tokens currently work until expiry. There is no server-side logout.
**Remediation:**
- Add `POST /auth/logout` that stores the token's `jti` in a Redis set with TTL = remaining token lifetime.
- Add `get_current_user` check: reject tokens whose `jti` is in the set.
- Add `jti` (UUID) to the JWT payload in `create_access_token`.
- Add `POST /auth/logout-everywhere` that revokes all tokens for the current user (increment a `revoked_before` timestamp in Redis keyed by user_id).
- Add tests for revocation + expiry.

### High (fix within 2–4 weeks)

**H-1. Enforce RLS with a dedicated non-owner application role.**
Currently `pulse` is the table-owning superuser; `FORCE ROW LEVEL SECURITY` has no effect. Multi-tenancy relies on service-layer filters, which is correct but not defense-in-depth.
**Remediation:**
- Add Postgres bootstrap script (compose + k8s) that creates:
  - `pulse_owner` (superuser, DDL only, used by migrations).
  - `pulse_api` (non-owner, RLS-subject, used by API runtime).
  - `pulse_worker` (non-owner, `BYPASSRLS`, used by worker/scheduler — trusted backend).
- Update compose `DATABASE_URL` for `pulse-api` → `pulse_api`. Keep `pulse` for `pulse-worker` and `pulse-scheduler` until they're refactored.
- Update `.env.example` with all three URLs.
- Update `alembic.ini` to use `pulse_owner` for migrations.
- Add an integration test against a real Postgres (Testcontainers) that asserts cross-workspace SELECTs are denied for `pulse_api`.

**H-2. Add k8s probes to pulse-worker and pulse-scheduler.**
Currently only `pulse-api`, `pulse-ui`, `postgres`, `redis` have probes. Worker/scheduler pods can silently die or hang.
**Remediation:**
- Add a metrics endpoint to `pulse-worker` (Prometheus already imported; serve on `PULSE_METRICS_PORT`, default off). Add `readinessProbe: httpGet /metrics`.
- Add a liveness probe to `pulse-scheduler` via a simple file-touch heartbeat, or expose a TCP port with a readiness socket.
- Add both probes to the k8s manifests.

**H-3. Cover LLM provider adapters with tests.**
`pulse/llm/providers/{anthropic,openai,ollama}.py` have 0% coverage. These are the cost center and the primary external integration.
**Remediation:**
- Add `tests/test_llm_providers.py` with recorded HTTP responses (VCR.py or `httpx.MockTransport`).
- Cover: successful generation, rate-limit responses (429), timeout, malformed response, circuit-breaker trip, fallback routing.
- Target: 85% coverage on `llm/`.

**H-4. Cover `worker/tasks.py` generation pipeline with integration tests.**
22% coverage. The core generation pipeline (CSV → orchestrator → output) is undertested.
**Remediation:**
- Add `tests/test_worker_tasks.py` with end-to-end flow tests using a mocked `GenerationOrchestrator`.
- Cover: happy path, per-row failure handling, pause/resume, cancellation, re-entry guard (status != PENDING skips).
- Target: 75% coverage on `worker/tasks.py`.

**H-5. Fix webhook SSRF DNS rebinding.**
Current guard validates IP ranges at dispatch time, but DNS can change between `getaddrinfo()` and the TCP connect.
**Remediation:**
- Resolve the hostname once and pass the IP to `httpx.AsyncClient` with a pinned `transport` that connects to the resolved IP (use `httpx.URL` override or custom `AsyncHTTPTransport`).
- Document residual risk for non-pinnable CDNs.
- Add tests that simulate DNS rebinding between validation and dispatch.

**H-6. Eliminate the in-place migration 001 edit.**
Developers with pre-existing DBs have a divergent schema.
**Remediation:**
- Introduce migration `003_review_annotations.py` that adds the `review_annotations` table as a proper migration step.
- Add a check in migration `001` that gracefully no-ops if the table already exists.
- Add a CI job that runs `alembic upgrade head` against a fresh Postgres to catch migration regressions.
- Document the migration split in `DEVELOPMENT.md`.

**H-7. Replace the CORS-dev wildcard with an explicit allowlist.**
Current dev config (`allow_origin_regex=r".*"`) + `allow_credentials=True` allows any origin to make credentialed requests. Safe only because dev isn't internet-exposed.
**Remediation:**
- Add `CORS_ALLOWED_ORIGINS` to config, defaulting to `http://localhost:5173` (Vite dev).
- Pass the list to `CORSMiddleware` (`allow_origins=CORS_ALLOWED_ORIGINS`).
- Production must supply explicit origins via env.

### Medium (fix within 1–3 months)

**M-1. Replace stub integration connectors with real implementations.**
Vault, Segment, GA4, Mixpanel connectors log but do not call external APIs.
**Remediation:**
- Implement Segment HTTP API client (batch endpoint).
- Implement GA4 Measurement Protocol client.
- Implement Mixpanel REST client.
- Gate each behind a feature flag (`SEGMENT_ENABLED`, etc.) so missing credentials don't break the app.
- Add integration tests with recorded responses.

**M-2. Enforce a stronger password policy.**
Current policy: minimum 8 characters, no complexity requirements.
**Remediation:**
- Require at least one uppercase, one lowercase, one digit, and one special character.
- Validate on both `POST /auth/register` and `POST /auth/users`.
- Consider using a breached-password check (HIBP API or local bloom filter).
- Document policy in the API schema descriptions.

**M-3. Audit log writes via a dedicated service.**
Audit entries are currently inserted inline in endpoints (`db.add(AuditLog(...))`). This duplicates logic and makes it hard to enforce schema invariants.
**Remediation:**
- Create `pulse/services/audit_service.py` with `record(workspace_id, action, actor_id, resource, details)`.
- Replace all inline `db.add(AuditLog(...))` calls in `auth.py`, `experiments.py`, etc.
- Add a `get_audit_log(workspace_id, filters)` endpoint for admin consumption.

**M-4. Add user deletion flow.**
Currently there's no way to delete a user (only deactivate). GDPR / data-subject-request compliance requires deletion.
**Remediation:**
- Add `DELETE /auth/users/{id}` (owner only, not self).
- Hard-delete the user row; cascade to related audit log actor references (set `actor_id` to NULL via `ON DELETE SET NULL`).
- Retain audit log rows (immutable).

**M-5. Worker dead-letter queue visibility.**
Dead-lettered jobs are marked FAILED with an `_worker` key in the `errors` JSON blob, but there's no dedicated query endpoint.
**Remediation:**
- Add `GET /bulk-jobs/{id}/errors` that returns the dead-letter reason + per-row errors.
- Add a filter to `GET /bulk-jobs?status=failed` that surfaces dead-letter jobs first.

**M-6. Add OpenAPI schema versioning.**
API is at `/api/v1/*` but there's no mechanism to evolve the schema without breaking clients.
**Remediation:**
- Add `/api/v2` routers alongside `/api/v1` when making breaking changes.
- Add deprecation headers (`Sunset`, `Deprecation`) on v1 endpoints once v2 ships.
- Generate OpenAPI JSON per version; publish to docs.

**M-7. Bulk job output CSV streaming.**
`GET /bulk-jobs/{id}/download` currently returns the entire CSV in memory. Large jobs will OOM.
**Remediation:**
- Stream the file via `StreamingResponse` reading the file in chunks.
- Add a size cap (e.g., 100 MB); beyond that, return a pre-signed S3 URL if storage is configured.

---

## 3. Future Improvement Roadmap (3–6 Months)

### Phase A — Hardening (Months 1–2)

**A.1. End-to-end integration test suite.**
- Add Playwright tests for the full user journey: register → login → generate content → view content → create bulk job → view results → run experiment.
- Add Testcontainers-based Postgres + Redis integration tests for migration integrity, RLS enforcement, and Redis Streams durability.
- Run in CI on every PR; block merge on failure.

**A.2. Observability stack.**
- Deploy an OpenTelemetry Collector + Jaeger/Tempo for trace visualization.
- Configure Prometheus alerts on: error rate > 1%, P95 latency > 2s, Redis queue depth > 100, worker consumer lag > 60s.
- Add structured logging with trace ID propagation across services.

**A.3. Database hardening.**
- Implement automated daily backups to S3 with 30-day retention.
- Add connection pooling via `pgbouncer` in front of Postgres.
- Implement read replicas for list endpoints (content list, bulk job list, experiment list).
- Add a `pg_stat_statements` monitoring dashboard.

**A.4. Secrets management.**
- Migrate from k8s `Secret` manifests to `external-secrets-operator` backed by AWS Secrets Manager or Vault.
- Implement automatic secret rotation for DB credentials (30-day cycle).
- Audit all secrets in transit (ensure TLS everywhere).

### Phase B — Scaling & Performance (Months 2–4)

**B.1. Horizontal worker scaling.**
- Implement consumer group sharding so multiple worker replicas can process bulk jobs in parallel without duplication.
- Add a job routing layer that picks the worker replica with the lowest in-flight job count (Redis gauge).
- Implement worker autoscaling based on Redis queue depth (K8s HPA against a custom metric).

**B.2. Content generation pipeline rewrite.**
- Replace the synchronous in-process orchestrator with a step-function architecture: each generation step is a discrete worker task (research, outline, draft, review, cultural adaptation, quality check).
- Enable streaming generation end-to-end via SSE (replace the current stub `/generate/stream`).
- Add a content cache (Redis) keyed by (prompt_hash, market, content_type) to avoid re-generating identical content.

**B.3. CDN & static asset optimization.**
- Serve `pulse-ui` from CloudFront/Cloudflare with long-lived cache headers (assets are content-hashed by Vite).
- Implement Brotli compression at the CDN edge.
- Add a service worker for offline resilience on the dashboard.

**B.4. Multi-region deployment.**
- Deploy pulse-api to two AWS regions (us-east-1, eu-west-1) with Route53 geo-routing.
- Implement cross-region Postgres replication (Aurora Global Database or logical replication).
- Implement cross-region Redis replication (ElastiCache Global Datastore).

### Phase C — Platform Maturity (Months 4–6)

**C.1. Multi-workspace super-admin.**
- Add a `platform_admin` role that can view/manage all workspaces.
- Add a `/platform/workspaces` API with list/create/suspend.
- Add a super-admin dashboard in `pulse-ui`.
- Implement cross-workspace audit log aggregation.

**C.2. LLM-based quality scoring.**
- Replace the heuristic `quality/engine.py` with an LLM-judge pass (GPT-4o or Claude) that scores content on: accuracy, tone fit, cultural appropriateness, readability.
- Use the heuristic score as a pre-filter; use the LLM score as the authoritative metric.
- Add a feedback loop: user corrections feed back into prompt tuning.

**C.3. Content moderation.**
- Integrate with a moderation API (OpenAI Moderation, AWS Comprehend, or self-hosted model) to scan generated content for: hate speech, PII leakage, brand-safety violations.
- Block publication of flagged content; route to a human reviewer queue.
- Add a moderation dashboard in `pulse-ui`.

**C.4. Prompt A/B testing.**
- Extend the experimentation engine to support prompt-template variants (not just content variants).
- Implement deterministic prompt assignment (hash of content_id + experiment_id).
- Add statistical significance checks (chi-squared) to the prompt-experiment results view.

**C.5. Real-time collaboration.**
- Implement WebSocket/SSE-based live updates for content edits, bulk job progress, and experiment results.
- Add presence indicators (who's viewing this content right now).
- Implement optimistic UI updates with conflict resolution.

**C.6. Technology stack migrations.**
- Migrate from PostgreSQL 16 to PostgreSQL 17 (pgvector for embedding search, JSON path improvements).
- Evaluate migrating the frontend from Vite to Turbopack for faster dev builds.
- Evaluate replacing `python-jose` with `authlib` for JWT (more actively maintained, better standards compliance).
- Evaluate replacing `passlib` (which has a known bcrypt compatibility issue) with direct `bcrypt` library usage.
- Consider migrating the scheduler from APScheduler to Celery Beat for distributed scheduling with retry guarantees.

---

## Appendix A: Quantitative Coverage Gaps

| Module | Coverage | Priority |
|---|---|---|
| `llm/providers/openai.py` | 0% | Critical (H-3) |
| `llm/providers/anthropic.py` | 0% | Critical (H-3) |
| `llm/providers/ollama.py` | 0% | Critical (H-3) |
| `worker/tasks.py` | 22% | High (H-4) |
| `llm/registry.py` | 40% | High (H-3) |
| `worker/redis_client.py` | 62% | Medium |
| `quality/engine.py` | 70% | Medium |
| `integrations/vault/client.py` | 77% | Medium (M-1) |
| `integrations/storage/client.py` | 78% | Medium (M-1) |
| `prompts/composer.py` | 80% | Low |

## Appendix B: Security Posture Summary

| Control | Status | Notes |
|---|---|---|
| Password storage | ✅ bcrypt | Via `passlib` (note: evaluate migration to direct `bcrypt` per C.6) |
| JWT signing | ✅ HS256 | Configurable algorithm; recommend RS256 migration |
| JWT expiry | ✅ 30 min | Configurable; consider 15 min + refresh token |
| JWT revocation | ❌ Not implemented | See C-4 |
| Rate limiting | ❌ Not implemented | See C-3 |
| SSRF protection (webhooks) | ⚠️ Partial | DNS rebinding gap; see H-5 |
| RLS enforcement | ⚠️ Inert | Policies exist but superuser bypass; see H-1 |
| CORS | ⚠️ Permissive in dev | See H-7 |
| Secret management | ⚠️ YAML-only | See A.4 |
| Audit logging | ✅ Present | Scattered; see M-3 |
| Input validation | ✅ Pydantic v2 | On all endpoints |
| Output encoding | ✅ html.escape | On HTML export |
| Dependency security | ⚠️ No automated scan | Add Dependabot or Snyk |

## Appendix C: Deployment Consistency Matrix

| Setting | `.env.example` | `docker-compose.yml` | `k8s/configmap.yaml` | `k8s/secrets.example.yaml` |
|---|---|---|---|---|
| `DATABASE_URL` | ✅ | ✅ | ❌ (constructed from components) | ✅ `POSTGRES_PASSWORD` |
| `DATABASE_ADMIN_URL` | ❌ | ❌ | ❌ | ❌ |
| `REDIS_URL` | ✅ | ✅ | ❌ | — |
| `PULSE_SECRET_KEY` | ✅ | ⚠️ (default only) | — | ✅ |
| `WEBHOOK_SIGNING_SECRET` | ✅ | ⚠️ (default only) | — | ✅ |
| `STORAGE_*` | ✅ | ✅ (partial) | ⚠️ (partial) | ⚠️ (partial) |
| `OPENAI_API_KEY` | ✅ | ⚠️ (via .env only) | — | ✅ |
| `ANTHROPIC_API_KEY` | ✅ | ⚠️ (via .env only) | — | ✅ |

**Gap summary:** `DATABASE_ADMIN_URL` is entirely absent from deployment artifacts. `STORAGE_*` is partially wired. Secret defaults in compose should be removed.

---

*End of report. Next review cycle recommended in 30 days or after any Critical/High remediation completes.*
