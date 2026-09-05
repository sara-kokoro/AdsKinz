import { forwardRef, useEffect, useRef, useState, type ReactNode, type RefObject, type TextareaHTMLAttributes } from "react";
import { useTranslation } from "react-i18next";
import { cn } from "@/lib/utils";
import { uploadCreativeImage } from "@/lib/api";
import { normalizeImageForUpload } from "@/lib/image";
import { applyToolbarFormat, type ToolbarFormat } from "@/lib/html-toolbar";
import { IconAlert, IconCheck, IconEmptyBox, IconImage, IconX } from "@/components/icons";

/* ---------- status system: single source of truth for colour + label ---------- */

export type StatusTone = "signal" | "bounty" | "neutral" | "danger" | "success";

const TONE: Record<StatusTone, { dot: string; text: string; bg: string }> = {
  signal: { dot: "bg-signal", text: "text-signal", bg: "bg-signal-soft" },
  bounty: { dot: "bg-bounty", text: "text-bounty", bg: "bg-bounty-soft" },
  neutral: { dot: "bg-paper-dim", text: "text-paper-dim", bg: "bg-panel-2" },
  danger: { dot: "bg-danger", text: "text-danger", bg: "bg-danger-soft" },
  success: { dot: "bg-success", text: "text-success", bg: "bg-success-soft" },
};

export const STATUS_TONE: Record<string, StatusTone> = {
  pending_review: "bounty",
  active: "signal",
  paused: "neutral",
  paused_balance: "neutral",
  stopped: "neutral",
  rejected: "danger",
  pending_moderation: "bounty",
  approved_not_started: "bounty",
  building_trust: "signal",
  suspended: "danger",
  archived: "neutral",
  pending: "bounty",
  approved: "signal",
  paid: "success",
  awaiting_confirmation: "bounty",
  confirmed: "success",
  in_progress: "bounty",
  swept: "success",
  failed: "danger",
};

export function StatusPill({ status, className }: { status: string; className?: string }) {
  const { t } = useTranslation();
  const tone = TONE[STATUS_TONE[status] ?? "neutral"];
  const withIcon = status === "paused_balance";
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border border-seam px-2.5 py-1 text-xs font-semibold whitespace-nowrap",
        tone.bg,
        tone.text,
        className,
      )}
    >
      <span className={cn("size-1.5 rounded-full", tone.dot)} aria-hidden />
      {t(`status.${status}`)}
      {withIcon && <IconAlert width={12} height={12} />}
    </span>
  );
}

/* ---------- surfaces ---------- */

export function Panel({ className, children, ...rest }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn("surface p-5", className)} {...rest}>
      {children}
    </div>
  );
}

export function SectionTitle({ children, sub }: { children: ReactNode; sub?: ReactNode }) {
  return (
    <div className="mb-4">
      <h2 className="font-display text-xl font-bold tracking-tight">{children}</h2>
      {sub && <p className="mt-1 text-sm text-paper-dim">{sub}</p>}
    </div>
  );
}

/* ---------- numbers ---------- */

export const fmtInt = (n: number) => n.toLocaleString("en-US");
export const fmtMoney = (n: number, d = 2) =>
  `$${n.toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d })}`;

/**
 * Formats a date as YYYY-MM-DD, accepting whatever shape actually shows up
 * at runtime: an ISO string (the normal case), a real Date instance (can
 * happen after SSR/hydration serialisation turns date-looking strings back
 * into Date objects), a unix timestamp, or null/undefined. Never throws —
 * unlike a bare `.slice(0, 10)` call, which assumes the value is always a
 * string and crashes the whole render if it isn't.
 */
/** Accepts an ISO string, a Date, or a numeric epoch in either seconds or
 * milliseconds (auto-detected: anything below ~year-2001-in-ms is treated
 * as seconds and scaled up) — a defensive parse so a backend that ever
 * sends epoch seconds by mistake still renders a sane date instead of
 * silently landing near 1970. */
const toDate = (value: string | number | Date | null | undefined): Date | null => {
  if (!value) return null;
  if (value instanceof Date) return Number.isNaN(value.getTime()) ? null : value;
  let n = value;
  if (typeof value === "string") {
    const asNum = Number(value);
    n = Number.isFinite(asNum) && /^-?\d+$/.test(value.trim()) ? asNum : value;
  }
  if (typeof n === "number") {
    // Unix seconds fit in ~10 digits through year 2286; ms timestamps for
    // any real date are always >= ~1e12. Below that, assume seconds.
    const ms = Math.abs(n) < 1e12 ? n * 1000 : n;
    const d = new Date(ms);
    return Number.isNaN(d.getTime()) ? null : d;
  }
  const d = new Date(n);
  return Number.isNaN(d.getTime()) ? null : d;
};

export const fmtDate = (value: string | number | Date | null | undefined): string => {
  const d = toDate(value);
  return d ? d.toISOString().slice(0, 10) : "—";
};

/** Same as fmtDate but includes the time (UTC, "YYYY-MM-DD HH:MM"). */
export const fmtDateTime = (value: string | number | Date | null | undefined): string => {
  const d = toDate(value);
  if (!d) return "—";
  return d.toISOString().slice(0, 16).replace("T", " ") + " UTC";
};

/** Count-up used only on the two hero metrics. */
export function CountUp({ value, money = false }: { value: number; money?: boolean }) {
  const [n, setN] = useState(0);
  const done = useRef(false);
  useEffect(() => {
    if (done.current) return;
    done.current = true;
    const start = performance.now();
    const tick = (now: number) => {
      const p = Math.min(1, (now - start) / 800);
      setN(value * (1 - Math.pow(1 - p, 3)));
      if (p < 1) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  }, [value]);
  return <span className="num">{money ? fmtMoney(n) : fmtInt(Math.round(n))}</span>;
}

/* ---------- sparkline (context only, never coloured by direction) ---------- */

export function Sparkline({
  points,
  tone = "signal",
  className,
}: {
  points: number[];
  tone?: "signal" | "bounty";
  className?: string;
}) {
  const max = Math.max(...points);
  const min = Math.min(...points);
  const d = points
    .map((p, i) => {
      const x = (i / (points.length - 1)) * 100;
      const y = 30 - ((p - min) / (max - min || 1)) * 26 - 2;
      return `${i === 0 ? "M" : "L"}${x.toFixed(2)} ${y.toFixed(2)}`;
    })
    .join(" ");
  return (
    <svg viewBox="0 0 100 30" preserveAspectRatio="none" className={cn("h-8 w-full", className)} aria-hidden>
      <path d={d} fill="none" stroke={tone === "bounty" ? "var(--bounty)" : "var(--signal)"} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

/* ---------- budget progress: animates width on change ---------- */

export function BudgetBar({ used, total }: { used: number; total: number }) {
  const pct = Math.min(100, (used / total) * 100);
  return (
    <div className="h-[5px] w-full overflow-hidden rounded-full bg-panel-2" role="presentation">
      <div
        className="h-full rounded-full bg-bounty transition-[width] duration-500 ease-out"
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

/* ---------- states ---------- */

export function SkeletonBlock({ className }: { className?: string }) {
  return <div className={cn("animate-pulse rounded-md bg-panel-2", className)} />;
}

export function KpiSkeleton() {
  return (
    <Panel>
      <SkeletonBlock className="h-3.5 w-28" />
      <SkeletonBlock className="mt-4 h-8 w-36" />
      <SkeletonBlock className="mt-4 h-8 w-full" />
      <SkeletonBlock className="mt-3 h-3 w-44" />
    </Panel>
  );
}

export function RowSkeleton({ rows = 4 }: { rows?: number }) {
  return (
    <div className="divide-y divide-seam">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="flex items-center gap-4 px-5 py-4">
          <SkeletonBlock className="h-4 w-48" />
          <SkeletonBlock className="ml-auto h-4 w-20" />
          <SkeletonBlock className="h-4 w-16" />
          <SkeletonBlock className="h-4 w-24" />
        </div>
      ))}
    </div>
  );
}

export function EmptyState({
  title,
  sub,
  action,
  positive = false,
}: {
  title: string;
  sub?: string;
  action?: ReactNode;
  positive?: boolean;
}) {
  return (
    <div className="flex flex-col items-center px-6 py-14 text-center">
      <IconEmptyBox className={positive ? "text-signal" : "text-paper-dim"} />
      <h3 className="mt-4 font-display text-lg font-bold">{title}</h3>
      {sub && <p className="mt-1.5 max-w-sm text-sm text-paper-dim">{sub}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

/** Network / server failure: non-blocking banner, never a modal. */
export function ErrorBanner({ onRetry, message }: { onRetry: () => void; message?: string }) {
  const { t } = useTranslation();
  return (
    <div className="flex flex-wrap items-center gap-3 rounded-xl border border-seam bg-panel-2 px-4 py-3 text-sm">
      <IconAlert className="text-paper-dim" width={16} height={16} />
      <span className="text-paper-dim">{message ?? t("common.loadError")}</span>
      <button
        onClick={onRetry}
        className="ml-auto rounded-lg border border-seam px-3 py-1.5 text-xs font-semibold transition-colors hover:bg-panel"
      >
        {t("common.retry")}
      </button>
    </div>
  );
}

/** Inline field-level validation error. */
export function FieldError({ children }: { children?: ReactNode }) {
  if (!children) return null;
  return <p className="mt-1.5 text-xs font-semibold text-danger">{children}</p>;
}

/* ---------- buttons ---------- */

export function Btn({
  variant = "primary",
  tone = "signal",
  className,
  ...rest
}: React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost";
  tone?: "signal" | "bounty" | "danger" | "ink";
}) {
  const toneBg =
    tone === "bounty"
      ? "bg-bounty text-[#1a1204]"
      : tone === "danger"
        ? "bg-danger text-white"
        : tone === "ink"
          ? "bg-black text-white"
          : "bg-signal text-white";
  return (
    <button
      className={cn(
        "inline-flex min-h-11 items-center justify-center gap-2 rounded-xl px-4 text-sm font-bold transition-all duration-200 disabled:pointer-events-none disabled:opacity-45",
        variant === "primary" && `${toneBg} hover:brightness-110`,
        variant === "secondary" && "border border-seam bg-transparent text-paper hover:bg-panel-2",
        variant === "ghost" && "text-paper hover:bg-panel-2",
        className,
      )}
      {...rest}
    />
  );
}

export function useFakeLoad(ms = 700) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [key, setKey] = useState(0);
  useEffect(() => {
    setLoading(true);
    const id = setTimeout(() => setLoading(false), ms);
    return () => clearTimeout(id);
  }, [ms, key]);
  return { loading, error, retry: () => { setError(false); setKey((k) => k + 1); } };
}

/* ---------- Telegram-style blockquote ---------- */

export type QuoteTone = "signal" | "bounty" | "danger" | "neutral";

const QUOTE_TONE: Record<QuoteTone, { bar: string; bg: string; label: string }> = {
  signal: { bar: "bg-signal", bg: "bg-signal-soft", label: "text-signal" },
  bounty: { bar: "bg-bounty", bg: "bg-bounty-soft", label: "text-bounty" },
  danger: { bar: "bg-danger", bg: "bg-danger-soft", label: "text-danger" },
  neutral: { bar: "bg-paper-dim", bg: "bg-panel-2", label: "text-paper-dim" },
};

/**
 * Telegram-like blockquote: coloured left bar, tinted body, optional caption.
 * Used across the advertiser and publisher workspaces for inline guidance.
 */
export function Quote({
  children,
  tone = "signal",
  label,
  className,
}: {
  children: ReactNode;
  tone?: QuoteTone | undefined;
  label?: string | undefined;
  className?: string | undefined;
}) {
  const c = QUOTE_TONE[tone];
  return (
    <blockquote className={cn("relative overflow-hidden rounded-xl rounded-l-[6px] py-3 pr-4 pl-4", c.bg, className)}>
      <span className={cn("absolute top-0 bottom-0 left-0 w-[3px] rounded-full", c.bar)} aria-hidden />
      {label && <p className={cn("mb-1 text-[11px] font-bold tracking-wide uppercase", c.label)}>{label}</p>}
      <p className="text-sm leading-relaxed text-paper">{children}</p>
    </blockquote>
  );
}

/* ---------- modal dialog ---------- */

export function Modal({
  open,
  onClose,
  title,
  sub,
  children,
  footer,
  wide = false,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  sub?: string | undefined;
  children: ReactNode;
  footer?: ReactNode | undefined;
  wide?: boolean;
}) {
  const { t } = useTranslation();
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-100 flex items-end justify-center overflow-y-auto bg-black/60 p-0 backdrop-blur-sm sm:items-center sm:p-6">
      <button className="absolute inset-0 cursor-default" aria-label={t("common.close")} onClick={onClose} />
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={cn(
          "surface relative my-0 w-full rounded-b-none p-0 sm:my-6 sm:rounded-2xl",
          wide ? "max-w-3xl" : "max-w-xl",
        )}
      >
        <div className="flex items-start gap-4 border-b border-seam p-5">
          <div className="min-w-0">
            <h2 className="font-display text-lg font-bold tracking-tight">{title}</h2>
            {sub && <p className="mt-1 text-sm text-paper-dim">{sub}</p>}
          </div>
          <button
            onClick={onClose}
            aria-label={t("common.close")}
            className="ml-auto grid size-9 shrink-0 place-items-center rounded-lg border border-seam transition-colors hover:bg-panel-2"
          >
            <IconX width={16} height={16} />
          </button>
        </div>
        <div className="max-h-[68vh] overflow-y-auto p-5">{children}</div>
        {footer && <div className="flex flex-wrap gap-3 border-t border-seam p-5">{footer}</div>}
      </div>
    </div>
  );
}

/* ---------- form primitives ---------- */

export function Field({
  label,
  hint,
  error,
  htmlFor,
  children,
}: {
  label: string;
  hint?: string | undefined;
  error?: string | undefined;
  htmlFor?: string | undefined;
  children: ReactNode;
}) {
  return (
    <div>
      <label className="text-sm font-semibold" htmlFor={htmlFor}>
        {label}
      </label>
      <div className="mt-2">{children}</div>
      {hint && !error && <p className="mt-1 text-xs text-paper-dim">{hint}</p>}
      <FieldError>{error}</FieldError>
    </div>
  );
}

export const inputCls = (invalid = false) =>
  cn(
    "w-full rounded-xl border bg-transparent p-3 text-sm outline-none transition-colors focus:border-signal",
    invalid ? "border-danger bg-danger-soft text-danger focus:border-danger" : "border-seam",
  );

/** Textarea that grows with its content instead of clipping it inside a
 * fixed-height box (the old `rows={3}` boxes needed an internal scroll to
 * read a full ad copy, which isn't reachable by drag-resize on mobile).
 * Keeps a sensible max-height with its own scrollbar past that point. */
export const AutoTextarea = forwardRef<
  HTMLTextAreaElement,
  {
    value: string;
    onChange: (v: string) => void;
    minRows?: number;
    maxHeight?: number;
    invalid?: boolean;
    className?: string;
  } & Omit<TextareaHTMLAttributes<HTMLTextAreaElement>, "value" | "onChange" | "className">
>(function AutoTextarea(
  { value, onChange, minRows = 3, maxHeight = 320, invalid, className, ...rest },
  forwardedRef,
) {
  const innerRef = useRef<HTMLTextAreaElement>(null);

  const resize = () => {
    const el = innerRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, maxHeight)}px`;
  };

  useEffect(resize, [value]);

  return (
    <textarea
      {...rest}
      ref={(el) => {
        innerRef.current = el;
        if (typeof forwardedRef === "function") forwardedRef(el);
        else if (forwardedRef) forwardedRef.current = el;
      }}
      rows={minRows}
      value={value}
      onChange={(e) => {
        onChange(e.target.value);
        resize();
      }}
      className={cn(inputCls(invalid), "resize-y overflow-y-auto leading-relaxed", className)}
      style={{ maxHeight }}
    />
  );
});

/** Formatting toolbar for an ad-copy textarea: select text, click a button,
 * it wraps the selection in the matching Telegram-HTML tag (or toggles it
 * off if already applied). Needs a ref to the underlying <textarea> — pass
 * the same ref given to AutoTextarea. */
export function HtmlFormatToolbar({
  textareaRef,
  value,
  onChange,
}: {
  textareaRef: RefObject<HTMLTextAreaElement | null>;
  value: string;
  onChange: (v: string) => void;
}) {
  const { t } = useTranslation();

  const apply = (format: ToolbarFormat) => {
    const el = textareaRef.current;
    if (!el) return;
    const { value: newValue, selectionStart, selectionEnd } = applyToolbarFormat(
      value,
      el.selectionStart ?? value.length,
      el.selectionEnd ?? value.length,
      format,
    );
    onChange(newValue);
    // Restore focus + selection after React re-renders the new value.
    requestAnimationFrame(() => {
      el.focus();
      el.setSelectionRange(selectionStart, selectionEnd);
    });
  };

  const buttons: Array<{ format: ToolbarFormat; label: string; title: string; className?: string }> = [
    { format: "bold", label: "B", title: t("adv.wizard.fmtBold"), className: "font-bold" },
    { format: "italic", label: "I", title: t("adv.wizard.fmtItalic"), className: "italic" },
    { format: "blockquote", label: "❝", title: t("adv.wizard.fmtQuote") },
    { format: "spoiler", label: "◐", title: t("adv.wizard.fmtSpoiler") },
  ];

  return (
    <div className="flex gap-1.5" role="toolbar" aria-label={t("adv.wizard.fmtToolbar")}>
      {buttons.map((b) => (
        <button
          key={b.format}
          type="button"
          title={b.title}
          aria-label={b.title}
          onMouseDown={(e) => e.preventDefault()} // keep the textarea selection intact
          onClick={() => apply(b.format)}
          className={cn(
            "flex h-8 w-8 items-center justify-center rounded-lg border border-seam text-sm hover:bg-panel-2",
            b.className,
          )}
        >
          {b.label}
        </button>
      ))}
    </div>
  );
}

/** Drag-and-drop image picker. Uploads directly to object storage via a
 * presigned URL — the value it returns is a real, permanent public URL. */
export function ImageUpload({
  value,
  onChange,
}: {
  value: { url: string; name: string } | null;
  onChange: (v: { url: string; name: string } | null) => void;
}) {
  const { t } = useTranslation();
  const inputRef = useRef<HTMLInputElement>(null);
  const [drag, setDrag] = useState(false);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  const take = async (file?: File) => {
    if (!file) return;
    if (!file.type.startsWith("image/")) return setErr(t("adv.wizard.imageWrongType"));
    if (file.size > 5 * 1024 * 1024) return setErr(t("adv.wizard.imageTooLarge"));
    setErr("");
    setBusy(true);
    try {
      // Always re-encode to JPEG client-side first: normalises formats the
      // backend doesn't accept for direct upload (HEIC/HEIF straight off
      // an Android or iPhone camera) and shrinks the payload for slow
      // connections — both silently produced this exact "upload failed"
      // symptom before.
      const normalized = await normalizeImageForUpload(file);
      const uploaded = await uploadCreativeImage(normalized);
      onChange(uploaded);
    } catch (e) {
      console.error("Image upload failed:", e);
      setErr(t("adv.wizard.imageUploadFailed"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        className="sr-only"
        aria-label={t("adv.wizard.image")}
        onChange={(e) => void take(e.target.files?.[0])}
      />
      {busy ? (
        <div className="flex w-full flex-col items-center gap-1.5 rounded-xl border border-dashed border-seam px-6 py-10 text-center">
          <div className="size-6 animate-spin rounded-full border-2 border-signal border-t-transparent" />
          <span className="text-sm font-semibold">{t("adv.wizard.imageUploading")}</span>
        </div>
      ) : value ? (
        <div className="overflow-hidden rounded-xl border border-seam">
          <img src={value.url} alt={value.name} className="aspect-[16/9] w-full object-cover" />
          <div className="flex items-center gap-3 border-t border-seam p-3">
            <p className="num truncate text-xs text-paper-dim">{value.name}</p>
            <div className="ml-auto flex gap-2">
              <Btn variant="secondary" className="min-h-9 px-3 text-xs" onClick={() => inputRef.current?.click()}>
                {t("adv.wizard.imageReplace")}
              </Btn>
              <Btn variant="ghost" className="min-h-9 px-3 text-xs text-danger" onClick={() => onChange(null)}>
                {t("adv.wizard.imageRemove")}
              </Btn>
            </div>
          </div>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          onDragOver={(e) => {
            e.preventDefault();
            setDrag(true);
          }}
          onDragLeave={() => setDrag(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDrag(false);
            void take(e.dataTransfer.files?.[0]);
          }}
          className={cn(
            "flex w-full flex-col items-center gap-1.5 rounded-xl border border-dashed px-6 py-10 text-center transition-colors",
            drag ? "border-signal bg-signal-soft" : "border-seam hover:bg-panel-2",
          )}
        >
          <IconImage className="text-paper-dim" width={26} height={26} />
          <span className="text-sm font-semibold">{t("adv.wizard.imageDrop")}</span>
          <span className="text-xs text-paper-dim">{t("adv.wizard.imageFormats")}</span>
        </button>
      )}
      <FieldError>{err}</FieldError>
    </div>
  );
}

/** Compact circular logo picker (channel/mini-app avatars) — uploads straight
 * to R2 via the given uploader and hands back only the public URL. */
export function LogoUpload({
  value,
  onChange,
  uploader,
  fallbackLabel,
  size = 64,
}: {
  value: string | null;
  onChange: (url: string | null) => void;
  uploader: (file: File) => Promise<{ url: string; name: string }>;
  fallbackLabel: string;
  size?: number;
}) {
  const { t } = useTranslation();
  const inputRef = useRef<HTMLInputElement>(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  const take = async (file?: File) => {
    if (!file) return;
    if (!file.type.startsWith("image/")) return setErr(t("adv.wizard.imageWrongType"));
    if (file.size > 5 * 1024 * 1024) return setErr(t("adv.wizard.imageTooLarge"));
    setErr("");
    setBusy(true);
    try {
      const normalized = await normalizeImageForUpload(file);
      const uploaded = await uploader(normalized);
      onChange(uploaded.url);
    } catch (e) {
      console.error("Logo upload failed:", e);
      setErr(t("adv.wizard.imageUploadFailed"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex items-center gap-3">
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        className="sr-only"
        onChange={(e) => void take(e.target.files?.[0])}
      />
      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        className="relative flex shrink-0 items-center justify-center overflow-hidden rounded-full border border-dashed border-seam bg-panel-2 transition-colors hover:bg-panel"
        style={{ width: size, height: size }}
      >
        {busy ? (
          <div className="size-5 animate-spin rounded-full border-2 border-signal border-t-transparent" />
        ) : value ? (
          <img src={value} alt="" className="size-full object-cover" />
        ) : (
          <span className="grad-avatar num flex size-full items-center justify-center font-bold" style={{ fontSize: size * 0.36 }}>
            {fallbackLabel.trim().slice(0, 1).toUpperCase() || "?"}
          </span>
        )}
      </button>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap gap-2">
          <Btn variant="secondary" className="min-h-8 px-3 text-xs" onClick={() => inputRef.current?.click()} disabled={busy}>
            {value ? t("adv.wizard.imageReplace") : t("adv.wizard.imageDrop")}
          </Btn>
          {value && (
            <Btn variant="ghost" className="min-h-8 px-3 text-xs text-danger" onClick={() => onChange(null)} disabled={busy}>
              {t("adv.wizard.imageRemove")}
            </Btn>
          )}
        </div>
        <FieldError>{err}</FieldError>
      </div>
    </div>
  );
}

/** Small pill showing whether @AdsKinzBot currently has admin rights on a
 * channel — shared by the channels list and the channel detail screen. */
export function BotBadge({ ok }: { ok: boolean }) {
  const { t } = useTranslation();
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border border-seam px-2.5 py-1 text-[11px] font-semibold",
        ok ? "bg-success-soft text-success" : "bg-danger-soft text-danger",
      )}
    >
      {ok ? <IconCheck width={11} height={11} /> : <IconAlert width={11} height={11} />}
      {ok ? t("pub.detail.botAdmin") : t("pub.detail.botMissing")}
    </span>
  );
}

/** Every UTC half-hour slot in a day, as minute-of-day (0, 30, 60, ...,
 * 1410) with its "HH:MM" label — the exact grid the backend stores
 * (app/schemas/publisher.py:validate_preferred_slots). */
const HALF_HOUR_SLOTS: { minute: number; label: string }[] = Array.from({ length: 48 }, (_, i) => {
  const minute = i * 30;
  const h = Math.floor(minute / 60);
  const m = minute % 60;
  return { minute, label: `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}` };
});

const WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"] as const;

/** Per-weekday posting schedule, built the way the publisher actually asked
 * for it: pick a day from a dropdown, then add UTC half-hour slots one at a
 * time from a second dropdown (up to the channel's own daily ad cap). Chosen
 * slots show as removable chips. A day with nothing picked means "any time
 * that day" — same convention the backend already uses. */
export function WeekSlotsEditor({
  value,
  onChange,
  maxSelectable,
}: {
  value: Record<string, number[]>;
  onChange: (v: Record<string, number[]>) => void;
  /** Caps how many slots can be picked per day — mirrors the channel's own
   * daily ad cap, so a publisher can never pick more slots than they can
   * actually receive ads for. */
  maxSelectable?: number;
}) {
  const { t } = useTranslation();
  const [day, setDay] = useState<(typeof WEEKDAYS)[number]>("mon");
  const [pending, setPending] = useState("");

  const dayMinutes = value[day] ?? [];
  const capped = typeof maxSelectable === "number" && maxSelectable > 0;
  const atCap = capped && dayMinutes.length >= maxSelectable!;
  const available = HALF_HOUR_SLOTS.filter((s) => !dayMinutes.includes(s.minute));

  const addSlot = (minute: number) => {
    if (atCap) return;
    onChange({ ...value, [day]: [...dayMinutes, minute].sort((a, b) => a - b) });
    setPending("");
  };
  const removeSlot = (minute: number) => {
    onChange({ ...value, [day]: dayMinutes.filter((m) => m !== minute) });
  };

  return (
    <div className="space-y-3">
      <div>
        <label className="text-xs font-semibold text-paper-dim">{t("pub.detail.pickDay")}</label>
        <select
          value={day}
          onChange={(e) => setDay(e.target.value as (typeof WEEKDAYS)[number])}
          className="mt-1 w-full rounded-xl border border-seam bg-transparent p-2.5 text-sm"
        >
          {WEEKDAYS.map((d) => {
            const count = (value[d] ?? []).length;
            return (
              <option key={d} value={d}>
                {t(`common.weekday.${d}`)}
                {count ? ` — ${t("pub.detail.hoursSelected", { count })}` : ""}
              </option>
            );
          })}
        </select>
      </div>

      {dayMinutes.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {dayMinutes.map((minute) => {
            const label = HALF_HOUR_SLOTS.find((s) => s.minute === minute)?.label ?? "";
            return (
              <button
                key={minute}
                type="button"
                onClick={() => removeSlot(minute)}
                className="num flex items-center gap-1.5 rounded-lg border border-signal bg-signal-soft px-2.5 py-1 text-xs font-semibold text-signal"
                title={t("common.remove")}
              >
                {label} UTC
                <IconX width={12} height={12} />
              </button>
            );
          })}
        </div>
      )}

      <div>
        <label className="text-xs font-semibold text-paper-dim">
          {atCap ? t("pub.detail.slotCapReached", { max: maxSelectable }) : t("pub.detail.addSlot")}
        </label>
        <select
          value={pending}
          disabled={atCap}
          onChange={(e) => e.target.value && addSlot(Number(e.target.value))}
          className="num mt-1 w-full rounded-xl border border-seam bg-transparent p-2.5 text-sm disabled:opacity-40"
        >
          <option value="">{t("pub.detail.anyHour")}</option>
          {available.map((s) => (
            <option key={s.minute} value={s.minute}>
              {s.label} UTC
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}
