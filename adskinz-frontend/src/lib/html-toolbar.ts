/**
 * Formatting toolbar logic for the ad copy editor: wraps (or unwraps) the
 * current text-selection in a Telegram-HTML tag, the way a rich-text editor
 * toolbar button would — except the underlying value stays plain text
 * containing real HTML tags (that's what the backend expects, see
 * app/core/html_format.py and AD_TEXT_MAX_LENGTH).
 *
 * Pure string logic, no DOM dependency, so it's usable from any textarea
 * wrapper: caller supplies the current value and selection range (from the
 * native <textarea> selectionStart/selectionEnd), gets back the new value
 * and where the selection should land afterwards.
 */

export type ToolbarFormat = "bold" | "italic" | "blockquote" | "spoiler";

const TAGS: Record<ToolbarFormat, { open: string; close: string }> = {
  bold: { open: "<b>", close: "</b>" },
  italic: { open: "<i>", close: "</i>" },
  blockquote: { open: "<blockquote>", close: "</blockquote>" },
  spoiler: { open: '<span class="tg-spoiler">', close: "</span>" },
};

export interface ToolbarResult {
  value: string;
  selectionStart: number;
  selectionEnd: number;
}

/**
 * Applies `format` to `value` around [selStart, selEnd).
 *
 * - If the selection is already wrapped in exactly that tag, unwraps it
 *   (toggle behaviour — click Bold again on bold text to remove it).
 * - If there's a selection, wraps just the selected text.
 * - If there's no selection (cursor only), inserts an empty pair and puts
 *   the cursor between the tags, ready to type.
 */
export function applyToolbarFormat(
  value: string,
  selStart: number,
  selEnd: number,
  format: ToolbarFormat,
): ToolbarResult {
  const { open, close } = TAGS[format];
  const before = value.slice(0, selStart);
  const selected = value.slice(selStart, selEnd);
  const after = value.slice(selEnd);

  const alreadyWrapped =
    before.endsWith(open) && after.startsWith(close);
  if (alreadyWrapped) {
    const newValue =
      before.slice(0, before.length - open.length) + selected + after.slice(close.length);
    const newStart = selStart - open.length;
    return { value: newValue, selectionStart: newStart, selectionEnd: newStart + selected.length };
  }

  const newValue = before + open + selected + close + after;
  if (selStart === selEnd) {
    // No selection: place the cursor right between the tags.
    const cursor = selStart + open.length;
    return { value: newValue, selectionStart: cursor, selectionEnd: cursor };
  }
  return {
    value: newValue,
    selectionStart: selStart + open.length,
    selectionEnd: selStart + open.length + selected.length,
  };
}

/**
 * Wraps the selection in a link: `<a href="URL">selected text</a>`.
 * If there's no selection, the URL itself becomes the link text too.
 */
export function applyToolbarLink(
  value: string,
  selStart: number,
  selEnd: number,
  url: string,
): ToolbarResult {
  const before = value.slice(0, selStart);
  const selected = value.slice(selStart, selEnd) || url;
  const after = value.slice(selEnd);
  const open = `<a href="${url}">`;
  const close = "</a>";
  const newValue = before + open + selected + close + after;
  return {
    value: newValue,
    selectionStart: selStart + open.length,
    selectionEnd: selStart + open.length + selected.length,
  };
}
