"""Channel category auto-detection.

Two layers, in order:

1. ``keyword_categorize`` — free, instant, no external call. Scores the
   channel's name/description against a keyword dictionary per category.
   This alone resolves the large majority of channels (most channel names
   are pretty on-the-nose: "Crypto Signals FR", "Meme Zone", "ZFlix-Team").
2. ``ai_categorize`` — only used when step 1 finds no confident match.
   Asks OpenRouter to pick exactly one category from our closed list
   (``CHANNEL_CATEGORIES``), never a free-form string, so the result is
   always safe to store as-is.

Both return one of ``CHANNEL_CATEGORIES`` or ``None``.
"""

from __future__ import annotations

import logging
import re

from app.core.enums import CHANNEL_CATEGORIES
from app.services import openrouter_service

logger = logging.getLogger(__name__)

# Keyword -> category. Lowercase, matched as whole words against the
# channel's name + description (any language mixed in is fine — publishers
# write channel names in FR/EN/RU/etc, so the list intentionally mixes them).
_KEYWORDS: dict[str, tuple[str, ...]] = {
    "news_media": ("news", "actu", "actualit", "media", "média", "presse", "journal", "info24", "breaking"),
    "entertainment": ("fun", "entertain", "divertissement", "show", "buzz"),
    "movies_tv": ("film", "movie", "cinema", "cinéma", "series", "série", "flix", "netflix", "anime", "drama", "tv"),
    "music": ("music", "musique", "song", "chanson", "beats", "rap", "hiphop", "playlist", "dj "),
    "gaming": ("game", "gaming", "jeux", "jeu vidéo", "esport", "fortnite", "cs2", "pubg", "valorant", "minecraft"),
    "tech": ("tech", "technolog", "gadget", "programming", "code", "dev", "coding", "ai ", "ia ", "startup"),
    "crypto_finance": ("crypto", "bitcoin", "btc", "eth", "nft", "trading", "forex", "signals", "signaux", "airdrop", "ton coin", "defi"),
    "business": ("business", "entrepreneur", "marketing", "affaires", "ecommerce", "e-commerce", "vente"),
    "education": ("cours", "course", "learn", "apprendre", "education", "école", "formation", "tutorial", "tuto"),
    "science": ("science", "espace", "space", "physique", "biologie", "recherche"),
    "sports": ("sport", "foot", "football", "basket", "nba", "ligue", "match", "fitness training"),
    "health_fitness": ("health", "santé", "fitness", "musculation", "workout", "nutrition", "wellness", "gym"),
    "beauty_fashion": ("beauty", "beauté", "fashion", "mode", "makeup", "maquillage", "style"),
    "food": ("food", "cuisine", "recette", "recipe", "restaurant", "cooking"),
    "travel": ("travel", "voyage", "tourism", "tourisme", "trip"),
    "art_design": ("art", "design", "dessin", "illustration", "graphisme"),
    "photography": ("photo", "photography", "photographie"),
    "books_literature": ("book", "livre", "literature", "littérature", "roman", "poésie", "poem"),
    "humor_memes": ("meme", "mème", "humour", "humor", "joke", "blague", "comedy"),
    "lifestyle": ("lifestyle", "vie quotidienne", "daily life", "motivation", "citations", "quotes"),
    "family_kids": ("famille", "family", "enfant", "kids", "parenting", "maman", "papa"),
    "spirituality": ("islam", "coran", "quran", "bible", "église", "spiritualit", "religion", "priere", "prière", "dua"),
    "politics": ("politi", "gouvernement", "government", "élection", "election"),
    "automotive": ("auto", "voiture", "car ", "moto", "tuning"),
    "real_estate": ("immobilier", "real estate", "immo", "appartement", "logement"),
    "adult": ("adulte", "adult", "nsfw", "18+", "xxx", "onlyfans"),
}


def keyword_categorize(name: str, description: str | None = None) -> str | None:
    """Score name/description against the keyword dictionary. Returns the
    best-scoring category, or None if nothing matched at all."""
    haystack = f" {name} {description or ''} ".lower()
    best_category: str | None = None
    best_score = 0
    for category, keywords in _KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in haystack)
        if score > best_score:
            best_score = score
            best_category = category
    return best_category


async def ai_categorize(name: str, description: str | None = None) -> str | None:
    """Ask the AI to pick one category from CHANNEL_CATEGORIES. Never raises
    to the caller — a classification miss just leaves category unset."""
    if not openrouter_service.is_configured():
        return None
    allowed = ", ".join(CHANNEL_CATEGORIES)
    prompt = (
        "Pick exactly one category for this Telegram channel from this list, "
        f"and reply with only that exact word, nothing else: {allowed}.\n\n"
        f"Channel name: {name}\nDescription: {description or '(none)'}"
    )
    try:
        text, _ = await openrouter_service._chat(  # noqa: SLF001 — internal reuse
            [
                {"role": "system", "content": "You are a strict single-label classifier. Reply with one word only."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
            max_tokens=10,
        )
    except Exception as exc:  # pragma: no cover — best-effort fallback
        logger.warning("ai_categorize.failed error=%s", exc)
        return None
    picked = re.sub(r"[^a-z_]", "", (text or "").strip().lower())
    return picked if picked in CHANNEL_CATEGORIES else None


async def detect_category(name: str, description: str | None = None) -> tuple[str | None, str]:
    """Full pipeline. Returns ``(category, source)`` where source is
    ``"keywords"``, ``"ai"`` or ``"none"``."""
    hit = keyword_categorize(name, description)
    if hit:
        return hit, "keywords"
    hit = await ai_categorize(name, description)
    if hit:
        return hit, "ai"
    return None, "none"
