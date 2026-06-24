"""Pydantic v2 schemas for bulk job endpoints (TSD §2.5)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from pulse.models.bulk_job import BulkJobStatus


class BulkJobConfig(BaseModel):
    """Configuration for a bulk generation job.

    Controls how CSV rows are mapped to generation parameters.
    """

    prompt_column: str = Field(
        default="prompt",
        description="CSV column containing the generation prompt",
    )
    content_type: str = Field(
        default="blog_post",
        description="Default content type for rows without explicit type",
    )
    target_market: str = Field(
        default="en-US",
        description="Default target market for rows without explicit market",
    )
    content_type_column: str | None = Field(
        default=None,
        description="Optional CSV column for per-row content type override",
    )
    target_market_column: str | None = Field(
        default=None,
        description="Optional CSV column for per-row market override",
    )
    brand_voice_id: str | None = Field(
        default=None,
        description="Optional brand voice ID for tone consistency",
    )


class BulkJobCreateRequest(BaseModel):
    """Request body for creating a bulk job (without file upload)."""

    config: BulkJobConfig = Field(default_factory=BulkJobConfig)


class BulkJobRead(BaseModel):
    """Public representation of a bulk job."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    status: BulkJobStatus
    total: int
    progress: int
    input_file: str | None = None
    output_file: str | None = None
    errors: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime

    @property
    def percent_complete(self) -> float:
        """Return progress as a percentage (0.0–100.0)."""
        if self.total == 0:
            return 0.0
        return round((self.progress / self.total) * 100, 2)


class BulkJobList(BaseModel):
    """Paginated list of bulk jobs."""

    items: list[BulkJobRead]
    total: int
