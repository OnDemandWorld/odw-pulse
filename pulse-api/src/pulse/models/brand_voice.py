"""BrandVoice model — per-workspace brand / tone configuration."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pulse.db.base import Base


class BrandVoice(Base):
    """Captures the brand's tone, vocabulary and editorial rules.

    Used by generation prompts to keep output on-brand.
    """

    __tablename__ = "brand_voices"

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
    tone_profile: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True, default=dict)
    guidelines: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True, default=dict)

    workspace: Mapped[object] = relationship(
        "Workspace", back_populates="brand_voices", lazy="noload"
    )

    __table_args__ = ({"comment": "Brand voice / tone configuration per workspace."},)

    def __repr__(self) -> str:
        return f"<BrandVoice id={self.id} name={self.name!r}>"
