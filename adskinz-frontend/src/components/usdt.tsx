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

const NETWORK_LOGOS = {
  ton: "/usdt-gram.png",
  trc20: "/usdt-trc20.png",
  bnb: "/usdt-bnb.png",
} as const;

export type UsdtNetwork = keyof typeof NETWORK_LOGOS;

/** USDT mark with the network-specific badge (TON, TRC20, BNB). Falls back to the plain mark for unknown networks. */
export function NetworkUsdtMark({
  network,
  size = 20,
  className,
}: {
  network: string;
  size?: number;
  className?: string;
}) {
  const src = NETWORK_LOGOS[network as UsdtNetwork];
  if (!src) return <UsdtMark size={size} className={className} />;
  return (
    <img
      src={src}
      alt={`USDT (${network.toUpperCase()})`}
      width={size}
      height={size}
      className={cn("shrink-0 rounded-full object-contain", className)}
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