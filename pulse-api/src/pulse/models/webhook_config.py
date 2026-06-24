"""WebhookConfig — outbound webhook subscriptions per workspace."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pulse.db.base import Base


class WebhookConfig(Base):
    """Configures an outbound webhook: URL, subscribed events, secret."""

    __tablename__ = "webhook_configs"

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
    url: Mapped[str] = mapped_column(Text, nullable=False)
    events: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        nullable=False,
        default=list,
        comment="Event types this webhook is subscribed to.",
    )
    signing_secret: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Shared secret used to HMAC-sign outgoing payloads.",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
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
        "Workspace", back_populates="webhook_configs", lazy="noload"
    )

    __table_args__ = ({"comment": "Outbound webhook subscriptions."},)

    def __repr__(self) -> str:
        return f"<WebhookConfig id={self.id} url={self.url!r} active={self.is_active}>"
