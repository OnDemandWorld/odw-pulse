"""Bulk job management tests (TSD §2.5)."""

from __future__ import annotations

import io
import uuid
from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from pulse.api.schemas.bulk_job import BulkJobConfig
from pulse.api.v1.auth import _MOCK_WORKSPACE_ID
from pulse.auth.security import create_access_token
from pulse.models.bulk_job import BulkJobStatus
from pulse.services.bulk_job_service import BulkJobService

# ---------------------------------------------------------------------------
# POST /api/v1/bulk-jobs — authentication
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_create_bulk_job_requires_auth(
    client: AsyncClient,
    test_workspace_and_user: tuple[Any, Any],
) -> None:
    """Creating a bulk job without authentication should return 401."""
    csv_content = b"prompt,content_type,target_market\nTest prompt,blog_post,en-US\n"
    files = {"file": ("test.csv", io.BytesIO(csv_content), "text/csv")}
    data = {"prompt_column": "prompt", "content_type": "blog_post"}

    response = await client.post("/api/v1/bulk-jobs", files=files, data=data)
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# POST + GET /api/v1/bulk-jobs — CRUD
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_create_and_get_bulk_job(
    authorized_client: AsyncClient,
    test_workspace_and_user: tuple[Any, Any],
) -> None:
    """Creating a bulk job and fetching it should return the job details."""
    csv_content = b"prompt,content_type,target_market\nTest prompt 1,blog_post,en-US\nTest prompt 2,email,de-DE\n"
    files = {"file": ("test.csv", io.BytesIO(csv_content), "text/csv")}
    data = {
        "prompt_column": "prompt",
        "content_type": "blog_post",
        "target_market": "en-US",
    }

    # Create job
    response = await authorized_client.post("/api/v1/bulk-jobs", files=files, data=data)
    assert response.status_code == 201
    job_data = response.json()
    assert job_data["status"] == "pending"
    assert job_data["total"] == 0  # Total is set by worker, not at creation
    assert job_data["progress"] == 0
    assert "id" in job_data
    job_id = job_data["id"]

    # Get job
    response = await authorized_client.get(f"/api/v1/bulk-jobs/{job_id}")
    assert response.status_code == 200
    fetched = response.json()
    assert fetched["id"] == job_id
    assert fetched["status"] == "pending"


# ---------------------------------------------------------------------------
# Service-level progress update
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_update_bulk_job_progress(
    async_session: AsyncSession,
    test_workspace_and_user: tuple[Any, Any],
) -> None:
    """Updating bulk job progress should increment the counter."""
    svc = BulkJobService()
    config = BulkJobConfig()

    # Create job directly via service
    job = await svc.create_job(
        db=async_session,
        workspace_id=_MOCK_WORKSPACE_ID,
        config=config,
        input_file="/tmp/test.csv",
        total=100,
    )
    job_id = job.id
    assert job.progress == 0

    # Increment progress
    job = await svc.increment_progress(async_session, job_id, _MOCK_WORKSPACE_ID, count=10)
    assert job.progress == 10

    job = await svc.increment_progress(async_session, job_id, _MOCK_WORKSPACE_ID, count=5)
    assert job.progress == 15

    # Update status
    job = await svc.update_status(
        async_session, job_id, _MOCK_WORKSPACE_ID, BulkJobStatus.RUNNING, progress=20
    )
    assert job.status == BulkJobStatus.RUNNING
    assert job.progress == 20


# ---------------------------------------------------------------------------
# POST /api/v1/bulk-jobs/{id}/cancel
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_cancel_bulk_job(
    authorized_client: AsyncClient,
    test_workspace_and_user: tuple[Any, Any],
) -> None:
    """Cancelling a pending job should set status to cancelled."""
    csv_content = b"prompt\nTest prompt\n"
    files = {"file": ("test.csv", io.BytesIO(csv_content), "text/csv")}
    data = {"prompt_column": "prompt"}

    # Create job
    response = await authorized_client.post("/api/v1/bulk-jobs", files=files, data=data)
    assert response.status_code == 201
    job_id = response.json()["id"]

    # Cancel job
    response = await authorized_client.post(f"/api/v1/bulk-jobs/{job_id}/cancel")
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"

    # Verify persisted
    response = await authorized_client.get(f"/api/v1/bulk-jobs/{job_id}")
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"


# ---------------------------------------------------------------------------
# Workspace isolation
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_bulk_job_isolation_between_workspaces(
    authorized_client: AsyncClient,
    client: AsyncClient,
    async_session: AsyncSession,
    test_workspace_and_user: tuple[Any, Any],
) -> None:
    """Bulk jobs in one workspace should not be visible from another."""
    csv_content = b"prompt\nTest prompt\n"
    files = {"file": ("test.csv", io.BytesIO(csv_content), "text/csv")}
    data = {"prompt_column": "prompt"}

    # Create job in default workspace
    response = await authorized_client.post("/api/v1/bulk-jobs", files=files, data=data)
    assert response.status_code == 201
    job_id = response.json()["id"]

    # Create token for different workspace
    other_workspace = uuid.UUID("00000000-0000-0000-0000-000000000099")
    token = create_access_token(
        user_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        email="other@example.com",
        workspace_id=other_workspace,
        role="editor",
    )

    # Try to get job with other workspace token
    response = await client.get(
        f"/api/v1/bulk-jobs/{job_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404  # Not found due to workspace isolation

    # List jobs with other workspace token
    response = await client.get(
        "/api/v1/bulk-jobs",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0  # No jobs visible in other workspace


# ---------------------------------------------------------------------------
# List jobs
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_list_bulk_jobs(
    authorized_client: AsyncClient,
    test_workspace_and_user: tuple[Any, Any],
) -> None:
    """Listing bulk jobs should return all jobs for the workspace."""
    # Create first job
    csv_content = b"prompt\nTest 1\n"
    files = {"file": ("test1.csv", io.BytesIO(csv_content), "text/csv")}
    response = await authorized_client.post("/api/v1/bulk-jobs", files=files)
    assert response.status_code == 201

    # Create second job
    csv_content = b"prompt\nTest 2\n"
    files = {"file": ("test2.csv", io.BytesIO(csv_content), "text/csv")}
    response = await authorized_client.post("/api/v1/bulk-jobs", files=files)
    assert response.status_code == 201

    # List all
    response = await authorized_client.get("/api/v1/bulk-jobs")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2

    # Test pagination
    response = await authorized_client.get("/api/v1/bulk-jobs?limit=1")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 1
    assert data["total"] == 2


# ---------------------------------------------------------------------------
# Pause / resume
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_pause_and_resume_bulk_job(
    async_session: AsyncSession,
    authorized_client: AsyncClient,
    test_workspace_and_user: tuple[Any, Any],
) -> None:
    """Pausing and resuming a running job should update status correctly."""
    svc = BulkJobService()
    config = BulkJobConfig()

    # Create job and set to running
    job = await svc.create_job(
        db=async_session,
        workspace_id=_MOCK_WORKSPACE_ID,
        config=config,
        total=50,
    )
    job_id = job.id
    await svc.update_status(
        async_session, job_id, _MOCK_WORKSPACE_ID, BulkJobStatus.RUNNING
    )

    # Pause via API
    response = await authorized_client.post(f"/api/v1/bulk-jobs/{job_id}/pause")
    assert response.status_code == 200
    assert response.json()["status"] == "paused"

    # Resume via API
    response = await authorized_client.post(f"/api/v1/bulk-jobs/{job_id}/resume")
    assert response.status_code == 200
    assert response.json()["status"] == "running"


# ---------------------------------------------------------------------------
# Download results
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_download_bulk_job_results(
    async_session: AsyncSession,
    authorized_client: AsyncClient,
    test_workspace_and_user: tuple[Any, Any],
) -> None:
    """Downloading results for a completed job should return the CSV file."""
    import tempfile

    # Create a mock output file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("prompt,generated_content\nTest,Generated text\n")
        output_path = f.name

    try:
        svc = BulkJobService()
        config = BulkJobConfig()

        # Create job and mark as succeeded with output
        job = await svc.create_job(
            db=async_session,
            workspace_id=_MOCK_WORKSPACE_ID,
            config=config,
            total=1,
        )
        job_id = job.id
        job.status = BulkJobStatus.SUCCEEDED
        job.output_file = output_path
        await async_session.commit()

        # Download results
        response = await authorized_client.get(f"/api/v1/bulk-jobs/{job_id}/download")
        assert response.status_code == 200
        assert "text/csv" in response.headers.get("content-type", "")
        assert "Generated text" in response.text

    finally:
        Path(output_path).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_cannot_pause_non_running_job(
    authorized_client: AsyncClient,
    test_workspace_and_user: tuple[Any, Any],
) -> None:
    """Pausing a pending job should return 400."""
    csv_content = b"prompt\nTest\n"
    files = {"file": ("test.csv", io.BytesIO(csv_content), "text/csv")}

    response = await authorized_client.post("/api/v1/bulk-jobs", files=files)
    assert response.status_code == 201
    job_id = response.json()["id"]

    # Try to pause (job is pending, not running)
    response = await authorized_client.post(f"/api/v1/bulk-jobs/{job_id}/pause")
    assert response.status_code == 400


@pytest.mark.anyio
async def test_cannot_resume_non_paused_job(
    authorized_client: AsyncClient,
    test_workspace_and_user: tuple[Any, Any],
) -> None:
    """Resuming a running job should return 400."""
    csv_content = b"prompt\nTest\n"
    files = {"file": ("test.csv", io.BytesIO(csv_content), "text/csv")}

    response = await authorized_client.post("/api/v1/bulk-jobs", files=files)
    assert response.status_code == 201
    job_id = response.json()["id"]

    # Try to resume (job is pending, not paused)
    response = await authorized_client.post(f"/api/v1/bulk-jobs/{job_id}/resume")
    assert response.status_code == 400
