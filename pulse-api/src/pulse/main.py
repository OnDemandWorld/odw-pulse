"""Pulse FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from pulse.api import health
from pulse.api.v1 import auth as auth_v1
from pulse.api.v1 import content as content_v1
from pulse.api.v1 import generate as generate_v1
from pulse.config import get_settings
from pulse.core.logging import configure_logging
from pulse.middleware.tenant import TenantMiddleware


def create_app() -> FastAPI:
    """Application factory."""
    settings = get_settings()
    configure_logging(settings.pulse_log_level)

    app = FastAPI(
        title="Pulse API",
        description="Multilingual content generation and localization module",
        version="0.1.0",
    )

    # Middleware stack (order matters — first added = outermost)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.is_development else [],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(TenantMiddleware)

    # Routes
    app.include_router(health.router, prefix="/api/v1")
    app.include_router(auth_v1.router, prefix="/api/v1")
    app.include_router(generate_v1.router, prefix="/api/v1")
    app.include_router(content_v1.router, prefix="/api/v1")

    @app.get("/health/live", tags=["health"])
    async def liveness() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready", tags=["health"])
    async def readiness() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
