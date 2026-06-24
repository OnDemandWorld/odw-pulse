"""Content management schemas (TSD §2.1, §2.6)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from pulse.models.content import ContentStatus  # Re-export single source of truth

__all__ = [
    "AnnotationCreate",
    "ContentCreate",
    "ContentList",
    "ContentRead",
    "ContentStatus",
    "ContentUpdate",
    "ContentVersionRead",
    "ReviewAction",
]


class ReviewAction(str):
    """Type of review action."""

    SUBMITTED = "submitted"
    APPROVED = "approved"
    REJECTED = "rejected"
    CHANGES_REQUESTED = "changes_requested"
    ANNOTATED = "annotated"


class ContentCreate(BaseModel):
    """Schema for creating a new content piece."""

    slug: str = Field(..., description="URL-friendly identifier (unique per workspace)")
    title: str = Field(..., description="Content title")
    body: str | None = Field(None, description="Content body")
    metadata: dict[str, Any] | None = Field(None, description="Additional metadata")
    market_code: str | None = Field(None, description="Target market code (ISO 639-1 + region)")


class ContentUpdate(BaseModel):
    """Schema for updating an existing content piece."""

    title: str | None = None
    body: str | None = None
    metadata: dict[str, Any] | None = None
    market_code: str | None = None


class ContentRead(BaseModel):
    """Schema for reading a content piece."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    slug: str
    title: str
    body: str | None
    metadata: dict[str, Any] | None = Field(None, alias="metadata_")
    status: ContentStatus
    market_code: str | None
    created_at: datetime
    updated_at: datetime


class ContentList(BaseModel):
    """Schema for a list of content pieces."""

    items: list[ContentRead]
    total: int


class ContentVersionRead(BaseModel):
    """Schema for reading a content version."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    content_piece_id: uuid.UUID
    version_number: int
    body: str | None
    metadata: dict[str, Any] | None = Field(None, alias="metadata_")
    status: ContentStatus
    change_note: str | None
    created_at: datetime
    created_by: uuid.UUID | None


class AnnotationCreate(BaseModel):
    """Schema for creating a review annotation."""

    action: str = Field(default=ReviewAction.ANNOTATED, description="Action type")
    comment: str = Field(..., description="Annotation comment")
    metadata: dict[str, Any] | None = Field(None, description="Additional metadata")
