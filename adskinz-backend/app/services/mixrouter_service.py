"""MixRouter LLM service: default provider for AI ad-copy generation.

This mirrors ``openrouter_service.py`` on purpose — OpenRouter stays wired
up as the alternate provider (advertiser picks GPT or Grok from the
wizard) and as the automatic fallback if a MixRouter call fails, so both
services intentionally expose the same shape (``generate_ad_copy``,
``emojify_text``).

All AI-generated ad copy is capped at ``settings.AD_TEXT_AI_MAX_CHARS``
(399 by default) — this is a *global* limit across providers, independent
of AD_TEXT_MAX_LENGTH which bounds manually-typed/HTML copy.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re

import httpx

from app.config import settings
from app.core.errors import ConfigurationError, UpstreamError

logger = logging.getLogger(__name__)

_COPY_SYSTEM_PROMPT = (
    "You are a senior performance copywriter for Telegram advertising. "
    "Write one short, punchy ad. Be concrete about the benefit. Never invent "
    "statistics, testimonials, guarantees, awards or user counts. Never "
    "promise financial returns. Do not use hashtags. Return only the ad "
    "text, with no preamble, no quotes and no explanation. The text MUST "
    "be under {limit} characters total, including spaces."
)

_EMOJIFY_SYSTEM_PROMPT = (
    "You add tasteful emojis to an existing Telegram ad. Keep every word of "
    "the original text and its meaning unchanged — only insert emojis at "
    "natural points (start of lines, after a strong benefit, before the "
    "call to action). Use at most 4 emojis total, never two in a row. "
    "Return only the updated text, no preamble, no quotes. The result MUST "
    "stay under {limit} characters total."
)


def _client() -> httpx.AsyncClient:
    if not settings.MIXROUTER_API_KEY:
        raise ConfigurationError("MixRouter is not configured on this instance.")
    return httpx.AsyncClient(
        base_url=settings.MIXROUTER_BASE_URL,
        timeout=settings.MIXROUTER_TIMEOUT_SECONDS,
        headers={
            "Authorization": f"Bearer {settings.MIXROUTER_API_KEY}",
            "Content-Type": "application/json",
        },
    )


def _clean(text: str, *, limit: int) -> str:
    text = text.strip()
    text = re.sub(r"^```[a-zA-Z]*\n?|```$", "", text).strip()
    if len(text) >= 2 and text[0] in "\"'“«" and text[-1] in "\"'”»":
        text = text[1:-1].strip()
    for prefix in ("Ad copy:", "Here is", "Voici"):
        if text.lower().startswith(prefix.lower()):
            text = text[len(prefix):].lstrip(": ").strip()
    return text[:limit]


async def _chat(messages: list[dict[str, str]], *, temperature: float, max_tokens: int) -> str:
    payload = {
        "model": settings.MIXROUTER_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    last_error: Exception | None = None

    for attempt in range(3):
        try:
            async with _client() as client:
                response = await client.post("/chat/completions", json=payload)
            if response.status_code == 429:
                await asyncio.sleep(1.5 * (attempt + 1))
                last_error = UpstreamError("MixRouter is rate limiting requests.")
                continue
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
        except (httpx.HTTPError, KeyError, IndexError, json.JSONDecodeError) as exc:
            last_error = exc
            logger.warning("mixrouter.request_failed attempt=%s error=%s", attempt + 1, exc)
            await asyncio.sleep(0.8 * (attempt + 1))

    raise UpstreamError(
        "The AI service is temporarily unavailable. Please try again in a moment."
    ) from last_error


async def generate_ad_copy(
    brief: str, *, language: str = "en", tone: str = "punchy"
) -> tuple[str, str, int | None]:
    """Draft ad copy from a short brief. Returns ``(copy, model, tokens)``."""
    limit = settings.AD_TEXT_AI_MAX_CHARS
    user_prompt = (
        f"Write the ad in {language}. Desired tone: {tone}.\n"
        f"Product or offer to promote:\n{brief.strip()}"
    )
    raw = await _chat(
        [
            {"role": "system", "content": _COPY_SYSTEM_PROMPT.format(limit=limit)},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.85,
        max_tokens=300,
    )
    text = _clean(raw, limit=limit)
    if not text:
        raise UpstreamError("The AI service returned an empty response.")
    return text, settings.MIXROUTER_MODEL, None


async def emojify_text(text: str) -> str:
    """Add emojis to an already-written ad, staying under the global cap."""
    limit = settings.AD_TEXT_AI_MAX_CHARS
    raw = await _chat(
        [
            {"role": "system", "content": _EMOJIFY_SYSTEM_PROMPT.format(limit=limit)},
            {"role": "user", "content": text.strip()},
        ],
        temperature=0.4,
        max_tokens=300,
    )
    result = _clean(raw, limit=limit)
    return result or text[:limit]


def is_configured() -> bool:
    return bool(settings.MIXROUTER_API_KEY)
