"""Bulk job management endpoints (TSD §2.5).

* ``POST   /bulk-jobs``            — create a bulk job (file upload + config)
* ``GET    /bulk-jobs``            — list jobs
* ``GET    /bulk-jobs/{id}``       — get job status / progress
* ``POST   /bulk-jobs/{id}/pause`` — pause a running job
* ``POST   /bulk-jobs/{id}/resume``— resume a paused job
* ``POST   /bulk-jobs/{id}/cancel``— cancel a job
* ``GET    /bulk-jobs/{id}/download`` — download generated results
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from pulse.api.deps import CurrentUser, get_db
from pulse.api.schemas.bulk_job import BulkJobConfig, BulkJobList, BulkJobRead
from pulse.services.bulk_job_service import BulkJobService

router = APIRouter(prefix="/bulk-jobs", tags=["bulk-jobs"])

_bulk_job_service = BulkJobService()

# Shared storage directories (must match worker.tasks).
import tempfile  # noqa: E402

_UPLOAD_DIR = Path(tempfile.gettempdir()) / "pulse_bulk_uploads"
_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# POST /bulk-jobs
# ---------------------------------------------------------------------------


@router.post("", response_model=BulkJobRead, status_code=status.HTTP_201_CREATED)
async def create_bulk_job(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    file: UploadFile = File(...),
    prompt_column: str = Form("prompt"),
    content_type: str = Form("blog_post"),
    target_market: str = Form("en-US"),
    content_type_column: str | None = Form(None),
    target_market_column: str | None = Form(None),
    brand_voice_id: str | None = Form(None),
) -> BulkJobRead:
    """Create a bulk generation job.

    Accepts a CSV file upload plus generation configuration as form fields.
    The file is persisted locally and a ``BulkJob`` row is created with
    status ``PENDING``.  An async worker picks up the job from a Redis
    stream (or falls back to an in-process background task).
    """
    if not file.filename or not file.filename.endswith(".csv"):
        from fastapi import HTTPException

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only CSV files are supported",
        )

    # Persist uploaded file.
    file_path = _UPLOAD_DIR / f"{uuid.uuid4()}_{file.filename}"
    content_bytes = await file.read()
    file_path.write_bytes(content_bytes)

    config = BulkJobConfig(
        prompt_column=prompt_column,
        content_type=content_type,
        target_market=target_market,
        content_type_column=content_type_column,
        target_market_column=target_market_column,
        brand_voice_id=brand_voice_id,
    )

    job = await _bulk_job_service.create_job(
        db=db,
        workspace_id=current_user.workspace_id,
        config=config,
        input_file=str(file_path),
    )

    # Dispatch to worker (best-effort — falls back to in-process).
    try:
        import asyncio

        from pulse.worker.tasks import process_bulk_job

        asyncio.create_task(
            process_bulk_job(str(job.id)),
            name=f"bulk-job-{job.id}",
        )
    except Exception:  # pragma: no cover — defensive
        import logging

        logging.getLogger(__name__).warning(
            "Could not dispatch job %s to worker", job.id, exc_info=True,
        )

    return BulkJobRead.model_validate(job, from_attributes=True)


# ---------------------------------------------------------------------------
# GET /bulk-jobs
# ---------------------------------------------------------------------------


@router.get("", response_model=BulkJobList)
async def list_bulk_jobs(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> BulkJobList:
    """List bulk jobs for the current workspace."""
    items, total = await _bulk_job_service.list_jobs(
        db=db,
        workspace_id=current_user.workspace_id,
        limit=limit,
        offset=offset,
    )
    return BulkJobList(
        items=[BulkJobRead.model_validate(j, from_attributes=True) for j in items],
        total=total,
    )


# ---------------------------------------------------------------------------
# GET /bulk-jobs/{id}
# ---------------------------------------------------------------------------


@router.get("/{job_id}", response_model=BulkJobRead)
async def get_bulk_job(
    job_id: uuid.UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> BulkJobRead:
    """Get status and progress of a bulk job."""
    job = await _bulk_job_service.get_job(
        db=db, job_id=job_id, workspace_id=current_user.workspace_id,
    )
    return BulkJobRead.model_validate(job, from_attributes=True)


# ---------------------------------------------------------------------------
# POST /bulk-jobs/{id}/pause
# ---------------------------------------------------------------------------


@router.post("/{job_id}/pause", response_model=BulkJobRead)
async def pause_bulk_job(
    job_id: uuid.UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> BulkJobRead:
    """Pause a running bulk job."""
    job = await _bulk_job_service.pause(
        db=db, job_id=job_id, workspace_id=current_user.workspace_id,
    )
    return BulkJobRead.model_validate(job, from_attributes=True)


# ---------------------------------------------------------------------------
# POST /bulk-jobs/{id}/resume
# ---------------------------------------------------------------------------


@router.post("/{job_id}/resume", response_model=BulkJobRead)
async def resume_bulk_job(
    job_id: uuid.UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> BulkJobRead:
    """Resume a paused bulk job."""
    job = await _bulk_job_service.resume(
        db=db, job_id=job_id, workspace_id=current_user.workspace_id,
    )
    return BulkJobRead.model_validate(job, from_attributes=True)


# ---------------------------------------------------------------------------
# POST /bulk-jobs/{id}/cancel
# ---------------------------------------------------------------------------


@router.post("/{job_id}/cancel", response_model=BulkJobRead)
async def cancel_bulk_job(
    job_id: uuid.UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> BulkJobRead:
    """Cancel a bulk job."""
    job = await _bulk_job_service.cancel(
        db=db, job_id=job_id, workspace_id=current_user.workspace_id,
    )
    return BulkJobRead.model_validate(job, from_attributes=True)


# ---------------------------------------------------------------------------
# GET /bulk-jobs/{id}/download
# ---------------------------------------------------------------------------


@router.get("/{job_id}/download")
async def download_bulk_job_results(
    job_id: uuid.UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    """Download the generated output CSV for a completed bulk job."""
    job: Any = await _bulk_job_service.get_job(
        db=db, job_id=job_id, workspace_id=current_user.workspace_id,
    )
    if not job.output_file or not Path(job.output_file).exists():
        from fastapi import HTTPException

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Output file not found",
        )
    return FileResponse(
        path=job.output_file,
        filename=f"bulk_job_{job_id}.csv",
        media_type="text/csv",
    )
