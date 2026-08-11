import { useState, type ReactNode } from "react";
import { Link, useRouterState } from "@tanstack/react-router";
import { useTranslation } from "react-i18next";
import { cn } from "@/lib/utils";
import { IconMenu, IconX } from "@/components/icons";
import { LanguageSelect, ThemeToggle } from "@/components/controls";
import logoAsset from "@/assets/adskinz-logo.png.asset.json";

export type NavItem = { to: string; label: string; icon: ReactNode; badge?: number | undefined };

export function Logo({ workspace }: { workspace?: string }) {
  return (
    <Link to="/" className="flex items-center gap-2">
      <img src={logoAsset.url} alt="AdsKinz" className="size-8 shrink-0 object-contain" width={32} height={32} />
      <span className="font-display text-lg font-extrabold tracking-tight">
        Ads<span className="text-signal">Kinz</span>
      </span>
      {workspace && (
        <span className="num rounded-md border border-seam px-1.5 py-0.5 text-[10px] font-semibold text-paper-dim">
          {workspace}
        </span>
      )}
    </Link>
  );
}

export function DashboardShell({
  workspace,
  nav,
  title,
  action,
  sidebarFooter,
  children,
}: {
  workspace: string;
  nav: NavItem[];
  title: string;
  action?: ReactNode;
  sidebarFooter?: ReactNode;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const { t } = useTranslation();
  const pathname = useRouterState({ select: (s) => s.location.pathname });

  const sidebar = (
    <div className="flex h-full flex-col border-r border-seam bg-panel">
      <div className="flex h-16 items-center px-5">
        <Logo workspace={workspace} />
      </div>
      <nav className="flex-1 space-y-1 px-3 py-2">
        {nav.map((item) => {
          const active = pathname === item.to || (item.to !== "/" && pathname.startsWith(item.to + "/"));
          return (
            <Link
              key={item.to}
              to={item.to}
              onClick={() => setOpen(false)}
              className={cn(
                "flex min-h-11 items-center gap-3 rounded-xl px-3 text-sm font-semibold transition-colors",
                active ? "bg-panel-2 text-signal" : "text-paper-dim hover:bg-panel-2 hover:text-paper",
              )}
            >
              <span aria-hidden>{item.icon}</span>
              <span>{item.label}</span>
              {item.badge ? (
                <span className="num ml-auto rounded-full bg-bounty-soft px-2 py-0.5 text-[11px] font-bold text-bounty">
                  {item.badge}
                </span>
              ) : null}
            </Link>
          );
        })}
      </nav>
      {sidebarFooter && <div className="border-t border-seam bg-panel-2 p-4">{sidebarFooter}</div>}
    </div>
  );

  return (
    <div className="min-h-screen bg-ink">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 lg:block">{sidebar}</aside>

      {open && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <button
            aria-label={t("common.close")}
            className="absolute inset-0 bg-black/60"
            onClick={() => setOpen(false)}
          />
          <div className="absolute inset-y-0 left-0 w-72">{sidebar}</div>
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
          <h1 className="font-display text-lg font-bold tracking-tight">{title}</h1>
          <div className="ml-auto flex flex-wrap items-center gap-2">
            <LanguageSelect compact />
            <ThemeToggle />
            {action}
          </div>
        </header>
        <main className="mx-auto max-w-[1400px] px-4 py-6 sm:px-6">{children}</main>
      </div>
    </div>
  );
}
