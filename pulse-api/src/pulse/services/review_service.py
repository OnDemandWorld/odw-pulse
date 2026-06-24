"""Review workflow service (TSD §2.6)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pulse.api.schemas.content import AnnotationCreate, ReviewAction
from pulse.models.content import ContentPiece, ContentStatus, ReviewAnnotation
from pulse.services.content_service import ContentService


class ReviewService:
    """Service for managing the review workflow."""

    def __init__(self) -> None:
        """Initialize the review service."""
        self.content_service = ContentService()

    async def submit_for_review(
        self,
        db: AsyncSession,
        content_id: uuid.UUID,
        workspace_id: uuid.UUID,
    ) -> ContentPiece:
        """Submit content for review."""
        content = await self.content_service.get(db, content_id, workspace_id)

        # Only draft or rejected content can be submitted
        if content.status not in (ContentStatus.DRAFT, ContentStatus.REJECTED):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot submit content in '{content.status.value}' status for review",
            )

        content.status = ContentStatus.REVIEW
        content.updated_at = datetime.now(UTC)

        # Create annotation for the submission
        annotation = ReviewAnnotation(
            id=uuid.uuid4(),
            content_piece_id=content_id,
            action=ReviewAction.SUBMITTED,
            comment="Content submitted for review",
            created_at=datetime.now(UTC),
        )
        db.add(annotation)
        await db.commit()
        await db.refresh(content)
        return content

    async def approve(
        self,
        db: AsyncSession,
        content_id: uuid.UUID,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> ContentPiece:
        """Approve content."""
        content = await self.content_service.get(db, content_id, workspace_id)

        # Only content in review can be approved
        if content.status != ContentStatus.REVIEW:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot approve content in '{content.status.value}' status",
            )

        content.status = ContentStatus.APPROVED
        content.updated_at = datetime.now(UTC)

        # Create annotation for the approval
        annotation = ReviewAnnotation(
            id=uuid.uuid4(),
            content_piece_id=content_id,
            user_id=user_id,
            action=ReviewAction.APPROVED,
            comment="Content approved",
            created_at=datetime.now(UTC),
        )
        db.add(annotation)
        await db.commit()
        await db.refresh(content)
        return content

    async def reject(
        self,
        db: AsyncSession,
        content_id: uuid.UUID,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        reason: str | None = None,
    ) -> ContentPiece:
        """Reject content."""
        content = await self.content_service.get(db, content_id, workspace_id)

        # Only content in review can be rejected
        if content.status != ContentStatus.REVIEW:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot reject content in '{content.status.value}' status",
            )

        content.status = ContentStatus.REJECTED
        content.updated_at = datetime.now(UTC)

        # Create annotation for the rejection
        annotation = ReviewAnnotation(
            id=uuid.uuid4(),
            content_piece_id=content_id,
            user_id=user_id,
            action=ReviewAction.REJECTED,
            comment=reason or "Content rejected",
            created_at=datetime.now(UTC),
        )
        db.add(annotation)
        await db.commit()
        await db.refresh(content)
        return content

    async def request_changes(
        self,
        db: AsyncSession,
        content_id: uuid.UUID,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        feedback: str | None = None,
    ) -> ContentPiece:
        """Request changes to content."""
        content = await self.content_service.get(db, content_id, workspace_id)

        # Only content in review can have changes requested
        if content.status != ContentStatus.REVIEW:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot request changes for content in '{content.status.value}' status",
            )

        # Return to draft status for editing
        content.status = ContentStatus.DRAFT
        content.updated_at = datetime.now(UTC)

        # Create annotation for the changes request
        annotation = ReviewAnnotation(
            id=uuid.uuid4(),
            content_piece_id=content_id,
            user_id=user_id,
            action=ReviewAction.CHANGES_REQUESTED,
            comment=feedback or "Changes requested",
            created_at=datetime.now(UTC),
        )
        db.add(annotation)
        await db.commit()
        await db.refresh(content)
        return content

    async def add_annotation(
        self,
        db: AsyncSession,
        content_id: uuid.UUID,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        annotation_data: AnnotationCreate,
    ) -> ReviewAnnotation:
        """Add an annotation to content."""
        # Verify content exists and belongs to workspace
        await self.content_service.get(db, content_id, workspace_id)

        annotation = ReviewAnnotation(
            id=uuid.uuid4(),
            content_piece_id=content_id,
            user_id=user_id,
            action=annotation_data.action,
            comment=annotation_data.comment,
            metadata_=annotation_data.metadata,
            created_at=datetime.now(UTC),
        )
        db.add(annotation)
        await db.commit()
        await db.refresh(annotation)
        return annotation

    async def get_review_annotations(
        self,
        db: AsyncSession,
        content_id: uuid.UUID,
        workspace_id: uuid.UUID,
    ) -> list[ReviewAnnotation]:
        """Get all review annotations for a content piece."""
        # Verify content exists and belongs to workspace
        await self.content_service.get(db, content_id, workspace_id)

        result = await db.execute(
            select(ReviewAnnotation)
            .where(ReviewAnnotation.content_piece_id == content_id)
            .order_by(ReviewAnnotation.created_at.asc())
        )
        return list(result.scalars().all())
