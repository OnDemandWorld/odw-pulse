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

    async def extend_claim(
        self, message_id: str, stream: str = "", group: str = "", consumer: str = ""
    ) -> None:
        """No-op heartbeat (tests finish before the first interval elapses)."""


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
    from tests.conftest import TEST_WORKSPACE_ID

    requeued: list[str] = []

    async def _fake_enqueue(job_id: str, redis_url: str | None = None) -> bool:
        requeued.append(job_id)
        return True

    monkeypatch.setattr(dispatch, "enqueue_job", _fake_enqueue)

    svc = BulkJobService()
    old = datetime.now(UTC) - timedelta(hours=1)

    async with reap_factory() as db:
        running = await svc.create_job(
            db=db, workspace_id=TEST_WORKSPACE_ID, config=BulkJobConfig(), total=5
        )
        running.status = BulkJobStatus.RUNNING
        running.updated_at = old
        pending = await svc.create_job(
            db=db, workspace_id=TEST_WORKSPACE_ID, config=BulkJobConfig(), total=5
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
    from tests.conftest import TEST_WORKSPACE_ID

    async def _enqueue_should_not_run(job_id: str, redis_url: str | None = None) -> bool:
        raise AssertionError("fresh jobs must not be requeued")

    monkeypatch.setattr(dispatch, "enqueue_job", _enqueue_should_not_run)

    svc = BulkJobService()
    async with reap_factory() as db:
        await svc.create_job(
            db=db, workspace_id=TEST_WORKSPACE_ID, config=BulkJobConfig(), total=1
        )
        await db.commit()

    stats = await reap_stale_jobs(session_factory=reap_factory)
    assert stats == {"failed": 0, "requeued": 0}


# ---------------------------------------------------------------------------
# Regression: audit #9 — never ack a message another consumer is processing
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_worker_does_not_ack_job_active_elsewhere(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _active(job_id: str) -> str:
        return "active"

    monkeypatch.setattr(worker_main, "process_job", _active)
    worker = _make_worker()

    acked = await worker.handle_message("1-0", {"job_id": "job-123"}, attempts=1)

    assert acked is False
    assert worker._client.acked == []  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Regression: audit #4 / #8 — fresh state reads and atomic job claim
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_get_job_observes_external_status_change(
    reap_factory: async_sessionmaker[AsyncSession],
    test_workspace_and_user: tuple[Any, Any],
) -> None:
    """A long-lived session must see status changes committed by other sessions."""
    from pulse.api.schemas.bulk_job import BulkJobConfig
    from tests.conftest import TEST_WORKSPACE_ID

    svc = BulkJobService()
    async with reap_factory() as db:
        job = await svc.create_job(
            db=db, workspace_id=TEST_WORKSPACE_ID, config=BulkJobConfig(), total=1
        )
        jid = job.id
        assert job.status == BulkJobStatus.PENDING

        # Simulate the API pausing the job from a different session.
        async with reap_factory() as other:
            other_job = await svc.get_job_unscoped(other, jid)
            other_job.status = BulkJobStatus.PAUSED
            await other.commit()

        fresh = await svc.get_job(db, jid, TEST_WORKSPACE_ID)
        assert fresh.status == BulkJobStatus.PAUSED


@pytest.mark.anyio
async def test_claim_pending_job_is_atomic(
    reap_factory: async_sessionmaker[AsyncSession],
    test_workspace_and_user: tuple[Any, Any],
) -> None:
    """Only the first claim wins; a duplicate delivery gets None."""
    from pulse.api.schemas.bulk_job import BulkJobConfig
    from tests.conftest import TEST_WORKSPACE_ID

    svc = BulkJobService()
    async with reap_factory() as db:
        job = await svc.create_job(
            db=db, workspace_id=TEST_WORKSPACE_ID, config=BulkJobConfig(), total=1
        )
        jid = job.id

    async with reap_factory() as db:
        claimed = await svc.claim_pending_job(db, jid)
        assert claimed is not None
        assert claimed.status == BulkJobStatus.RUNNING

        duplicate = await svc.claim_pending_job(db, jid)
        assert duplicate is None


@pytest.mark.anyio
async def test_process_bulk_job_outcomes_for_non_pending_jobs(
    reap_factory: async_sessionmaker[AsyncSession],
    test_workspace_and_user: tuple[Any, Any],
) -> None:
    """RUNNING/PAUSED jobs report 'active'; terminal jobs report 'terminal'."""
    from pulse.api.schemas.bulk_job import BulkJobConfig
    from pulse.worker.tasks import process_bulk_job
    from tests.conftest import TEST_WORKSPACE_ID

    svc = BulkJobService()
    async with reap_factory() as db:
        running = await svc.create_job(
            db=db, workspace_id=TEST_WORKSPACE_ID, config=BulkJobConfig(), total=1
        )
        running.status = BulkJobStatus.RUNNING
        done = await svc.create_job(
            db=db, workspace_id=TEST_WORKSPACE_ID, config=BulkJobConfig(), total=1
        )
        done.status = BulkJobStatus.SUCCEEDED
        await db.commit()
        running_id, done_id = str(running.id), str(done.id)

    assert await process_bulk_job(running_id, session_factory=reap_factory) == "active"
    assert await process_bulk_job(done_id, session_factory=reap_factory) == "terminal"


# ---------------------------------------------------------------------------
# Regression: audit #50 — orphaned PAUSED jobs are recovered
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_reap_fails_orphaned_paused_but_not_live_pause(
    reap_factory: async_sessionmaker[AsyncSession],
    test_workspace_and_user: tuple[Any, Any],
) -> None:
    from pulse.api.schemas.bulk_job import BulkJobConfig
    from tests.conftest import TEST_WORKSPACE_ID

    svc = BulkJobService()
    old = datetime.now(UTC) - timedelta(hours=1)
    async with reap_factory() as db:
        orphaned = await svc.create_job(
            db=db, workspace_id=TEST_WORKSPACE_ID, config=BulkJobConfig(), total=5
        )
        orphaned.status = BulkJobStatus.PAUSED
        orphaned.updated_at = old
        live = await svc.create_job(
            db=db, workspace_id=TEST_WORKSPACE_ID, config=BulkJobConfig(), total=5
        )
        live.status = BulkJobStatus.PAUSED  # fresh updated_at = live heartbeat
        await db.commit()
        orphaned_id, live_id = orphaned.id, live.id

    stats = await reap_stale_jobs(session_factory=reap_factory, stale_after=timedelta(minutes=1))
    assert stats["failed"] == 1

    async with reap_factory() as db:
        assert (await svc.get_job_unscoped(db, orphaned_id)).status == BulkJobStatus.FAILED
        assert (await svc.get_job_unscoped(db, live_id)).status == BulkJobStatus.PAUSED


# ---------------------------------------------------------------------------
# Regression: audit #47/#48/#49 — Redis hardening
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_incr_uses_atomic_script(monkeypatch: pytest.MonkeyPatch) -> None:
    from pulse.core.redis_kv import RedisKV

    class _StubClient:
        def __init__(self) -> None:
            self.eval_calls: list[Any] = []

        async def eval(self, script: str, numkeys: int, *args: Any) -> list[int]:
            self.eval_calls.append((script, numkeys, args))
            return [5, 42]

    kv = RedisKV(redis_url="redis://fake")
    stub = _StubClient()

    async def _client() -> Any:
        return stub

    monkeypatch.setattr(kv, "_client", _client)
    count, retry_after = await kv.incr("pulse:ratelimit:login:1.2.3.4", 60)
    assert (count, retry_after) == (5, 42)
    assert len(stub.eval_calls) == 1
    script, numkeys, args = stub.eval_calls[0]
    assert "INCR" in script and "EXPIRE" in script and numkeys == 1
    assert args == ("pulse:ratelimit:login:1.2.3.4", 60)


def test_redact_url_strips_credentials() -> None:
    from pulse.core.redis_kv import redact_url

    assert redact_url("rediss://:s3cret@redis.internal:6380/0") == "rediss://redis.internal:6380/0"
    assert redact_url("redis://redis:6379/0") == "redis://redis:6379/0"


@pytest.mark.anyio
async def test_push_job_bounds_stream_length() -> None:
    from pulse.worker.redis_client import RedisClient

    class _StubRedis:
        def __init__(self) -> None:
            self.xadd_kwargs: list[Any] = []

        async def xadd(self, stream: str, fields: dict[str, str], **kwargs: Any) -> str:
            self.xadd_kwargs.append(kwargs)
            return "1-0"

    client = RedisClient(redis_url="redis://fake")
    stub = _StubRedis()
    client._redis = stub
    await client.push_job("job-1")
    assert stub.xadd_kwargs[0].get("maxlen") == 10_000
    assert stub.xadd_kwargs[0].get("approximate") is True


# ---------------------------------------------------------------------------
# Regression: audit #87 — XPENDING pagination covers the whole PEL
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_pending_delivery_counts_paginates() -> None:
    from pulse.worker.redis_client import RedisClient

    class _StubRedis:
        def __init__(self) -> None:
            self.calls: list[str] = []

        async def xpending_range(self, name: str, groupname: str, min: str, max: str, count: int) -> list[dict[str, Any]]:
            self.calls.append(min)
            if min == "-":
                return [{"message_id": f"{i}-0", "times_delivered": 2} for i in range(1000)]
            if min == "999-0":
                return [{"message_id": "1000-0", "times_delivered": 7}]
            return []

    client = RedisClient(redis_url="redis://fake")
    stub = _StubRedis()
    client._redis = stub
    counts = await client.pending_delivery_counts()
    assert len(counts) == 1001
    assert counts["1000-0"] == 7
    assert stub.calls == ["-", "999-0"]


# ---------------------------------------------------------------------------
# Regression: audit #91 — dispatch reuses one Redis connection
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_enqueue_reuses_shared_client(monkeypatch: pytest.MonkeyPatch) -> None:
    from pulse.worker import dispatch as dispatch_mod

    connects = 0
    pushes: list[str] = []

    class _StubClient:
        def __init__(self, redis_url: str | None = None) -> None:
            pass

        async def connect(self) -> None:
            nonlocal connects
            connects += 1

        async def ensure_group(self, *a: Any, **k: Any) -> None:
            pass

        async def push_job(self, job_id: str, *a: Any, **k: Any) -> None:
            pushes.append(job_id)

        async def disconnect(self) -> None:
            pass

    monkeypatch.setattr(dispatch_mod, "RedisClient", _StubClient)
    monkeypatch.setattr(dispatch_mod, "_shared_client", None)
    monkeypatch.setattr(dispatch_mod, "_group_ready", False)

    assert await dispatch_mod.enqueue_job("j1") is True
    assert await dispatch_mod.enqueue_job("j2") is True
    assert connects == 1
    assert pushes == ["j1", "j2"]
