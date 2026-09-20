"""Campaign translation: deep-translator (Google) + MixRouter safety review.

Translations are produced **once, at approval time**, and stored in
``campaign_translations``. They are never generated while serving an
impression: an ad request must stay a database read.

Pipeline for one ad and one target language
-------------------------------------------
1. **Structure-preserving machine translation.** The ad is Telegram HTML
   (``<b>``, ``<a href="…">``…). Sending it raw to Google Translate can
   mangle tags, so we never do that: the HTML is split into *tags*,
   *line breaks* and *text segments*, and only the text segments go to
   deep-translator. Tags, attributes, URLs and line breaks are copied
   through untouched, so the result has exactly the same markup as the
   original by construction.
2. **AI review (MixRouter).** Translating segment by segment can leave rough
   sentences where an inline tag splits a sentence (``Avec <b>Brand</b>,
   transfère…``). A model sees the whole ad, fixes wording and checks the
   markup.
3. **Deterministic validation of the AI output.** The model is never trusted:
   its answer is accepted only if the tag sequence, every ``href``, every
   URL / @handle / brand name is identical to the original. Otherwise the
   machine translation from step 1 is kept.

If a language fails outright, the caller skips it and the ad falls back to the
advertiser's original copy for that language — one bad language never blocks
the approval.
"""

from __future__ import annotations

import asyncio
import functools
import html
import logging
import re
from dataclasses import dataclass

from app.config import settings
from app.core.errors import UpstreamError
from app.services import mixrouter_service

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

# Our language codes -> Google's. deep-translator rejects a bare "zh".
_GOOGLE_CODES: dict[str, str] = {"zh": "zh-CN"}

# Stored in campaign_translations.source (VARCHAR(20)).
SOURCE_MACHINE = "deep_translator"
SOURCE_MACHINE_REVIEWED = "deep_translator+ai"

MAX_BUTTON_LABEL_CHARS = 40

# A tag, or a run of line breaks. Everything else is a translatable text segment.
_SPLIT_RE = re.compile(r"(</?[a-zA-Z][^>]*>|\n+)")
_TAG_RE = re.compile(r"<(/?)([a-zA-Z][a-zA-Z0-9-]*)([^>]*)>")
_HREF_RE = re.compile(r"""href\s*=\s*(?:"([^"]*)"|'([^']*)')""", re.IGNORECASE)
# Things that must survive translation verbatim inside the visible text.
_PROTECTED_RE = re.compile(r"(?:https?://|t\.me/)[^\s<>\"']+|@\w{3,}")


def google_code(lang: str) -> str:
    """Map one of our language codes (or ``auto``) to deep-translator's."""
    return _GOOGLE_CODES.get(lang, lang)


def target_languages(source_lang: str) -> list[str]:
    """The supported languages to generate, excluding the source one."""
    return [lang for lang in settings.translation_langs if lang != source_lang]


# --------------------------------------------------------------------------- #
# Source language
# --------------------------------------------------------------------------- #
_LATIN_HINTS: dict[str, frozenset[str]] = {
    "en": frozenset(
        "the and to of in for with your you is are on now get from this that it "
        "our we can new more".split()
    ),
    "fr": frozenset(
        "le la les de des du et un une pour avec vous tu toi ton ta tes sur est en "
        "qui que plus fini aussi entre dans par pas ce cette au aux si ou où".split()
    ),
    "es": frozenset(
        "el la los las de del y un una para con tu tus su es en que más muy este "
        "esta por al como pero".split()
    ),
    "pt": frozenset(
        "o os as de do da dos das e um uma para com você seu sua é em que mais muito "
        "este esta por ao como mas não".split()
    ),
    "id": frozenset(
        "yang dan di ke dari untuk dengan ini itu anda kamu adalah pada akan lebih "
        "juga atau tidak".split()
    ),
    "tr": frozenset(
        "ve bir bu için ile de da en daha çok ama gibi olarak senin sizin şimdi".split()
    ),
}
_ACCENT_HINTS: dict[str, str] = {
    "fr": "éèêëàâçùûôîï",
    "es": "ñ¿¡áíóú",
    "pt": "ãõçâêôáéíóú",
    "tr": "ığşİ",
}


def detect_language(text: str) -> str:
    """Best-effort source language for copy targeted at "all" languages.

    Only used to *label* the stored original correctly (so a French ad is not
    filed under ``en``); the machine translation itself uses Google's own
    auto-detection. Falls back to ``en`` when nothing is conclusive.
    """
    visible = html.unescape(_TAG_RE.sub(" ", text))
    letters = [ch for ch in visible if ch.isalpha()]
    if not letters:
        return "en"

    def ratio(lo: int, hi: int) -> float:
        return sum(1 for ch in letters if lo <= ord(ch) <= hi) / len(letters)

    if ratio(0x4E00, 0x9FFF) > 0.2 or ratio(0x3400, 0x4DBF) > 0.2:
        return "zh"
    if ratio(0x0400, 0x04FF) > 0.3:
        return "uk" if any(ch in "іїєґІЇЄҐ" for ch in letters) else "ru"
    if ratio(0x0600, 0x06FF) > 0.3:
        return "ar"
    if ratio(0x0900, 0x097F) > 0.3:
        return "hi"

    words = re.findall(r"[^\W\d_]+", visible.lower())
    scores: dict[str, int] = {}
    for lang, hints in _LATIN_HINTS.items():
        score = sum(1 for w in words if w in hints)
        accents = _ACCENT_HINTS.get(lang, "")
        score += sum(1 for ch in visible.lower() if ch in accents) // 2
        scores[lang] = score
    best = max(scores, key=lambda k: scores[k])
    return best if scores[best] >= 2 else "en"


def resolve_source_lang(target_language: str | None, text: str) -> str:
    """The campaign's own language, detecting it when it targets "all"."""
    if target_language and target_language != "all":
        return target_language
    return detect_language(text)


# --------------------------------------------------------------------------- #
# HTML helpers
# --------------------------------------------------------------------------- #
def _signature(markup: str) -> list[tuple[str, str, str]]:
    """Ordered ``(open|close, tag, href)`` list — the markup's skeleton."""
    out: list[tuple[str, str, str]] = []
    for closing, name, attrs in _TAG_RE.findall(markup):
        href = ""
        if not closing:
            m = _HREF_RE.search(attrs)
            if m:
                href = (m.group(1) or m.group(2) or "").strip()
        out.append(("close" if closing else "open", name.lower(), href))
    return out


def _visible_text(markup: str) -> str:
    return _TAG_RE.sub("", markup)


def _protected_tokens(text: str, keep_terms: tuple[str, ...]) -> list[str]:
    visible = html.unescape(text)
    tokens = _PROTECTED_RE.findall(visible)
    tokens.extend(term for term in keep_terms if term and term in visible)
    return tokens


def validate_html(
    original: str,
    candidate: str,
    keep_terms: tuple[str, ...] = (),
    *,
    max_len: int | None = None,
) -> str | None:
    """Return why ``candidate`` is not a safe translation of ``original``.

    ``None`` means it is safe: same tags in the same order with the same
    ``href`` values, no stray angle brackets in the text, and every URL,
    @handle and brand name of the original still present. ``max_len`` (when
    given) stops a model from padding the ad.
    """
    if not candidate.strip():
        return "empty"
    if _signature(original) != _signature(candidate):
        return "tags_changed"
    stray = _visible_text(candidate)
    if "<" in stray or ">" in stray:
        return "unescaped_angle_bracket"
    candidate_visible = html.unescape(stray)
    original_visible = html.unescape(_visible_text(original))
    for token in set(_protected_tokens(_visible_text(original), keep_terms)):
        # Counted, not just "present": a brand mentioned twice must stay twice.
        if candidate_visible.count(token) < original_visible.count(token):
            return f"lost_protected_token:{token}"
    if max_len is not None and len(candidate) > max_len:
        return "too_long"
    return None


# --------------------------------------------------------------------------- #
# Google (deep-translator)
# --------------------------------------------------------------------------- #
@functools.lru_cache(maxsize=2048)
def _google_translate_sync(text: str, source: str, target: str) -> str:
    # Imported lazily so the API still boots if the package is missing.
    from deep_translator import GoogleTranslator

    result = GoogleTranslator(source=source, target=target).translate(text)
    if not result or not result.strip():
        raise UpstreamError("Translation service returned an empty result.")
    return result


async def _google(text: str, *, source: str, target: str, sem: asyncio.Semaphore) -> str:
    """One Google call: off the event loop, bounded, retried, never hanging."""
    last: Exception | None = None
    for attempt in range(3):
        try:
            async with sem:
                return await asyncio.wait_for(
                    asyncio.to_thread(
                        _google_translate_sync,
                        text,
                        google_code(source),
                        google_code(target),
                    ),
                    timeout=settings.TRANSLATION_HTTP_TIMEOUT_SECONDS,
                )
        except ImportError:
            raise
        except Exception as exc:  # noqa: BLE001 - network/rate-limit errors vary
            last = exc
            logger.warning(
                "translation.google_failed target=%s attempt=%s error=%s",
                target, attempt + 1, exc,
            )
            await asyncio.sleep(0.6 * (attempt + 1))
    raise UpstreamError("The translation service is temporarily unavailable.") from last


def _has_letters(text: str) -> bool:
    return any(ch.isalpha() for ch in text)


async def translate_html(
    markup: str,
    *,
    source: str,
    target: str,
    keep_terms: tuple[str, ...],
    sem: asyncio.Semaphore,
) -> str:
    """Translate the text of Telegram HTML, leaving all markup untouched."""
    parts = _SPLIT_RE.split(markup)  # even index = text, odd index = tag / newlines

    async def one(segment: str) -> str:
        m = re.match(r"^(\s*)(.*?)(\s*)$", segment, re.DOTALL)
        assert m is not None  # the pattern matches any string
        lead, core, trail = m.groups()
        plain = html.unescape(core)
        if not core or not _has_letters(plain):
            return segment  # emojis, digits, punctuation: nothing to translate
        translated = html.escape(
            await _google(plain, source=source, target=target, sem=sem), quote=False
        ).strip()
        # A translator that eats a URL / @handle / brand name gets overruled
        # for that segment: better one untranslated phrase than a broken link.
        for token in _protected_tokens(core, keep_terms):
            if token not in html.unescape(translated):
                logger.info("translation.segment_kept_original token=%s", token)
                return segment
        return f"{lead}{translated}{trail}"

    translated_segments = await asyncio.gather(
        *(one(parts[i]) for i in range(0, len(parts), 2))
    )
    out: list[str] = []
    for i, part in enumerate(parts):
        out.append(translated_segments[i // 2] if i % 2 == 0 else part)
    return "".join(out)


async def translate_label(
    label: str, *, source: str, target: str, sem: asyncio.Semaphore
) -> str:
    """Translate a call-to-action label; the original label if that fails."""
    if not label or not _has_letters(label):
        return label
    try:
        translated = (await _google(label, source=source, target=target, sem=sem)).strip()
    except ImportError:
        raise
    except Exception as exc:  # noqa: BLE001 - a bad label must not lose the ad text
        logger.warning("translation.label_failed target=%s error=%s", target, exc)
        return label
    return translated[:MAX_BUTTON_LABEL_CHARS] if translated else label


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class TranslatedAd:
    text: str
    button_label: str
    reviewed: bool  # True when the AI review's output passed validation

    @property
    def source(self) -> str:
        return SOURCE_MACHINE_REVIEWED if self.reviewed else SOURCE_MACHINE


async def translate_ad(
    *,
    text: str,
    button_label: str,
    source_lang: str,
    target_lang: str,
    google_source: str | None = None,
    brand_name: str | None = None,
    sem: asyncio.Semaphore | None = None,
) -> TranslatedAd:
    """Translate one ad into one language. Raises if it cannot be done safely.

    ``google_source`` is what Google is told the source is (``auto`` when the
    campaign targets all languages); ``source_lang`` is the best-known code,
    used for the review prompt.
    """
    sem = sem or asyncio.Semaphore(settings.TRANSLATION_CONCURRENCY)
    google_source = google_source or source_lang
    keep_terms = (brand_name.strip(),) if brand_name and brand_name.strip() else ()

    machine = await translate_html(
        text, source=google_source, target=target_lang, keep_terms=keep_terms, sem=sem
    )
    problem = validate_html(text, machine, keep_terms)
    if problem:
        # Should be impossible (markup is copied verbatim) — treat as a bug, not a pass.
        raise UpstreamError(f"Machine translation failed validation: {problem}")

    final, reviewed = machine, False
    if settings.TRANSLATION_AI_REVIEW and mixrouter_service.is_configured():
        try:
            candidate = await asyncio.wait_for(
                mixrouter_service.review_translation(
                    text,
                    machine,
                    source_name=LANGUAGE_NAMES.get(source_lang, "the source language"),
                    target_name=LANGUAGE_NAMES.get(target_lang, target_lang),
                    keep_terms=keep_terms,
                ),
                timeout=settings.TRANSLATION_REVIEW_TIMEOUT_SECONDS,
            )
            problem = validate_html(
                text, candidate, keep_terms, max_len=int(len(machine) * 1.25) + 40
            )
            if problem is None:
                final, reviewed = candidate, True
            else:
                logger.warning(
                    "translation.review_rejected lang=%s reason=%s — keeping machine translation",
                    target_lang, problem,
                )
        except Exception as exc:  # noqa: BLE001 - the review is best-effort
            logger.warning("translation.review_failed lang=%s error=%s", target_lang, exc)

    label = await translate_label(
        button_label, source=google_source, target=target_lang, sem=sem
    )
    return TranslatedAd(text=final, button_label=label, reviewed=reviewed)
