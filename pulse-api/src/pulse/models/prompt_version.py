"""PromptVersion — append-only history of prompt templates (TSD §4.18-4.19).

Prompts are the core artefact Pulse manages: every generation run
resolves to a specific prompt version.  The model is append-only —
existing versions are never mutated, only superseded.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from pulse.db.base import Base


class PromptStatus(enum.StrEnum):
    """Lifecycle status of a prompt version."""

    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class PromptVersion(Base):
    """An immutable, versioned prompt template."""

    __tablename__ = "prompt_versions"

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
    name: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Stable identifier shared across versions, e.g. 'blog_outline_v1'.",
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    template: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="The prompt body with {{variable}} placeholders.",
    )
    variables: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        default=dict,
        comment="Schema describing expected template variables.",
    )
    metadata_: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata", JSONB, nullable=True, default=dict
    )
    status: Mapped[PromptStatus] = mapped_column(
        Enum(PromptStatus, name="prompt_status", create_constraint=True),
        nullable=False,
        default=PromptStatus.DRAFT,
        server_default=PromptStatus.DRAFT.value,
    )
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

    __table_args__ = (
        UniqueConstraint(
            "workspace_id", "name", "version_number", name="uq_prompt_versions_name_version"
        ),
        {"comment": "Append-only prompt version history (TSD §4.18-4.19)."},
    )

    def __repr__(self) -> str:
        return f"<PromptVersion id={self.id} name={self.name!r} v={self.version_number}>"
