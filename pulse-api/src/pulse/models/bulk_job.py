"""BulkJob — tracks asynchronous batch processing runs."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pulse.db.base import Base


class BulkJobStatus(enum.StrEnum):
    """Lifecycle status of a bulk job."""

    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class BulkJob(Base):
    """Tracks a batch content-generation / localisation job."""

    __tablename__ = "bulk_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[BulkJobStatus] = mapped_column(
        Enum(BulkJobStatus, name="bulk_job_status", create_constraint=True),
        nullable=False,
        default=BulkJobStatus.PENDING,
        server_default=BulkJobStatus.PENDING.value,
    )
    total: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    input_file: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Storage URI for the input payload."
    )
    output_file: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Storage URI for the generated output."
    )
    errors: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True, default=dict, comment="Per-row errors keyed by row id."
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    workspace: Mapped[object] = relationship("Workspace", back_populates="bulk_jobs", lazy="noload")

    __table_args__ = ({"comment": "Asynchronous batch content-generation jobs."},)

    def __repr__(self) -> str:
        return (
            f"<BulkJob id={self.id} status={self.status.value} "
            f"progress={self.progress}/{self.total}>"
        )
