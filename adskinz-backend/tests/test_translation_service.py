"""Unit tests for translation_service — no network, no database.

Google is replaced by a fake translator, and MixRouter by a fake reviewer, so
these tests pin down the guarantees that matter: markup and links survive, a
misbehaving AI review can never corrupt an ad, and one failure is contained.
"""

from __future__ import annotations

import asyncio

import pytest

from app.services import mixrouter_service
from app.services import translation_service as ts

# The JessiKaPay ad that was stuck in the review queue.
AD = (
    "<b>🌍 Et si envoyer de l’argent en Afrique devenait aussi simple "
    "qu’envoyer un message ?</b>\n\n"
    "Avec <b>JessiKaPay</b>, transfère, paie et achète en toute simplicité.\n\n"
    "<b>Fini les barrières entre toi et tes clients. 🔥</b>\n\n"
    '👉 <a href="https://t.me/JessiKaPayBot"><b>Découvrir JessiKaPay maintenant</b></a>'
)


def run(coro):
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def fake_google(monkeypatch):
    """Upper-case "translation": easy to assert on, and it mangles brand names on purpose."""

    monkeypatch.setattr(ts, "_google_translate_sync", lambda text, source, target: text.upper())
    monkeypatch.setattr(ts.settings, "TRANSLATION_AI_REVIEW", False)


# --------------------------------------------------------------------------- #
# Structure preservation
# --------------------------------------------------------------------------- #
def test_markup_links_and_line_breaks_survive():
    sem = asyncio.Semaphore(2)
    out = run(
        ts.translate_html(AD, source="auto", target="en", keep_terms=("JessiKaPay",), sem=sem)
    )
    assert ts.validate_html(AD, out, ("JessiKaPay",)) is None
    assert 'href="https://t.me/JessiKaPayBot"' in out
    assert out.count("\n\n") == AD.count("\n\n")
    assert "SIMPLE" in out  # text really went through the translator


def test_entities_are_unescaped_for_the_translator_and_escaped_back(monkeypatch):
    seen: list[str] = []

    def fake(text, source, target):
        seen.append(text)
        return text + " & <more>"

    monkeypatch.setattr(ts, "_google_translate_sync", fake)
    out = run(
        ts.translate_html(
            "<b>Tom &amp; Jerry rock</b>", source="en", target="fr", keep_terms=(),
            sem=asyncio.Semaphore(1),
        )
    )
    assert seen == ["Tom & Jerry rock"]
    assert "&amp; &lt;more&gt;" in out
    assert ts.validate_html("<b>Tom &amp; Jerry rock</b>", out) is None


def test_protected_terms_overrule_the_translator_for_that_segment(monkeypatch):
    monkeypatch.setattr(ts, "_google_translate_sync", lambda t, s, g: "Contactez le support")
    src = "Write to @AdsKinzHelp today"
    out = run(
        ts.translate_html(src, source="en", target="fr", keep_terms=(), sem=asyncio.Semaphore(1))
    )
    assert out == src  # the @handle was lost, so the original segment is kept


def test_emoji_and_number_only_segments_are_not_sent_to_google(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(ts, "_google_translate_sync", lambda t, s, g: calls.append(t) or t)
    run(
        ts.translate_html(
            "<b>🔥 100%</b>\nHello there", source="en", target="fr", keep_terms=(),
            sem=asyncio.Semaphore(1),
        )
    )
    assert calls == ["Hello there"]


# --------------------------------------------------------------------------- #
# Validation of untrusted (AI) output
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("candidate", "reason"),
    [
        (AD.replace("<b>Fini", "Fini").replace("🔥</b>", "🔥"), "tags_changed"),
        (AD.replace("JessiKaPayBot", "JessiKaPayBotX"), "tags_changed"),
        (AD.replace("Avec <b>JessiKaPay</b>", "Avec <b>JessiKa</b>"), "lost_protected_token"),
        (AD + " <script>", "tags_changed"),
        ("", "empty"),
        (AD.replace("Avec", "Avec 1 < 2"), "unescaped_angle_bracket"),
    ],
)
def test_validate_html_rejects_broken_candidates(candidate, reason):
    problem = ts.validate_html(AD, candidate, ("JessiKaPay",))
    assert problem is not None and problem.startswith(reason)


def test_validate_html_accepts_reworded_text_with_same_markup():
    good = AD.replace("aussi simple", "tout aussi simple")
    assert ts.validate_html(AD, good, ("JessiKaPay",)) is None


# --------------------------------------------------------------------------- #
# AI review: accepted only when it passes validation
# --------------------------------------------------------------------------- #
def _enable_review(monkeypatch, reviewer):
    monkeypatch.setattr(ts.settings, "TRANSLATION_AI_REVIEW", True)
    monkeypatch.setattr(mixrouter_service, "is_configured", lambda: True)
    monkeypatch.setattr(mixrouter_service, "review_translation", reviewer)


def _translate(**kw):
    return run(
        ts.translate_ad(
            text=AD, button_label="Start now", source_lang="fr", google_source="auto",
            target_lang="en", brand_name="JessiKaPay", **kw,
        )
    )


def test_valid_ai_review_is_used(monkeypatch):
    async def reviewer(original, translated, **kw):
        return translated.replace("SIMPLE", "EASY")

    _enable_review(monkeypatch, reviewer)
    result = _translate()
    assert result.reviewed is True
    assert "EASY" in result.text
    assert result.source == ts.SOURCE_MACHINE_REVIEWED


def test_ai_review_that_breaks_tags_is_discarded(monkeypatch):
    async def reviewer(original, translated, **kw):
        return translated.replace("</a>", "")  # drops a closing tag

    _enable_review(monkeypatch, reviewer)
    result = _translate()
    assert result.reviewed is False
    assert result.source == ts.SOURCE_MACHINE
    assert ts.validate_html(AD, result.text, ("JessiKaPay",)) is None


def test_ai_review_that_changes_a_link_is_discarded(monkeypatch):
    async def reviewer(original, translated, **kw):
        return translated.replace("JessiKaPayBot", "SomeOtherBot")

    _enable_review(monkeypatch, reviewer)
    result = _translate()
    assert result.reviewed is False
    assert "JessiKaPayBot" in result.text


def test_ai_review_error_or_timeout_keeps_machine_translation(monkeypatch):
    async def boom(original, translated, **kw):
        raise RuntimeError("mixrouter down")

    _enable_review(monkeypatch, boom)
    assert _translate().reviewed is False

    async def slow(original, translated, **kw):
        await asyncio.sleep(5)

    _enable_review(monkeypatch, slow)
    monkeypatch.setattr(ts.settings, "TRANSLATION_REVIEW_TIMEOUT_SECONDS", 0.05)
    assert _translate().reviewed is False


def test_review_is_skipped_when_mixrouter_is_not_configured(monkeypatch):
    async def reviewer(original, translated, **kw):
        raise AssertionError("must not be called")

    _enable_review(monkeypatch, reviewer)
    monkeypatch.setattr(mixrouter_service, "is_configured", lambda: False)
    assert _translate().reviewed is False


def test_padded_ai_output_is_rejected(monkeypatch):
    async def reviewer(original, translated, **kw):
        return translated + " " + "blah " * 200

    _enable_review(monkeypatch, reviewer)
    assert _translate().reviewed is False


# --------------------------------------------------------------------------- #
# Failures are contained; labels
# --------------------------------------------------------------------------- #
def test_google_failure_raises_so_the_language_is_skipped(monkeypatch):
    def down(text, source, target):
        raise ConnectionError("blocked")

    monkeypatch.setattr(ts, "_google_translate_sync", down)
    monkeypatch.setattr(ts.settings, "TRANSLATION_HTTP_TIMEOUT_SECONDS", 1.0)
    monkeypatch.setattr(asyncio, "sleep", _instant_sleep)
    with pytest.raises(Exception, match="temporarily unavailable"):
        _translate()


async def _instant_sleep(_delay):  # keeps the retry backoff out of the test runtime
    return None


def test_label_failure_falls_back_to_the_original_label(monkeypatch):
    calls = {"n": 0}

    def flaky(text, source, target):
        calls["n"] += 1
        if text == "Start now":
            raise ConnectionError("nope")
        return text

    monkeypatch.setattr(ts, "_google_translate_sync", flaky)
    monkeypatch.setattr(asyncio, "sleep", _instant_sleep)
    result = _translate()
    assert result.button_label == "Start now"
    assert result.text  # the ad text itself was still translated


def test_zh_is_sent_to_google_as_zh_cn():
    assert ts.google_code("zh") == "zh-CN"
    assert ts.google_code("fr") == "fr"
    assert ts.google_code("auto") == "auto"


# --------------------------------------------------------------------------- #
# Source language labelling
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (AD, "fr"),
        ("Send money to Africa as easily as a message. Try it now with your friends!", "en"),
        ("Отправляйте деньги в Африку так же просто, как сообщение", "ru"),
        ("像发消息一样简单地向非洲汇款", "zh"),
        ("🔥🔥🔥", "en"),
    ],
)
def test_detect_language(text, expected):
    assert ts.detect_language(text) == expected


def test_resolve_source_lang_prefers_the_campaign_language():
    assert ts.resolve_source_lang("ru", AD) == "ru"
    assert ts.resolve_source_lang("all", AD) == "fr"
