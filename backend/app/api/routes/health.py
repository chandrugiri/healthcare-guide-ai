from fastapi import APIRouter

from app.core.config import settings


router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> dict[str, str]:
    return {
        "status": "healthy",
        "service": "healthcare-guide-ai-api",
        "version": settings.app_version,
    }
