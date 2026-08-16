import type { ReactNode } from "react";
import { Link } from "@tanstack/react-router";
import { useTranslation } from "react-i18next";
import { DashboardShell, type NavItem } from "@/components/dashboard-shell";
import { Btn, fmtMoney } from "@/components/kit";
import {
  IconAlert,
  IconApp,
  IconChannel,
  IconGrid,
  IconList,
  IconMegaphone,
  IconScale,
  IconSettings,
  IconShield,
  IconTrend,
  IconWallet,
} from "@/components/icons";
import { useBalance, usePublisherStats, useAdminOverview } from "@/lib/queries";
import { num } from "@/lib/api";
import { useAuthGuard } from "@/lib/auth";

const ico = { width: 18, height: 18 };

function AuthLoading() {
  return <div className="flex min-h-screen items-center justify-center bg-ink text-sm text-paper-dim">Checking your session…</div>;
}

export function AdvShell({ title, action, children }: { title: string; action?: ReactNode; children: ReactNode }) {
  const { t } = useTranslation();
  const allowed = useAuthGuard("advertiser");
  const { data: balance } = useBalance(allowed);
  if (!allowed) return <AuthLoading />;
  const nav: NavItem[] = [
    { to: "/traffic", label: t("adv.nav.dashboard"), icon: <IconGrid {...ico} /> },
    { to: "/traffic/campaigns", label: t("adv.nav.campaigns"), icon: <IconMegaphone {...ico} /> },
    { to: "/traffic/deposits", label: t("adv.nav.deposits"), icon: <IconWallet {...ico} /> },
    { to: "/traffic/settings", label: t("adv.nav.settings"), icon: <IconSettings {...ico} /> },
  ];
  return (
    <DashboardShell
      workspace={t("adv.workspace")}
      nav={nav}
      title={title}
      action={action}
      sidebarFooter={
        <div>
          <p className="text-xs font-semibold text-paper-dim">{t("adv.balance")}</p>
          <p className="num mt-1 text-2xl font-extrabold text-bounty">{fmtMoney(num(balance?.balance))}</p>
          <Link to="/traffic/deposits" className="mt-3 block">
            <Btn tone="bounty" className="w-full">
              {t("adv.topUp")}
            </Btn>
          </Link>
        </div>
      }
    >
      {children}
    </DashboardShell>
  );
}

export function PubShell({ title, action, children }: { title: string; action?: ReactNode; children: ReactNode }) {
  const { t } = useTranslation();
  const allowed = useAuthGuard("publisher");
  const { data: stats } = usePublisherStats(allowed);
  if (!allowed) return <AuthLoading />;
  const available = num(stats?.availableBalance);
  const nav: NavItem[] = [
    { to: "/partner", label: t("pub.nav.dashboard"), icon: <IconGrid {...ico} /> },
    { to: "/partner/channels", label: t("pub.nav.channels"), icon: <IconChannel {...ico} /> },
    { to: "/partner/mini-apps", label: t("pub.nav.miniapps"), icon: <IconApp {...ico} /> },
    { to: "/partner/withdrawals", label: t("pub.nav.withdrawals"), icon: <IconWallet {...ico} /> },
    { to: "/partner/settings", label: t("pub.nav.settings"), icon: <IconSettings {...ico} /> },
  ];
  const locked = available < 50;
  return (
    <DashboardShell
      workspace={t("pub.workspace")}
      nav={nav}
      title={title}
      action={action}
      sidebarFooter={
        <div>
          <p className="text-xs font-semibold text-paper-dim">{t("pub.balance")}</p>
          <p className="num mt-1 text-2xl font-extrabold text-bounty">{fmtMoney(available)}</p>
          <p className="mt-1 text-[11px] text-paper-dim">{t("pub.withdrawThreshold")}</p>
          <Link to="/partner/withdrawals" className="mt-3 block">
            <Btn tone="bounty" className="w-full" disabled={locked}>
              {t("pub.withdraw")}
            </Btn>
          </Link>
          {available < 50 && (
            <p className="mt-2 text-[11px] text-paper-dim">
              {t("pub.belowThreshold", { amount: fmtMoney(available) })}
            </p>
          )}
        </div>
      }
    >
      {children}
    </DashboardShell>
  );
}

export function AdminShell({
  title,
  badges,
  action,
  children,
}: {
  title: string;
  badges?: Partial<Record<"campaigns" | "channels" | "miniapps" | "users" | "withdrawals" | "disputes" | "anomalies", number>>;
  action?: ReactNode;
  children: ReactNode;
}) {
  const { t } = useTranslation();
  const allowed = useAuthGuard("admin");
  const { data: overview } = useAdminOverview(allowed);
  if (!allowed) return <AuthLoading />;
  const liveBadges = {
    campaigns: overview?.pendingCampaigns,
    channels: overview?.pendingChannels,
    miniapps: overview?.pendingMiniApps,
    withdrawals: overview?.pendingWithdrawals,
    anomalies: overview?.openAnomalies,
    ...badges,
  };
  const nav: NavItem[] = [
    { to: "/kingcey/overview", label: t("admin.nav.overview"), icon: <IconGrid {...ico} /> },
    { to: "/kingcey/campaigns", label: t("admin.nav.campaigns"), icon: <IconMegaphone {...ico} />, badge: liveBadges.campaigns },
    { to: "/kingcey/channels", label: t("admin.nav.channels"), icon: <IconChannel {...ico} />, badge: liveBadges.channels },
    { to: "/kingcey/mini-apps", label: t("x.admin.miniApps"), icon: <IconApp {...ico} />, badge: liveBadges.miniapps },
    { to: "/kingcey/users", label: t("x.admin.users"), icon: <IconShield {...ico} />, badge: liveBadges.users },
    { to: "/kingcey/withdrawals", label: t("admin.nav.withdrawals"), icon: <IconWallet {...ico} />, badge: liveBadges.withdrawals },
    { to: "/kingcey/disputes", label: t("admin.nav.disputes"), icon: <IconScale {...ico} />, badge: liveBadges.disputes },
    { to: "/kingcey/finances", label: t("admin.nav.finances"), icon: <IconTrend {...ico} /> },
    { to: "/kingcey/anomalies", label: t("admin.nav.anomalies"), icon: <IconAlert {...ico} />, badge: liveBadges.anomalies },
    { to: "/kingcey/audit", label: t("admin.nav.audit"), icon: <IconList {...ico} /> },
  ];
  return (
    <DashboardShell workspace={t("admin.workspace")} nav={nav} title={title} action={action}>
      {children}
    </DashboardShell>
  );
}

