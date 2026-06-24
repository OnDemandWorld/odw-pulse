"""Experiment + ExperimentVariant — A/B/n testing definitions (TSD §4.14)."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pulse.db.base import Base


class ExperimentStatus(enum.StrEnum):
    """Lifecycle status of an experiment."""

    DRAFT = "draft"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class Experiment(Base):
    """Top-level A/B/n experiment definition.

    Experiments are workspace-scoped and optionally tied to a content
    piece (for content-level experiments) or used globally.
    """

    __tablename__ = "experiments"

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
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ExperimentStatus] = mapped_column(
        Enum(ExperimentStatus, name="experiment_status", create_constraint=True),
        nullable=False,
        default=ExperimentStatus.DRAFT,
        server_default=ExperimentStatus.DRAFT.value,
    )
    hypothesis: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="The hypothesis being tested.",
    )
    configuration: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        default=dict,
        comment="Randomisation unit, targeting rules, etc.",
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
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
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    workspace: Mapped[object] = relationship(
        "Workspace", back_populates="experiments", lazy="noload"
    )
    variants: Mapped[list[Any]] = relationship(
        "ExperimentVariant",
        back_populates="experiment",
        cascade="all, delete-orphan",
        lazy="noload",
    )

    __table_args__ = ({"comment": "Experiment definitions (TSD §4.14)."},)

    def __repr__(self) -> str:
        return f"<Experiment id={self.id} name={self.name!r} status={self.status.value}>"


class ExperimentVariant(Base):
    """A single variant (arm / treatment) inside an experiment."""

    __tablename__ = "experiment_variants"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    experiment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("experiments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    weight: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=1.0,
        server_default="1.0",
        comment="Relative traffic weight (normalised at assignment time).",
    )
    configuration: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        default=dict,
        comment="Variant-specific payload: prompt_id, temperature, etc.",
    )
    position: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        comment="Display ordering index.",
    )

    experiment: Mapped[object] = relationship(
        "Experiment", back_populates="variants", lazy="noload"
    )

    __table_args__ = (
        UniqueConstraint("experiment_id", "name", name="uq_experiment_variants_experiment_name"),
        {"comment": "Experiment variants / treatment arms (TSD §4.14)."},
    )

    def __repr__(self) -> str:
        return f"<ExperimentVariant id={self.id} name={self.name!r}>"
