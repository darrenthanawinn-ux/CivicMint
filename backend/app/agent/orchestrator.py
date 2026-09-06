"""
Core agent orchestration for permit analysis.

Pipeline:
  1. Sanitize input (app.security) -- already done by the route layer before
     this is called, but re-validated here defensively.
  2. Build several targeted retrieval queries from the structured business
     fields (not just the raw description) so retrieval isn't solely at the
     mercy of injection-stripped free text.
  3. Retrieve candidate municipal-code chunks (app.rag.retriever), merged and
     deduplicated across queries.
  4. If no chunks retrieved at all -> return a degraded, honest empty result
     rather than fabricating anything.
  5. Ask the LLM to select/summarize permits, but ONLY as pointers back to
     chunk_ids -- the LLM never gets to invent citation metadata.
  6. VALIDATE every LLM-claimed chunk_id against the actually-retrieved set.
     Any permit citing a chunk_id we did not retrieve is dropped and logged
     as a caught hallucination -- this is the hard citation-integrity gate.
  7. If the LLM is unavailable or its output fails validation entirely, fall
     back to a deterministic rule-based mapping straight from the retrieved
     chunks (lower confidence, but still 100% citation-backed).

At no point can a permit reach the client without a citation whose
source_document/section/chunk_id was independently confirmed against the
vector store -- the LLM proposes, the retrieval index disposes.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import List

from app.agent.llm_client import LLMUnavailableError, call_llm
from app.agent.prompts import SYSTEM_PROMPT, build_user_message
from app.cache import llm_cache
from app.models import (
    BusinessInput,
    BusinessType,
    CitationMeta,
    ConfidenceLevel,
    PermitAnalysisResponse,
    PermitRequirement,
)
from app.pdf.templates import TEMPLATES
from app.rag.retriever import RetrievedChunk, retrieve
from app.security import sanitize_business_payload

logger = logging.getLogger("civicmint.agent.orchestrator")

# Keyword -> pre-fillable form template mapping. This is a presentation-layer
# convenience (which downloadable PDF to offer), never used for citation
# purposes -- citations always come from the verified chunk metadata above.
_FORM_TEMPLATE_KEYWORDS: dict[str, list[str]] = {
    "general_business_license": ["business license", "5.02"],
    "food_establishment_permit": ["food establishment", "8.14.100", "mobile food"],
    "home_occupation_permit": ["home occupation", "17.44"],
}


def _guess_form_template_id(permit_name: str, section: str) -> str | None:
    haystack = f"{permit_name} {section}".lower()
    for template_id, keywords in _FORM_TEMPLATE_KEYWORDS.items():
        if template_id not in TEMPLATES:
            continue
        if any(kw.lower() in haystack for kw in keywords):
            return template_id
    return None

# Business-type -> extra keyword queries, to make sure retrieval isn't solely
# dependent on the free-text description (which may have been heavily
# stripped by sanitization if it contained injection attempts).
_TYPE_QUERIES = {
    BusinessType.RESTAURANT: ["food establishment permit", "restaurant health inspection"],
    BusinessType.FOOD_TRUCK: ["mobile food facility permit", "food truck commissary"],
    BusinessType.RETAIL: ["retail business license", "tenant improvement building permit"],
    BusinessType.HOME_BASED: ["home occupation permit", "home-based business"],
    BusinessType.PROFESSIONAL_SERVICES: ["professional services registration"],
    BusinessType.CONSTRUCTION_CONTRACTOR: ["contractor license", "building permit"],
    BusinessType.SALON_PERSONAL_CARE: ["cosmetology license", "professional services registration"],
    BusinessType.BAR_NIGHTLIFE: ["alcohol license", "assembly occupancy permit"],
    BusinessType.OTHER: ["general business license"],
}


def _build_queries(business: BusinessInput) -> List[str]:
    queries = ["general business license requirement"]
    queries.extend(_TYPE_QUERIES.get(business.business_type, []))
    if business.serves_alcohol:
        queries.append("alcohol service license permit")
    if business.outdoor_seating:
        queries.append("outdoor seating sidewalk permit")
    if business.employee_count and business.employee_count >= 1:
        queries.append("fire department operational permit occupant load")
    # A trimmed slice of the (already-sanitized) description adds semantic
    # signal without letting an oversized field dominate every query.
    queries.append(business.description[:300])
    return queries


def _retrieve_all(queries: List[str]) -> List[RetrievedChunk]:
    seen_ids: set[str] = set()
    merged: List[RetrievedChunk] = []
    for q in queries:
        for chunk in retrieve(q):
            if chunk.chunk_id not in seen_ids:
                seen_ids.add(chunk.chunk_id)
                merged.append(chunk)
    merged.sort(key=lambda c: c.score, reverse=True)
    return merged


def _chunk_lookup(chunks: List[RetrievedChunk]) -> dict[str, RetrievedChunk]:
    return {c.chunk_id: c for c in chunks}


def _fallback_permits_from_chunks(chunks: List[RetrievedChunk], limit: int = 6) -> List[PermitRequirement]:
    """Deterministic, LLM-free fallback: every retrieved chunk above a basic
    relevance floor becomes a low-confidence permit entry, citation-backed by
    construction since it IS the retrieved chunk."""
    permits: List[PermitRequirement] = []
    for chunk in chunks[:limit]:
        if chunk.score < 0.05:
            continue
        permits.append(
            PermitRequirement(
                permit_name=chunk.section,
                issuing_authority=chunk.source_document,
                description=chunk.text[:400],
                estimated_processing_days=None,
                estimated_fee_usd=None,
                citation=CitationMeta(
                    source_document=chunk.source_document,
                    section=chunk.section,
                    chunk_id=chunk.chunk_id,
                    retrieval_score=chunk.score,
                    excerpt=chunk.text[:400],
                ),
                confidence=ConfidenceLevel.LOW,
                form_template_id=_guess_form_template_id(chunk.section, chunk.section),
            )
        )
    return permits


def _parse_llm_json(raw: str) -> dict:
    text = raw.strip()
    # Defensive stripping in case the model wraps output in a code fence
    # despite instructions not to.
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    return json.loads(text)


def _validate_and_build_permits(
    llm_payload: dict, chunk_lookup: dict[str, RetrievedChunk]
) -> tuple[List[PermitRequirement], int]:
    """Cross-checks every LLM-proposed permit's chunk_id against the actually
    retrieved chunks. Returns (validated_permits, hallucinated_count)."""
    validated: List[PermitRequirement] = []
    hallucinated = 0

    raw_permits = llm_payload.get("permits", [])
    if not isinstance(raw_permits, list):
        return [], 0

    for item in raw_permits:
        if not isinstance(item, dict):
            continue
        chunk_id = str(item.get("supporting_chunk_id", ""))
        chunk = chunk_lookup.get(chunk_id)
        if chunk is None:
            # The model cited a chunk_id we never retrieved -- this is exactly
            # the hallucination case the whole pipeline exists to catch.
            hallucinated += 1
            logger.warning("Dropped LLM permit citing unknown chunk_id=%r", chunk_id)
            continue

        confidence = ConfidenceLevel.HIGH if chunk.score >= 0.35 else ConfidenceLevel.MEDIUM

        try:
            permit = PermitRequirement(
                permit_name=str(item.get("permit_name", chunk.section))[:200],
                issuing_authority=str(item.get("issuing_authority", chunk.source_document))[:200],
                description=str(item.get("description", chunk.text[:400]))[:800],
                estimated_processing_days=item.get("estimated_processing_days"),
                estimated_fee_usd=item.get("estimated_fee_usd"),
                # NOTE: citation is built ENTIRELY from our own verified chunk
                # metadata, never from LLM-supplied fields -- the model cannot
                # forge a section number or source document even if it tries.
                citation=CitationMeta(
                    source_document=chunk.source_document,
                    section=chunk.section,
                    chunk_id=chunk.chunk_id,
                    retrieval_score=chunk.score,
                    excerpt=chunk.text[:400],
                ),
                confidence=confidence,
                form_template_id=_guess_form_template_id(
                    str(item.get("permit_name", "")), chunk.section
                ),
            )
        except Exception:  # noqa: BLE001
            logger.exception("Skipping malformed LLM permit item.")
            continue

        validated.append(permit)

    return validated, hallucinated


def analyze_business(business: BusinessInput) -> PermitAnalysisResponse:
    request_id = str(uuid.uuid4())
    warnings: List[str] = []

    # Defensive re-sanitization (route layer already does this before the
    # model is constructed, but orchestration should never assume a caller
    # upstream did its job).
    cleaned_payload, sanitize_warnings = sanitize_business_payload(business.model_dump())
    warnings.extend(sanitize_warnings)
    business = business.model_copy(update=cleaned_payload)

    jurisdiction = f"{business.city}, {business.state}"

    try:
        queries = _build_queries(business)
        chunks = _retrieve_all(queries)
    except Exception:  # noqa: BLE001
        logger.exception("Retrieval stage failed unexpectedly.")
        chunks = []
        warnings.append("Municipal code search was temporarily unavailable; results may be incomplete.")

    if not chunks:
        return PermitAnalysisResponse(
            request_id=request_id,
            generated_at=datetime.now(timezone.utc),
            business_name=business.business_name,
            jurisdiction=jurisdiction,
            degraded_mode=True,
            permits=[],
            warnings=warnings
            + ["No matching municipal code sections were found for this business profile."],
        )

    chunk_lookup = _chunk_lookup(chunks)
    business_summary = (
        f"Name: {business.business_name}\n"
        f"Type: {business.business_type.value}\n"
        f"Address: {business.address}, {business.city}, {business.state}\n"
        f"Employees: {business.employee_count}\n"
        f"Serves alcohol: {business.serves_alcohol}\n"
        f"Outdoor seating: {business.outdoor_seating}\n"
        f"Description: {business.description}"
    )

    cache_key = llm_cache.make_key(
        "analyze", business_summary, ",".join(c.chunk_id for c in chunks)
    )
    cached_payload = llm_cache.get(cache_key)

    if cached_payload is not None:
        llm_payload = cached_payload
    else:
        try:
            user_message = build_user_message(business_summary, chunks)
            raw_response = call_llm(SYSTEM_PROMPT, user_message)
            llm_payload = _parse_llm_json(raw_response)
            llm_cache.set(cache_key, llm_payload)
        except LLMUnavailableError:
            logger.info("LLM unavailable; using rule-based fallback for request_id=%s", request_id)
            fallback_permits = _fallback_permits_from_chunks(chunks)
            return PermitAnalysisResponse(
                request_id=request_id,
                generated_at=datetime.now(timezone.utc),
                business_name=business.business_name,
                jurisdiction=jurisdiction,
                degraded_mode=True,
                permits=fallback_permits,
                warnings=warnings
                + ["AI analysis is temporarily unavailable; showing citation-backed matches only."],
            )
        except (json.JSONDecodeError, ValueError):
            logger.exception("Failed to parse LLM JSON output for request_id=%s", request_id)
            fallback_permits = _fallback_permits_from_chunks(chunks)
            return PermitAnalysisResponse(
                request_id=request_id,
                generated_at=datetime.now(timezone.utc),
                business_name=business.business_name,
                jurisdiction=jurisdiction,
                degraded_mode=True,
                permits=fallback_permits,
                warnings=warnings + ["AI response could not be validated; showing safe fallback results."],
            )
        except Exception:  # noqa: BLE001 -- final safety net, never leak internals to client
            logger.exception("Unexpected orchestrator failure for request_id=%s", request_id)
            fallback_permits = _fallback_permits_from_chunks(chunks)
            return PermitAnalysisResponse(
                request_id=request_id,
                generated_at=datetime.now(timezone.utc),
                business_name=business.business_name,
                jurisdiction=jurisdiction,
                degraded_mode=True,
                permits=fallback_permits,
                warnings=warnings + ["An unexpected error occurred; showing safe fallback results."],
            )

    permits, hallucinated_count = _validate_and_build_permits(llm_payload, chunk_lookup)
    if hallucinated_count:
        warnings.append(
            f"{hallucinated_count} AI-suggested item(s) could not be verified against official "
            "sources and were removed."
        )

    if not permits:
        # LLM produced nothing verifiable -- degrade to the deterministic
        # fallback rather than returning an empty-handed response.
        permits = _fallback_permits_from_chunks(chunks)
        warnings.append("Showing citation-backed matches directly from municipal code.")
        degraded = True
    else:
        degraded = False

    return PermitAnalysisResponse(
        request_id=request_id,
        generated_at=datetime.now(timezone.utc),
        business_name=business.business_name,
        jurisdiction=jurisdiction,
        degraded_mode=degraded,
        permits=permits,
        warnings=warnings,
    )
