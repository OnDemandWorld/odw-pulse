# Pulse Worker

Async worker for processing bulk content generation jobs in the Pulse platform.

## Overview

The Pulse Worker consumes bulk job tasks from a Redis Stream and processes them asynchronously. Each task generates content using the configured LLM provider, applies cultural adaptation, and stores results in the database.

## Architecture

```
Redis Stream (bulk_jobs:stream)
    ↓
Pulse Worker (consumer)
    ↓
┌────────────────────────────────────────┐
│ 1. Fetch bulk job item from database   │
│ 2. Load workspace config & brand voice │
│ 3. Generate content via LLM            │
│ 4. Apply cultural adaptation           │
│ 5. Score quality                       │
│ 6. Store result in database            │
│ 7. Update job progress                 │
│ 8. Emit webhook if configured          │
└────────────────────────────────────────┘
```

## Quick Start

```bash
# Worker runs from pulse-api's virtualenv
cd pulse-api
source .venv/bin/activate

# Start the worker
python -m pulse_worker.main
```

The worker connects to Redis and begins consuming from the `bulk_jobs:stream` stream. It processes tasks as they arrive.

## Configuration

The worker uses the same environment variables as the API. Key variables:

| Variable | Description |
|---|---|
| `REDIS_URL` | Redis connection URL (e.g., `redis://localhost:6379`) |
| `DATABASE_URL` | PostgreSQL connection URL |
| `OPENAI_API_KEY` | OpenAI API key (or other LLM provider keys) |
| `VAULT_API_URL` | Vault API URL for knowledge retrieval |
| `STORAGE_ENDPOINT` | S3/MinIO endpoint for file storage |

See `../.env.example` for the complete list.

## How It Works

1. **Job submission:** API creates a `bulk_job` record and pushes items to Redis Stream
2. **Task consumption:** Worker reads from stream using consumer groups
3. **Content generation:** For each item, the worker:
   - Loads workspace config, brand voice, market profile
   - Composes prompt with cultural adaptation hints
   - Calls LLM provider (with circuit breaker failover)
   - Scores quality of generated content
   - Stores result as a `content` record
4. **Progress tracking:** Worker updates `bulk_job_item.status` and `bulk_job.progress`
5. **Completion:** When all items are processed, marks job as `completed` and emits webhook

## Deployment

### Docker

```bash
docker build -t ondemandworld/pulse-worker:latest pulse-worker/
docker run ondemandworld/pulse-worker:latest
```

### Kubernetes

The worker is deployed as a Deployment with 2 replicas. See `k8s/pulse-worker.yaml`.

### Scaling

Scale worker replicas to increase throughput:
```bash
kubectl scale deployment pulse-worker --replicas=5
```

Each replica independently consumes from the Redis Stream. Redis consumer groups ensure tasks are distributed across workers without duplication.

## Monitoring

The worker emits structured logs via structlog:
- Task start/completion with timing
- LLM provider calls with latency
- Errors with full stack traces

Metrics are exposed via Prometheus (if configured).

## Error Handling

- **LLM failures:** Circuit breaker trips after N failures, falls back to alternate provider
- **Database errors:** Retried with exponential backoff
- **Invalid tasks:** Logged and acknowledged (not retried)
- **Worker crashes:** Unacknowledged tasks are redelivered to another consumer

## Known Limitations

1. **No task priority** — All tasks are processed FIFO
2. **No dead letter queue** — Permanently failed tasks are not preserved
3. **No task cancellation** — Once queued, tasks cannot be cancelled
4. **Single stream** — All jobs share one stream (no per-workspace isolation)
5. **No rate limiting** — Worker processes as fast as Redis delivers

## Future Improvements

- Add task priority levels (urgent vs. normal)
- Add dead letter queue for failed tasks
- Add task cancellation support
- Add per-workspace stream isolation
- Add rate limiting per LLM provider
- Add task retry with exponential backoff
- Add worker health checks and graceful shutdown
