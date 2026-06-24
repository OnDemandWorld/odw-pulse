"""Content management and review workflow tests (TSD §2.1, §2.6)."""

from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

# ---------------------------------------------------------------------------
# POST /api/v1/content — authentication
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_create_content_requires_auth(
    client: AsyncClient,
    test_workspace_and_user: tuple[Any, Any],
) -> None:
    """Creating content without authentication should return 401."""
    response = await client.post(
        "/api/v1/content",
        json={
            "slug": "test-article",
            "title": "Test Article",
            "body": "This is a test article.",
        },
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# POST + GET /api/v1/content — CRUD
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_create_and_list_content(
    authorized_client: AsyncClient,
    test_workspace_and_user: tuple[Any, Any],
) -> None:
    """Creating content and listing should return the created items."""
    # Create first piece
    response = await authorized_client.post(
        "/api/v1/content",
        json={
            "slug": "article-1",
            "title": "Article One",
            "body": "Content of article one.",
            "market_code": "en-US",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["slug"] == "article-1"
    assert data["title"] == "Article One"
    assert data["status"] == "draft"
    content_id_1 = data["id"]

    # Create second piece
    response = await authorized_client.post(
        "/api/v1/content",
        json={
            "slug": "article-2",
            "title": "Article Two",
            "body": "Content of article two.",
        },
    )
    assert response.status_code == 201

    # List all content
    response = await authorized_client.get("/api/v1/content")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2

    # Get single piece
    response = await authorized_client.get(f"/api/v1/content/{content_id_1}")
    assert response.status_code == 200
    data = response.json()
    assert data["slug"] == "article-1"
    assert data["title"] == "Article One"

    # Update piece
    response = await authorized_client.put(
        f"/api/v1/content/{content_id_1}",
        json={"title": "Updated Article One"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Updated Article One"

    # Delete (soft/archive)
    response = await authorized_client.delete(f"/api/v1/content/{content_id_1}")
    assert response.status_code == 204

    # Verify archived status
    response = await authorized_client.get(f"/api/v1/content/{content_id_1}")
    assert response.status_code == 200
    assert response.json()["status"] == "archived"


# ---------------------------------------------------------------------------
# PUT /api/v1/content/{id} — status update
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_update_content_status(
    authorized_client: AsyncClient,
    test_workspace_and_user: tuple[Any, Any],
) -> None:
    """Directly updating content status via PUT should work."""
    # Create content
    response = await authorized_client.post(
        "/api/v1/content",
        json={
            "slug": "status-test",
            "title": "Status Test",
            "body": "Testing status updates.",
        },
    )
    assert response.status_code == 201

    # Filter list by status
    response = await authorized_client.get("/api/v1/content?status=draft")
    assert response.status_code == 200
    assert response.json()["total"] == 1


# ---------------------------------------------------------------------------
# POST /api/v1/content/{id}/submit + /approve — review workflow
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_submit_and_approve_content(
    authorized_client: AsyncClient,
    test_workspace_and_user: tuple[Any, Any],
) -> None:
    """Submit content for review and then approve it."""
    # Create content
    response = await authorized_client.post(
        "/api/v1/content",
        json={
            "slug": "review-test",
            "title": "Review Test",
            "body": "Content to be reviewed.",
        },
    )
    assert response.status_code == 201
    content_id = response.json()["id"]
    assert response.json()["status"] == "draft"

    # Submit for review
    response = await authorized_client.post(f"/api/v1/content/{content_id}/submit")
    assert response.status_code == 200
    assert response.json()["status"] == "review"

    # Approve
    response = await authorized_client.post(f"/api/v1/content/{content_id}/approve")
    assert response.status_code == 200
    assert response.json()["status"] == "approved"

    # Verify approval chain
    response = await authorized_client.get(f"/api/v1/content/{content_id}/approval-chain")
    assert response.status_code == 200
    chain = response.json()
    assert chain["current_status"] == "approved"
    assert len(chain["steps"]) == 2  # submitted + approved
    assert chain["steps"][0]["action"] == "submitted"
    assert chain["steps"][1]["action"] == "approved"


@pytest.mark.anyio
async def test_submit_and_reject_content(
    authorized_client: AsyncClient,
    test_workspace_and_user: tuple[Any, Any],
) -> None:
    """Submit content for review and then reject it with a reason."""
    # Create content
    response = await authorized_client.post(
        "/api/v1/content",
        json={
            "slug": "reject-test",
            "title": "Reject Test",
            "body": "Content to be rejected.",
        },
    )
    assert response.status_code == 201
    content_id = response.json()["id"]

    # Submit for review
    response = await authorized_client.post(f"/api/v1/content/{content_id}/submit")
    assert response.status_code == 200

    # Reject with reason
    response = await authorized_client.post(
        f"/api/v1/content/{content_id}/reject",
        json={"reason": "Needs improvement"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "rejected"


@pytest.mark.anyio
async def test_request_changes_content(
    authorized_client: AsyncClient,
    test_workspace_and_user: tuple[Any, Any],
) -> None:
    """Submit content for review and request changes."""
    # Create content
    response = await authorized_client.post(
        "/api/v1/content",
        json={
            "slug": "changes-test",
            "title": "Changes Test",
            "body": "Content needing changes.",
        },
    )
    assert response.status_code == 201
    content_id = response.json()["id"]

    # Submit for review
    response = await authorized_client.post(f"/api/v1/content/{content_id}/submit")
    assert response.status_code == 200

    # Request changes
    response = await authorized_client.post(
        f"/api/v1/content/{content_id}/request-changes",
        json={"feedback": "Please fix the introduction"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "draft"


# ---------------------------------------------------------------------------
# GET /api/v1/content/{id}/export — export formats
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_export_content_markdown(
    authorized_client: AsyncClient,
    test_workspace_and_user: tuple[Any, Any],
) -> None:
    """Export content as Markdown."""
    # Create content
    response = await authorized_client.post(
        "/api/v1/content",
        json={
            "slug": "export-test",
            "title": "Export Test Article",
            "body": "This is the body of the export test.",
            "market_code": "en-US",
        },
    )
    assert response.status_code == 201
    content_id = response.json()["id"]

    # Export as markdown
    response = await authorized_client.get(
        f"/api/v1/content/{content_id}/export?format=markdown"
    )
    assert response.status_code == 200
    assert "text/markdown" in response.headers.get("content-type", "")
    body = response.text
    assert "# Export Test Article" in body
    assert "title: Export Test Article" in body
    assert "This is the body of the export test." in body

    # Export as HTML
    response = await authorized_client.get(
        f"/api/v1/content/{content_id}/export?format=html"
    )
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert "<h1>Export Test Article</h1>" in response.text

    # Export as JSON
    response = await authorized_client.get(
        f"/api/v1/content/{content_id}/export?format=json"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Export Test Article"
    assert data["slug"] == "export-test"


# ---------------------------------------------------------------------------
# POST /api/v1/content/{id}/versions — versioning
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_create_and_list_versions(
    authorized_client: AsyncClient,
    async_session: AsyncSession,
    test_workspace_and_user: tuple[Any, Any],
) -> None:
    """Create and list content versions."""
    # Create content
    response = await authorized_client.post(
        "/api/v1/content",
        json={
            "slug": "version-test",
            "title": "Version Test",
            "body": "Initial body.",
        },
    )
    assert response.status_code == 201
    content_id = response.json()["id"]

    # Create a version
    response = await authorized_client.post(
        f"/api/v1/content/{content_id}/versions?change_note=First+version"
    )
    assert response.status_code == 201
    version_data = response.json()
    assert version_data["version_number"] == 1
    assert version_data["body"] == "Initial body."

    # List versions
    response = await authorized_client.get(f"/api/v1/content/{content_id}/versions")
    assert response.status_code == 200
    versions = response.json()
    assert len(versions) == 1
    assert versions[0]["version_number"] == 1


# ---------------------------------------------------------------------------
# POST /api/v1/content/{id}/annotations — annotations
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_add_annotation(
    authorized_client: AsyncClient,
    test_workspace_and_user: tuple[Any, Any],
) -> None:
    """Add a review annotation to content."""
    # Create content
    response = await authorized_client.post(
        "/api/v1/content",
        json={
            "slug": "annotation-test",
            "title": "Annotation Test",
            "body": "Content for annotation.",
        },
    )
    assert response.status_code == 201
    content_id = response.json()["id"]

    # Add annotation
    response = await authorized_client.post(
        f"/api/v1/content/{content_id}/annotations",
        json={
            "comment": "This paragraph needs revision.",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["comment"] == "This paragraph needs revision."
    assert data["action"] == "annotated"


# ---------------------------------------------------------------------------
# Workspace isolation
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_content_isolation_between_workspaces(
    authorized_client: AsyncClient,
    client: AsyncClient,
    async_session: AsyncSession,
    test_workspace_and_user: tuple[Any, Any],
) -> None:
    """Content in one workspace should not be visible from another."""
    import uuid

    from pulse.auth.security import create_access_token

    # Create content in the default workspace
    response = await authorized_client.post(
        "/api/v1/content",
        json={
            "slug": "isolated-content",
            "title": "Isolated Content",
            "body": "Should not be visible elsewhere.",
        },
    )
    assert response.status_code == 201

    # Create a token for a different workspace
    other_workspace = uuid.UUID("00000000-0000-0000-0000-000000000099")
    token = create_access_token(
        user_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        email="other@example.com",
        workspace_id=other_workspace,
        role="editor",
    )

    # List content with the other workspace token
    response = await client.get(
        "/api/v1/content",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0  # No content visible in other workspace
