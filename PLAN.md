# Pulse — Review Report & Improvement Plan

**Date:** 2026-08-31
**Scope:** Full-repository review (backend, frontend, worker/scheduler, deployment, docs), refactor of everything clearly broken, and a sequenced roadmap for what comes next.

---

## 1. Executive Summary

The codebase was in good structural shape — clean lint, clean types, passing tests — but the review found that **several major surfaces were wired against a contract that didn't exist**:

- The **frontend** was built against an imagined API: wrong request/response shapes on nearly every page, no login flow despite a 401 redirect to `/login`, list endpoints returning `{items, total}` where the UI expected arrays. It compiled cleanly but could not have worked against the real backend.
- The **deployment artifacts** would not produce a running system: the k8s manifests referenced a ConfigMap that didn't exist, Secret keys with dashes that never match the env vars the app reads, an ingress rewrite that clobbered every path, Dockerfiles that ran `pip install -e .` before copying the source, and a compose UI pointing at an unreachable Docker-internal hostname.
- The **security layer** had the right shape but no teeth: RLS policies were `USING (true)` placeholders, the function that sets the RLS context was never called, `/generate` (the expensive LLM endpoint) had no authentication, and a dead database silently accepted deactivated users' tokens.
- The **local dev environment itself was broken**: the Python venv contained hardcoded paths from a previous directory name, so nothing in the Makefile ran; `make worker` / `make scheduler` targeted modules that were never installed; ESLint had no config file.

All of the above is now fixed. **59 backend tests pass, ruff/mypy/tsc/ESLint are clean, the Vite build succeeds, and every manifest parses.** The remaining work (Section 4) is real-integration and hardening work, not repairs.

---

## 2. What Was Fixed in This Pass

### 2.1 Developer environment & tooling

| Fix | Details |
|---|---|
| Broken venv after directory rename | The venv's activation scripts, wrapper shebangs, `pyvenv.cfg` and editable-install `.pth` all pointed at the old `odw-ai 2/...` path, so `pytest`/`ruff`/`mypy` couldn't run. Paths repaired; suite runs again. |
| `make install` bootstrap target | One shared venv now installs `pulse-api[dev]`, `pulse-worker`, and `pulse-scheduler` editable together, so `make worker` / `make scheduler` actually work (the modules previously weren't importable from the venv the Makefile used). |
| Missing ESLint config | `npm run lint` existed with all plugins installed but no config file → ESLint errored. Added `pulse-ui/.eslintrc.cjs`; lint now passes with `--max-warnings 0`. |
| `.dockerignore` files | Added to all four sub-projects (`.venv`, `node_modules`, `dist`, caches, `.env*`) so build contexts stop leaking secrets and junk into images. |

### 2.2 Backend — correctness bugs

| Fix | File(s) | Details |
|---|---|---|
| Market fallback chain was dead code | `cultural/market_profile.py` | `load_market_profile_with_fallback` looked up the fallback code from a cache that never stores misses — the fallback branch could never run. Now queries `fallback_code` from the DB and walks the chain (max depth 5, cycle-safe). |
| Bulk-job progress counted wrong | `worker/tasks.py` | Progress was incremented by **1** every `PROGRESS_BATCH` (10) rows — a 100-row job ended at 10/100. Now increments by the actual number of rows processed since the last write. |
| Chi-squared p-value was wrong | `core/experiment/statistics.py` | Used `exp(-chi2/2)` (not a valid chi-squared survival function; ~3× error at the p=0.05 threshold), which made experiment significance testing unreliable. Replaced with the exact df=1 survival function `erfc(sqrt(chi2/2))`. The docstring example (0.285…) already documented the correct value. |
| Misleading Yates'-correction comment | `core/experiment/statistics.py` | Formula is Pearson's chi-squared; comment corrected. |
| HTML export XSS-adjacent escaping | `services/content_service.py` | Title/slug were interpolated unescaped into `<title>`/`<meta>`; body escaping was hand-rolled. All three now use `html.escape`. |
| `setattr` update loop | `services/content_service.py` | Content updates now use an explicit field allowlist instead of blindly `setattr`-ing request fields onto the ORM object. |

### 2.3 Backend — security

| Fix | File(s) | Details |
|---|---|---|
| Real RLS policies | `db/migrations/versions/001_initial_schema.py` | All 15 placeholder `USING (true)` policies replaced with workspace-scoped predicates against `current_setting('pulse.workspace_id', true)` (NULL ⇒ deny). Child tables (`content_versions`, `glossary_terms`, `experiment_variants`, …) are scoped via `EXISTS` on their parent's workspace. **Note:** migration `001` was edited in place — existing dev databases should be recreated (`docker compose down -v` + `alembic upgrade head`). |
| RLS context actually applied | `db/session.py`, `auth/dependencies.py` | `get_current_user` now publishes the workspace into `WorkspaceContext`; a session `after_begin` hook issues `SET LOCAL pulse.workspace_id` at the start of **every** transaction (re-applied after commits). Postgres-only; no-op on SQLite tests. |
| Missing `review_annotations` table | migration `001` | The ORM model and review service used a table the migration never created — any review operation would 500 against a migrated Postgres. Table + index + RLS policy added (upgrade and downgrade). |
| `/generate` unauthenticated | `api/v1/generate.py` | Both `/generate` and `/generate/stream` now require a JWT — previously anonymous callers could burn LLM credits. Covered by a new 401 test. |
| Auth accepted tokens when DB down | `auth/dependencies.py` | The blanket `except Exception: pass` was narrowed: only a genuinely missing `users` table falls back to token claims; connection failures now return 503 instead of silently authenticating. |
| Impersonation checks target exists | `api/v1/auth.py` | `POST /auth/impersonate` now 404s when the target workspace doesn't exist (previously minted a JWT for *any* UUID). Full membership checks await the real user model (Section 4). |
| Weak password fallback removed | `auth/security.py` | `hash_password` now refuses to run without bcrypt instead of silently writing single-iteration SHA-256 hashes; legacy `plain:` hashes still verify but with `hmac.compare_digest` (constant time). |
| Default secrets rejected in prod | `main.py` | `create_app` raises on boot in production if `PULSE_SECRET_KEY` or `WEBHOOK_SIGNING_SECRET` still hold their placeholder values. |
| `PULSE_DEBUG` default flipped | `config.py` | Debug (which echoes SQL statements + parameters to logs) now defaults off. |
| Tenant middleware hardened | `middleware/tenant.py` | Removed the client-controllable `X-Workspace-Id` header / `workspace_id` query-param workspace resolution — workspace now derives exclusively from the verified JWT. |
| CORS | `main.py` | Dev mode uses `allow_origin_regex` (echoes origin), because `allow_origins=["*"]` + `allow_credentials=True` is rejected by browsers. Production still needs an explicit allowlist (Section 4). |
| Upload size limit | `api/v1/bulk_jobs.py` | CSV uploads capped at 5 MiB (413 beyond); imports tidied while there. |

### 2.4 Standalone worker & scheduler packages

| Fix | Details |
|---|---|
| Scheduler graceful shutdown | Previously imported `signal` but never used it — Docker's SIGTERM killed the process instantly, skipping `scheduler.shutdown()`. Now mirrors the worker's signal-handler pattern; verified by smoke test (clean `pulse-scheduler.stopped` on SIGTERM). APScheduler also gets `coalesce`/`max_instances=1`/`misfire_grace_time` job defaults. |
| Worker idle loop | The stub now waits on its shutdown event instead of busy-sleeping; TODO points at moving the in-API consumer (`pulse-api/src/pulse/worker/`) into this package (Section 4, Phase 1). |
| Unused imports removed | `typing.Any` removed from both entrypoints. |

### 2.5 Docker & Kubernetes

| Fix | Details |
|---|---|
| Python Dockerfiles (×3) | `pip install -e .` ran **before** `COPY src` (broken build) — now `COPY src` first, non-editable install, dropped `build-essential`, containers run as a non-root `app` user. |
| UI image | Was the Vite **dev server** in a "production" image. Now a multi-stage build: `npm run build` → nginx serving `dist/`, with an `nginx.conf.template` that proxies `/api` to `$API_UPSTREAM` (envsubst at container start). This makes the SPA's relative `/api/v1` base URL work in every environment. |
| docker-compose | Removed deprecated `version:` key; MinIO gets a healthcheck and `pulse-api` now `depends_on` it; `.env` is optional (`required: false`) so compose works without one; UI gets `API_UPSTREAM=http://pulse-api:8000`; API gets a `/health/live` healthcheck; compose passes MinIO credentials and `STORAGE_USE_SSL=false` to the API. |
| k8s ConfigMap | **Created** `k8s/configmap.yaml` (`pulse-config`) — previously referenced by three Deployments but nonexistent, so nothing would schedule. |
| k8s Secret keys | Renamed `postgres-password` → `POSTGRES_PASSWORD` etc. The dashed names never matched `$(POSTGRES_PASSWORD)` expansion or the app's env-var names, silently producing an empty DB password and default secret keys. Example secret also gains webhook/storage keys. |
| Ingress rewrite | Removed `rewrite-target: /`, which rewrote **every** request path to `/` (no route could ever match). |
| UI manifests | Container/service port corrected 5173 → 80 (nginx image), `API_UPSTREAM=http://pulse-api:80` set. |
| Probes & resources | Readiness/liveness probes added to API and UI; CPU/memory requests+limits on all four app workloads. Scheduler annotated as must-stay-1-replica (no leader election yet). |

### 2.6 Frontend — rewritten against the real API

- **Auth flow (new):** `Login` page wired to `POST /auth/login`, `RequireAuth` route guard, `/login` + 404 routes, logout button + identity in the sidebar (from `GET /auth/me`), 401 interceptor no longer redirect-loops on failed login attempts. Dev credentials shown on the login page (mock auth — see Phase 2).
- **Types (`types/index.ts`):** fully rewritten to mirror the Pydantic schemas — `ContentRead`/`ContentVersionRead`, `BulkJobRead`, `ExperimentRead`/`VariantRead`, `GenerationRequest`/`GenerationResult`, results/statistics shapes, `{items,total}` list wrappers. Dead `PaginatedResponse` removed.
- **Every page fixed:**
  - *Dashboard* — real totals via the three list endpoints + recent content, instead of hardcoded fake numbers.
  - *Generate* — sends `{content_type, target_market, prompt, llm_params}` (was 422ing on unknown/missing fields); renders `quality_score`, `quality_flags`, `llm_model`, `llm_usage`, `latency_ms` (was crashing on `result.metadata.*`).
  - *ContentList / BulkJobs / Experiments* — unwrap `{items,total}` (was `.map is not a function`); columns use real fields (`market_code`, `total`/`progress`, variant `weight`, …).
  - *ContentDetail* — reads `body`/`version_number`/`change_note`; distinguishes load errors from 404.
  - *BulkJobs* — upload sends the real form fields (`prompt_column`, `content_type`, `target_market`), no manual `Content-Type: multipart/form-data` (which stripped the boundary), file input actually resets, authenticated blob download for results.
  - *Experiments* — create payload uses `{name, weight, configuration, is_control}`; start/pause/stop lifecycle buttons; results fetched on demand from `/experiments/{id}/results` with winner recommendation rendered.
  - *Settings* — fake do-nothing form replaced with real webhook management (register/list/test/delete against `/webhooks`) plus workspace identity display.
- **Resilience:** top-level `ErrorBoundary` (no more white screens), axios errors surface the backend `detail` instead of "Request failed with status code 422", `NavLink` stays active on nested routes, `vite-env.d.ts` types `VITE_API_URL`, and `baseURL` finally respects it (`VITE_API_URL || '/api/v1'`).
- **Vite proxy** target overridable via `API_PROXY_TARGET` so the dev server works both on the host and inside compose.

### 2.7 Docs

README (endpoint table, quick start incl. `make install`, login credentials, k8s instructions, counts), DEVELOPMENT.md (verification numbers, gap list updated with resolutions), CLAUDE.md (agent-facing status + known gaps) — all synchronized with reality.

### 2.8 Verification after the pass

| Check | Result |
|---|---|
| `pytest tests -q` (pulse-api) | **59 passed** in ~2.6s (57 original + 2 new auth tests) |
| `ruff check src tests` | clean |
| `mypy src` (strict) | clean |
| `tsc --noEmit` (pulse-ui) | clean |
| `eslint . --max-warnings 0` (pulse-ui) | clean |
| `vite build` | ✅ 147 modules |
| YAML parse of compose + all k8s manifests | ✅ |
| Worker/scheduler smoke test (start + SIGTERM) | ✅ graceful both |

Not yet verifiable on this machine: Docker image builds and a live `docker compose up` / cluster apply (no Docker daemon here) — see Phase 0.

---

## 3. Known Limitations Introduced or Preserved by This Pass

1. **RLS policies are correct but not yet enforced.** The app connects as the table *owner*; PostgreSQL skips RLS for owners unless `FORCE ROW LEVEL SECURITY` is set or a separate role is used. The service-layer `workspace_id` filters remain the actual isolation boundary. Fixing this properly is Phase 2 work (dedicated DB role).
2. **Migration `001` was edited in place.** Correct for a pre-production project, but any database that already ran the old `001` must be recreated or manually patched.
3. **Auth is still a mock** (hardcoded dev user). It is now *safely* mocked (tokens verified, DB failures not swallowed), but user management doesn't exist.
4. **The standalone worker still doesn't consume** — bulk jobs run in-process inside pulse-api (as before). The packages now start/stop cleanly and the path to move the consumer is clear (Phase 1).
5. **K8s has no MinIO/object storage** — `STORAGE_ENDPOINT` defaults to disabled; document or deploy external S3 before using storage features on a cluster.

---

## 4. Roadmap — Next Set of Improvements

Sequenced so each phase leaves the system shippable. Rough sizes in engineer-days.

### Phase 0 — Quick wins & verification (1–2 days)
1. **LICENSE file** — README declares MIT; commit the actual `LICENSE` text. (0.1d)
2. **Compose/k8s smoke test on a Docker host** — `make dev`, log in through the UI, run one generation and one bulk job end-to-end; `kind`/`minikube` apply of `k8s/`. Closes the one verification gap of this pass. (0.5d)
3. **GitHub Actions CI** — single workflow: backend `pytest + ruff + mypy`, frontend `typecheck + lint + build`, YAML lint of k8s/, Docker build (no push). The repo has zero CI today; everything above currently depends on humans remembering `make test`. (0.5d)
4. **index.html meta** — favicon/description/theme-color. (0.1d)
5. **Image tags** — pin versions instead of `:latest` in k8s manifests; wire CI to push `:sha-<git>`. (0.3d)
6. **Postgres PVC `storageClassName`** — make explicit (or document the default-SC requirement). (0.1d)

### Phase 1 — Make the job pipeline real (3–5 days)
The bulk-job path currently works only because it runs inside the API process. To make it production-shaped:
1. **Move the Redis Streams consumer into `pulse-worker`** — `XGROUP CREATE` + `XREADGROUP COUNT/BLOCK` + `XACK`, pending-entry recovery with exponential backoff, dead-letter after N retries. The in-API `pulse/worker/` code is the reference implementation; delete it from pulse-api once parity is reached (keep an in-process fallback behind a flag for dev).
2. **Durable dispatch** — `POST /bulk-jobs` should enqueue to the stream and let the worker pick up; the current `asyncio.create_task` is lost on restart. Add a startup sweep that reclaims `RUNNING` jobs whose consumer died.
3. **Worker observability** — Prometheus counter/gauge for queue depth, processed rows, failures (prometheus-client is already a dependency).
4. **Scheduler jobs** — replace the heartbeat with real duties: stale-job reaper, webhook retry scan (ties into Phase 3), prompt/report generation hooks.

### Phase 2 — Real identity & enforceable tenancy (1–2 weeks)
The security skeleton is now correct; it needs a body:
1. **User management** — users table CRUD + registration/invite, real `POST /auth/login` against it (the mock user store in `api/v1/auth.py` is explicitly marked), refresh tokens or short-lived access + rotation.
2. **Workspace membership & roles** — membership table, enforce on impersonation (currently existence-only) and on `require_workspace`.
3. **Dedicated DB role for RLS** — migration creates `pulse_app` role (non-owner), app connects as it (or `FORCE ROW LEVEL SECURITY` + careful worker context-setting); then the Phase-0-correct policies actually bind. Add integration tests against real PostgreSQL (testcontainers or a CI service container) covering cross-workspace denial.
4. **httpOnly cookie sessions** (optional but recommended) — removes the XSS-exfiltratable JWT from localStorage.

### Phase 3 — Production hardening (1 week, parallelizable)
1. **Rate limiting** — per-tenant + per-IP (e.g. `slowapi` or a Redis token-bucket middleware); most urgent for `/generate` (cost) and `/auth/login` (brute force).
2. **Webhook test SSRF** — `POST /webhooks/{id}/test` will currently fetch any URL the user supplies (cloud metadata, internal services). Add scheme/host validation with a private-range blocklist and https-only in production. **Highest-severity item left open from the review.**
3. **Request hygiene** — global timeouts, production CORS allowlist from config, structured RFC-7807 error bodies, request-id propagation.
4. **Webhook retries** — exponential backoff (3 attempts), delivery log table, dead-letter visibility in Settings.
5. **Backups & restores** — documented Postgres backup job (cron in k8s or managed-DB snapshot), restore runbook.
6. **Secrets management** — sealed-secrets/external-secrets in k8s; rotate the dev defaults out of `.env.example` docs.
7. **Bulk-download streaming** — `FileResponse` already streams the CSV, but cap job size or paginate generation to bound memory for very large jobs.

### Phase 4 — Real integrations (1–2 weeks, after Phase 2)
1. **Analytics connectors** — Segment/GA4/Mixpanel currently log-only; wire real HTTP sends with the existing payload normalizers, behind config flags, with delivery metrics.
2. **Vault connector** — replace the canned-response mock with the real retrieval API; generation already threads `vault_sources` through the pipeline.
3. **Storage on k8s** — deploy MinIO (or document external S3) and supply `STORAGE_*` via the Secret/ConfigMap; add a startup connectivity check.
4. **Real LLM provider matrix tests** — recorded-response (VCR-style) tests per provider adapter, plus circuit-breaker chaos tests.

### Phase 5 — Quality & safety of output (1 week)
1. **LLM-based quality evaluation** — judge pass over generated content (rubric in the prompt composer), feeding `quality_score` beyond heuristics; keep heuristics as the cheap pre-filter.
2. **Content moderation** — provider moderation endpoint or self-hosted classifier gate before content is stored/published.
3. **Streaming generation for real** — `/generate/stream` is a stub; implement token streaming from providers through SSE (the BaseHTTPMiddleware→pure-ASGI refactor, flagged in review, should happen first to avoid streaming pitfalls).

### Phase 6 — Testing & observability (1 week, overlapping)
1. **E2E tests** — Playwright: login → generate → content list/detail; bulk-job upload → progress; experiment create → start → results. Run in CI against the compose stack.
2. **PostgreSQL integration tests** — migrations, RLS enforcement (post Phase 2.3), partitioned-table behavior.
3. **OpenTelemetry end-to-end** — collector + trace export (SDK is wired but exports nowhere), Prometheus alert rules (error rate, generation latency P95, queue depth, circuit-breaker state).
4. **Load test** — k6 script for `/generate` + bulk upload to size the k8s requests/limits added in this pass.

### Phase 7 — Product features (ongoing)
- Content personalization (audience-segment variants), prompt-template A/B testing in the experiment engine, multi-workspace super-admin, content scheduling & templates, real-time job progress (SSE/WebSocket), PDBs + pod `securityContext` in k8s, Redis persistence (StatefulSet+PVC), scheduler leader election (unblocks >1 replica), composite-PK ORM alignment for partitioned tables.

### Suggested order at a glance

```
Phase 0 (days)  →  Phase 1 (worker)  →  Phase 2 (auth/RLS)  →  Phase 3 (hardening)
                                              ↓
                            Phase 4 (integrations) + Phase 6 (tests/observability) in parallel
                                              ↓
                                    Phase 5 (quality/safety) → Phase 7 (features)
```

---

## 5. Appendix — Full Findings Inventory & Disposition

Every verified finding from the review, and what happened to it.

### Backend core (auth/middleware/db/models/api)
| # | Severity | Finding | Disposition |
|---|---|---|---|
| 1 | critical | RLS policies `USING (true)` — zero tenant isolation | ✅ Fixed (real policies, §2.3) |
| 2 | critical | RLS context never set (`_set_rls_context` dead) | ✅ Fixed (`after_begin` hook, §2.3) |
| 3 | critical | `/generate` + `/generate/stream` unauthenticated | ✅ Fixed (+ test) |
| 4 | high | Impersonate mints token for any workspace UUID | 🔶 Partial (existence check); membership check → Phase 2.2 |
| 5 | high | `review_annotations` missing from migration | ✅ Fixed (table + policy + downgrade) |
| 6 | high | Auth succeeds when DB unreachable | ✅ Fixed (only missing-table falls back) |
| 7 | high | SHA-256 password fallback + `==` compare | ✅ Fixed (bcrypt mandatory, `compare_digest`) |
| 8 | high | Webhook test endpoint enables SSRF | ⏳ Plan Phase 3.2 (highest open item) |
| 9 | medium | Workspace from untrusted header/query | ✅ Fixed (JWT-only) |
| 10 | medium | No default-secret startup check | ✅ Fixed (boot refuses in prod) |
| 11 | medium | `pulse_debug=True` default echoes SQL | ✅ Fixed (default false) |
| 12 | medium | Unbounded CSV upload | ✅ Fixed (5 MiB cap) |
| 13 | medium | `get_job_unscoped` public bypass | ⏳ Keep (legit worker use); rename/role-guard in Phase 1 |
| 14 | medium | `setattr` update loop | ✅ Fixed (allowlist) |
| 15 | medium | ORM PK vs partitioned `(workspace_id, id)` | ⏳ Plan Phase 7 (functionally benign w/ UUIDs) |
| 16 | low | Non-constant-time hash compare | ✅ Fixed |
| 17 | low | HTML export escaping gaps | ✅ Fixed (`html.escape`) |
| 18 | low | CORS `*` + credentials | ✅ Fixed (regex echo; prod allowlist → Phase 3.3) |
| 19 | low | `BaseHTTPMiddleware` + streaming | ⏳ Plan Phase 5.3 |
| 20 | low | API-key auth stub | ⏳ Plan Phase 2 (or delete) |

### Backend domain (generation/LLM/experiments/services)
| # | Severity | Finding | Disposition |
|---|---|---|---|
| 1 | high | Market fallback chain unreachable | ✅ Fixed |
| 2 | high | Bulk progress +1 per batch of 10 | ✅ Fixed |
| 3 | medium | Chi-squared p-value approximation wrong | ✅ Fixed (exact df=1 SF) |
| 4 | low | Yates'-correction comment incorrect | ✅ Fixed |
| — | — | Circuit breaker, assignment hashing, quality scoring, cultural engine, webhook HMAC, storage signing, redis stream ops, results aggregation | ✅ Reviewed, confirmed correct |

### Worker / scheduler / tooling
| # | Severity | Finding | Disposition |
|---|---|---|---|
| 1 | critical | Compose `VITE_API_URL` unreachable from browsers | ✅ Fixed (nginx `/api` proxy; env-driven) |
| 2 | critical | `make worker/scheduler` run uninstalled modules | ✅ Fixed (`make install`) |
| 3 | critical | Dockerfiles `pip install -e .` before `COPY src` | ✅ Fixed |
| 4 | high | Scheduler: no SIGTERM handling | ✅ Fixed (+ smoke-tested) |
| 5 | high | Standalone worker is a no-op stub | 🔶 Documented; real consumer → Phase 1 |
| 6 | high | `env_file: .env` required but absent | ✅ Fixed (`required: false`) |
| 7 | medium | build-essential bloat + root containers | ✅ Fixed |
| 8 | medium | UI image ran Vite dev server | ✅ Fixed (nginx multi-stage) |
| 9 | medium | MinIO healthcheck/depends_on missing | ✅ Fixed |
| 10 | medium | alembic.ini localhost URL | ✅ Acceptable (env.py overrides; commented) |
| 11 | medium | Unused `Any` imports | ✅ Fixed |
| 12–16 | low | dockerignore, compose `version`, root pyproject, scheduler job defaults, EXPOSE | ✅ Fixed (dockerignore, version, job defaults); pyproject/EXPOSE no-ops |

### Frontend
| # | Severity | Finding | Disposition |
|---|---|---|---|
| 1 | critical | List pages call `.map` on `{items,total}` | ✅ Fixed |
| 2 | critical | `VITE_API_URL` ignored | ✅ Fixed |
| 3 | critical | 401 → `/login` but no login exists | ✅ Fixed (full auth flow) |
| 4 | critical | Generate request/response shapes wrong | ✅ Fixed |
| 5 | critical | Experiment variant fields wrong | ✅ Fixed |
| 6–9 | high | Content/BulkJob/Version/Experiment types don't match backend | ✅ Fixed (types rewritten) |
| 10 | high | Manual multipart header breaks upload | ✅ Fixed |
| 11 | high | Variant weights unvalidated/semantics | ✅ Fixed (relative weights, control marked) |
| 12 | medium | Settings Save button dead | ✅ Fixed (real webhooks management) |
| 13 | medium | Query errors not rendered | ✅ Fixed |
| 14 | medium | Raw axios error messages | ✅ Fixed (`apiErrorMessage`) |
| 15 | medium | Error vs not-found conflated | ✅ Fixed |
| 16 | medium | Dashboard hardcoded stats | ✅ Fixed (real totals) |
| 17 | medium | No ErrorBoundary | ✅ Fixed |
| 18 | medium | localStorage token (XSS) | ⏳ Plan Phase 2.4 (httpOnly cookies) |
| 19 | medium | File input not reset | ✅ Fixed (ref reset) |
| 20–24 | low | 404 route, NavLink prefix, array keys, `id!`, index.html meta | ✅ Fixed except index.html (Phase 0.4) |
| 25 | low | ESLint config missing | ✅ Fixed |
| 26 | low | Dead `PaginatedResponse` type | ✅ Removed |

### Kubernetes / deployment
| # | Severity | Finding | Disposition |
|---|---|---|---|
| C1 | critical | Secret keys dashed → empty DB password | ✅ Fixed |
| C2 | critical | `pulse-config` ConfigMap missing | ✅ Fixed |
| C3 | critical | No usable Secret shipped | 🔶 Example corrected; real secret tooling → Phase 3.6 |
| H1 | high | Ingress rewrite clobbers paths | ✅ Fixed |
| H2 | high | UI API URL wrong/unset in cluster | ✅ Fixed (nginx proxy + `API_UPSTREAM`) |
| H3 | high | No probes | ✅ Fixed (API/UI; workers get none until they serve a port — Phase 1) |
| H4 | high | No resource requests/limits | ✅ Fixed (all app workloads) |
| M1 | medium | UI dev-server port 5173 in prod manifests | ✅ Fixed (nginx :80) |
| M2 | medium | No MinIO/S3 in k8s | ⏳ Plan Phase 4.3 |
| M3 | medium | Redis non-persistent | ⏳ Plan Phase 7 |
| M4 | medium | `:latest` tags | ⏳ Plan Phase 0.5 |
| M5 | medium | No storageClassName on Postgres PVC | ⏳ Plan Phase 0.6 |
| M6 | medium | `$(VAR)` ordering fragility | ✅ Documented via comment |
| L1–L6 | low | dev/prod password divergence, no TLS on ingress, duplicated vars, scheduler replicas, no PDBs, no securityContext | 🔶 Scheduler annotated; rest → Phase 3/7 |

---

*Maintained by the Pulse team. Update Section 4 checkboxes as phases land; keep DEVELOPMENT.md and CLAUDE.md in sync.*
