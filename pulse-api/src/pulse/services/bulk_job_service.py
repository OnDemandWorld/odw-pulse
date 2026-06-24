"""Bulk job management service (TSD §2.5)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from pulse.api.schemas.bulk_job import BulkJobConfig
from pulse.models.bulk_job import BulkJob, BulkJobStatus


class BulkJobService:
    """Service for managing bulk generation jobs."""

    async def create_job(
        self,
        db: AsyncSession,
        workspace_id: uuid.UUID,
        config: BulkJobConfig,
        input_file: str | None = None,
        total: int = 0,
    ) -> BulkJob:
        """Create a new bulk job."""
        job = BulkJob(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            status=BulkJobStatus.PENDING,
            total=total,
            progress=0,
            input_file=input_file,
            errors={},
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        # Stash config as JSON on the errors field (abused as generic JSONB).
        # A dedicated ``config`` column would be cleaner but requires a migration.
        job.errors = {"_config": config.model_dump()}
        db.add(job)
        await db.commit()
        await db.refresh(job)
        return job

    async def get_job(
        self,
        db: AsyncSession,
        job_id: uuid.UUID,
        workspace_id: uuid.UUID,
    ) -> BulkJob:
        """Get a bulk job by ID, scoped to workspace."""
        result = await db.execute(
            select(BulkJob).where(
                BulkJob.id == job_id,
                BulkJob.workspace_id == workspace_id,
            )
        )
        job = result.scalar_one_or_none()
        if job is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Bulk job not found",
            )
        return job

    async def get_job_unscoped(
        self,
        db: AsyncSession,
        job_id: uuid.UUID,
    ) -> BulkJob:
        """Get a bulk job by ID without workspace scoping (for workers)."""
        result = await db.execute(select(BulkJob).where(BulkJob.id == job_id))
        job = result.scalar_one_or_none()
        if job is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Bulk job not found",
            )
        return job

    async def list_jobs(
        self,
        db: AsyncSession,
        workspace_id: uuid.UUID,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[BulkJob], int]:
        """List bulk jobs with pagination, scoped to workspace."""
        # Total count
        count_query = (
            select(func.count())
            .select_from(BulkJob)
            .where(BulkJob.workspace_id == workspace_id)
        )
        count_result = await db.execute(count_query)
        total = count_result.scalar() or 0

        # Paginated items
        query = (
            select(BulkJob)
            .where(BulkJob.workspace_id == workspace_id)
            .order_by(BulkJob.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await db.execute(query)
        items = list(result.scalars().all())

        return items, total

    async def update_status(
        self,
        db: AsyncSession,
        job_id: uuid.UUID,
        workspace_id: uuid.UUID,
        new_status: BulkJobStatus,
        progress: int | None = None,
    ) -> BulkJob:
        """Update job status and optionally progress."""
        job = await self.get_job(db, job_id, workspace_id)
        job.status = new_status
        if progress is not None:
            job.progress = progress
        job.updated_at = datetime.now(UTC)
        await db.commit()
        await db.refresh(job)
        return job

    async def increment_progress(
        self,
        db: AsyncSession,
        job_id: uuid.UUID,
        workspace_id: uuid.UUID,
        count: int = 1,
    ) -> BulkJob:
        """Increment the progress counter by *count*."""
        job = await self.get_job(db, job_id, workspace_id)
        job.progress = (job.progress or 0) + count
        job.updated_at = datetime.now(UTC)
        await db.commit()
        await db.refresh(job)
        return job

    async def pause(
        self,
        db: AsyncSession,
        job_id: uuid.UUID,
        workspace_id: uuid.UUID,
    ) -> BulkJob:
        """Pause a running job."""
        job = await self.get_job(db, job_id, workspace_id)
        if job.status != BulkJobStatus.RUNNING:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot pause job in '{job.status.value}' status",
            )
        job.status = BulkJobStatus.PAUSED
        job.updated_at = datetime.now(UTC)
        await db.commit()
        await db.refresh(job)
        return job

    async def resume(
        self,
        db: AsyncSession,
        job_id: uuid.UUID,
        workspace_id: uuid.UUID,
    ) -> BulkJob:
        """Resume a paused job."""
        job = await self.get_job(db, job_id, workspace_id)
        if job.status != BulkJobStatus.PAUSED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot resume job in '{job.status.value}' status",
            )
        job.status = BulkJobStatus.RUNNING
        job.updated_at = datetime.now(UTC)
        await db.commit()
        await db.refresh(job)
        return job

    async def cancel(
        self,
        db: AsyncSession,
        job_id: uuid.UUID,
        workspace_id: uuid.UUID,
    ) -> BulkJob:
        """Cancel a job (allowed from PENDING, RUNNING, or PAUSED)."""
        job = await self.get_job(db, job_id, workspace_id)
        if job.status not in (
            BulkJobStatus.PENDING,
            BulkJobStatus.RUNNING,
            BulkJobStatus.PAUSED,
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot cancel job in '{job.status.value}' status",
            )
        job.status = BulkJobStatus.CANCELLED
        job.updated_at = datetime.now(UTC)
        await db.commit()
        await db.refresh(job)
        return job

    @staticmethod
    def extract_config(job: BulkJob) -> dict[str, Any]:
        """Extract the generation config stashed in ``job.errors``."""
        raw = job.errors or {}
        config = raw.get("_config", {})
        if isinstance(config, dict):
            return config
        return {}
