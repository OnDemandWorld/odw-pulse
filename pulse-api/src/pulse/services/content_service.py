"""Content management service (TSD §2.1)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from pulse.api.schemas.content import (
    ContentCreate,
    ContentRead,
    ContentUpdate,
    ContentVersionRead,
)
from pulse.models.content import ContentPiece, ContentStatus, ContentVersion


def _content_to_read(content: ContentPiece) -> ContentRead:
    """Convert a ContentPiece ORM object to a ContentRead schema."""
    return ContentRead.model_validate(content, from_attributes=True)


def _version_to_read(version: ContentVersion) -> ContentVersionRead:
    """Convert a ContentVersion ORM object to a ContentVersionRead schema."""
    return ContentVersionRead.model_validate(version, from_attributes=True)


class ContentService:
    """Service for managing content pieces and versions."""

    async def create(
        self,
        db: AsyncSession,
        workspace_id: uuid.UUID,
        data: ContentCreate,
    ) -> ContentPiece:
        """Create a new content piece."""
        # Check if slug already exists in workspace
        result = await db.execute(
            select(ContentPiece).where(
                ContentPiece.workspace_id == workspace_id,
                ContentPiece.slug == data.slug,
            )
        )
        if result.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Content with slug '{data.slug}' already exists in this workspace",
            )

        content = ContentPiece(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            slug=data.slug,
            title=data.title,
            body=data.body,
            metadata_=data.metadata,
            market_code=data.market_code,
            status=ContentStatus.DRAFT,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        db.add(content)
        await db.commit()
        await db.refresh(content)
        return content

    async def get(
        self,
        db: AsyncSession,
        content_id: uuid.UUID,
        workspace_id: uuid.UUID,
    ) -> ContentPiece:
        """Get a content piece by ID."""
        result = await db.execute(
            select(ContentPiece)
            .options(selectinload(ContentPiece.versions))
            .where(
                ContentPiece.id == content_id,
                ContentPiece.workspace_id == workspace_id,
            )
        )
        content = result.scalar_one_or_none()
        if content is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Content not found",
            )
        return content

    async def list_content(
        self,
        db: AsyncSession,
        workspace_id: uuid.UUID,
        status_filter: ContentStatus | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Any], int]:
        """List content pieces with optional status filter and pagination."""
        query = select(ContentPiece).where(ContentPiece.workspace_id == workspace_id)

        if status_filter is not None:
            query = query.where(ContentPiece.status == status_filter)

        # Get total count
        count_query = select(func.count()).select_from(ContentPiece).where(
            ContentPiece.workspace_id == workspace_id
        )
        if status_filter is not None:
            count_query = count_query.where(ContentPiece.status == status_filter)
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        # Apply pagination
        query = query.order_by(ContentPiece.created_at.desc()).limit(limit).offset(offset)
        result = await db.execute(query)
        items = list(result.scalars().all())

        return items, total

    async def update(
        self,
        db: AsyncSession,
        content_id: uuid.UUID,
        workspace_id: uuid.UUID,
        data: ContentUpdate,
    ) -> ContentPiece:
        """Update a content piece."""
        content = await self.get(db, content_id, workspace_id)

        # Only allow updates if status is draft or rejected
        if content.status not in (ContentStatus.DRAFT, ContentStatus.REJECTED):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot update content in '{content.status.value}' status",
            )

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if field == "metadata":
                content.metadata_ = value
            else:
                setattr(content, field, value)

        content.updated_at = datetime.now(UTC)
        await db.commit()
        await db.refresh(content)
        return content

    async def delete(
        self,
        db: AsyncSession,
        content_id: uuid.UUID,
        workspace_id: uuid.UUID,
    ) -> None:
        """Soft delete a content piece by archiving it."""
        content = await self.get(db, content_id, workspace_id)
        content.status = ContentStatus.ARCHIVED
        content.updated_at = datetime.now(UTC)
        await db.commit()

    async def update_status(
        self,
        db: AsyncSession,
        content_id: uuid.UUID,
        workspace_id: uuid.UUID,
        new_status: ContentStatus,
    ) -> ContentPiece:
        """Update the status of a content piece."""
        content = await self.get(db, content_id, workspace_id)
        content.status = new_status
        content.updated_at = datetime.now(UTC)
        await db.commit()
        await db.refresh(content)
        return content

    async def create_version(
        self,
        db: AsyncSession,
        content_id: uuid.UUID,
        workspace_id: uuid.UUID,
        body: str | None = None,
        change_note: str | None = None,
        created_by: uuid.UUID | None = None,
    ) -> ContentVersion:
        """Create a new version snapshot of the content."""
        content = await self.get(db, content_id, workspace_id)

        # Determine next version number
        result = await db.execute(
            select(func.max(ContentVersion.version_number)).where(
                ContentVersion.content_piece_id == content_id
            )
        )
        max_version = result.scalar() or 0
        next_version = max_version + 1

        # Update content body if provided
        if body is not None:
            content.body = body
            content.updated_at = datetime.now(UTC)

        # Create version snapshot
        version = ContentVersion(
            id=uuid.uuid4(),
            content_piece_id=content_id,
            version_number=next_version,
            body=content.body,
            metadata_=content.metadata_,
            status=content.status,
            change_note=change_note,
            created_by=created_by,
            created_at=datetime.now(UTC),
        )
        db.add(version)
        await db.commit()
        await db.refresh(version)
        return version

    async def list_versions(
        self,
        db: AsyncSession,
        content_id: uuid.UUID,
        workspace_id: uuid.UUID,
    ) -> list[ContentVersion]:
        """List all versions of a content piece."""
        # Verify content exists and belongs to workspace
        await self.get(db, content_id, workspace_id)

        result = await db.execute(
            select(ContentVersion)
            .where(ContentVersion.content_piece_id == content_id)
            .order_by(ContentVersion.version_number.desc())
        )
        return list(result.scalars().all())

    async def export(
        self,
        db: AsyncSession,
        content_id: uuid.UUID,
        workspace_id: uuid.UUID,
        format: str = "markdown",
    ) -> str | dict[str, Any]:
        """Export content in the specified format (markdown, html, json)."""
        content = await self.get(db, content_id, workspace_id)

        if format == "markdown":
            return self._export_markdown(content)
        if format == "html":
            return self._export_html(content)
        if format == "json":
            return self._export_json(content)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported export format: {format}",
        )

    def _export_markdown(self, content: ContentPiece) -> str:
        """Export content as Markdown with YAML frontmatter."""
        lines = [
            "---",
            f"title: {content.title}",
            f"slug: {content.slug}",
            f"status: {content.status.value}",
            f"market_code: {content.market_code or 'none'}",
            f"created_at: {content.created_at.isoformat()}",
            f"updated_at: {content.updated_at.isoformat()}",
            "---",
            "",
            f"# {content.title}",
            "",
            content.body or "",
        ]
        return "\n".join(lines)

    def _export_html(self, content: ContentPiece) -> str:
        """Export content as HTML."""
        body_escaped = (
            (content.body or "")
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
        return (
            "<!DOCTYPE html>\n"
            "<html>\n"
            "<head>\n"
            f"  <title>{content.title}</title>\n"
            f"  <meta name=\"slug\" content=\"{content.slug}\">\n"
            f"  <meta name=\"status\" content=\"{content.status.value}\">\n"
            "</head>\n"
            "<body>\n"
            f"  <h1>{content.title}</h1>\n"
            f"  <div>{body_escaped}</div>\n"
            "</body>\n"
            "</html>"
        )

    def _export_json(self, content: ContentPiece) -> dict[str, Any]:
        """Export content as JSON-serializable dict."""
        return {
            "id": str(content.id),
            "workspace_id": str(content.workspace_id),
            "slug": content.slug,
            "title": content.title,
            "body": content.body,
            "metadata": content.metadata_,
            "status": content.status.value,
            "market_code": content.market_code,
            "created_at": content.created_at.isoformat(),
            "updated_at": content.updated_at.isoformat(),
        }
