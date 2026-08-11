import { createFileRoute } from "@tanstack/react-router";
import { useTranslation } from "react-i18next";
import { AdminShell } from "@/components/workspaces";
import { Panel, fmtInt, fmtMoney } from "@/components/kit";
import { adminCampaignQueue, adminChannelQueue, adminMiniAppQueue, anomalies, financeSummary, withdrawals } from "@/lib/mock-data";

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
  component: () => {
    const { t } = useTranslation();
    const pendingW = withdrawals.filter((w) => w.status === "pending").length;
    const cards = [
      { l: t("admin.nav.campaigns"), v: fmtInt(adminCampaignQueue.length) },
      { l: t("admin.nav.channels"), v: fmtInt(adminChannelQueue.length + adminMiniAppQueue.length) },
      { l: t("admin.nav.withdrawals"), v: fmtInt(pendingW) },
      { l: t("admin.nav.anomalies"), v: fmtInt(anomalies.length) },
      { l: t("admin.revenue"), v: fmtMoney(financeSummary.month.volume) },
      { l: t("admin.payouts"), v: fmtMoney(financeSummary.year.volume) },
    ];
    return (
      <AdminShell title={t("admin.nav.overview")} badges={{ campaigns: adminCampaignQueue.length, channels: adminChannelQueue.length, withdrawals: pendingW, anomalies: anomalies.length }}>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {cards.map((c) => (
            <Panel key={c.l}>
              <p className="text-xs font-semibold text-paper-dim">{c.l}</p>
              <p className="num mt-2 text-3xl font-bold">{c.v}</p>
            </Panel>
          ))}
        </div>
      </AdminShell>
    );
  },
});
