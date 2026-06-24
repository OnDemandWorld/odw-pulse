"""GenerationCache — deterministic cache of LLM prompt/response pairs.

The cache is *not* workspace-scoped; it stores globally useful
prompt→response mappings keyed by a content hash.  TTL-based eviction
is expressed via ``expires_at``.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Index, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from pulse.db.base import Base


class GenerationCache(Base):
    """Keyed by SHA-256 of the normalised prompt."""

    __tablename__ = "generation_cache"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    hash: Mapped[str] = mapped_column(
        "hash", Text, nullable=False, comment="Hex-encoded SHA-256 of the normalised prompt."
    )
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    response: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata", JSONB, nullable=True, default=dict
    )
    provider: Mapped[str | None] = mapped_column(Text, nullable=True)
    model: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="TTL-based expiration; rows are reaped by a background job.",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        Index("ix_generation_cache_hash", "hash"),
        Index("ix_generation_cache_expires_at", "expires_at"),
        {"comment": "Deterministic LLM prompt/response cache."},
    )

    def __repr__(self) -> str:
        return f"<GenerationCache id={self.id} hash={self.hash[:12]}…>"
