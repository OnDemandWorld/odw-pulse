"""Tests for the bulk-job dispatch pipeline (Phase 1).

Covers: stream enqueue fallback, the standalone worker's message handling
(ack / retry / dead-letter / poison), and the stale-job reaper.
"""

from __future__ import annotations

import asyncio
import io
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pulse_worker.main as worker_main
import pytest
import pytest_asyncio
from httpx import AsyncClient
from pulse_worker.main import Worker
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from pulse.models.bulk_job import BulkJobStatus
from pulse.services.bulk_job_service import BulkJobService
from pulse.worker import dispatch
from pulse.worker.maintenance import reap_stale_jobs

# ---------------------------------------------------------------------------
# Dispatch (API -> Redis stream)
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_enqueue_job_returns_false_when_redis_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """enqueue_job degrades to False (never raises) when Redis is down."""
    from pulse.worker.redis_client import RedisClient

    async def _fail_connect(self: Any) -> None:
        raise ConnectionError("no redis here")

    monkeypatch.setattr(RedisClient, "connect", _fail_connect)
    assert await dispatch.enqueue_job("some-job-id", redis_url="redis://unreachable") is False


@pytest.mark.anyio
async def test_create_bulk_job_falls_back_to_in_process(
    authorized_client: AsyncClient,
    test_workspace_and_user: tuple[Any, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the stream is unavailable the API processes the job in-process."""
    import pulse.api.v1.bulk_jobs as bulk_jobs

    processed: list[str] = []

    async def _enqueue_unavailable(job_id: str) -> bool:
        return False

    async def _fake_in_process(job_id: str) -> None:
        processed.append(job_id)

    monkeypatch.setattr(bulk_jobs, "enqueue_job", _enqueue_unavailable)
    monkeypatch.setattr(bulk_jobs, "_run_in_process", _fake_in_process)

    files = {"file": ("test.csv", io.BytesIO(b"prompt\nHello\n"), "text/csv")}
    response = await authorized_client.post("/api/v1/bulk-jobs", files=files)
    assert response.status_code == 201
    job_id = response.json()["id"]

    await asyncio.sleep(0.05)  # let the fallback task run
    assert processed == [job_id]


# ---------------------------------------------------------------------------
# Worker message handling
# ---------------------------------------------------------------------------


class _FakeRedis:
    """Just enough of RedisClient for handle_message()."""

    def __init__(self) -> None:
        self.acked: list[str] = []

    async def ack(self, message_id: str, stream: str = "", group: str = "") -> None:
        self.acked.append(message_id)


def _make_worker() -> Worker:
    worker = Worker(redis_url="redis://fake")
    worker._client = _FakeRedis()  # type: ignore[assignment]
    return worker


@pytest.mark.anyio
async def test_worker_acks_successful_job(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str] = []

    async def _ok(job_id: str) -> None:
        seen.append(job_id)

    monkeypatch.setattr(worker_main, "process_job", _ok)
    worker = _make_worker()

    acked = await worker.handle_message("1-0", {"job_id": "job-123"}, attempts=1)

    assert acked is True
    assert seen == ["job-123"]
    assert worker._client.acked == ["1-0"]  # type: ignore[attr-defined]


@pytest.mark.anyio
async def test_worker_leaves_failed_job_pending_for_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _boom(job_id: str) -> None:
        raise RuntimeError("llm provider down")

    monkeypatch.setattr(worker_main, "process_job", _boom)
    worker = _make_worker()

    acked = await worker.handle_message("1-0", {"job_id": "job-123"}, attempts=1)

    assert acked is False
    assert worker._client.acked == []  # type: ignore[attr-defined]


@pytest.mark.anyio
async def test_worker_dead_letters_after_max_attempts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dead_lettered: list[tuple[str, str]] = []

    async def _should_not_run(job_id: str) -> None:
        raise AssertionError("job must not be reprocessed after max attempts")

    async def _fail(job_id: str, reason: str) -> None:
        dead_lettered.append((job_id, reason))

    monkeypatch.setattr(worker_main, "process_job", _should_not_run)
    monkeypatch.setattr(worker_main, "mark_job_failed", _fail)
    worker = _make_worker()

    acked = await worker.handle_message(
        "1-0", {"job_id": "job-123"}, attempts=worker._max_attempts + 1
    )

    assert acked is True
    assert len(dead_lettered) == 1
    assert dead_lettered[0][0] == "job-123"
    assert worker._client.acked == ["1-0"]  # type: ignore[attr-defined]


@pytest.mark.anyio
async def test_worker_acks_poison_message_without_job_id() -> None:
    worker = _make_worker()

    acked = await worker.handle_message("1-0", {}, attempts=1)

    assert acked is True
    assert worker._client.acked == ["1-0"]  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Stale-job reaper
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def reap_factory(async_engine: Any) -> async_sessionmaker[AsyncSession]:
    """A session factory bound to the shared in-memory engine."""
    return async_sessionmaker(async_engine, expire_on_commit=False)


@pytest.mark.anyio
async def test_reap_stale_jobs_fails_running_and_requeues_pending(
    reap_factory: async_sessionmaker[AsyncSession],
    test_workspace_and_user: tuple[Any, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Old RUNNING jobs are failed; old PENDING jobs are re-enqueued."""
    from pulse.api.schemas.bulk_job import BulkJobConfig
    from pulse.api.v1.auth import _MOCK_WORKSPACE_ID

    requeued: list[str] = []

    async def _fake_enqueue(job_id: str, redis_url: str | None = None) -> bool:
        requeued.append(job_id)
        return True

    monkeypatch.setattr(dispatch, "enqueue_job", _fake_enqueue)

    svc = BulkJobService()
    old = datetime.now(UTC) - timedelta(hours=1)

    async with reap_factory() as db:
        running = await svc.create_job(
            db=db, workspace_id=_MOCK_WORKSPACE_ID, config=BulkJobConfig(), total=5
        )
        running.status = BulkJobStatus.RUNNING
        running.updated_at = old
        pending = await svc.create_job(
            db=db, workspace_id=_MOCK_WORKSPACE_ID, config=BulkJobConfig(), total=5
        )
        pending.updated_at = old
        await db.commit()
        running_id, pending_id = str(running.id), str(pending.id)

    stats = await reap_stale_jobs(session_factory=reap_factory, stale_after=timedelta(minutes=1))

    assert stats["failed"] == 1
    assert stats["requeued"] == 1
    assert requeued == [pending_id]

    async with reap_factory() as db:
        job = await svc.get_job_unscoped(db, uuid.UUID(running_id))
        assert job.status == BulkJobStatus.FAILED
        assert "reaped" in (job.errors or {}).get("_worker", "")


@pytest.mark.anyio
async def test_reap_ignores_fresh_jobs(
    reap_factory: async_sessionmaker[AsyncSession],
    test_workspace_and_user: tuple[Any, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Jobs inside the staleness window are left alone."""
    from pulse.api.schemas.bulk_job import BulkJobConfig
    from pulse.api.v1.auth import _MOCK_WORKSPACE_ID

    async def _enqueue_should_not_run(job_id: str, redis_url: str | None = None) -> bool:
        raise AssertionError("fresh jobs must not be requeued")

    monkeypatch.setattr(dispatch, "enqueue_job", _enqueue_should_not_run)

    svc = BulkJobService()
    async with reap_factory() as db:
        await svc.create_job(
            db=db, workspace_id=_MOCK_WORKSPACE_ID, config=BulkJobConfig(), total=1
        )
        await db.commit()

    stats = await reap_stale_jobs(session_factory=reap_factory)
    assert stats == {"failed": 0, "requeued": 0}
