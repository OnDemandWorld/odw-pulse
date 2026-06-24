"""Content management and review workflow endpoints (TSD §2.1, §2.6).

* ``GET    /content``                      — list content pieces
* ``POST   /content``                      — create content piece
* ``GET    /content/{id}``                 — get content piece
* ``PUT    /content/{id}``                 — update content piece
* ``DELETE /content/{id}``                 — soft delete (archive)
* ``POST   /content/{id}/submit``          — submit for review
* ``POST   /content/{id}/approve``         — approve
* ``POST   /content/{id}/reject``          — reject
* ``POST   /content/{id}/request-changes`` — request changes
* ``POST   /content/{id}/annotations``     — add annotation
* ``GET    /content/{id}/versions``        — list versions
* ``POST   /content/{id}/versions``        — create version
* ``GET    /content/{id}/export``          — export content
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from pulse.api.deps import CurrentUser, get_db
from pulse.api.schemas.content import (
    AnnotationCreate,
    ContentCreate,
    ContentList,
    ContentRead,
    ContentStatus,
    ContentUpdate,
    ContentVersionRead,
)
from pulse.api.schemas.review import (
    ApprovalChainRead,
    ApprovalStepRead,
    ReviewActionRequest,
    ReviewRead,
)
from pulse.services.content_service import ContentService, _content_to_read, _version_to_read
from pulse.services.review_service import ReviewService

router = APIRouter(prefix="/content", tags=["content"])

content_service = ContentService()
review_service = ReviewService()


# ---------------------------------------------------------------------------
# GET /content
# ---------------------------------------------------------------------------


@router.get("", response_model=ContentList)
async def list_content(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    status_filter: ContentStatus | None = Query(None, alias="status"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> ContentList:
    """List content pieces with optional status filter and pagination."""
    items, total = await content_service.list_content(
        db=db,
        workspace_id=current_user.workspace_id,
        status_filter=status_filter,
        limit=limit,
        offset=offset,
    )
    return ContentList(
        items=[_content_to_read(item) for item in items],
        total=total,
    )


# ---------------------------------------------------------------------------
# POST /content
# ---------------------------------------------------------------------------


@router.post("", response_model=ContentRead, status_code=status.HTTP_201_CREATED)
async def create_content(
    data: ContentCreate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> ContentRead:
    """Create a new content piece."""
    content = await content_service.create(
        db=db,
        workspace_id=current_user.workspace_id,
        data=data,
    )
    return _content_to_read(content)


# ---------------------------------------------------------------------------
# GET /content/{id}
# ---------------------------------------------------------------------------


@router.get("/{content_id}", response_model=ContentRead)
async def get_content(
    content_id: uuid.UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> ContentRead:
    """Get a content piece by ID."""
    content = await content_service.get(
        db=db,
        content_id=content_id,
        workspace_id=current_user.workspace_id,
    )
    return _content_to_read(content)


# ---------------------------------------------------------------------------
# PUT /content/{id}
# ---------------------------------------------------------------------------


@router.put("/{content_id}", response_model=ContentRead)
async def update_content(
    content_id: uuid.UUID,
    data: ContentUpdate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> ContentRead:
    """Update a content piece."""
    content = await content_service.update(
        db=db,
        content_id=content_id,
        workspace_id=current_user.workspace_id,
        data=data,
    )
    return _content_to_read(content)


# ---------------------------------------------------------------------------
# DELETE /content/{id}
# ---------------------------------------------------------------------------


@router.delete("/{content_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_content(
    content_id: uuid.UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Soft delete (archive) a content piece."""
    await content_service.delete(
        db=db,
        content_id=content_id,
        workspace_id=current_user.workspace_id,
    )


# ---------------------------------------------------------------------------
# POST /content/{id}/submit
# ---------------------------------------------------------------------------


@router.post("/{content_id}/submit", response_model=ContentRead)
async def submit_for_review(
    content_id: uuid.UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> ContentRead:
    """Submit content for review."""
    content = await review_service.submit_for_review(
        db=db,
        content_id=content_id,
        workspace_id=current_user.workspace_id,
    )
    return _content_to_read(content)


# ---------------------------------------------------------------------------
# POST /content/{id}/approve
# ---------------------------------------------------------------------------


@router.post("/{content_id}/approve", response_model=ContentRead)
async def approve_content(
    content_id: uuid.UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> ContentRead:
    """Approve content."""
    content = await review_service.approve(
        db=db,
        content_id=content_id,
        workspace_id=current_user.workspace_id,
        user_id=current_user.user_id,
    )
    return _content_to_read(content)


# ---------------------------------------------------------------------------
# POST /content/{id}/reject
# ---------------------------------------------------------------------------


@router.post("/{content_id}/reject", response_model=ContentRead)
async def reject_content(
    content_id: uuid.UUID,
    body: ReviewActionRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> ContentRead:
    """Reject content."""
    content = await review_service.reject(
        db=db,
        content_id=content_id,
        workspace_id=current_user.workspace_id,
        user_id=current_user.user_id,
        reason=body.reason,
    )
    return _content_to_read(content)


# ---------------------------------------------------------------------------
# POST /content/{id}/request-changes
# ---------------------------------------------------------------------------


@router.post("/{content_id}/request-changes", response_model=ContentRead)
async def request_changes(
    content_id: uuid.UUID,
    body: ReviewActionRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> ContentRead:
    """Request changes to content."""
    content = await review_service.request_changes(
        db=db,
        content_id=content_id,
        workspace_id=current_user.workspace_id,
        user_id=current_user.user_id,
        feedback=body.feedback,
    )
    return _content_to_read(content)


# ---------------------------------------------------------------------------
# POST /content/{id}/annotations
# ---------------------------------------------------------------------------


@router.post(
    "/{content_id}/annotations",
    response_model=ReviewRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_annotation(
    content_id: uuid.UUID,
    data: AnnotationCreate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> ReviewRead:
    """Add an annotation to content."""
    annotation = await review_service.add_annotation(
        db=db,
        content_id=content_id,
        workspace_id=current_user.workspace_id,
        user_id=current_user.user_id,
        annotation_data=data,
    )
    return ReviewRead.model_validate(annotation, from_attributes=True)


# ---------------------------------------------------------------------------
# GET /content/{id}/versions
# ---------------------------------------------------------------------------


@router.get("/{content_id}/versions", response_model=list[ContentVersionRead])
async def list_versions(
    content_id: uuid.UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> list[ContentVersionRead]:
    """List all versions of a content piece."""
    versions = await content_service.list_versions(
        db=db,
        content_id=content_id,
        workspace_id=current_user.workspace_id,
    )
    return [_version_to_read(v) for v in versions]


# ---------------------------------------------------------------------------
# POST /content/{id}/versions
# ---------------------------------------------------------------------------


@router.post(
    "/{content_id}/versions",
    response_model=ContentVersionRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_version(
    content_id: uuid.UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    body: str | None = None,
    change_note: str | None = None,
) -> ContentVersionRead:
    """Create a new version snapshot of the content."""
    version = await content_service.create_version(
        db=db,
        content_id=content_id,
        workspace_id=current_user.workspace_id,
        body=body,
        change_note=change_note,
        created_by=current_user.user_id,
    )
    return _version_to_read(version)


# ---------------------------------------------------------------------------
# GET /content/{id}/export
# ---------------------------------------------------------------------------


@router.get("/{content_id}/export", response_model=None)
async def export_content(
    content_id: uuid.UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    format: str = Query("markdown", pattern="^(markdown|html|json)$"),
) -> PlainTextResponse | JSONResponse:
    """Export content in the specified format (markdown, html, json)."""
    result = await content_service.export(
        db=db,
        content_id=content_id,
        workspace_id=current_user.workspace_id,
        format=format,
    )

    if format == "markdown":
        return PlainTextResponse(
            content=result,
            media_type="text/markdown",
            headers={"Content-Disposition": f"attachment; filename={content_id}.md"},
        )
    elif format == "html":
        return PlainTextResponse(
            content=result,
            media_type="text/html",
            headers={"Content-Disposition": f"attachment; filename={content_id}.html"},
        )
    else:  # json
        return JSONResponse(content=result)


# ---------------------------------------------------------------------------
# GET /content/{id}/approval-chain (bonus endpoint)
# ---------------------------------------------------------------------------


@router.get("/{content_id}/approval-chain", response_model=ApprovalChainRead)
async def get_approval_chain(
    content_id: uuid.UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> ApprovalChainRead:
    """Get the approval chain for a content piece."""
    content = await content_service.get(
        db=db,
        content_id=content_id,
        workspace_id=current_user.workspace_id,
    )
    annotations = await review_service.get_review_annotations(
        db=db,
        content_id=content_id,
        workspace_id=current_user.workspace_id,
    )

    steps = [
        ApprovalStepRead(
            user_id=ann.user_id,
            action=ann.action,
            comment=ann.comment,
            created_at=ann.created_at,
        )
        for ann in annotations
    ]

    return ApprovalChainRead(
        steps=steps,
        current_status=ContentStatus(content.status),
    )
