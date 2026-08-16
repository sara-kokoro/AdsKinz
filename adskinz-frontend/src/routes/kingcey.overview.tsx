import { createFileRoute, Link } from "@tanstack/react-router";
import { useTranslation } from "react-i18next";
import { AdminShell } from "@/components/workspaces";
import { ErrorBanner, KpiSkeleton, Panel, fmtInt, fmtMoney } from "@/components/kit";
import { useAdminOverview } from "@/lib/queries";
import { num } from "@/lib/api";
import { useAuthGuard } from "@/lib/auth";

export const Route = createFileRoute("/kingcey/overview")({
  head: () => ({
    meta: [
      { title: "Overview — AdsKinz admin" },
      { name: "description", content: "Pending moderation, payouts and platform revenue at a glance." },
      { property: "og:title", content: "Overview — AdsKinz admin" },
      { property: "og:description", content: "Queues and finance snapshot for AdsKinz operators." },
      { name: "robots", content: "noindex" },
    ],
  }),
  component: Overview,
});

function Overview() {
  useAuthGuard("admin");
  const { t } = useTranslation();
  const { data, isLoading, isError, refetch } = useAdminOverview();

  const cards = data
    ? [
        { l: t("admin.nav.campaigns"), v: fmtInt(data.pendingCampaigns), to: "/kingcey/campaigns" as const },
        { l: t("admin.nav.channels"), v: fmtInt(data.pendingChannels), to: "/kingcey/channels" as const },
        { l: "Pending mini apps", v: fmtInt(data.pendingMiniApps), to: "/kingcey/mini-apps" as const },
        { l: t("admin.nav.withdrawals"), v: fmtInt(data.pendingWithdrawals), to: "/kingcey/withdrawals" as const },
        { l: t("admin.nav.anomalies"), v: fmtInt(data.openAnomalies), to: "/kingcey/anomalies" as const },
        { l: "Active campaigns", v: fmtInt(data.activeCampaigns), to: "/kingcey/campaigns" as const },
        { l: "Active channels", v: fmtInt(data.activeChannels), to: "/kingcey/channels" as const },
        { l: "Advertisers", v: fmtInt(data.advertisers), to: "/kingcey/users" as const },
        { l: "Publishers", v: fmtInt(data.publishers), to: "/kingcey/users" as const },
        { l: "Owed to publishers", v: fmtMoney(num(data.balanceOwedToPublishers)), to: "/kingcey/finances" as const },
        { l: "Commission today", v: fmtMoney(num(data.commissionToday)), to: "/kingcey/finances" as const },
      ]
    : [];

  return (
    <AdminShell
      title={t("admin.nav.overview")}
      badges={
        data
          ? {
              campaigns: data.pendingCampaigns,
              channels: data.pendingChannels,
              miniapps: data.pendingMiniApps,
              withdrawals: data.pendingWithdrawals,
              anomalies: data.openAnomalies,
            }
          : {}
      }
    >
      {isError && <ErrorBanner onRetry={refetch} />}
      {isLoading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => <KpiSkeleton key={i} />)}
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {cards.map((c) => (
            <Link key={c.l} to={c.to}>
              <Panel className="transition-transform hover:-translate-y-0.5">
                <p className="text-xs font-semibold text-paper-dim">{c.l}</p>
                <p className="num mt-2 text-3xl font-bold">{c.v}</p>
              </Panel>
            </Link>
          ))}
        </div>
      )}
    </AdminShell>
  );
}
