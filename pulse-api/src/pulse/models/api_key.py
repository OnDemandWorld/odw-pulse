"""APIKey — workspace-scoped programmatic access credential."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pulse.db.base import Base


class APIKey(Base):
    """Stored credential for programmatic API access.

    Only the hash of the key is persisted — the plaintext is shown to
    the user exactly once at creation time.
    """

    __tablename__ = "api_keys"

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
    name: Mapped[str] = mapped_column(Text, nullable=False, comment="Human-friendly label.")
    key_hash: Mapped[str] = mapped_column(
        Text, nullable=False, unique=True, comment="SHA-256 hex digest of the API key."
    )
    scopes: Mapped[list[str] | None] = mapped_column(
        ARRAY(Text),
        nullable=True,
        default=list,
        comment="Authorised scope tokens, e.g. ['content:read','content:write'].",
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="NULL means the key never expires.",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    workspace: Mapped[object] = relationship("Workspace", back_populates="api_keys", lazy="noload")

    __table_args__ = ({"comment": "Workspace-scoped API access keys."},)

    def __repr__(self) -> str:
        return f"<APIKey id={self.id} name={self.name!r}>"
