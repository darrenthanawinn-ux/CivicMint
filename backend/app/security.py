"""
Input sanitization and prompt-injection defense.

This module implements defense-in-depth for anything that will eventually be
interpolated into an LLM prompt:

  1. Structural validation happens first, in app.models (Pydantic) -- length
     limits, charset checks, enum constraints.
  2. Pattern-based injection detection happens here -- known jailbreak /
     instruction-override phrasing is flagged and stripped.
  3. System/user message separation happens in agent.prompts -- user content
     is ALWAYS passed as clearly delimited, quoted data, never concatenated
     into the system prompt string itself.

No single layer is trusted alone; a request must pass all three.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import List

logger = logging.getLogger("civicmint.security")

# Known prompt-injection / jailbreak phrasing. Not exhaustive (no static list
# ever is) but catches the overwhelming majority of automated/naive attempts,
# and every hit is logged for later pattern review.
_INJECTION_PATTERNS: List[re.Pattern] = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions", re.I),
    re.compile(r"disregard\s+(all\s+)?(previous|prior|above)", re.I),
    re.compile(r"you\s+are\s+now\s+(a|an)\s+\w+", re.I),
    re.compile(r"system\s*prompt", re.I),
    re.compile(r"</?\s*(system|assistant|user)\s*>", re.I),
    re.compile(r"\bact\s+as\s+(if\s+you\s+are\s+)?\w+", re.I),
    re.compile(r"reveal\s+(your|the)\s+(system\s+)?prompt", re.I),
    re.compile(r"new\s+instructions?\s*:", re.I),
    re.compile(r"override\s+(your\s+)?(rules|guidelines|instructions)", re.I),
    re.compile(r"\bjailbreak\b", re.I),
    re.compile(r"```", re.S),  # code fences have no place in a business description
]

_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_ZERO_WIDTH_RE = re.compile(r"[\u200b\u200c\u200d\u2060\ufeff]")


@dataclass
class SanitizationResult:
    clean_text: str
    flagged: bool = False
    matched_patterns: List[str] = field(default_factory=list)


def sanitize_text(raw: str, *, field_name: str = "text") -> SanitizationResult:
    """
    Strip control/zero-width characters, then scan for injection phrasing.
    Injection attempts are *removed* from the text (not just flagged) before
    the text is allowed anywhere near a prompt, and the attempt is logged
    with the offending pattern for observability -- never with the raw user
    text at a level above DEBUG, to avoid log-injection / PII sprawl.
    """
    text = _CONTROL_CHAR_RE.sub("", raw)
    text = _ZERO_WIDTH_RE.sub("", text)

    matched: List[str] = []
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(text):
            matched.append(pattern.pattern)
            text = pattern.sub("[removed]", text)

    if matched:
        logger.warning(
            "Potential prompt injection stripped from field=%s pattern_count=%d",
            field_name,
            len(matched),
        )

    return SanitizationResult(clean_text=text.strip(), flagged=bool(matched), matched_patterns=matched)


def sanitize_business_payload(payload: dict) -> tuple[dict, List[str]]:
    """
    Runs sanitize_text over every free-text field of a business intake
    payload. Returns the cleaned payload plus a list of user-facing warnings
    (never internal pattern details) for any field that was flagged.
    """
    warnings: List[str] = []
    cleaned = dict(payload)
    for field_name in ("business_name", "address", "city", "state", "description"):
        if field_name in cleaned and isinstance(cleaned[field_name], str):
            result = sanitize_text(cleaned[field_name], field_name=field_name)
            cleaned[field_name] = result.clean_text
            if result.flagged:
                warnings.append(
                    f"Unsupported content was removed from '{field_name}' before processing."
                )
    return cleaned, warnings
