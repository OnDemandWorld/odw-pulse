"""Pydantic models for authentication tokens and user context."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class UserInToken(BaseModel):
    """User identity embedded in a JWT token.

    This is the *decoded* representation; it is not authoritative until
    validated against the database via ``get_current_user``.
    """

    user_id: uuid.UUID
    email: str
    workspace_id: uuid.UUID
    role: str


class TokenPayload(BaseModel):
    """Full JWT payload including standard claims."""

    sub: str
    workspace_id: uuid.UUID
    email: str
    role: str
    exp: datetime
    iat: datetime


class TokenResponse(BaseModel):
    """Response model returned by the ``/auth/login`` and ``/auth/register`` endpoints."""

    access_token: str
    token_type: str = Field(default="bearer")
    workspace_id: uuid.UUID | None = Field(
        default=None, description="Workspace the token is scoped to"
    )
    email: str | None = Field(default=None, description="Authenticated user's email")


class LoginRequest(BaseModel):
    """Request body for the ``/auth/login`` endpoint."""

    username: str = Field(description="Account email address")
    password: str


class RegisterRequest(BaseModel):
    """Request body for the ``/auth/register`` endpoint.

    Creates a new workspace and its owner account in one step.
    """

    workspace_name: str = Field(min_length=1, max_length=100)
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=8, description="At least 8 characters")


class UserCreate(BaseModel):
    """Request body for ``POST /auth/users`` (invite a user to the workspace)."""

    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=8)
    role: str = Field(
        default="viewer", description="One of: owner, admin, editor, viewer"
    )


class UserRead(BaseModel):
    """Public representation of a workspace user."""

    id: uuid.UUID
    email: str
    role: str
    is_active: bool
    created_at: datetime


class ImpersonateRequest(BaseModel):
    """Request body for the ``/auth/impersonate`` endpoint."""

    target_workspace_id: uuid.UUID
