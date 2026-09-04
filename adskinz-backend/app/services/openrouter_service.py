"""OpenRouter LLM service: ad copy generation and campaign translation.

Translations are produced **once, at approval time**, and stored in
``campaign_translations``. They are never generated while serving an
impression: an ad request must stay a database read.
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

LANGUAGE_NAMES: dict[str, str] = {
    "en": "English",
    "fr": "French",
    "ru": "Russian",
    "zh": "Simplified Chinese",
    "es": "Spanish",
    "pt": "Portuguese",
    "ar": "Arabic",
    "hi": "Hindi",
    "id": "Indonesian",
    "tr": "Turkish",
    "uk": "Ukrainian",
}

_COPY_SYSTEM_PROMPT = (
    "You are a senior performance copywriter for Telegram advertising. "
    "Write one short ad, 2 to 4 lines, under 300 characters. Be concrete and "
    "concrete about the benefit. Never invent statistics, testimonials, "
    "guarantees, awards or user counts. Never promise financial returns. "
    "Do not use hashtags. At most two emojis. Return only the ad text, with no "
    "preamble, no quotes and no explanation."
)

_TRANSLATE_SYSTEM_PROMPT = (
    "You are a professional advertising translator. Translate the ad copy into "
    "the requested language, preserving meaning, tone, line breaks and emojis. "
    "Adapt idioms rather than translating them literally. Do not add or remove "
    "any claim. Return only the translation, with no preamble and no quotes."
)

_MAX_COPY_CHARS = 900


def _client() -> httpx.AsyncClient:
    if not settings.OPENROUTER_API_KEY:
        raise ConfigurationError("AI generation is not configured on this instance.")
    return httpx.AsyncClient(
        base_url=settings.OPENROUTER_BASE_URL,
        timeout=settings.OPENROUTER_TIMEOUT_SECONDS,
        headers={
            "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            # OpenRouter attributes usage in its dashboard by these two
            # optional headers; harmless if OpenRouter is ever swapped out.
            "HTTP-Referer": settings.OPENROUTER_SITE_URL,
            "X-Title": settings.OPENROUTER_SITE_NAME,
        },
    )


def _clean(text: str) -> str:
    """Strip the wrappers models like to add around the answer."""
    text = text.strip()
    text = re.sub(r"^```[a-zA-Z]*\n?|```$", "", text).strip()
    if len(text) >= 2 and text[0] in "\"'“«" and text[-1] in "\"'”»":
        text = text[1:-1].strip()
    for prefix in ("Ad copy:", "Translation:", "Here is", "Voici"):
        if text.lower().startswith(prefix.lower()):
            text = text[len(prefix):].lstrip(": ").strip()
    return text[:_MAX_COPY_CHARS]


async def _chat(
    messages: list[dict[str, str]],
    *,
    temperature: float,
    max_tokens: int,
) -> tuple[str, int | None]:
    payload = {
        "model": settings.OPENROUTER_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    last_error: Exception | None = None

    # Two retries with a short backoff; the caller is a user-facing request.
    for attempt in range(3):
        try:
            async with _client() as client:
                response = await client.post("/chat/completions", json=payload)
            if response.status_code == 429:
                await asyncio.sleep(1.5 * (attempt + 1))
                last_error = UpstreamError("AI provider is rate limiting requests.")
                continue
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            usage = (data.get("usage") or {}).get("total_tokens")
            return _clean(content), usage
        except (httpx.HTTPError, KeyError, IndexError, json.JSONDecodeError) as exc:
            last_error = exc
            logger.warning("openrouter.request_failed attempt=%s error=%s", attempt + 1, exc)
            await asyncio.sleep(0.8 * (attempt + 1))

    raise UpstreamError(
        "The AI service is temporarily unavailable. Please try again in a moment."
    ) from last_error


async def generate_ad_copy(
    brief: str, *, language: str = "en", tone: str = "punchy"
) -> tuple[str, str, int | None]:
    """Draft ad copy from a short brief. Returns ``(copy, model, tokens)``."""
    language_name = LANGUAGE_NAMES.get(language, "English")
    user_prompt = (
        f"Write the ad in {language_name}. Desired tone: {tone}.\n"
        f"Product or offer to promote:\n{brief.strip()}"
    )
    text, tokens = await _chat(
        [
            {"role": "system", "content": _COPY_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.85,
        max_tokens=400,
    )
    if not text:
        raise UpstreamError("The AI service returned an empty response.")
    return text, settings.OPENROUTER_MODEL, tokens


async def translate_text(text: str, *, target_lang: str, source_lang: str = "en") -> str:
    """Translate one ad copy into one target language (one call per language)."""
    target_name = LANGUAGE_NAMES.get(target_lang, target_lang)
    source_name = LANGUAGE_NAMES.get(source_lang, source_lang)
    translated, _ = await _chat(
        [
            {"role": "system", "content": _TRANSLATE_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Source language: {source_name}. Target language: {target_name}.\n\n"
                    f"{text}"
                ),
            },
        ],
        temperature=0.2,
        max_tokens=600,
    )
    return translated or text


async def translate_button_label(label: str, *, target_lang: str) -> str:
    """Translate a call-to-action label, keeping it short enough for a button."""
    target_name = LANGUAGE_NAMES.get(target_lang, target_lang)
    translated, _ = await _chat(
        [
            {
                "role": "system",
                "content": (
                    "Translate this call-to-action button label. Keep it under "
                    "22 characters. Return only the translated label."
                ),
            },
            {"role": "user", "content": f"Target language: {target_name}\nLabel: {label}"},
        ],
        temperature=0.1,
        max_tokens=40,
    )
    cleaned = (translated or label).strip()
    return cleaned[:40] if cleaned else label


def target_languages(source_lang: str) -> list[str]:
    """The supported languages to generate, excluding the source one."""
    supported = settings.translation_langs
    return [lang for lang in supported if lang != source_lang]


def is_configured() -> bool:
    return bool(settings.OPENROUTER_API_KEY)
