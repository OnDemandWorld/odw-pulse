"""Health check API routes."""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health", response_model=dict[str, str])
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
