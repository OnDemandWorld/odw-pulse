# Pulse Scheduler

Scheduled task runner for the Pulse platform.

## Overview

The Pulse Scheduler runs periodic tasks such as:
- Cleaning up expired sessions and tokens
- Aggregating analytics metrics
- Generating usage reports
- Purging old audit logs
- Checking experiment statistical significance
- Sending webhook retry attempts

## Quick Start

```bash
# Scheduler runs from pulse-api's virtualenv
cd pulse-api
source .venv/bin/activate

# Start the scheduler
python -m pulse_scheduler.main
```

## Configuration

The scheduler uses the same environment variables as the API. Key variables:

| Variable | Description |
|---|---|
| `DATABASE_URL` | PostgreSQL connection URL |
| `REDIS_URL` | Redis connection URL |
| `PULSE_ENV` | Environment (development, production) |

See `../.env.example` for the complete list.

## Scheduled Tasks

| Task | Frequency | Description |
|---|---|---|
| Session cleanup | Every hour | Remove expired sessions and tokens |
| Analytics aggregation | Every 15 minutes | Roll up performance events into metrics |
| Usage reports | Daily (midnight) | Generate daily usage summary per workspace |
| Audit log purge | Weekly | Remove audit logs older than retention period |
| Experiment checks | Every 5 minutes | Check if experiments have reached significance |
| Webhook retries | Every minute | Retry failed webhooks with exponential backoff |
| Cache invalidation | Every 10 minutes | Clear stale generation cache entries |

## Deployment

### Docker

```bash
docker build -t ondemandworld/pulse-scheduler:latest pulse-scheduler/
docker run ondemandworld/pulse-scheduler:latest
```

### Kubernetes

The scheduler is deployed as a Deployment with 1 replica. See `k8s/pulse-scheduler.yaml`.

**Important:** Only run 1 replica to avoid duplicate task execution. If you need high availability, implement leader election.

## Architecture

```
┌────────────────────────────────────┐
│        Pulse Scheduler             │
│                                    │
│  ┌──────────────────────────────┐ │
│  │     Task Scheduler Core      │ │
│  │  (cron-like task dispatcher) │ │
│  └──────────┬───────────────────┘ │
│             │                     │
│  ┌──────────▼───────────────────┐ │
│  │      Task Registry           │ │
│  │  - session_cleanup           │ │
│  │  - analytics_aggregation     │ │
│  │  - usage_reports             │ │
│  │  - audit_log_purge           │ │
│  │  - experiment_checks         │ │
│  │  - webhook_retries           │ │
│  │  - cache_invalidation        │ │
│  └──────────────────────────────┘ │
└────────────────────────────────────┘
```

## Adding a New Scheduled Task

1. Create a task function in `src/pulse_scheduler/tasks/`
2. Register the task in `src/pulse_scheduler/main.py` with a cron expression
3. Add configuration in `src/pulse_scheduler/config.py` if needed
4. Test locally by running the scheduler

Example:
```python
from pulse_scheduler.tasks.base import ScheduledTask

class MyTask(ScheduledTask):
    name = "my_task"
    schedule = "*/5 * * * *"  # Every 5 minutes

    async def run(self):
        # Task logic here
        pass
```

## Monitoring

The scheduler emits structured logs via structlog:
- Task execution start/completion with timing
- Errors with full stack traces
- Skipped tasks (if previous instance still running)

## Error Handling

- **Task failures:** Logged and retried on next schedule
- **Long-running tasks:** Skipped if previous instance is still running
- **Database errors:** Retried with exponential backoff
- **Scheduler crash:** Tasks resume on restart (no persistent state)

## Known Limitations

1. **Single replica only** — No leader election; multiple replicas would duplicate tasks
2. **No task persistence** — If scheduler crashes mid-task, task state is lost
3. **No task dependencies** — Tasks run independently; no DAG support
4. **No task history** — Past executions are not recorded in database
5. **Fixed schedules** — Cannot dynamically adjust task frequency

## Future Improvements

- Add leader election for high availability
- Add task persistence and history tracking
- Add task dependency graph (DAG support)
- Add dynamic schedule adjustment
- Add task execution dashboard
- Add distributed scheduler (e.g., Celery Beat, APScheduler)
- Add task timeout and cancellation
- Add alerting on task failures
