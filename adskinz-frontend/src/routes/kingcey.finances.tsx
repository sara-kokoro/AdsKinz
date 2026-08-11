import { createFileRoute } from "@tanstack/react-router";
import { useTranslation } from "react-i18next";
import { AdminShell } from "@/components/workspaces";
import { Panel, fmtMoney } from "@/components/kit";
import { financeSummary } from "@/lib/mock-data";

export const Route = createFileRoute("/kingcey/finances")({
  head: () => ({
    meta: [
      { title: "Finances — AdsKinz admin" },
      { name: "description", content: "Platform revenue, publisher payouts and outstanding advertiser balances." },
      { property: "og:title", content: "Finances — AdsKinz admin" },
      { property: "og:description", content: "Revenue and payout snapshot." },
      { name: "robots", content: "noindex" },
    ],
  }),
  component: () => {
    const { t } = useTranslation();
    const rows = [
      { l: t("admin.revenue"), v: financeSummary.month.volume },
      { l: t("admin.payouts"), v: financeSummary.year.volume },
      { l: t("admin.margin"), v: financeSummary.month.profit },
    ];
    return (
      <AdminShell title={t("admin.nav.finances")}>
        <div className="grid gap-4 sm:grid-cols-3">
          {rows.map((r) => (
            <Panel key={r.l}>
              <p className="text-xs font-semibold text-paper-dim">{r.l}</p>
              <p className="num mt-2 text-2xl font-bold text-bounty">{fmtMoney(r.v)}</p>
            </Panel>
          ))}
        </div>
      </AdminShell>
    );
  },
});
