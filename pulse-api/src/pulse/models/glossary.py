"""Glossary and GlossaryTerm — workspace-owned terminology databases."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pulse.db.base import Base


class Glossary(Base):
    """A named glossary owned by a workspace."""

    __tablename__ = "glossaries"

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
    metadata_: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata", JSONB, nullable=True, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    workspace: Mapped[object] = relationship(
        "Workspace", back_populates="glossaries", lazy="noload"
    )
    terms: Mapped[list[Any]] = relationship(
        "GlossaryTerm",
        back_populates="glossary",
        cascade="all, delete-orphan",
        lazy="noload",
    )

    __table_args__ = (
        UniqueConstraint("workspace_id", "name", name="uq_glossaries_workspace_name"),
        {"comment": "Workspace-owned terminology glossaries."},
    )

    def __repr__(self) -> str:
        return f"<Glossary id={self.id} name={self.name!r}>"


class GlossaryTerm(Base):
    """A single term inside a glossary with optional translations."""

    __tablename__ = "glossary_terms"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    glossary_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("glossaries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    term: Mapped[str] = mapped_column(Text, nullable=False)
    definition: Mapped[str | None] = mapped_column(Text, nullable=True)
    translations: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True, default=dict)
    metadata_: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata", JSONB, nullable=True, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    glossary: Mapped[object] = relationship("Glossary", back_populates="terms", lazy="noload")

    __table_args__ = (
        UniqueConstraint("glossary_id", "term", name="uq_glossary_terms_glossary_term"),
        {"comment": "Terminology entries within a glossary."},
    )

    def __repr__(self) -> str:
        return f"<GlossaryTerm id={self.id} term={self.term!r}>"
