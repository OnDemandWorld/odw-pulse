"""Bulk-job task processor (TSD §2.5).

The :func:`process_bulk_job` coroutine is the main entry-point for workers.
It loads a ``BulkJob`` from the database, parses the CSV input file, iterates
through rows calling :class:`GenerationOrchestrator`, updates progress every
``PROGRESS_BATCH`` items, and writes results back to storage.
"""

from __future__ import annotations

import asyncio
import csv
import logging
import tempfile
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from pulse.api.schemas.bulk_job import BulkJobConfig
from pulse.generation.models import GenerationRequest
from pulse.models.bulk_job import BulkJobStatus
from pulse.services.bulk_job_service import BulkJobService

logger = logging.getLogger(__name__)

# How many rows to process between progress DB writes.
PROGRESS_BATCH = 10

# How often (seconds) to poll for pause/cancel while waiting.
_PAUSE_POLL_INTERVAL = 2.0

# Shared storage directories.
_UPLOAD_DIR = Path(tempfile.gettempdir()) / "pulse_bulk_uploads"
_OUTPUT_DIR = Path(tempfile.gettempdir()) / "pulse_bulk_outputs"
_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Public entry-point
# ---------------------------------------------------------------------------


async def process_bulk_job(
    job_id: str,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> None:
    """Process a bulk job end-to-end.

    1. Load the job from the database.
    2. Transition status to RUNNING.
    3. Parse the CSV input file.
    4. For each row, build a :class:`GenerationRequest` and call the
       orchestrator.
    5. Update progress every :data:`PROGRESS_BATCH` items.
    6. On pause, wait until resumed or cancelled.
    7. Write results to an output CSV file.
    8. Update final status (SUCCEEDED / FAILED).
    """
    if session_factory is None:
        from pulse.db.session import get_session_factory

        session_factory = get_session_factory()

    svc = BulkJobService()

    # Parse job_id as UUID (always a string from API/worker).
    jid = uuid.UUID(job_id)

    async with session_factory() as db:
        job = await svc.get_job_unscoped(db, jid)
        await svc.update_status(db, jid, job.workspace_id, BulkJobStatus.RUNNING)

        config_dict = svc.extract_config(job)
        config = BulkJobConfig(**config_dict)
        input_path = job.input_file

        if not input_path or not Path(input_path).exists():
            await svc.update_status(db, jid, job.workspace_id, BulkJobStatus.FAILED)
            logger.error("Input file missing for job %s: %s", job_id, input_path)
            return

        rows = _read_input_csv(input_path)
        await svc.update_status(
            db, jid, job.workspace_id, BulkJobStatus.RUNNING, progress=0,
        )
        # Stash ``total`` on the job so we don't need another update call.
        job.total = len(rows)
        await db.commit()

        if not rows:
            await svc.update_status(db, jid, job.workspace_id, BulkJobStatus.SUCCEEDED)
            return

        # Lazily import orchestrator to avoid heavy deps at module load.
        from pulse.api.v1.generate import get_orchestrator

        orchestrator = get_orchestrator()
        results: list[dict[str, Any]] = []
        errors: dict[str, Any] = {}

        for idx, row in enumerate(rows):
            # ---- pause / cancel gate ----
            fresh = await svc.get_job(db, jid, job.workspace_id)
            if fresh.status == BulkJobStatus.PAUSED:
                cancelled = await _wait_for_resume(db, svc, jid, job.workspace_id)
                if cancelled:
                    break
            elif fresh.status == BulkJobStatus.CANCELLED:
                logger.info("Job %s cancelled mid-flight", job_id)
                break

            # ---- generate ----
            try:
                gen_req = _build_generation_request(row, config)
                gen_result = await orchestrator.generate(gen_req)
                results.append(
                    {
                        **row,
                        "generated_content": gen_result.content,
                        "quality_score": gen_result.quality_score,
                        "quality_flags": gen_result.quality_flags,
                    }
                )
            except Exception as exc:
                logger.warning("Row %d failed: %s", idx, exc)
                errors[str(idx)] = str(exc)
                results.append({**row, "error": str(exc)})

            # ---- progress ----
            if (idx + 1) % PROGRESS_BATCH == 0 or idx == len(rows) - 1:
                await svc.increment_progress(db, jid, job.workspace_id, count=1)

        # ---- write output ----
        output_path = _write_output_csv(jid, results)

        final_status = (
            BulkJobStatus.CANCELLED
            if (await svc.get_job(db, jid, job.workspace_id)).status
            == BulkJobStatus.CANCELLED
            else BulkJobStatus.SUCCEEDED
            if not errors
            else BulkJobStatus.FAILED
        )

        job.status = final_status
        job.output_file = str(output_path)
        job.errors = errors or None
        await db.commit()

        logger.info(
            "Job %s finished: %s (%d/%d)",
            job_id,
            final_status.value,
            job.progress,
            job.total,
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _wait_for_resume(
    db: AsyncSession,
    svc: BulkJobService,
    job_id: uuid.UUID,
    workspace_id: uuid.UUID,
) -> bool:
    """Block until the job is resumed or cancelled.

    Returns ``True`` if the job was cancelled, ``False`` if it was resumed.
    """
    while True:
        await asyncio.sleep(_PAUSE_POLL_INTERVAL)
        fresh = await svc.get_job(db, job_id, workspace_id)
        if fresh.status == BulkJobStatus.RUNNING:
            return False
        if fresh.status == BulkJobStatus.CANCELLED:
            return True


def _read_input_csv(path: str) -> list[dict[str, str]]:
    """Read a CSV file and return rows as ``dict[str, str]``."""
    with Path(path).open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        return list(reader)


def _write_output_csv(
    job_id: uuid.UUID,
    results: list[dict[str, Any]],
) -> Path:
    """Write generation results to a CSV file and return its path."""
    output_path = _OUTPUT_DIR / f"{job_id}.csv"

    if not results:
        output_path.write_text("", encoding="utf-8")
        return output_path

    # Collect all column names preserving first-row order, then append extras.
    base_keys = list(results[0].keys())
    extra_keys: list[str] = []
    for row in results[1:]:
        for k in row:
            if k not in base_keys and k not in extra_keys:
                extra_keys.append(k)
    all_keys = base_keys + extra_keys

    with output_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=all_keys, extrasaction="ignore")
        writer.writeheader()
        for row in results:
            writer.writerow(row)

    return output_path


def _build_generation_request(
    row: dict[str, str],
    config: BulkJobConfig,
) -> GenerationRequest:
    """Map a CSV row + job config to a :class:`GenerationRequest`."""
    prompt = row.get(config.prompt_column, "").strip()
    content_type = (
        row.get(config.content_type_column, "")
        if config.content_type_column
        else ""
    ) or config.content_type
    target_market = (
        row.get(config.target_market_column, "")
        if config.target_market_column
        else ""
    ) or config.target_market

    if not prompt:
        raise ValueError(f"Empty prompt in row (expected column '{config.prompt_column}')")

    return GenerationRequest(
        prompt=prompt,
        content_type=content_type,
        target_market=target_market,
        brand_voice_id=config.brand_voice_id,
    )
