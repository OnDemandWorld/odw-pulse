"""Pulse FastAPI application entry point."""

import asyncio
import logging
import secrets
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from pulse.api import health
from pulse.api.v1 import auth as auth_v1
from pulse.api.v1 import bulk_jobs as bulk_jobs_v1
from pulse.api.v1 import content as content_v1
from pulse.api.v1 import experiments as experiments_v1
from pulse.api.v1 import generate as generate_v1
from pulse.api.v1 import integrations as integrations_v1
from pulse.config import get_settings
from pulse.core.logging import configure_logging
from pulse.db.session import get_initialized_engine
from pulse.middleware.tenant import TenantMiddleware

# Values that must never reach production unchanged.
_DEFAULT_SECRET_KEY = "change-me-in-production"
_DEFAULT_WEBHOOK_SECRET = "whsec_change_me"

logger = logging.getLogger(__name__)


async def _db_ping(engine: Any) -> None:
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))


def create_app() -> FastAPI:
    """Application factory."""
    settings = get_settings()
    configure_logging(settings.pulse_log_level)

    if settings.is_production:
        insecure_defaults = [
            name
            for name, value, default in (
                ("PULSE_SECRET_KEY", settings.pulse_secret_key, _DEFAULT_SECRET_KEY),
                (
                    "WEBHOOK_SIGNING_SECRET",
                    settings.webhook_signing_secret,
                    _DEFAULT_WEBHOOK_SECRET,
                ),
            )
            if value == default
        ]
        if insecure_defaults:
            raise RuntimeError(
                "Refusing to start in production with default secrets: "
                + ", ".join(insecure_defaults)
            )
    else:
        # Audit finding #53: outside production, never sign tokens with the
        # publicly known default key. Replace defaults with ephemeral random
        # secrets (per-process, dev-only) so the shipped dev stack keeps
        # working while token forgery with the committed key is impossible.
        if settings.pulse_secret_key == _DEFAULT_SECRET_KEY:
            settings.pulse_secret_key = secrets.token_urlsafe(32)
            logger.warning(
                "PULSE_SECRET_KEY is the committed default; generated an ephemeral "
                "development key (tokens invalidate on restart). Set a real secret."
            )
        if settings.webhook_signing_secret == _DEFAULT_WEBHOOK_SECRET:
            settings.webhook_signing_secret = "whsec_" + secrets.token_urlsafe(32)
            logger.warning(
                "WEBHOOK_SIGNING_SECRET is the committed default; generated an "
                "ephemeral development secret. Set a real secret."
            )

    app = FastAPI(
        title="Pulse API",
        description="Multilingual content generation and localization module",
        version="0.1.0",
    )

    # Middleware stack: Starlette inserts each add_middleware at position 0,
    # so the LAST added is OUTERMOST (audit finding #100 — the old comment
    # claimed the opposite). CORS must stay outermost so preflight OPTIONS
    # is answered before any tenant enforcement.
    # In development any origin is allowed; ``allow_origin_regex`` echoes the
    # request origin back, which — unlike ``allow_origins=["*"]`` — works
    # with credentialed requests. Production must set explicit origins.
    if settings.is_development:
        cors_kwargs: dict[str, object] = {"allow_origin_regex": r".*"}
    else:
        cors_kwargs = {"allow_origins": []}
    app.add_middleware(TenantMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        **cors_kwargs,  # type: ignore[arg-type]
    )

    # Routes
    app.include_router(health.router, prefix="/api/v1")
    app.include_router(auth_v1.router, prefix="/api/v1")
    app.include_router(generate_v1.router, prefix="/api/v1")
    app.include_router(content_v1.router, prefix="/api/v1")
    app.include_router(bulk_jobs_v1.router, prefix="/api/v1")
    app.include_router(integrations_v1.router, prefix="/api/v1")
    app.include_router(experiments_v1.router, prefix="/api/v1")

    @app.get("/health/live", tags=["health"])
    async def liveness() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready", tags=["health"])
    async def readiness() -> dict[str, str]:
        # Audit finding #75: reflect DB reachability so k8s stops routing
        # traffic to pods that cannot serve requests. Skipped until the
        # engine is initialized (e.g. fresh process / unit tests).
        engine = get_initialized_engine()
        if engine is not None:
            try:
                await asyncio.wait_for(_db_ping(engine), timeout=2.0)
            except Exception as exc:
                raise HTTPException(
                    status_code=503, detail="Database unavailable"
                ) from exc
        return {"status": "ok"}

    return app


app = create_app()
