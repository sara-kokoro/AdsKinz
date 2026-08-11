import usdtAsset from "@/assets/usdt.png.asset.json";
import { cn } from "@/lib/utils";

/** Transparent-background Tether (USDT) mark, used everywhere money moves. */
export function UsdtMark({ size = 20, className }: { size?: number; className?: string }) {
  return (
    <img
      src={usdtAsset.url}
      alt="USDT"
      width={size}
      height={size}
      className={cn("shrink-0 object-contain", className)}
      style={{ width: size, height: size }}
    />
  );
}

export function UsdtBadge({ label, className }: { label: string; className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-1.5 rounded-full border border-seam px-2.5 py-1 text-xs font-semibold", className)}>
      <UsdtMark size={14} />
      {label}
    </span>
  );
}
