"""Experiment telemetry and content performance events.

* ``ExperimentAssignment``  — subject → variant mapping (§4.15)
* ``ExperimentExposure``    — variant was shown to a subject (§4.16)
* ``PerformanceEvent``      — business-metric signal (§4.17)

All three are *very* high-volume tables and are therefore partitioned
in the migration:

* ``experiment_assignments`` — RANGE(assigned_at) monthly
* ``experiment_exposures``   — RANGE(exposed_at)  weekly
* ``performance_events``     — RANGE(received_at) weekly

The ORM models only declare the logical schema; the migration owns
partitioning DDL.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Index, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from pulse.db.base import Base


class ExposureChannel(enum.StrEnum):
    """Channel through which a variant was exposed."""

    WEB = "web"
    EMAIL = "email"
    MOBILE = "mobile"
    API = "api"
    OTHER = "other"


class PerformanceMetricType(enum.StrEnum):
    """Kind of business-metric signal."""

    IMPRESSION = "impression"
    CLICK = "click"
    CONVERSION = "conversion"
    REVENUE = "revenue"
    CUSTOM = "custom"


# ---------------------------------------------------------------------------
# ExperimentAssignment (§4.15)
# ---------------------------------------------------------------------------


class ExperimentAssignment(Base):
    """Deterministic mapping of a subject to a variant."""

    __tablename__ = "experiment_assignments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    experiment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("experiments.id", ondelete="CASCADE"),
        nullable=False,
    )
    variant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("experiment_variants.id", ondelete="CASCADE"),
        nullable=False,
    )
    subject_id: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Opaque subject identifier (user id, session id, …).",
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        Index("ix_experiment_assignments_experiment_subject", "experiment_id", "subject_id"),
        Index("ix_experiment_assignments_assigned_at", "assigned_at"),
        {
            "comment": (
                "Experiment subject → variant assignments — "
                "partitioned by RANGE(assigned_at) monthly."
            ),
            "postgresql_partition_by": "RANGE(assigned_at)",
        },
    )


# ---------------------------------------------------------------------------
# ExperimentExposure (§4.16)
# ---------------------------------------------------------------------------


class ExperimentExposure(Base):
    """Records that a variant was actually shown to a subject."""

    __tablename__ = "experiment_exposures"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    experiment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("experiments.id", ondelete="CASCADE"),
        nullable=False,
    )
    variant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("experiment_variants.id", ondelete="CASCADE"),
        nullable=False,
    )
    subject_id: Mapped[str] = mapped_column(Text, nullable=False)
    channel: Mapped[ExposureChannel] = mapped_column(
        Enum(ExposureChannel, name="exposure_channel", create_constraint=True),
        nullable=False,
        default=ExposureChannel.WEB,
        server_default=ExposureChannel.WEB.value,
    )
    exposed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    metadata_: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata", JSONB, nullable=True, default=dict
    )

    __table_args__ = (
        Index("ix_experiment_exposures_experiment_subject", "experiment_id", "subject_id"),
        Index("ix_experiment_exposures_exposed_at", "exposed_at"),
        {
            "comment": ("Variant exposure events — partitioned by RANGE(exposed_at) weekly."),
            "postgresql_partition_by": "RANGE(exposed_at)",
        },
    )


# ---------------------------------------------------------------------------
# PerformanceEvent (§4.17)
# ---------------------------------------------------------------------------


class PerformanceEvent(Base):
    """Business-metric signal tied to a content piece (and optionally a variant)."""

    __tablename__ = "performance_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    content_piece_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("content_pieces.id", ondelete="SET NULL"),
        nullable=True,
    )
    experiment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("experiments.id", ondelete="SET NULL"),
        nullable=True,
    )
    variant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("experiment_variants.id", ondelete="SET NULL"),
        nullable=True,
    )
    subject_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    metric_type: Mapped[PerformanceMetricType] = mapped_column(
        Enum(PerformanceMetricType, name="performance_metric_type", create_constraint=True),
        nullable=False,
    )
    value: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=1.0,
        server_default="1.0",
        comment="Numeric value of the metric (count, revenue, …).",
    )
    metadata_: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata", JSONB, nullable=True, default=dict
    )
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        Index("ix_performance_events_content_piece", "content_piece_id"),
        Index("ix_performance_events_experiment", "experiment_id"),
        Index("ix_performance_events_received_at", "received_at"),
        Index("ix_performance_events_metric_type", "metric_type"),
        {
            "comment": ("Business-metric signals — partitioned by RANGE(received_at) weekly."),
            "postgresql_partition_by": "RANGE(received_at)",
        },
    )
