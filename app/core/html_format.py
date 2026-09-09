"""Validation and sanitisation of the HTML subset Telegram's Bot API accepts
in message text / captions (``parse_mode=HTML``).

This replaces the earlier Markdown-based ad copy format: the advertiser-facing
editor now has a formatting toolbar (bold / italic / blockquote / spoiler)
that inserts real HTML tags around the current selection, so what the
advertiser types *is* what gets sent to Telegram — no conversion step.

Two entry points:
  - ``validate_ad_html`` — used at submit time (schemas/advertiser.py) to
    reject malformed input with a message that points at the exact problem,
    the same way the old Markdown validator did, so the advertiser can fix
    it themselves before the campaign goes to review.
  - ``sanitize_telegram_html`` — used at posting time (aiogram_bot.py) as a
    defensive last line: strips anything outside Telegram's whitelist so a
    post can never fail with a Bot API "can't parse entities" error, even if
    something bypassed the submit-time validation (an old campaign row from
    before this change, a direct API call, etc).
"""

from __future__ import annotations

import html as _html
from dataclasses import dataclass
from html.parser import HTMLParser

# Telegram Bot API HTML whitelist (message text / captions), trimmed to the
# tags this editor's toolbar can actually produce plus a few common aliases
# advertisers might type by hand. See:
# https://core.telegram.org/bots/api#html-style
_ALLOWED_TAGS = {
    "b", "strong",
    "i", "em",
    "u", "ins",
    "s", "strike", "del",
    "a",
    "code",
    "pre",
    "blockquote",
    "span",
}
# Self-closing / void tags are not part of Telegram's set at all — anything
# not in _ALLOWED_TAGS is stripped (tag removed, inner text kept).
_ALLOWED_ATTRS: dict[str, set[str]] = {
    "a": {"href"},
    "blockquote": {"expandable"},
    "span": {"class"},
}


@dataclass
class HtmlIssue:
    message: str
    position: int
    snippet: str


def _excerpt(text: str, position: int, radius: int = 18) -> str:
    start = max(0, position - radius)
    end = min(len(text), position + radius)
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(text) else ""
    return f"{prefix}{text[start:end]}{suffix}"


class _ValidatingParser(HTMLParser):
    """Walks the input once, recording the first structural problem found."""

    def __init__(self, source: str) -> None:
        super().__init__(convert_charrefs=True)
        self.source = source
        self.stack: list[tuple[str, int]] = []
        self.issue: HtmlIssue | None = None

    def _pos(self) -> int:
        line, col = self.getpos()
        # Cheap line/col -> offset: fine for single-line ad copy (the
        # overwhelming case) and still a reasonable approximation otherwise.
        lines = self.source.split("\n")
        return sum(len(l) + 1 for l in lines[: line - 1]) + col

    def _fail(self, message: str) -> None:
        if self.issue is not None:
            return
        pos = self._pos()
        self.issue = HtmlIssue(message=message, position=pos, snippet=_excerpt(self.source, pos))

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self.issue is not None:
            return
        if tag not in _ALLOWED_TAGS:
            self._fail(
                f'Balise "<{tag}>" non supportée par Telegram — utilise les '
                "boutons de la barre d'outils (gras, italique, citation, spoiler)."
            )
            return
        allowed_attrs = _ALLOWED_ATTRS.get(tag, set())
        for name, value in attrs:
            if name not in allowed_attrs:
                self._fail(f'Attribut "{name}" non autorisé sur "<{tag}>".')
                return
            if tag == "a" and name == "href":
                if not value or not value.startswith(("http://", "https://")):
                    self._fail('Le lien doit commencer par "https://" (ou "http://").')
                    return
            if tag == "span" and name == "class" and value != "tg-spoiler":
                self._fail('Sur "<span>", seule la classe "tg-spoiler" (spoiler) est autorisée.')
                return
        self.stack.append((tag, self._pos()))

    def handle_endtag(self, tag: str) -> None:
        if self.issue is not None:
            return
        if tag not in _ALLOWED_TAGS:
            return  # already reported (or silently ignorable) at the start tag
        if not self.stack:
            self._fail(f'Balise fermante "</{tag}>" sans balise ouvrante correspondante.')
            return
        open_tag, open_pos = self.stack[-1]
        if open_tag != tag:
            self._fail(
                f'"<{open_tag}>" ouverte n\'est jamais refermée avant "</{tag}>".'
            )
            return
        self.stack.pop()

    def error(self, message: str) -> None:  # pragma: no cover - py3.10+ never calls this
        self._fail(message)


def find_html_issue(text: str) -> HtmlIssue | None:
    """First formatting problem in ``text``, or ``None`` if it's clean and
    fully balanced. Fixing one and re-checking surfaces the next."""
    parser = _ValidatingParser(text)
    try:
        parser.feed(text)
        parser.close()
    except Exception:  # noqa: BLE001 - malformed input, not a bug in the parser
        return HtmlIssue(
            message="Ce formatage n'est pas valide.", position=0, snippet=_excerpt(text, 0)
        )
    if parser.issue is not None:
        return parser.issue
    if parser.stack:
        tag, pos = parser.stack[0]
        return HtmlIssue(
            message=f'Balise "<{tag}>" ouverte mais jamais refermée.',
            position=pos,
            snippet=_excerpt(text, pos),
        )
    return None


def validate_ad_html(text: str) -> None:
    """Raise ``ValueError`` with a precise, user-facing message if the
    advertiser's HTML is malformed or uses anything outside Telegram's
    whitelist. No-op on clean text."""
    issue = find_html_issue(text)
    if issue is not None:
        raise ValueError(f'{issue.message} — près de : "{issue.snippet}"')


class _SanitizingParser(HTMLParser):
    """Best-effort rebuild: keeps only whitelisted tags/attrs, escapes text,
    silently drops anything else instead of raising. Used at posting time as
    a defensive net — validation should already have caught real problems."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.stack: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag not in _ALLOWED_TAGS:
            return
        allowed_attrs = _ALLOWED_ATTRS.get(tag, set())
        kept = []
        for name, value in attrs:
            if name not in allowed_attrs or value is None:
                continue
            if tag == "a" and name == "href" and not value.startswith(("http://", "https://")):
                continue
            if tag == "span" and name == "class" and value != "tg-spoiler":
                continue
            kept.append(f'{name}="{_html.escape(value, quote=True)}"')
        attr_str = (" " + " ".join(kept)) if kept else ""
        self.out.append(f"<{tag}{attr_str}>")
        self.stack.append(tag)

    def handle_endtag(self, tag: str) -> None:
        if tag not in _ALLOWED_TAGS or tag not in self.stack:
            return
        # Close any unclosed inner tags first so output nests correctly.
        while self.stack and self.stack[-1] != tag:
            self.out.append(f"</{self.stack.pop()}>")
        if self.stack:
            self.stack.pop()
            self.out.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        self.out.append(_html.escape(data))

    def get_html(self) -> str:
        # Close whatever is still open, innermost first.
        while self.stack:
            self.out.append(f"</{self.stack.pop()}>")
        return "".join(self.out)


def sanitize_telegram_html(text: str) -> str:
    """Best-effort: return ``text`` with only Telegram's whitelisted tags
    kept, everything else stripped or escaped. Never raises."""
    parser = _SanitizingParser()
    try:
        parser.feed(text)
        parser.close()
        return parser.get_html()
    except Exception:  # noqa: BLE001 - fall back to fully-escaped plain text
        return _html.escape(text)
