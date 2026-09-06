from __future__ import annotations

from fastapi import APIRouter

from app.config import get_settings
from app.rag.vector_store import collection_is_empty

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check() -> dict:
    settings = get_settings()
    return {
        "status": "ok",
        "environment": settings.ENVIRONMENT,
        "vector_store_empty": collection_is_empty(),
        "llm_provider_configured": bool(settings.ANTHROPIC_API_KEY or settings.OPENAI_API_KEY),
    }
