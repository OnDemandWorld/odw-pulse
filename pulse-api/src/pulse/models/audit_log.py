"""AuditLog — immutable workspace-scoped audit trail.

The table is partitioned by RANGE(created_at) on a monthly cadence
in the migration.  The ORM model does not declare the partitioning
itself — that's a DDL-only concern.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pulse.db.base import Base


class AuditLog(Base):
    """Append-only audit log — partitioned by month on ``created_at``."""

    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    action: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Dot-namespaced action, e.g. 'content_piece.created'.",
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        comment="User or API key that performed the action.",
    )
    resource: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Resource identifier, e.g. 'content_piece:1234'.",
    )
    details: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        default=dict,
        comment="Free-form structured payload describing the action.",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    workspace: Mapped[object] = relationship(
        "Workspace", back_populates="audit_logs", lazy="noload"
    )

    __table_args__ = (
        Index("ix_audit_logs_workspace_created", "workspace_id", "created_at"),
        Index("ix_audit_logs_workspace_action", "workspace_id", "action"),
        {
            "comment": ("Immutable audit trail — partitioned by RANGE(created_at) monthly."),
            "postgresql_partition_by": "RANGE(created_at)",
        },
    )

    def __repr__(self) -> str:
        return f"<AuditLog id={self.id} action={self.action!r}>"
