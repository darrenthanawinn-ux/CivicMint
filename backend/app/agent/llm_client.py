"""
Minimal, provider-agnostic LLM client used by the orchestrator.

Supports Anthropic and OpenAI, selected via LLM_PROVIDER in settings. Every
call is wrapped with a hard timeout and bounded retries with backoff. If
neither provider is configured (no API key), `call_llm` raises
LLMUnavailableError immediately so the orchestrator can drop into its
rule-based degraded mode without wasting a retry budget.
"""
from __future__ import annotations

import logging
import time
from typing import Optional

from app.config import get_settings

logger = logging.getLogger("civicmint.agent.llm_client")


class LLMUnavailableError(RuntimeError):
    """Raised when no LLM provider is configured or the provider call fails after retries."""


def _call_anthropic(system_prompt: str, user_message: str, timeout: float) -> str:
    import anthropic

    settings = get_settings()
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY, timeout=timeout)
    response = client.messages.create(
        model=settings.LLM_MODEL,
        max_tokens=2000,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )
    text_parts = [block.text for block in response.content if getattr(block, "type", None) == "text"]
    return "".join(text_parts)


def _call_openai(system_prompt: str, user_message: str, timeout: float) -> str:
    from openai import OpenAI

    settings = get_settings()
    client = OpenAI(api_key=settings.OPENAI_API_KEY, timeout=timeout)
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        temperature=0.1,
        response_format={"type": "json_object"},
    )
    return response.choices[0].message.content or ""


def call_llm(system_prompt: str, user_message: str) -> str:
    settings = get_settings()

    provider = settings.LLM_PROVIDER.lower()
    if provider == "anthropic" and not settings.ANTHROPIC_API_KEY:
        provider = "openai" if settings.OPENAI_API_KEY else "none"
    if provider == "openai" and not settings.OPENAI_API_KEY:
        provider = "anthropic" if settings.ANTHROPIC_API_KEY else "none"

    if provider == "none":
        raise LLMUnavailableError("No LLM provider configured (missing API key).")

    last_error: Optional[Exception] = None
    for attempt in range(1, settings.LLM_MAX_RETRIES + 2):
        try:
            if provider == "anthropic":
                return _call_anthropic(system_prompt, user_message, settings.LLM_TIMEOUT_SECONDS)
            return _call_openai(system_prompt, user_message, settings.LLM_TIMEOUT_SECONDS)
        except Exception as exc:  # noqa: BLE001 -- broad by design, see module docstring
            last_error = exc
            logger.warning("LLM call attempt %d/%d failed: %s", attempt, settings.LLM_MAX_RETRIES + 1, type(exc).__name__)
            if attempt <= settings.LLM_MAX_RETRIES:
                time.sleep(min(2 ** attempt * 0.25, 3.0))

    raise LLMUnavailableError(f"LLM call failed after retries: {last_error}") from last_error
