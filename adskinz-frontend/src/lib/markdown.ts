/**
 * Validation (not rendering) of the lenient Markdown subset AdsKinz accepts
 * in ad copy: **bold**/__bold__, *italic*/_italic_, `code`, [label](url).
 *
 * This mirrors app/core/markdown.py on the backend so the advertiser gets
 * the exact same "here's what's wrong" message before they even submit,
 * instead of only finding out from the API error. It only points at the
 * first problem — fixing it and re-checking surfaces the next one.
 */

export interface MarkdownIssue {
  message: string;
  position: number;
  snippet: string;
}

function excerpt(text: string, position: number, radius = 18): string {
  const start = Math.max(0, position - radius);
  const end = Math.min(text.length, position + radius);
  const prefix = start > 0 ? "…" : "";
  const suffix = end < text.length ? "…" : "";
  return `${prefix}${text.slice(start, end)}${suffix}`;
}

const MARKER_LABEL: Record<string, string> = {
  "**": "gras (**...**)",
  "__": "gras (__...__)",
  "*": "italique (*...*)",
  "_": "italique (_..._)",
  "`": "code (`...`)",
};

export function findMarkdownIssue(text: string): MarkdownIssue | null {
  let i = 0;
  const length = text.length;
  const stack: Array<[string, number]> = [];

  while (i < length) {
    const two = text.slice(i, i + 2);
    if (two === "**" || two === "__") {
      const top = stack[stack.length - 1];
      if (top && top[0] === two) stack.pop();
      else stack.push([two, i]);
      i += 2;
      continue;
    }

    const ch = text[i];
    if (ch === "`") {
      const top = stack[stack.length - 1];
      if (top && top[0] === "`") stack.pop();
      else stack.push(["`", i]);
      i += 1;
      continue;
    }

    if (ch === "*" || ch === "_") {
      const top = stack[stack.length - 1];
      if (top && top[0] === ch) stack.pop();
      else stack.push([ch, i]);
      i += 1;
      continue;
    }

    if (ch === "[") {
      const close = text.indexOf("]", i + 1);
      if (close === -1) {
        return {
          message: 'Lien Markdown non fermé : "[" sans "]" correspondant.',
          position: i,
          snippet: excerpt(text, i),
        };
      }
      if (close + 1 >= length || text[close + 1] !== "(") {
        return {
          message: 'Lien Markdown incomplet : il manque "(url)" juste après "[texte]".',
          position: i,
          snippet: excerpt(text, i),
        };
      }
      const endParen = text.indexOf(")", close + 2);
      if (endParen === -1) {
        return {
          message: 'Lien Markdown non fermé : "(" sans ")" correspondant.',
          position: close + 1,
          snippet: excerpt(text, close + 1),
        };
      }
      const linkUrl = text.slice(close + 2, endParen);
      if (!linkUrl.startsWith("http://") && !linkUrl.startsWith("https://")) {
        return {
          message: 'Le lien doit commencer par "https://" (ou "http://").',
          position: close + 2,
          snippet: excerpt(text, close + 2),
        };
      }
      i = endParen + 1;
      continue;
    }

    i += 1;
  }

  if (stack.length > 0) {
    const [marker, pos] = stack[0];
    return {
      message: `Marqueur ${MARKER_LABEL[marker]} ouvert mais jamais refermé.`,
      position: pos,
      snippet: excerpt(text, pos),
    };
  }

  return null;
}

/** Returns a ready-to-display error string, or null when the text is clean. */
export function validateAdMarkdown(text: string): string | null {
  const issue = findMarkdownIssue(text);
  if (!issue) return null;
  return `${issue.message} — près de : "${issue.snippet}"`;
}
