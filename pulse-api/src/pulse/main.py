"""Pulse FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from pulse.api import health
from pulse.api.v1 import auth as auth_v1
from pulse.api.v1 import bulk_jobs as bulk_jobs_v1
from pulse.api.v1 import content as content_v1
from pulse.api.v1 import experiments as experiments_v1
from pulse.api.v1 import generate as generate_v1
from pulse.api.v1 import integrations as integrations_v1
from pulse.config import get_settings
from pulse.core.logging import configure_logging
from pulse.middleware.tenant import TenantMiddleware

# Values that must never reach production unchanged.
_DEFAULT_SECRET_KEY = "change-me-in-production"
_DEFAULT_WEBHOOK_SECRET = "whsec_change_me"


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

    app = FastAPI(
        title="Pulse API",
        description="Multilingual content generation and localization module",
        version="0.1.0",
    )

    # Middleware stack (order matters — first added = outermost).
    # In development any origin is allowed; ``allow_origin_regex`` echoes the
    # request origin back, which — unlike ``allow_origins=["*"]`` — works
    # with credentialed requests. Production must set explicit origins.
    if settings.is_development:
        cors_kwargs: dict[str, object] = {"allow_origin_regex": r".*"}
    else:
        cors_kwargs = {"allow_origins": []}
    app.add_middleware(
        CORSMiddleware,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        **cors_kwargs,  # type: ignore[arg-type]
    )
    app.add_middleware(TenantMiddleware)

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
        return {"status": "ok"}

    return app


app = create_app()
