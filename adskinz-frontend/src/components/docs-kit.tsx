import { useState, type ReactNode } from "react";
import { Link, useRouterState } from "@tanstack/react-router";
import { cn } from "@/lib/utils";
import { Logo } from "@/components/dashboard-shell";
import { LanguageSelect, ThemeToggle } from "@/components/controls";
import {
  IconAlert,
  IconApp,
  IconCheck,
  IconClock,
  IconCopy,
  IconGrid,
  IconList,
  IconMenu,
  IconScale,
  IconShield,
  IconSparkle,
  IconX,
} from "@/components/icons";

export type DocNavItem = { to: string; label: string; icon: ReactNode };

export const DOCS_NAV: DocNavItem[] = [
  { to: "/docs", label: "Overview", icon: <IconGrid width={16} height={16} /> },
  { to: "/docs/quickstart", label: "Quickstart", icon: <IconSparkle width={16} height={16} /> },
  { to: "/docs/sdk-reference", label: "SDK Reference", icon: <IconList width={16} height={16} /> },
  { to: "/docs/react-hook", label: "React Hook", icon: <IconApp width={16} height={16} /> },
  { to: "/docs/ad-formats", label: "Ad Formats", icon: <IconScale width={16} height={16} /> },
  { to: "/docs/error-handling", label: "Error Handling", icon: <IconAlert width={16} height={16} /> },
  { to: "/docs/faq", label: "FAQ", icon: <IconShield width={16} height={16} /> },
  { to: "/docs/changelog", label: "Changelog", icon: <IconClock width={16} height={16} /> },
];

/* ---------- shell ---------- */

export function DocsShell({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const pathname = useRouterState({ select: (s) => s.location.pathname });

  const nav = (
    <div className="flex h-full flex-col border-r border-seam bg-panel">
      <div className="flex h-16 items-center px-5">
        <Logo workspace="docs" />
      </div>
      <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-2">
        {DOCS_NAV.map((item) => {
          const active = pathname === item.to;
          return (
            <Link
              key={item.to}
              to={item.to}
              onClick={() => setOpen(false)}
              className={cn(
                "flex min-h-10 items-center gap-3 rounded-xl px-3 text-sm font-semibold transition-colors",
                active ? "bg-panel-2 text-signal" : "text-paper-dim hover:bg-panel-2 hover:text-paper",
              )}
            >
              <span aria-hidden>{item.icon}</span>
              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>
      <div className="border-t border-seam bg-panel-2 p-4">
        <Link
          to="/partner/mini-apps"
          className="flex min-h-10 items-center justify-center rounded-xl bg-signal px-3 text-sm font-bold text-white transition-all hover:brightness-110"
        >
          Get your kinzId
        </Link>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-ink">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 lg:block">{nav}</aside>

      {open && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <button
            aria-label="Close navigation"
            className="absolute inset-0 bg-black/60"
            onClick={() => setOpen(false)}
          />
          <div className="absolute inset-y-0 left-0 w-72">{nav}</div>
        </div>
      )}

      <div className="lg:pl-64">
        <header className="sticky top-0 z-20 flex min-h-16 flex-wrap items-center gap-3 border-b border-seam bg-ink/95 px-4 py-3 backdrop-blur sm:px-6">
          <button
            aria-label="Open navigation"
            className="inline-flex size-11 items-center justify-center rounded-xl border border-seam lg:hidden"
            onClick={() => setOpen(true)}
          >
            {open ? <IconX /> : <IconMenu />}
          </button>
          <span className="font-display text-lg font-bold tracking-tight">Kinz-ID SDK Docs</span>
          <div className="ml-auto flex flex-wrap items-center gap-2">
            <LanguageSelect compact />
            <ThemeToggle />
          </div>
        </header>
        <main className="mx-auto max-w-4xl px-4 py-10 sm:px-8">{children}</main>
      </div>
    </div>
  );
}

/* ---------- page wrapper ---------- */

export function DocPage({
  title,
  lede,
  children,
}: {
  title: string;
  lede?: ReactNode;
  children: ReactNode;
}) {
  return (
    <article>
      <h1 className="font-display text-3xl font-extrabold tracking-tight">{title}</h1>
      {lede && <p className="mt-3 max-w-2xl text-base leading-relaxed text-paper-dim">{lede}</p>}
      <div className="prose-docs mt-8 space-y-6">{children}</div>
    </article>
  );
}

/* ---------- code block with copy ---------- */

export function CodeBlock({ code, lang }: { code: string; lang?: string }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard unavailable */
    }
  };
  return (
    <div className="relative overflow-hidden rounded-xl border border-seam bg-panel-2">
      <div className="flex items-center justify-between border-b border-seam px-4 py-2">
        <span className="num text-[11px] font-semibold tracking-wide text-paper-dim uppercase">
          {lang ?? "code"}
        </span>
        <button
          type="button"
          onClick={copy}
          className="inline-flex items-center gap-1.5 rounded-lg px-2 py-1 text-xs font-semibold text-paper-dim transition-colors hover:bg-panel hover:text-paper"
        >
          {copied ? <IconCheck width={13} height={13} /> : <IconCopy width={13} height={13} />}
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      <pre className="num overflow-x-auto p-4 text-[13px] leading-relaxed text-paper">
        <code>{code}</code>
      </pre>
    </div>
  );
}

/* ---------- table ---------- */

export function DocTable({
  head,
  rows,
}: {
  head: string[];
  rows: ReactNode[][];
}) {
  return (
    <div className="overflow-x-auto rounded-xl border border-seam">
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="bg-panel-2 text-left">
            {head.map((h) => (
              <th key={h} className="border-b border-seam px-4 py-2.5 font-semibold text-paper-dim">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-seam">
          {rows.map((row, i) => (
            <tr key={i}>
              {row.map((cell, j) => (
                <td key={j} className="px-4 py-2.5 align-top">
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* ---------- callout ---------- */

export type CalloutTone = "signal" | "bounty" | "danger" | "neutral";

const CALLOUT_TONE: Record<CalloutTone, { bar: string; bg: string; label: string }> = {
  signal: { bar: "bg-signal", bg: "bg-signal-soft", label: "text-signal" },
  bounty: { bar: "bg-bounty", bg: "bg-bounty-soft", label: "text-bounty" },
  danger: { bar: "bg-danger", bg: "bg-danger-soft", label: "text-danger" },
  neutral: { bar: "bg-paper-dim", bg: "bg-panel-2", label: "text-paper-dim" },
};

export function Callout({
  tone = "signal",
  title,
  children,
}: {
  tone?: CalloutTone;
  title?: string;
  children: ReactNode;
}) {
  const c = CALLOUT_TONE[tone];
  return (
    <div className={cn("relative overflow-hidden rounded-xl py-3 pr-4 pl-4", c.bg)}>
      <span className={cn("absolute top-0 bottom-0 left-0 w-[3px] rounded-full", c.bar)} aria-hidden />
      {title && <p className={cn("mb-1 text-[11px] font-bold tracking-wide uppercase", c.label)}>{title}</p>}
      <div className="text-sm leading-relaxed text-paper">{children}</div>
    </div>
  );
}

/* ---------- next / prev nav ---------- */

export function NextPrev({
  prev,
  next,
}: {
  prev?: { to: string; label: string } | undefined;
  next?: { to: string; label: string } | undefined;
}) {
  return (
    <div className="mt-12 flex items-center gap-3 border-t border-seam pt-6">
      {prev ? (
        <Link
          to={prev.to}
          className="flex min-h-11 flex-1 items-center gap-1 rounded-xl border border-seam px-4 text-sm font-semibold transition-colors hover:bg-panel-2"
        >
          <span className="text-paper-dim">←</span>
          <span className="truncate">{prev.label}</span>
        </Link>
      ) : (
        <span />
      )}
      {next ? (
        <Link
          to={next.to}
          className="flex min-h-11 flex-1 items-center justify-end gap-1 rounded-xl border border-seam px-4 text-sm font-semibold transition-colors hover:bg-panel-2"
        >
          <span className="truncate">{next.label}</span>
          <span className="text-paper-dim">→</span>
        </Link>
      ) : (
        <span />
      )}
    </div>
  );
}
