"""
/api/permits routes.

Every route here is rate-limited (app.rate_limit) and every exception path
returns a sanitized ErrorResponse -- raw exceptions/tracebacks are logged
server-side only and never included in the HTTP response body.
"""
from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.agent.orchestrator import analyze_business
from app.models import BusinessInput, ErrorResponse, PermitAnalysisResponse
from app.rate_limit import enforce_rate_limit

logger = logging.getLogger("civicmint.routes.permits")

router = APIRouter(prefix="/api/permits", tags=["permits"])


@router.post(
    "/analyze",
    response_model=PermitAnalysisResponse,
    responses={429: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
def analyze(
    business: BusinessInput,
    request: Request,
    _rate_limit: None = Depends(enforce_rate_limit),
) -> PermitAnalysisResponse:
    request_id = str(uuid.uuid4())
    try:
        return analyze_business(business)
    except Exception:  # noqa: BLE001 -- final safety net at the HTTP boundary
        logger.exception("Unhandled error in /api/permits/analyze request_id=%s", request_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Permit analysis is temporarily unavailable. Please try again.",
        ) from None
