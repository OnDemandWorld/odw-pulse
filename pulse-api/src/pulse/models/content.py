"""ContentPiece + ContentVersion models.

``ContentPiece`` is partitioned by HASH(workspace_id) into 16
partitions — the partition declaration is handled in the Alembic
migration (SQLAlchemy's ``postgresql_partition_by`` only works when
DDL is emitted by the ORM, which we don't do at runtime because the
migration owns the schema).

The ORM model therefore uses a plain ``__tablename__``; the migration
creates the partitioned parent table and attaches child partitions.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pulse.db.base import Base


class ContentStatus(enum.StrEnum):
    """Editorial lifecycle status of a content piece."""

    DRAFT = "draft"
    REVIEW = "review"
    APPROVED = "approved"
    REJECTED = "rejected"
    ARCHIVED = "archived"


class ContentPiece(Base):
    """A piece of content — article, landing page, email, etc.

    Partitioned by HASH(workspace_id) in Postgres (see migration).
    """

    __tablename__ = "content_pieces"

    # The table is declared as a *partitioned* table in the migration;
    # SQLAlchemy only needs the logical schema here.
    __table_args__ = (
        UniqueConstraint("workspace_id", "slug", name="uq_content_pieces_workspace_slug"),
        Index("ix_content_pieces_workspace_status", "workspace_id", "status"),
        Index("ix_content_pieces_workspace_market", "workspace_id", "market_code"),
        {
            "comment": (
                "Content pieces — partitioned by HASH(workspace_id) into 16 partitions in Postgres."
            ),
            # Hint for the migration; ignored by SQLAlchemy's default PG dialect.
            "postgresql_partition_by": "HASH(workspace_id)",
        },
    )

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
    slug: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata", JSONB, nullable=True, default=dict
    )
    status: Mapped[ContentStatus] = mapped_column(
        Enum(ContentStatus, name="content_status", create_constraint=True),
        nullable=False,
        default=ContentStatus.DRAFT,
        server_default=ContentStatus.DRAFT.value,
    )
    market_code: Mapped[str | None] = mapped_column(Text, nullable=True)
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

    workspace: Mapped[object] = relationship(
        "Workspace", back_populates="content_pieces", lazy="noload"
    )
    versions: Mapped[list[Any]] = relationship(
        "ContentVersion",
        back_populates="content_piece",
        cascade="all, delete-orphan",
        lazy="noload",
    )

    def __repr__(self) -> str:
        return f"<ContentPiece id={self.id} slug={self.slug!r} status={self.status.value}>"


class ContentVersion(Base):
    """Immutable snapshot of a content piece at a point in time.

    Inherits the partitioning of its parent ``content_pieces`` via FK.
    """

    __tablename__ = "content_versions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    content_piece_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("content_pieces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata", JSONB, nullable=True, default=dict
    )
    status: Mapped[ContentStatus] = mapped_column(
        Enum(ContentStatus, name="content_status", create_constraint=False, create_type=False),
        nullable=False,
    )
    change_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    content_piece: Mapped[object] = relationship(
        "ContentPiece", back_populates="versions", lazy="noload"
    )

    __table_args__ = (
        UniqueConstraint(
            "content_piece_id", "version_number", name="uq_content_versions_piece_version"
        ),
        {"comment": "Immutable content versions."},
    )

    def __repr__(self) -> str:
        return (
            f"<ContentVersion id={self.id} piece={self.content_piece_id} v={self.version_number}>"
        )
