/**
 * Hand-authored inline SVG artwork used across the campaign (advertiser) and
 * publisher surfaces. Every colour comes from design-system tokens via
 * `currentColor` and the token utility classes — no hardcoded palette values.
 */
import type { SVGProps } from "react";
import { cn } from "@/lib/utils";

type Art = SVGProps<SVGSVGElement> & { className?: string };

const base = "h-auto w-full max-w-[360px]";

/** Campaign broadcast: a post fanning out to channel audiences. */
export function ArtCampaignBroadcast({ className, ...p }: Art) {
  return (
    <svg viewBox="0 0 360 200" role="img" aria-label="A campaign post reaching Telegram channels" className={cn(base, className)} {...p}>
      <defs>
        <linearGradient id="ak-broadcast" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="currentColor" stopOpacity="0.35" />
          <stop offset="100%" stopColor="currentColor" stopOpacity="0.05" />
        </linearGradient>
      </defs>
      <g className="text-signal">
        <rect x="16" y="40" width="128" height="120" rx="16" fill="url(#ak-broadcast)" stroke="currentColor" strokeOpacity="0.4" />
        <rect x="32" y="56" width="96" height="40" rx="10" fill="currentColor" fillOpacity="0.25" />
        <rect x="32" y="106" width="72" height="8" rx="4" fill="currentColor" fillOpacity="0.55" />
        <rect x="32" y="122" width="52" height="8" rx="4" fill="currentColor" fillOpacity="0.3" />
        <rect x="32" y="140" width="60" height="14" rx="7" fill="currentColor" fillOpacity="0.8" />
      </g>
      <g className="text-paper-dim" stroke="currentColor" strokeOpacity="0.35" strokeDasharray="4 5" fill="none">
        <path d="M148 70 C 200 60, 216 46, 254 44" />
        <path d="M148 100 C 200 100, 216 100, 254 100" />
        <path d="M148 130 C 200 140, 216 154, 254 156" />
      </g>
      <g>
        {[32, 88, 144].map((y, i) => (
          <g key={y} className={i === 1 ? "text-bounty" : "text-signal"}>
            <rect x="256" y={y} width="88" height="44" rx="12" fill="currentColor" fillOpacity="0.12" stroke="currentColor" strokeOpacity="0.35" />
            <circle cx="278" cy={y + 22} r="10" fill="currentColor" fillOpacity="0.5" />
            <rect x="294" y={y + 14} width="38" height="6" rx="3" fill="currentColor" fillOpacity="0.5" />
            <rect x="294" y={y + 26} width="24" height="6" rx="3" fill="currentColor" fillOpacity="0.25" />
          </g>
        ))}
      </g>
    </svg>
  );
}

/** Empty-state artwork for "no campaigns yet". */
export function ArtCampaignEmpty({ className, ...p }: Art) {
  return (
    <svg viewBox="0 0 240 160" role="img" aria-label="No campaigns yet" className={cn("h-auto w-[200px]", className)} {...p}>
      <g className="text-paper-dim">
        <rect x="40" y="28" width="160" height="104" rx="18" fill="currentColor" fillOpacity="0.06" stroke="currentColor" strokeOpacity="0.25" strokeDasharray="6 6" />
        <rect x="62" y="52" width="76" height="10" rx="5" fill="currentColor" fillOpacity="0.25" />
        <rect x="62" y="70" width="48" height="10" rx="5" fill="currentColor" fillOpacity="0.15" />
      </g>
      <g className="text-signal">
        <rect x="62" y="96" width="64" height="20" rx="10" fill="currentColor" fillOpacity="0.25" stroke="currentColor" strokeOpacity="0.4" />
        <circle cx="168" cy="106" r="18" fill="currentColor" fillOpacity="0.15" />
        <path d="M168 98v16M160 106h16" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
      </g>
    </svg>
  );
}

/** Funnel: impressions to clicks, used on campaign analytics. */
export function ArtFunnel({ className, ...p }: Art) {
  return (
    <svg viewBox="0 0 320 160" role="img" aria-label="Impressions narrowing to clicks" className={cn(base, className)} {...p}>
      {[
        { w: 280, o: 0.3 },
        { w: 210, o: 0.45 },
        { w: 140, o: 0.6 },
        { w: 80, o: 0.85 },
      ].map((b, i) => (
        <rect
          key={i}
          x={(320 - b.w) / 2}
          y={16 + i * 34}
          width={b.w}
          height="24"
          rx="12"
          className={i === 3 ? "text-bounty" : "text-signal"}
          fill="currentColor"
          fillOpacity={b.o}
        />
      ))}
    </svg>
  );
}

/** Publisher channel monetization artwork. */
export function ArtChannelPayout({ className, ...p }: Art) {
  return (
    <svg viewBox="0 0 360 200" role="img" aria-label="A Telegram channel earning USDT" className={cn(base, className)} {...p}>
      <g className="text-signal">
        <rect x="20" y="30" width="150" height="140" rx="18" fill="currentColor" fillOpacity="0.08" stroke="currentColor" strokeOpacity="0.35" />
        <circle cx="52" cy="62" r="14" fill="currentColor" fillOpacity="0.45" />
        <rect x="74" y="54" width="70" height="8" rx="4" fill="currentColor" fillOpacity="0.45" />
        <rect x="74" y="68" width="44" height="8" rx="4" fill="currentColor" fillOpacity="0.2" />
        <rect x="38" y="92" width="114" height="30" rx="10" fill="currentColor" fillOpacity="0.18" />
        <rect x="38" y="130" width="114" height="30" rx="10" fill="currentColor" fillOpacity="0.1" />
      </g>
      <g className="text-bounty">
        <path d="M176 100 h44" stroke="currentColor" strokeOpacity="0.5" strokeWidth="2" strokeDasharray="5 5" />
        <path d="M214 94 l10 6 -10 6z" fill="currentColor" fillOpacity="0.7" />
        <circle cx="286" cy="100" r="54" fill="currentColor" fillOpacity="0.1" />
        <circle cx="286" cy="100" r="34" fill="currentColor" fillOpacity="0.18" stroke="currentColor" strokeOpacity="0.45" />
        <text x="286" y="107" textAnchor="middle" fontSize="20" fontWeight="700" fill="currentColor">
          $
        </text>
      </g>
    </svg>
  );
}

/** Publisher Mini App placement artwork. */
export function ArtMiniAppPlacement({ className, ...p }: Art) {
  return (
    <svg viewBox="0 0 360 200" role="img" aria-label="An interstitial ad inside a Telegram Mini App" className={cn(base, className)} {...p}>
      <g className="text-paper-dim">
        <rect x="112" y="14" width="136" height="172" rx="22" fill="currentColor" fillOpacity="0.06" stroke="currentColor" strokeOpacity="0.3" />
        <rect x="158" y="24" width="44" height="6" rx="3" fill="currentColor" fillOpacity="0.35" />
      </g>
      <g className="text-signal">
        <rect x="126" y="44" width="108" height="86" rx="14" fill="currentColor" fillOpacity="0.2" stroke="currentColor" strokeOpacity="0.4" />
        <rect x="140" y="60" width="80" height="34" rx="8" fill="currentColor" fillOpacity="0.35" />
        <rect x="140" y="102" width="52" height="8" rx="4" fill="currentColor" fillOpacity="0.5" />
        <rect x="140" y="116" width="80" height="0" rx="4" fill="currentColor" />
      </g>
      <g className="text-bounty">
        <rect x="126" y="140" width="108" height="26" rx="13" fill="currentColor" fillOpacity="0.75" />
        <rect x="152" y="150" width="56" height="6" rx="3" fill="currentColor" fillOpacity="0.35" />
      </g>
      <g className="text-paper-dim" stroke="currentColor" strokeOpacity="0.25" fill="none">
        <path d="M40 60 q28 40 0 80" strokeDasharray="4 6" />
        <path d="M320 60 q-28 40 0 80" strokeDasharray="4 6" />
      </g>
    </svg>
  );
}

/** Trust-building period artwork for freshly approved channels. */
export function ArtTrustPeriod({ className, ...p }: Art) {
  return (
    <svg viewBox="0 0 240 140" role="img" aria-label="Trust-building period in progress" className={cn("h-auto w-[220px]", className)} {...p}>
      <g className="text-bounty">
        <circle cx="120" cy="70" r="48" fill="none" stroke="currentColor" strokeOpacity="0.18" strokeWidth="12" />
        <circle
          cx="120"
          cy="70"
          r="48"
          fill="none"
          stroke="currentColor"
          strokeOpacity="0.8"
          strokeWidth="12"
          strokeLinecap="round"
          strokeDasharray="180 302"
          transform="rotate(-90 120 70)"
        />
        <path d="M120 52v20l14 10" stroke="currentColor" strokeWidth="4" strokeLinecap="round" fill="none" />
      </g>
    </svg>
  );
}

/** Publisher earnings empty state. */
export function ArtPublisherEmpty({ className, ...p }: Art) {
  return (
    <svg viewBox="0 0 240 160" role="img" aria-label="No placements yet" className={cn("h-auto w-[200px]", className)} {...p}>
      <g className="text-paper-dim">
        <rect x="36" y="34" width="76" height="92" rx="14" fill="currentColor" fillOpacity="0.06" stroke="currentColor" strokeOpacity="0.25" strokeDasharray="6 6" />
        <rect x="128" y="34" width="76" height="92" rx="14" fill="currentColor" fillOpacity="0.06" stroke="currentColor" strokeOpacity="0.25" strokeDasharray="6 6" />
      </g>
      <g className="text-signal">
        <circle cx="74" cy="80" r="14" fill="currentColor" fillOpacity="0.2" />
        <path d="M74 72v16M66 80h16" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
        <circle cx="166" cy="80" r="14" fill="currentColor" fillOpacity="0.2" />
        <path d="M166 72v16M158 80h16" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
      </g>
    </svg>
  );
}
