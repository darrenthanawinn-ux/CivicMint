"""
/api/forms routes: renders a pre-filled PDF from validated business data and
serves it back for download. Filenames are server-generated UUID-suffixed
strings (see pdf.form_filler) specifically so this download endpoint can
safely treat the incoming filename as an opaque lookup key restricted to a
strict charset -- never a raw filesystem path -- which forecloses path
traversal regardless of anything upstream.
"""
from __future__ import annotations

import logging
import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse

from app.config import FILLED_FORMS_DIR
from app.models import ErrorResponse, FormFillRequest, FormFillResponse
from app.pdf.form_filler import FormValidationError, fill_form
from app.rate_limit import enforce_rate_limit

logger = logging.getLogger("civicmint.routes.forms")

router = APIRouter(prefix="/api/forms", tags=["forms"])

_SAFE_FILENAME_RE = re.compile(r"^[a-zA-Z0-9_\-]+\.pdf$")


@router.post(
    "/fill",
    response_model=FormFillResponse,
    responses={400: {"model": ErrorResponse}, 429: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
def fill(
    payload: FormFillRequest,
    request: Request,
    _rate_limit: None = Depends(enforce_rate_limit),
) -> FormFillResponse:
    request_id = str(uuid.uuid4())
    business = payload.business
    field_values = {
        "business_name": business.business_name,
        "business_type": business.business_type.value.replace("_", " ").title(),
        "address": business.address,
        "city_state": f"{business.city}, {business.state}",
        "employee_count": str(business.employee_count),
        "serves_alcohol": "Yes" if business.serves_alcohol else "No",
        "square_footage": str(business.square_footage) if business.square_footage else "N/A",
        "description": business.description,
    }

    try:
        filename, _path, fields_written = fill_form(payload.form_template_id, field_values)
    except FormValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from None
    except Exception:  # noqa: BLE001
        logger.exception("Unhandled error filling form request_id=%s", request_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Form generation is temporarily unavailable. Please try again.",
        ) from None

    return FormFillResponse(
        filename=filename,
        download_url=f"/api/forms/download/{filename}",
        fields_written=fields_written,
    )


@router.get("/download/{filename}")
def download(filename: str) -> FileResponse:
    if not _SAFE_FILENAME_RE.fullmatch(filename):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid filename.")

    file_path = (FILLED_FORMS_DIR / filename).resolve()
    if FILLED_FORMS_DIR.resolve() not in file_path.parents or not file_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found.")

    return FileResponse(path=file_path, media_type="application/pdf", filename=filename)
