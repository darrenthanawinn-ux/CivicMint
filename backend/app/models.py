"""
Strict Pydantic schemas for every request/response boundary in CivicMint.

Design principle: nothing crosses an API boundary (in or out) without being
validated against an explicit schema. This is both a correctness feature and
a security feature (see app.security for the sanitization layer that runs
*before* these validators).
"""
from __future__ import annotations

import re
from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

# ---------------------------------------------------------------------------
# Shared enums
# ---------------------------------------------------------------------------


class BusinessType(str, Enum):
    RESTAURANT = "restaurant"
    RETAIL = "retail"
    HOME_BASED = "home_based"
    PROFESSIONAL_SERVICES = "professional_services"
    CONSTRUCTION_CONTRACTOR = "construction_contractor"
    FOOD_TRUCK = "food_truck"
    SALON_PERSONAL_CARE = "salon_personal_care"
    BAR_NIGHTLIFE = "bar_nightlife"
    OTHER = "other"


class ConfidenceLevel(str, Enum):
    HIGH = "high"          # Directly grounded in a retrieved chunk with matching metadata
    MEDIUM = "medium"      # Grounded, but retrieval score was below the strict threshold
    LOW = "low"            # Rule-based fallback only (LLM unavailable / degraded mode)


# ---------------------------------------------------------------------------
# Inbound: business intake
# ---------------------------------------------------------------------------

# Deliberately conservative allowlist for free-text fields. This is a defense
# -in-depth layer that runs *before* the LLM ever sees the text (see
# app.security.sanitize_text for pattern-based prompt-injection stripping).
_SAFE_TEXT_RE = re.compile(r"^[a-zA-Z0-9\s.,'\-&()/#°:;!?\"@%]+$")


class BusinessInput(BaseModel):
    business_name: str = Field(..., min_length=2, max_length=150)
    business_type: BusinessType
    address: str = Field(..., min_length=5, max_length=250)
    city: str = Field(..., min_length=2, max_length=100)
    state: str = Field(..., min_length=2, max_length=56)
    description: str = Field(..., min_length=10, max_length=1200)
    employee_count: int = Field(default=1, ge=0, le=100000)
    serves_alcohol: bool = False
    outdoor_seating: bool = False
    square_footage: Optional[int] = Field(default=None, ge=0, le=2_000_000)

    @field_validator("business_name", "city", "state", "address", "description")
    @classmethod
    def no_control_chars(cls, v: str) -> str:
        # Strip null bytes / control characters outright -- these have no
        # legitimate use in a business description and are a classic smuggling
        # vector for terminal/log injection or downstream parser confusion.
        cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", v).strip()
        if not cleaned:
            raise ValueError("Field cannot be empty after sanitization.")
        return cleaned

    @field_validator("description")
    @classmethod
    def description_charset(cls, v: str) -> str:
        # Reject descriptions that are mostly outside the expected charset
        # (a cheap but effective signal for injected code/markup/instructions
        # rather than a plain-English business description).
        printable_ratio = sum(1 for c in v if _SAFE_TEXT_RE.match(c)) / max(len(v), 1)
        if printable_ratio < 0.85:
            raise ValueError(
                "Description contains an unusual proportion of unsupported characters."
            )
        return v

    @model_validator(mode="after")
    def alcohol_implies_relevant_type(self) -> "BusinessInput":
        # Not a hard error, just keeps the model internally consistent; the
        # agent layer uses this to decide whether to pull liquor-license chunks.
        return self


# ---------------------------------------------------------------------------
# Outbound: permit analysis
# ---------------------------------------------------------------------------


class CitationMeta(BaseModel):
    """
    A hard citation back to the exact ingested source chunk. Every permit
    requirement returned by the API MUST carry one of these, and its fields
    are cross-checked against the vector store's retrieved metadata before
    the response is allowed to leave the server (see agent.orchestrator).
    """

    source_document: str
    section: str
    chunk_id: str
    retrieval_score: float = Field(..., ge=0.0, le=1.0)
    excerpt: str = Field(..., max_length=400)


class PermitRequirement(BaseModel):
    permit_name: str
    issuing_authority: str
    description: str
    estimated_processing_days: Optional[int] = Field(default=None, ge=0, le=365)
    estimated_fee_usd: Optional[float] = Field(default=None, ge=0)
    citation: CitationMeta
    confidence: ConfidenceLevel
    form_template_id: Optional[str] = None


class PermitAnalysisResponse(BaseModel):
    request_id: str
    generated_at: datetime
    business_name: str
    jurisdiction: str
    degraded_mode: bool = Field(
        default=False,
        description="True if the LLM path failed and a citation-only rule-based "
        "fallback was used instead.",
    )
    permits: List[PermitRequirement]
    warnings: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Outbound: generic API error (never leaks stack traces / internals)
# ---------------------------------------------------------------------------


class ErrorResponse(BaseModel):
    error: str
    detail: str
    request_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Form filling
# ---------------------------------------------------------------------------


class FormFillRequest(BaseModel):
    form_template_id: str = Field(..., min_length=1, max_length=64)
    business: BusinessInput
    permit_name: str = Field(..., min_length=1, max_length=200)

    @field_validator("form_template_id")
    @classmethod
    def alnum_id(cls, v: str) -> str:
        # Template IDs map directly to a filesystem lookup -- restrict to a
        # strict allowlist charset to make path traversal structurally
        # impossible regardless of downstream code.
        if not re.fullmatch(r"[a-zA-Z0-9_\-]+", v):
            raise ValueError("form_template_id must be alphanumeric/underscore/hyphen only.")
        return v


class FormFillResponse(BaseModel):
    filename: str
    download_url: str
    fields_written: int
