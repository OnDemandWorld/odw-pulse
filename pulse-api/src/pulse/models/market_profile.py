"""MarketProfile — ISO-639-1 language + optional region descriptor.

Market profiles live at the *system* level (not per-workspace) so they
can be shared; workspaces reference them via ``market_code`` on
``content_pieces``.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import Boolean, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from pulse.db.base import Base


class MarketProfile(Base):
    """A locale / market: a language code (ISO 639-1) + optional region.

    ``cultural_dimensions`` holds Hofstede-style or custom attributes
    that guides content localisation.  ``fallback_code`` points at
    another market profile used when generation for this market fails.
    """

    __tablename__ = "market_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    code: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="ISO 639-1 language code optionally suffixed with a region, e.g. 'en-US'.",
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    cultural_dimensions: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True, default=dict
    )
    fallback_code: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Market code to fall back to when generation for this market fails.",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )

    __table_args__ = (
        UniqueConstraint("code", name="uq_market_profiles_code"),
        {"comment": "Language / region profile for content localisation."},
    )

    def __repr__(self) -> str:
        return f"<MarketProfile id={self.id} code={self.code!r}>"
