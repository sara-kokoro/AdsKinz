import { cn } from "@/lib/utils";
import { trackingUrl } from "@/lib/api";

/** Faithful preview of how a native post renders inside Telegram. */
export function TelegramPostPreview({
  channel = "Crypto Signals Daily",
  title,
  brandName,
  copy,
  buttonLabel,
  imageAlt,
  imageUrl = null,
  trackingId,
  showAdTag = true,
  className,
}: {
  channel?: string;
  title?: string | null;
  brandName?: string | null;
  copy: string;
  buttonLabel: string;
  imageAlt?: string | undefined;
  imageUrl?: string | null;
  trackingId?: string;
  showAdTag?: boolean;
  className?: string;
}) {
  return (
    <div className={cn("surface-2 max-w-md overflow-hidden p-0", className)}>
      <div className="flex items-center gap-3 border-b border-seam px-4 py-3">
        <div className="num flex size-9 items-center justify-center rounded-full bg-signal-soft text-xs font-bold text-signal">
          {channel.slice(0, 2).toUpperCase()}
        </div>
        <div className="min-w-0">
          <p className="truncate text-sm font-bold">{channel}</p>
          <p className="text-xs text-paper-dim">Telegram channel</p>
        </div>
        {showAdTag && (
          <span className="ml-auto rounded-md border border-seam px-1.5 py-0.5 text-[10px] font-semibold text-paper-dim">
            Ad
          </span>
        )}
      </div>
      {imageUrl ? (
        <img src={imageUrl} alt={imageAlt ?? "Creative image"} className="aspect-[16/9] w-full border-b border-seam object-cover" />
      ) : (
        <div className="flex aspect-[16/9] items-center justify-center border-b border-seam bg-panel px-4 text-center text-xs text-paper-dim">
          {imageAlt ?? "Creative image"}
        </div>
      )}
      <div className="space-y-3 p-4">
        {(title || brandName) && (
          <div className="flex items-baseline justify-between gap-3">
            {title && <p className="text-base leading-snug font-bold">{title}</p>}
            {brandName && <p className="shrink-0 text-xs font-semibold text-paper-dim">{brandName}</p>}
          </div>
        )}
        <p className="text-sm leading-relaxed whitespace-pre-wrap">{copy}</p>
        <div className="rounded-xl bg-signal py-2.5 text-center text-sm font-bold text-white">{buttonLabel}</div>
        {trackingId && (
          <p className="num text-[11px] break-all text-paper-dim">{trackingUrl(trackingId)}</p>
        )}
      </div>
    </div>
  );
}
