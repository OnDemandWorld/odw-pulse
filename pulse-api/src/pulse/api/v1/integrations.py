"""Webhook configuration endpoints (TSD §2.14).

* ``POST   /webhooks``          — register a webhook config
* ``GET    /webhooks``          — list webhook configs for the workspace
* ``DELETE /webhooks/{id}``     — delete a webhook config
* ``POST   /webhooks/{id}/test`` — fire a test event at the subscriber
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pulse.api.deps import CurrentUser, get_db
from pulse.integrations.webhooks.dispatcher import WebhookDispatcher
from pulse.models.webhook_config import WebhookConfig

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class WebhookCreate(BaseModel):
    """Body for ``POST /webhooks``."""

    url: str = Field(..., description="Subscriber URL that will receive events.")
    events: list[str] = Field(
        default_factory=list,
        description="Event types to subscribe to (empty = all events).",
    )
    signing_secret: str = Field(
        ...,
        min_length=8,
        description="Shared secret used to HMAC-sign outgoing payloads.",
    )
    is_active: bool = True


class WebhookRead(BaseModel):
    """Public representation of a webhook config."""

    id: uuid.UUID
    workspace_id: uuid.UUID
    url: str
    events: list[str]
    is_active: bool
    created_at: str  # ISO-8601 string — avoids datetime serialiser hassle

    model_config = {"from_attributes": True}


class WebhookTestResult(BaseModel):
    """Result of a test dispatch."""

    status_code: int
    ok: bool


# ---------------------------------------------------------------------------
# POST /webhooks
# ---------------------------------------------------------------------------


@router.post("", response_model=WebhookRead, status_code=status.HTTP_201_CREATED)
async def create_webhook(
    data: WebhookCreate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> WebhookRead:
    """Register a new webhook config for the authenticated workspace."""
    config = WebhookConfig(
        workspace_id=current_user.workspace_id,
        url=data.url,
        events=data.events,
        signing_secret=data.signing_secret,
        is_active=data.is_active,
    )
    db.add(config)
    await db.commit()
    await db.refresh(config)
    return _to_read(config)


# ---------------------------------------------------------------------------
# GET /webhooks
# ---------------------------------------------------------------------------


@router.get("", response_model=list[WebhookRead])
async def list_webhooks(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> list[WebhookRead]:
    """List all webhook configs for the authenticated workspace."""
    result = await db.execute(
        select(WebhookConfig).where(
            WebhookConfig.workspace_id == current_user.workspace_id,
        )
    )
    rows = result.scalars().all()
    return [_to_read(c) for c in rows]


# ---------------------------------------------------------------------------
# DELETE /webhooks/{id}
# ---------------------------------------------------------------------------


@router.delete("/{webhook_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_webhook(
    webhook_id: uuid.UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a webhook config.  Must belong to the caller's workspace."""
    config = await _get_config_or_404(db, webhook_id, current_user.workspace_id)
    await db.delete(config)
    await db.commit()


# ---------------------------------------------------------------------------
# POST /webhooks/{id}/test
# ---------------------------------------------------------------------------


@router.post("/{webhook_id}/test", response_model=WebhookTestResult)
async def test_webhook(
    webhook_id: uuid.UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> WebhookTestResult:
    """Fire a synthetic ``webhook.test`` event at the subscriber."""
    config = await _get_config_or_404(db, webhook_id, current_user.workspace_id)

    dispatcher = WebhookDispatcher()
    try:
        response = await dispatcher.dispatch(
            event_type="webhook.test",
            payload={"message": "This is a test event from Pulse."},
            webhook_config=config,
        )
        return WebhookTestResult(status_code=response.status_code, ok=True)
    except Exception as exc:  # noqa: BLE001
        # Surface a best-effort result rather than a 500.
        status_code = getattr(getattr(exc, "response", None), "status_code", 0)
        return WebhookTestResult(status_code=status_code, ok=False)
    finally:
        await dispatcher.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_config_or_404(
    db: AsyncSession,
    webhook_id: uuid.UUID,
    workspace_id: uuid.UUID,
) -> WebhookConfig:
    result = await db.execute(
        select(WebhookConfig).where(
            WebhookConfig.id == webhook_id,
            WebhookConfig.workspace_id == workspace_id,
        )
    )
    config = result.scalar_one_or_none()
    if config is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found")
    return config


def _to_read(config: WebhookConfig) -> WebhookRead:
    return WebhookRead(
        id=config.id,
        workspace_id=config.workspace_id,
        url=config.url,
        events=list(config.events),
        is_active=config.is_active,
        created_at=config.created_at.isoformat() if config.created_at else "",
    )
