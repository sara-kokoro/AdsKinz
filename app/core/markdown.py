"""Validation of the lenient Markdown subset accepted in ad copy.

This is deliberately a *validator*, not the renderer: it never fixes
anything, it points at the first problem so the advertiser can fix it
themselves before submitting. The bot's own renderer
(``app.bot.aiogram_bot._markdown_to_telegram_html``) stays tolerant at
posting time and simply leaves any stray marker as a literal character —
this module is what gives the advertiser an actual error message instead
of a silently-broken bold/italic span.

Only ``*_ ``/``__``, ``*``/``_`` and inline ``` ` ``` are checked for
balance; ``[label](url)`` links are checked for a matching close.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_MARKERS = ("**", "__", "`")
_LINK_OPEN = "["


@dataclass
class MarkdownIssue:
    message: str
    position: int  # 0-based character offset into the original text
    snippet: str  # short excerpt around the problem, for display


def _excerpt(text: str, position: int, radius: int = 18) -> str:
    start = max(0, position - radius)
    end = min(len(text), position + radius)
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(text) else ""
    return f"{prefix}{text[start:end]}{suffix}"


def find_markdown_issue(text: str) -> MarkdownIssue | None:
    """Return the first Markdown problem in ``text``, or ``None`` if clean.

    Scans left to right so the reported position is always the *first*
    thing to fix — fixing it and re-checking will surface the next one,
    which is the pattern the advertiser-facing form uses.
    """
    i = 0
    length = len(text)
    stack: list[tuple[str, int]] = []  # (marker, position) currently open

    while i < length:
        # Two-char markers first so "**" isn't mistaken for two "*".
        two = text[i : i + 2]
        if two in ("**", "__"):
            if stack and stack[-1][0] == two:
                stack.pop()
            else:
                stack.append((two, i))
            i += 2
            continue

        ch = text[i]
        if ch == "`":
            if stack and stack[-1][0] == "`":
                stack.pop()
            else:
                stack.append(("`", i))
            i += 1
            continue

        if ch in ("*", "_"):
            if stack and stack[-1][0] == ch:
                stack.pop()
            else:
                stack.append((ch, i))
            i += 1
            continue

        if ch == "[":
            close = text.find("]", i + 1)
            if close == -1:
                return MarkdownIssue(
                    message=f'Lien Markdown non fermé : "[" sans "]" correspondant.',
                    position=i,
                    snippet=_excerpt(text, i),
                )
            if close + 1 >= length or text[close + 1] != "(":
                return MarkdownIssue(
                    message='Lien Markdown incomplet : il manque "(url)" juste après "[texte]".',
                    position=i,
                    snippet=_excerpt(text, i),
                )
            end_paren = text.find(")", close + 2)
            if end_paren == -1:
                return MarkdownIssue(
                    message='Lien Markdown non fermé : "(" sans ")" correspondant.',
                    position=close + 1,
                    snippet=_excerpt(text, close + 1),
                )
            url = text[close + 2 : end_paren]
            if not url.startswith(("http://", "https://")):
                return MarkdownIssue(
                    message='Le lien doit commencer par "https://" (ou "http://").',
                    position=close + 2,
                    snippet=_excerpt(text, close + 2),
                )
            i = end_paren + 1
            continue

        i += 1

    if stack:
        marker, pos = stack[0]
        label = {
            "**": "gras (**...**)",
            "__": "gras (__...__)",
            "*": "italique (*...*)",
            "_": "italique (_..._)",
            "`": "code (`...`)",
        }[marker]
        return MarkdownIssue(
            message=f'Marqueur {label} ouvert mais jamais refermé.',
            position=pos,
            snippet=_excerpt(text, pos),
        )

    return None


def validate_ad_markdown(text: str) -> None:
    """Raise ``ValueError`` with a precise, user-facing message if the
    advertiser's Markdown is malformed. No-op on clean text."""
    issue = find_markdown_issue(text)
    if issue is not None:
        raise ValueError(f'{issue.message} — près de : "{issue.snippet}"')
