# Full-Repository Code Audit — odw-pulse

- **Date:** 2026-11-24
- **Mode:** Open Code Review — delegation mode, host-driven (no external `ocr` CLI; analysis performed by the host session's model via six parallel subsystem reviewers, with every High-severity finding independently re-verified against source by the orchestrating session)
- **Commit reviewed:** `7d4ae71` (`master`, in sync with `origin/master`)
- **Scope:** All tracked source code — backend (`pulse-api`), standalone worker/scheduler, frontend (`pulse-ui`), deployment artifacts (Dockerfiles, compose, k8s, CI, nginx), and the test suite
- **Excluded:** `.git`, `node_modules`, venvs, `__pycache__`, build outputs, lockfiles, binaries/media, prose docs (`prd.md`, `tsd.md`, `sad.md`, `tbk.md`, `research.md`, `*.md` reports — used as context only)
- **Companion data:** [`full-audit.json`](./full-audit.json) — finding IDs below match the `id` field there
- **Guardrails honored:** no source files were modified during this pass; outputs are confined to `./.ocr-reports/`

## Fix-round baseline (2026-11-24, branch `dev` off `master@7d4ae71`)

Run before any edits; **no pre-existing failures**:

| Check | Command (from repo root) | Result |
|---|---|---|
| Backend tests | `cd pulse-api && .venv/bin/pytest tests -q` | ✅ 98 passed in 22.17s (exit 0) |
| Backend lint | `cd pulse-api && .venv/bin/ruff check src tests` | ✅ All checks passed (exit 0) |
| Backend types | `cd pulse-api && .venv/bin/mypy src` | ✅ Success: no issues in 97 source files (exit 0) |
| Frontend types | `cd pulse-ui && npm run typecheck` | ✅ exit 0 |
| Frontend lint | `cd pulse-ui && npm run lint` | ✅ exit 0 |
| Frontend build | `cd pulse-ui && npm run build` | ✅ built in 944ms (exit 0) |

Fix progress is tracked per finding via `status` / `verification_notes` in `full-audit.json` and the checkboxes below.

## Coverage

| Metric | Value |
|---|---|
| Total reviewable files | 171 |
| Reviewed | 171 |
| Skipped | 0 |
| **Coverage rate** | **100%** |

Breakdown: 113 Python files (90 app + 13 test + worker/scheduler), 19 TS/TSX, 39 config/infra files. Six subsystem reviewers covered 167 files; the orchestrator directly reviewed the remaining 4 (`pulse-api/src/pulse/__init__.py`, `api/__init__.py`, `integrations/__init__.py`, `pulse-ui/.dockerignore` — all clean) plus `.gitignore`, `script.py.mako`, and `db/migrations/__init__.py`.

## Summary of Findings

**102 unique findings** (117 raw reviewer findings + 1 orchestrator finding, minus 16 cross-report duplicates merged):

| Severity | Count | IDs |
|---|---|---|
| **High** | 12 | #1–#12 |
| **Medium** | 46 | #13–#58 |
| **Low** | 44 | #59–#102 |

Categories: bug (40), security (22), concurrency (13), performance (12), error-handling (8), maintainability (6), test (7) — some findings span categories; the JSON records the primary one.

### Executive summary

The repo presents as "fully implemented, all checks pass," but the audit found that **the core product workflows do not function in the shipped deployment topologies**, and the test suite structurally cannot detect this:

1. **Generation is dead on arrival in production** — no code ever registers an LLM provider (#1), and when providers do fail, failures are returned as successes (#2).
2. **The database schema cannot be created on PostgreSQL** — migration 001's partitioned-table PKs are invalid (#3), and no deployment path runs migrations at all (#6).
3. **The "durable" bulk-job pipeline is broken end-to-end in multi-container deployments** — container-local `/tmp` files (#7), duplicate-processing races (#8, #9), a pause/resume deadlock (#4), and a reaper that fails live jobs (#42).
4. **k8s manifests cannot deploy as shipped** — `$(POSTGRES_PASSWORD)` never expands from `envFrom` (#5), example secrets trip the production guard (#38).
5. **Live cross-tenant authorization bypasses** — impersonation into any workspace (#11) and unscoped performance-event ingestion (#12), plus missing role gating (#56) and a review-workflow bypass (#57).

**Root cause of the blind spot:** tests run on SQLite (ignoring PostgreSQL partitioning/enums/JSONB), build a hand-made FastAPI app instead of `create_app()` (#81), and use mock LLM providers that bypass the registry (#1). CI "manifest validation" is YAML-syntax-only (#72). Every PostgreSQL-specific and production-wiring defect therefore passes CI.

**Known documented gaps were NOT re-reported as findings** (RLS-not-binding itself, analytics/Vault stubs, no backend pagination, no streaming, heuristic quality, no E2E, no live smoke test) — except where a *distinct live defect* exists inside or around them (e.g. #11 is acknowledged as a TODO but is an exploitable bypass, not the RLS gap; #23/#25 are defects that will bite *when* the documented RLS rollout happens).

---

## HIGH severity (12) — fix first

- [x] **#1 — LLM provider registry never populated; every /generate and bulk row fails** ✅ fixed 2026-11-24 (102 tests pass; bootstrap + 2 regression tests) (`pulse-api/src/pulse/api/v1/generate.py:38-51`)
  No production code calls `registry.register()`; `get_orchestrator()` raises `RuntimeError`. Bootstrap providers from settings at API/worker startup with explicit preference order; add an end-to-end registry test.
- [x] **#2 — LLM failures returned as successful results; bulk jobs mark SUCCEEDED with empty content** ✅ fixed 2026-11-24 (GenerationError → 502 / per-row bulk errors; regression test) (`pulse-api/src/pulse/generation/orchestrator.py:146-170`)
  `finish_reason='error'` only feeds the circuit breaker; empty text is scored and returned. Raise a GenerationError on error responses; map to 502/503 and per-row bulk failures.
- [x] **#3 — Migration 001 invalid on PostgreSQL: partitioned PKs omit partition key; child FKs illegal** ✅ fixed 2026-11-24 (composite PKs/FKs in DDL+ORM; regression test; real-PG alembic run pending Docker host) (`pulse-api/src/pulse/db/migrations/versions/001_initial_schema.py:258-263`)
  `content_pieces`/`audit_logs`/`experiment_assignments`/`experiment_exposures`/`performance_events` all affected. Composite PKs + composite FKs (or drop partitioning); add a real-PostgreSQL migration CI job.
- [x] **#4 — Pause/resume deadlock: worker polls a stale identity-map instance forever** (`pulse-api/src/pulse/worker/tasks.py:181-197`)
  `expire_on_commit=False` + plain re-SELECT in `get_job` → `_wait_for_resume` never sees RUNNING/CANCELLED; wedges the sequential worker. Use `populate_existing=True` or `db.refresh()` per poll; cap pause duration.
- [x] **#5 — k8s `$(POSTGRES_PASSWORD)` never expands (envFrom vars aren't in the expansion map)** ✅ fixed 2026-11-24 (explicit secretKeyRef env in all 3 manifests; YAML validated) (`k8s/pulse-api.yaml:26-29`, also `pulse-worker.yaml:24-26`, `pulse-scheduler.yaml:26-28`)
  All three Python services crash-loop with a literal password. Define POSTGRES_PASSWORD via `valueFrom.secretKeyRef` in `env` before DATABASE_URL, or secret the whole URL.
- [x] **#6 — No deployment path runs Alembic migrations; fresh deployments have an empty schema** ✅ fixed 2026-11-24 (compose migrate service + k8s initContainers + alembic.ini in images; live run pending Docker host) (`pulse-api/Dockerfile:16`)
  No compose migrate service, no k8s Job/initContainer, `alembic.ini` not in the image. Add a migration step (fix #3 first).
- [x] **#7 — Bulk input/output files are container-local /tmp; no shared volume between API and worker** (`pulse-api/src/pulse/api/v1/bulk_jobs.py:39-41`)
  Every job fails "Input file missing" in compose/k8s; downloads 404 permanently. Move payloads to S3/MinIO (fix #85 signing first) or a shared RWX volume.
- [x] **#8 — Non-atomic PENDING→RUNNING claim allows duplicate job processing** (`pulse-api/src/pulse/worker/tasks.py:72-85`)
  Reaper re-enqueue + read-then-write guard → two workers generate the same job (double LLM spend). Claim via conditional `UPDATE ... WHERE status='pending' RETURNING` or `FOR UPDATE SKIP LOCKED`.
- [x] **#9 — XAUTOCLAIM min-idle 60s < job runtime; second worker claims and ACKs in-flight messages** (`pulse-worker/src/pulse_worker/main.py:169-188`)
  Crash recovery destroyed: acked-but-running jobs are never retried after a crash. Heartbeat/extend claims during processing; never ack a RUNNING job you don't own.
- [x] **#10 — Results endpoint crashes (ValueError) when conversions > unique visitors** (`pulse-api/src/pulse/core/experiment/statistics.py:58-82`)
  Negative contingency cells → `sqrt(negative)`; `asin(sqrt(p>1))` domain error. Reachable with normal server-side conversion events (no visitor_hash). Validate/clamp inputs; fix counting model (#43).
- [x] **#11 — Impersonation grants any self-registered owner access to ANY workspace** (`pulse-api/src/pulse/api/v1/auth.py:373-422`)
  Only checks caller role + target existence; no membership check; audit written to caller's workspace only. Require membership/admin of target (or platform super-admin); audit in target workspace. *(Acknowledged TODO in docs, but a live cross-tenant bypass.)*
- [x] **#12 — Performance-event ingestion has no workspace/ownership check (cross-workspace write IDOR)** (`pulse-api/src/pulse/api/v1/experiments.py:363-412`)
  Client-supplied experiment_id/variant_id inserted verbatim; experiment IDs are semi-public via tracking URLs. Scope to caller's workspace, validate variant↔experiment, handle FK errors as 400/404.

## MEDIUM severity (46)

### Generation / LLM / cultural
- [x] **#13 — Prompt injection: unsanitized content_type/market/overrides interpolated into system prompt** (`generation/orchestrator.py:122-136`) — allowlist content_type, locale-pattern market, enum persuasion_style; also via bulk CSV.
- [x] **#14 — System prompt flattened into one user message; instruction hierarchy defeated** (`generation/orchestrator.py:138-144`) — pass system/user separately; use provider system roles.
- [x] **#15 — Client-caused 4xx trips the global circuit breaker for all tenants** (`generation/orchestrator.py:146-150`) — count only 5xx/network/timeout toward the breaker.
- [x] **#16 — record_failure is provider-agnostic; secondary failures reset the recovery timer forever** (`llm/fallback_router.py:117-127`) — track which provider failed; timestamp the OPEN transition.
- [x] **#17 — HALF_OPEN admits unlimited concurrent probes to a possibly-dead primary** (`llm/fallback_router.py:98-105`) — cap in-flight probes; route the rest to secondary.
- [x] **#18 — Language-only cultural fallback picks first dict-order region (zh-TW→zh-CN, pt-PT→pt-BR…)** (`cultural/engine.py:188-194`) — explicit language-default map or DB fallback_code chain.
- [x] **#19 — Brand voice loading is dead code; brand_voice_id silently ignored** (`generation/orchestrator.py:96-119`) — implement the lookup or document as unsupported.
- [x] **#20 — DB market profiles never loaded: production orchestrator has no session factory** (`generation/orchestrator.py:99-104`) — wire the factory in `get_orchestrator()`.

### Database / migrations / services
- [x] **#21 — Migration enum `bulk_job_status` omits 'paused' that the ORM writes** (`001_initial_schema.py:52-60`) — pause() 500s on PostgreSQL. Add the enum value.
- [x] **#22 — ~18 JSONB model columns created as plain JSON (schema drift)** (`001_initial_schema.py:113`) — use postgresql.JSONB; blocks future JSONB operators/GIN.
- [x] **#23 — performance_events excluded from RLS enable/policy/FORCE lists** (`001_initial_schema.py:904-921`) — unprotected tenant telemetry once RLS binds.
- [x] **#24 — Fixed partition windows, no DEFAULT partition, no maintenance job** (`001_initial_schema.py:852-886`) — weekly-partition inserts start failing **2027-01-04 (~6 weeks away)**; backdated rows fail today.
- [x] **#25 — Admin-session fallback to DATABASE_URL breaks login/register once RLS is enforced** (`db/session.py:112-131`) — fail fast; admin role needs BYPASSRLS (FORCE binds owners too).
- [x] **#26 — cancel/pause/resume are check-then-act; worker's final commit overwrites CANCELLED** (`services/bulk_job_service.py:185-206`) — atomic conditional transitions.
- [x] **#27 — increment_progress read-modify-write race loses updates** (`services/bulk_job_service.py:132-145`) — atomic SQL increment.
- [x] **#28 — promote_winner mutates JSONB dict in place; winner info never persisted** (`services/experiment_service.py:429-436`) — assign a copy or MutableDict.
- [x] **#29 — Unbounded event batch ingestion + full-table event load in results (OOM)** (`services/experiment_service.py:350-356`) — SQL aggregation; cap batch size. Amplifiable via #12.

### Frontend
- [ ] **#30 — Logout doesn't clear TanStack Query cache; cross-workspace data bleed on next login** (`components/Layout.tsx:18-29`) — `queryClient.clear()`; workspace-scoped keys.
- [ ] **#31 — JWT in localStorage readable by any XSS** (`api/client.ts:13-24`) — httpOnly cookie or in-memory token; CSP (#68); shorter TTL.
- [ ] **#32 — nginx default 1 MiB body cap rejects 5 MiB CSVs the backend accepts; ingress same** (`nginx.conf.template:15-22`) — `client_max_body_size 6m` + ingress `proxy-body-size` annotation.
- [ ] **#33 — nginx default 60s proxy_read_timeout truncates long /generate requests** (`nginx.conf.template:16-21`) — raise to 300s; retries cause duplicate spend.
- [ ] **#34 — crypto.randomUUID() crashes Experiments page on HTTP origins (both shipped topologies)** (`pages/Experiments.tsx:35-37`) — fallback key generator.
- [ ] **#35 — Bulk job list never polls; progress appears frozen** (`pages/BulkJobs.tsx:37-40`) — refetchInterval while jobs active.
- [ ] **#36 — downloadResults: silent unhandled rejections + revokeObjectURL race** (`pages/BulkJobs.tsx:70-80`) — try/catch + surface error; defer revoke.
- [ ] **#37 — Content/BulkJobs/Experiments lists silently truncate at 20 rows; total discarded** (`pages/ContentList.tsx:6-10`) — pagination UI.

### Deployment / infra
- [ ] **#38 — secrets.example.yaml defaults trip the production guard in configmap → CrashLoopBackOff** (`k8s/secrets.example.yaml:14-23`) — dev overlay or documented placeholder flow.
- [ ] **#39 — Ingress has no TLS; credentials and JWTs in plaintext** (`k8s/ingress.yaml:8-26`) — tls block + ssl-redirect; also unblocks #34.
- [ ] **#40 — Redis: ephemeral, unauthenticated Deployment; restart wipes revocation markers + stream state** (`k8s/redis.yaml:16-37`) — StatefulSet+PVC, requirepass, NetworkPolicy.
- [ ] **#41 — Tenant-isolation test never attempts cross-workspace access (vacuous)** (`tests/test_auth.py:86-133`) — request A's resources with B's token; assert 404/empty.

### Worker / integrations / experiments core
- [x] **#42 — Reaper fails live RUNNING jobs (progress written only every 10 rows > 10-min window)** (`worker/maintenance.py:56-69`) — time-based heartbeat; conditional final write.
- [x] **#43 — Conversions counted per event vs unique visitors: rates >1, inflated significance** (`core/experiment/results.py:49-57`) — dedupe converting visitors; feeds #10.
- [x] **#44 — Winner recommendation inverted with 3+ arms ("control significantly better" when treatment won)** (`core/experiment/results.py:140-160`) — evaluate the significant pair's own direction; multiple-comparison correction.
- [ ] **#45 — SSRF guard validate-then-fetch: DNS rebinding bypass** (`integrations/webhooks/url_guard.py:72-82`) — pin the validated IP for the connection.
- [ ] **#46 — Blocking socket.getaddrinfo on the event loop; attacker DNS stalls all requests** (`integrations/webhooks/url_guard.py:73`) — async/threaded resolution with timeout.
- [x] **#47 — Non-atomic INCR+EXPIRE: rate-limit key can lose TTL → permanent 429 lockout of an IP** (`core/redis_kv.py:104-111`) — Lua/pipeline; defensively re-expire TTL=-1 keys.
- [x] **#48 — Full Redis URL (with password) logged at INFO** (`worker/redis_client.py:39`, also `core/redis_kv.py:67`) — strip userinfo.
- [x] **#49 — Bulk-job stream never trimmed (no MAXLEN/XTRIM/XDEL); unbounded Redis memory** (`worker/redis_client.py:49-54`) — approximate MAXLEN or periodic XTRIM.
- [x] **#50 — PAUSED jobs orphaned by worker crash are never recovered** (`worker/maintenance.py:56-83`) — include PAUSED in reaper recovery; ownership-aware acks.

### Auth / API
- [ ] **#51 — Passwords >72 bytes → unhandled 500 (bcrypt 5.0 raises, no length cap)** (`auth/models.py:65-74`) — schema max-length or pre-hash; catch ValueError.
- [ ] **#52 — Rate limits bypassable via spoofed leftmost X-Forwarded-For (compose exposes :8000)** (`api/ratelimit.py:33-38`) — trust configured proxy hops only; don't publish 8000; nginx overwrite XFF.
- [ ] **#53 — Fail-open defaults: known JWT key + credentialed any-origin CORS unless PULSE_ENV=production; compose never sets it** (`main.py:27-66`) — refuse default secrets in all envs; set PULSE_ENV/secret in compose.
- [x] **#54 — Variant is_control flag silently discarded; control inferred as position 0** (`api/v1/experiments.py:176-185`) — persist and read back the flag.
- [ ] **#55 — Updating a draft experiment nulls variant attribution of existing events (silent data loss)** (`api/v1/experiments.py:170-174`) — preserve variant ids or reject updates once events exist.
- [ ] **#56 — No role gating: viewers can approve/delete content, run bulk jobs, register webhooks** (`api/v1/content.py:184-197`) — apply the unused `require_role` dependency per operation.
- [ ] **#57 — POST /content/{id}/versions edits APPROVED content, bypassing the editorial guard** (`api/v1/content.py:298-319`) — same DRAFT/REJECTED guard as update(), or snapshot-only semantics.
- [ ] **#58 — Upload size limit enforced only after full body spools to disk (disk-exhaustion DoS)** (`api/v1/bulk_jobs.py:74-87`) — streaming cap + proxy/server body limit.

## LOW severity (44)

### Backend
- [ ] **#59 — Anthropic adapter reads only first content block (thinking/tool_use → empty "success")** (`llm/providers/anthropic.py:98-101`)
- [ ] **#60 — Single-provider wiring sets secondary=primary; OPEN-state "fallback" hammers the dead provider** (`llm/fallback_router.py:96-105`)
- [ ] **#61 — User model unique constraint drifts from migration 002 (workspace+email vs global email)** (`models/user.py:60-63`)
- [ ] **#62 — Workspace.slug duplicate unique constraint (unique=True + named constraint)** (`models/workspace.py:31`)
- [ ] **#63 — list_experiments N+1 variant queries (102 queries at limit=100)** (`services/experiment_service.py:145-152`)
- [ ] **#64 — create_version max+1 race → unhandled IntegrityError 500 on concurrent snapshots** (`services/content_service.py:200-227`)
- [ ] **#65 — Alembic env.py: '%' in DATABASE_URL breaks ConfigParser interpolation** (`db/migrations/env.py:43`)
- [ ] **#75 — /health/ready always ok; k8s readiness probe meaningless** (`main.py:82-84`)
- [ ] **#82 — A/B assignment float boundary off-by-one; %100 granularity vs documented %10000** (`core/experiment/assignment.py:49-56`)
- [ ] **#83 — Mixpanel event properties can overwrite the project token (latent)** (`integrations/analytics/mixpanel.py:40-44`)
- [ ] **#84 — Analytics send() ignores HTTP status; failed deliveries silently lost (all 3 connectors, latent)** (`integrations/analytics/ga4.py:59-63`)
- [ ] **#85 — Storage presign signs raw key vs encoded path; upload/download unauthenticated (latent; blocks #7 fix)** (`integrations/storage/client.py:96-112`)
- [ ] **#86 — Tracking-URL generation drops repeated/blank query params** (`core/experiment/tracking.py:39-42`)
- [ ] **#87 — Dead-letter attempt off-by-one; XPENDING capped at 1000 without pagination** (`pulse-worker/src/pulse_worker/main.py:185-188`)
- [ ] **#88 — claim_stale discards XAUTOCLAIM cursor; recovery starves behind fresh PEL head** (`worker/redis_client.py:113-121`)
- [ ] **#89 — stdlib logging not actually routed through structlog despite comment** (`core/logging.py:28-33`)
- [ ] **#90 — Blocking CSV file I/O in async worker loop** (`worker/tasks.py:200-204`)
- [ ] **#91 — New Redis connection + ensure_group per enqueued job** (`worker/dispatch.py:19-26`)
- [ ] **#92 — ContentRead serializes 'metadata_' (alias leak); TS types claim 'metadata'** (`api/schemas/content.py:64`, `pulse-ui/src/types/index.ts:41,53`)
- [ ] **#93 — /content/{id}/versions binds body/change_note from query string; JSON body silently ignored** (`api/v1/content.py:303-309`)
- [ ] **#94 — Annotation action free-text allows approval-chain spoofing** (`api/schemas/content.py:94-99`)
- [ ] **#95 — 'does not exist' substring match fails open on user validation (partial migration → deactivated users keep access)** (`auth/dependencies.py:172-181`)
- [ ] **#96 — Missing/malformed JWT claims → KeyError 500 instead of 401** (`auth/dependencies.py:123-130`)
- [ ] **#97 — Blocking write_bytes/Path.exists in async bulk endpoints** (`api/v1/bulk_jobs.py:88-89`)
- [ ] **#98 — Fire-and-forget fallback task unreferenced; GC can kill a running job** (`api/v1/bulk_jobs.py:109-113`)
- [ ] **#99 — Unsanitized upload filename → 500s on '/' or null bytes** (`api/v1/bulk_jobs.py:68-89`)
- [ ] **#100 — Middleware-order comment inverted; future TenantMiddleware enforcement would break CORS preflight** (`main.py:52-67`)
- [ ] **#101 — redis_kv concurrent first-request client creation leaks unclosed clients** (`core/redis_kv.py:54-71`)

### Frontend
- [ ] **#66 — Webhook deleteMutation has no onError; failures invisible** (`pages/Settings.tsx:52-59`)
- [ ] **#67 — BulkJobStatus type omits 'paused'** (`types/index.ts:89`)
- [ ] **#68 — No security headers (CSP/X-Frame-Options/nosniff) on the SPA** (`nginx.conf.template:1-23`)

### Infra / config / tests
- [ ] **#69 — Compose publishes unauthenticated Redis + default-cred Postgres/MinIO on all host interfaces** (`docker-compose.yml:18-26`)
- [ ] **#70 — Makefile 'source' fails under /bin/sh (dash) on Linux** (`Makefile:27-28`)
- [ ] **#71 — Dockerfile copies src before pip install; dependency layer caching claim false** (`pulse-api/Dockerfile:5-9`)
- [ ] **#72 — CI 'manifest validation' is YAML-syntax-only; broken manifests pass** (`.github/workflows/ci.yml:41-51`)
- [ ] **#73 — Worker/scheduler Deployments have no liveness/readiness probes** (`k8s/pulse-worker.yaml:16-35`)
- [ ] **#74 — PULSE_API_HOST/PORT advertised but consumed by nothing** (`.env.example:7-8`)
- [ ] **#76 — test_list_users_requires_admin never tests the negative (viewer 403) path** (`tests/test_auth.py:240-258`)
- [ ] **#77 — test_update_content_status never updates a status** (`tests/test_content.py:110-130`)
- [ ] **#78 — test_ingest_event_updates_variant_metrics never checks a metric** (`tests/test_experiments.py:176-247`)
- [ ] **#79 — Storage test's mock transport masks the unauthenticated S3 request** (`tests/test_integrations.py:73-92`)
- [ ] **#80 — In-process fallback test relies on a 50ms sleep (flaky)** (`tests/test_worker_pipeline.py:66-72`)
- [ ] **#81 — conftest builds a private FastAPI app, not create_app(); production wiring untested** (`tests/conftest.py:203-258`)
- [ ] **#102 — .gitignore missing .venv/ (the name CLAUDE.md's setup uses)** (`.gitignore:26-28`)

---

## Suggested remediation order

1. **Make the product run at all (deployment blockers):** #3 → #6 (schema), #5 + #38 (k8s startup), #1 (provider bootstrap), #7 + #85 (shared bulk storage).
2. **Stop silent corruption / false success:** #2 (error propagation), #8 + #9 + #27 (exactly-once-ish job processing), #4 (pause deadlock), #42 + #26 (reaper/cancel races), #28 + #54 + #55 (experiment data integrity), #10 + #43 + #44 (statistics correctness).
3. **Close cross-tenant and authz holes:** #11, #12, #56, #57, #95, then #53 + #52 + #47 (secret/rate-limit hardening), #45 + #46 (SSRF), #23 + #25 (prepare for RLS rollout).
4. **Time-sensitive:** #24 — weekly partitions expire **2027-01-04**; add DEFAULT partitions + maintenance before then.
5. **Frontend correctness/security:** #34, #32, #33, #30, #35, #37, #31 + #68, #39 (TLS).
6. **Test-suite credibility (prevents regression of all the above):** #81 (real create_app fixture), #41 (real isolation test), #72 (semantic manifest validation + real-PostgreSQL migration job), #76–#80.
7. Remaining Medium/Low items per subsystem.

**Verification after fixes:** `cd pulse-api && pytest tests -v && ruff check src tests && mypy src`; `cd pulse-ui && npm run typecheck && npm run lint && npm run build`; plus the new real-PostgreSQL migration check and a live compose smoke test (register → login → generate → bulk job → pause/resume → download) — none of which exist today.

## Method notes

- Delegation-mode workflow per the `open-code-review-delegate` skill, executed host-side per the user's constraint (no external OCR binary, no separate API config): full-file checklist → per-file review in six parallel subsystem passes → severity classification → coverage accounting.
- Every High finding was re-verified by the orchestrating session by reading the cited source (registry grep, orchestrator error path, migration DDL, session factory, worker loops, k8s env semantics, impersonation/ingestion routers, statistics math). Medium/Low findings carry reviewer-cited line evidence; spot-checks were performed on a sample (nginx template, Layout logout, Experiments randomUUID, metadata alias, PAUSED enum, require_role usage, bcrypt 5.0.0 in .venv, fail-open substring).
- Cross-report duplicates merged (16): e.g. bulk /tmp files (worker+auth), pause deadlock (DB+auth), chi²/asin crash (worker+auth), ingestion IDOR (auth+DB), INCR+EXPIRE (worker+auth), winner misattribution (worker+auth), nginx/ingress body size (frontend+auth), readiness probe (infra+auth), metadata_ alias (frontend+auth), fail-open defaults (infra+auth). Merged findings note both locations.
- Discarded false positives are not listed (per skill guidance); reviewers documented their discarded hypotheses (e.g. webhook redirect SSRF — httpx follow_redirects defaults False; market-profile cache cross-tenant leak — table is system-level; str.format re-formatting of substituted values — safe).
