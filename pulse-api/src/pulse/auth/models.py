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
    """Response model returned by the ``/auth/login`` endpoint."""

    access_token: str
    token_type: str = Field(default="bearer")


class LoginRequest(BaseModel):
    """Request body for the ``/auth/login`` endpoint."""

    username: str
    password: str


class ImpersonateRequest(BaseModel):
    """Request body for the ``/auth/impersonate`` endpoint."""

    target_workspace_id: uuid.UUID
