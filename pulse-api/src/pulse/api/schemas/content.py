"""Content management schemas (TSD §2.1, §2.6)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

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

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    slug: str
    title: str
    body: str | None
    metadata: dict[str, Any] | None = Field(None, validation_alias="metadata_")
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

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    content_piece_id: uuid.UUID
    version_number: int
    body: str | None
    metadata: dict[str, Any] | None = Field(None, validation_alias="metadata_")
    status: ContentStatus
    change_note: str | None
    created_at: datetime
    created_by: uuid.UUID | None


class AnnotationCreate(BaseModel):
    """Schema for creating a review annotation."""

    # Audit finding #94: workflow-transition actions (approved/submitted/…)
    # must not be injectable via annotations — they spoof the approval chain.
    action: Literal["annotated", "commented"] = Field(
        default="annotated", description="Annotation action (annotated or commented)"
    )
    comment: str = Field(..., description="Annotation comment")
    metadata: dict[str, Any] | None = Field(None, description="Additional metadata")


class VersionCreate(BaseModel):
    """Request body for POST /content/{id}/versions (audit finding #93).

    Previously body/change_note bound from the query string, silently
    ignoring the natural JSON payload.
    """

    body: str | None = Field(None, description="Optional new content body")
    change_note: str | None = Field(None, description="Optional change note")
