"""Review workflow schemas (TSD §2.6)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from pulse.api.schemas.content import ContentStatus


class ReviewRead(BaseModel):
    """Schema for reading a review annotation."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    content_piece_id: uuid.UUID
    user_id: uuid.UUID | None
    action: str
    comment: str | None
    created_at: datetime


class ReviewActionRequest(BaseModel):
    """Schema for requesting a review action (reject, request changes)."""

    reason: str | None = Field(None, description="Reason for rejection or changes request")
    feedback: str | None = Field(None, description="Feedback for the author")


class ApprovalStepRead(BaseModel):
    """Schema for a single step in the approval chain."""

    user_id: uuid.UUID | None
    action: str
    comment: str | None
    created_at: datetime


class ApprovalChainRead(BaseModel):
    """Schema for the approval chain of a content piece."""

    steps: list[ApprovalStepRead]
    current_status: ContentStatus
