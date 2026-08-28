import type { ReactNode } from "react";
import { BudgetBar, StatusPill, fmtInt, fmtMoney } from "@/components/kit";
import { cn } from "@/lib/utils";

/** Gradient monogram avatar used in every placement / user list. */
export function Avatar({ name, size = 44, src }: { name: string; size?: number; src?: string | null }) {
  if (src) {
    return (
      <img
        src={src}
        alt=""
        width={size}
        height={size}
        className="shrink-0 rounded-full object-cover"
        style={{ width: size, height: size }}
      />
    );
  }
  return (
    <div
      className="grad-avatar num flex shrink-0 items-center justify-center rounded-full font-bold"
      style={{ width: size, height: size, fontSize: size * 0.36 }}
      aria-hidden
    >
      {name.trim().slice(0, 1).toUpperCase()}
    </div>
  );
}

/** Compact metric column used inside cards. */
export function Metric({ label, value, tone }: { label: string; value: string; tone?: "bounty" | "success" | undefined }) {
  return (
    <div className="min-w-0">
      <p className="text-[10px] font-semibold tracking-wide text-paper-dim uppercase">{label}</p>
      <p className={cn("num mt-1 truncate text-base font-bold", tone === "bounty" && "text-bounty", tone === "success" && "text-success")}>
        {value}
      </p>
    </div>
  );
}

/**
 * Telegram-app style placement row: gradient avatar, handle, subscribers and
 * earnings, with a chevron affordance. Used for channels and Mini Apps.
 */
export function PlacementCard({
  name,
  handle,
  status,
  people,
  peopleLabel,
  earnings,
  onOpen,
}: {
  name: string;
  handle: string;
  status: string;
  people: number;
  peopleLabel: string;
  earnings: number;
  onOpen: () => void;
}) {
  return (
    <button
      onClick={onOpen}
      className="glass flex w-full items-center gap-4 p-4 text-left transition-transform hover:-translate-y-0.5"
    >
      <Avatar name={name} size={52} />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <p className="truncate font-display text-base font-bold">{name}</p>
          <StatusPill status={status} />
        </div>
        <p className="num truncate text-xs text-paper-dim">{handle}</p>
        <p className="num mt-1.5 flex items-center gap-3 text-sm">
          <span className="text-paper-dim">
            {fmtInt(people)} {peopleLabel}
          </span>
          <span className="font-bold text-success">{fmtMoney(earnings)}</span>
        </p>
      </div>
      <span className="text-paper-dim" aria-hidden>
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
          <path d="m9 6 6 6-6 6" />
        </svg>
      </span>
    </button>
  );
}

/** Campaign card: status, three metrics, gradient budget bar and two actions. */
export function CampaignCard({
  name,
  status,
  views,
  clicks,
  spent,
  budget,
  labels,
  actions,
}: {
  name: string;
  status: string;
  views: number;
  clicks: number;
  spent: number;
  budget: number;
  labels: { views: string; clicks: string; budget: string };
  actions?: ReactNode;
}) {
  return (
    <div className="glass space-y-4 p-4">
      <div className="flex items-start justify-between gap-3">
        <StatusPill status={status} />
      </div>
      <h3 className="font-display text-lg font-bold">{name}</h3>
      <div className="glass-2 grid grid-cols-3 gap-3 p-3">
        <Metric label={labels.views} value={fmtInt(views)} />
        <Metric label={labels.clicks} value={fmtInt(clicks)} />
        <Metric label={labels.budget} value={`${fmtMoney(spent, 0)} / ${fmtMoney(budget, 0)}`} tone="bounty" />
      </div>
      <BudgetBar used={spent} total={budget} />
      {actions && <div className="grid grid-cols-2 gap-3">{actions}</div>}
    </div>
  );
}

/** Pill segmented control (tabs / filters). */
export function Segmented<T extends string>({
  value,
  onChange,
  options,
  className,
}: {
  value: T;
  onChange: (v: T) => void;
  options: { v: T; l: string; badge?: number }[];
  className?: string;
}) {
  return (
    <div className={cn("glass-2 inline-flex flex-wrap gap-1 p-1", className)}>
      {options.map((o) => (
        <button
          key={o.v}
          onClick={() => onChange(o.v)}
          aria-pressed={value === o.v}
          className={cn(
            "inline-flex min-h-9 items-center gap-1.5 rounded-[10px] px-3 text-xs font-bold transition-colors",
            value === o.v ? "bg-panel text-signal shadow-sm" : "text-paper-dim hover:text-paper",
          )}
        >
          {o.l}
          {o.badge !== undefined && o.badge > 0 && (
            <span className="num rounded-full bg-signal-soft px-1.5 py-0.5 text-[10px] text-signal">{o.badge}</span>
          )}
        </button>
      ))}
    </div>
  );
}
