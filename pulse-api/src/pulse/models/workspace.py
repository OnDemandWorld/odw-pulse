"""Workspace model — top-level tenant boundary."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pulse.db.base import Base


class Workspace(Base):
    """A workspace is the fundamental multi-tenant isolation boundary.

    All workspace-scoped tables carry a ``workspace_id`` FK back here
    and RLS policies enforce row-level isolation per workspace.
    """

    __tablename__ = "workspaces"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    settings: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True, default=dict)
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

    # Relationships (back_populates on the child side)
    users: Mapped[list[Any]] = relationship("User", back_populates="workspace", lazy="noload")
    content_pieces: Mapped[list[Any]] = relationship(
        "ContentPiece", back_populates="workspace", lazy="noload"
    )
    brand_voices: Mapped[list[Any]] = relationship(
        "BrandVoice", back_populates="workspace", lazy="noload"
    )
    glossaries: Mapped[list[Any]] = relationship(
        "Glossary", back_populates="workspace", lazy="noload"
    )
    bulk_jobs: Mapped[list[Any]] = relationship(
        "BulkJob", back_populates="workspace", lazy="noload"
    )
    audit_logs: Mapped[list[Any]] = relationship(
        "AuditLog", back_populates="workspace", lazy="noload"
    )
    api_keys: Mapped[list[Any]] = relationship("APIKey", back_populates="workspace", lazy="noload")
    webhook_configs: Mapped[list[Any]] = relationship(
        "WebhookConfig", back_populates="workspace", lazy="noload"
    )
    experiments: Mapped[list[Any]] = relationship(
        "Experiment", back_populates="workspace", lazy="noload"
    )

    __table_args__ = (
        UniqueConstraint("slug", name="uq_workspaces_slug"),
        {"comment": "Top-level tenant boundary."},
    )

    def __repr__(self) -> str:
        return f"<Workspace id={self.id} slug={self.slug!r}>"
