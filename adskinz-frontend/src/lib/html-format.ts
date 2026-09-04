/**
 * Validation of the Telegram-HTML subset AdsKinz's ad copy editor accepts:
 * <b>/<strong>, <i>/<em>, <u>/<ins>, <s>/<strike>/<del>, <a href="https://...">,
 * <code>, <pre>, <blockquote>, <span class="tg-spoiler">.
 *
 * Mirrors app/core/html_format.py on the backend so the advertiser gets the
 * exact same "here's what's wrong" message before they even submit. This is
 * a validator, not a renderer — the toolbar (see html-toolbar.ts) is what
 * actually inserts tags; this only checks what the advertiser typed or
 * pasted by hand is still well-formed.
 */

export interface HtmlIssue {
  message: string;
  position: number;
  snippet: string;
}

const ALLOWED_TAGS = new Set([
  "b", "strong",
  "i", "em",
  "u", "ins",
  "s", "strike", "del",
  "a",
  "code",
  "pre",
  "blockquote",
  "span",
]);

const ALLOWED_ATTRS: Record<string, Set<string>> = {
  a: new Set(["href"]),
  blockquote: new Set(["expandable"]),
  span: new Set(["class"]),
};

function excerpt(text: string, position: number, radius = 18): string {
  const start = Math.max(0, position - radius);
  const end = Math.min(text.length, position + radius);
  const prefix = start > 0 ? "…" : "";
  const suffix = end < text.length ? "…" : "";
  return `${prefix}${text.slice(start, end)}${suffix}`;
}

// Matches an opening tag "<tag attr="val" ...>", a closing tag "</tag>", or
// a self-closing "<tag ... />" (treated as an ordinary open tag — Telegram
// doesn't use self-closing tags, but a stray "/>" shouldn't crash parsing).
const TAG_RE = /<\/?([a-zA-Z][a-zA-Z0-9]*)((?:\s+[a-zA-Z-]+(?:="[^"]*")?)*)\s*\/?>/g;
const ATTR_RE = /([a-zA-Z-]+)(?:="([^"]*)")?/g;

export function findHtmlIssue(text: string): HtmlIssue | null {
  const stack: Array<[string, number]> = [];
  TAG_RE.lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = TAG_RE.exec(text)) !== null) {
    const full = match[0];
    const tag = match[1].toLowerCase();
    const attrsRaw = match[2] ?? "";
    const isClosing = full.startsWith("</");
    const pos = match.index;

    if (!ALLOWED_TAGS.has(tag)) {
      return {
        message: `Balise "<${tag}>" non supportée par Telegram — utilise les boutons de la barre d'outils (gras, italique, citation, spoiler).`,
        position: pos,
        snippet: excerpt(text, pos),
      };
    }

    if (isClosing) {
      if (stack.length === 0) {
        return {
          message: `Balise fermante "</${tag}>" sans balise ouvrante correspondante.`,
          position: pos,
          snippet: excerpt(text, pos),
        };
      }
      const [openTag] = stack[stack.length - 1];
      if (openTag !== tag) {
        return {
          message: `"<${openTag}>" ouverte n'est jamais refermée avant "</${tag}>".`,
          position: pos,
          snippet: excerpt(text, pos),
        };
      }
      stack.pop();
      continue;
    }

    const allowedAttrs = ALLOWED_ATTRS[tag] ?? new Set<string>();
    ATTR_RE.lastIndex = 0;
    let attrMatch: RegExpExecArray | null;
    while ((attrMatch = ATTR_RE.exec(attrsRaw)) !== null) {
      const name = attrMatch[1].toLowerCase();
      const value = attrMatch[2] ?? "";
      if (!allowedAttrs.has(name)) {
        return {
          message: `Attribut "${name}" non autorisé sur "<${tag}>".`,
          position: pos,
          snippet: excerpt(text, pos),
        };
      }
      if (tag === "a" && name === "href" && !/^https?:\/\//.test(value)) {
        return {
          message: 'Le lien doit commencer par "https://" (ou "http://").',
          position: pos,
          snippet: excerpt(text, pos),
        };
      }
      if (tag === "span" && name === "class" && value !== "tg-spoiler") {
        return {
          message: 'Sur "<span>", seule la classe "tg-spoiler" (spoiler) est autorisée.',
          position: pos,
          snippet: excerpt(text, pos),
        };
      }
    }

    stack.push([tag, pos]);
  }

  if (stack.length > 0) {
    const [tag, pos] = stack[0];
    return {
      message: `Balise "<${tag}>" ouverte mais jamais refermée.`,
      position: pos,
      snippet: excerpt(text, pos),
    };
  }

  return null;
}

/** Returns a ready-to-display error string, or null when the text is clean. */
export function validateAdHtml(text: string): string | null {
  const issue = findHtmlIssue(text);
  if (!issue) return null;
  return `${issue.message} — près de : "${issue.snippet}"`;
}
