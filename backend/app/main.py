"""
CivicMint API entry point.

Run locally:
    uvicorn app.main:app --reload --port 8000
"""
from __future__ import annotations

import logging
import uuid

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from app.config import get_settings
from app.models import ErrorResponse
from app.rag.vector_store import collection_is_empty

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("civicmint.main")

settings = get_settings()

app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="AI-driven local compliance & permit navigator for small businesses.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Global exception handling: NOTHING leaks a raw stack trace to the client.
# Every unhandled exception is logged in full server-side with a correlation
# ID, and the client receives only that ID plus a generic message.
# ---------------------------------------------------------------------------


@app.exception_handler(ValidationError)
async def pydantic_validation_handler(request: Request, exc: ValidationError) -> JSONResponse:
    request_id = str(uuid.uuid4())
    logger.warning("Validation error request_id=%s errors=%s", request_id, exc.errors())
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=ErrorResponse(
            error="validation_error",
            detail="One or more fields failed validation.",
            request_id=request_id,
        ).model_dump(),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = str(uuid.uuid4())
    logger.exception("Unhandled exception request_id=%s path=%s", request_id, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            error="internal_error",
            detail="Something went wrong on our end. Please try again shortly.",
            request_id=request_id,
        ).model_dump(),
    )


@app.on_event("startup")
def on_startup() -> None:
    logger.info("Starting %s (environment=%s)", settings.APP_NAME, settings.ENVIRONMENT)
    if collection_is_empty():
        logger.warning(
            "Vector store collection is empty. Run `python -m app.rag.ingest` to load the "
            "sample municipal code corpus before analyzing businesses."
        )
    if not (settings.ANTHROPIC_API_KEY or settings.OPENAI_API_KEY):
        logger.warning(
            "No LLM provider API key configured -- running in rule-based degraded mode only."
        )


from app.routes import forms, health, permits  # noqa: E402  (import after app/logging setup)

app.include_router(health.router)
app.include_router(permits.router)
app.include_router(forms.router)


@app.get("/")
def root() -> dict:
    return {"service": settings.APP_NAME, "status": "running", "docs": "/docs"}
