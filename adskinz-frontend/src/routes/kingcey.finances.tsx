import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { AdminShell } from "@/components/workspaces";
import { Segmented } from "@/components/cards";
import { ErrorBanner, KpiSkeleton, Panel, SectionTitle, fmtMoney } from "@/components/kit";
import { useAdminFinances } from "@/lib/queries";
import { num } from "@/lib/api";
import { useAuthGuard } from "@/lib/auth";

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
  component: Finances,
});

type Period = "7d" | "30d" | "90d";

function Finances() {
  useAuthGuard("admin");
  const { t } = useTranslation();
  const [period, setPeriod] = useState<Period>("30d");
  const { data, isLoading, isError, refetch } = useAdminFinances(period);

  const kpis = data
    ? [
        { l: "Gross revenue", v: fmtMoney(num(data.grossRevenue)) },
        { l: "Commission", v: fmtMoney(num(data.commission)) },
        { l: "Publisher share", v: fmtMoney(num(data.publisherShare)) },
        { l: "Deposits", v: fmtMoney(num(data.depositsTotal)) },
        { l: "Withdrawals paid", v: fmtMoney(num(data.withdrawalsPaid)) },
        { l: "Withdrawals pending", v: fmtMoney(num(data.withdrawalsPending)) },
        { l: "Advertiser balances", v: fmtMoney(num(data.advertiserBalances)) },
        { l: "Publisher liabilities", v: fmtMoney(num(data.publisherLiabilities)) },
        { l: "Net treasury", v: fmtMoney(num(data.netTreasury)) },
      ]
    : [];

  const series = (data?.series ?? []).map((s) => ({
    date: s.date,
    gross: num(s.gross),
    commission: num(s.commission),
    payouts: num(s.payouts),
  }));

  return (
    <AdminShell title={t("admin.nav.finances")}>
      {isError && <ErrorBanner onRetry={refetch} />}
      <div className="space-y-5">
        <Segmented
          value={period}
          onChange={setPeriod}
          options={[
            { v: "7d" as const, l: "7 days" },
            { v: "30d" as const, l: "30 days" },
            { v: "90d" as const, l: "90 days" },
          ]}
        />

        {isLoading ? (
          <div className="grid gap-4 sm:grid-cols-3">
            {Array.from({ length: 6 }).map((_, i) => <KpiSkeleton key={i} />)}
          </div>
        ) : (
          <>
            <div className="grid gap-4 sm:grid-cols-3">
              {kpis.map((r) => (
                <Panel key={r.l}>
                  <p className="text-xs font-semibold text-paper-dim">{r.l}</p>
                  <p className="num mt-2 text-2xl font-bold text-bounty">{r.v}</p>
                </Panel>
              ))}
            </div>

            <Panel>
              <SectionTitle>Revenue trend</SectionTitle>
              <div className="h-64 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={series}>
                    <XAxis dataKey="date" tick={{ fontSize: 11 }} stroke="var(--color-paper-dim, currentColor)" />
                    <YAxis tick={{ fontSize: 11 }} width={48} />
                    <Tooltip formatter={(v: number) => fmtMoney(v)} />
                    <Line type="monotone" dataKey="gross" stroke="var(--signal)" strokeWidth={2} dot={false} name="Gross" />
                    <Line type="monotone" dataKey="commission" stroke="var(--bounty)" strokeWidth={2} dot={false} name="Commission" />
                    <Line type="monotone" dataKey="payouts" stroke="var(--danger)" strokeWidth={2} dot={false} name="Payouts" />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </Panel>

            <div className="grid gap-5 lg:grid-cols-2">
              <Panel className="p-0">
                <div className="p-5 pb-0"><SectionTitle>Top advertisers</SectionTitle></div>
                {data && data.topAdvertisers.length === 0 ? (
                  <p className="px-5 pb-5 text-sm text-paper-dim">No data for this period.</p>
                ) : (
                  <ul className="divide-y divide-seam">
                    {data?.topAdvertisers.map((a) => (
                      <li key={a.id} className="flex items-center justify-between gap-3 px-5 py-3 text-sm">
                        <span className="min-w-0 truncate font-semibold">{a.label}</span>
                        <span className="num shrink-0 font-bold text-bounty">{fmtMoney(num(a.amount))}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </Panel>
              <Panel className="p-0">
                <div className="p-5 pb-0"><SectionTitle>Top publishers</SectionTitle></div>
                {data && data.topPublishers.length === 0 ? (
                  <p className="px-5 pb-5 text-sm text-paper-dim">No data for this period.</p>
                ) : (
                  <ul className="divide-y divide-seam">
                    {data?.topPublishers.map((p) => (
                      <li key={p.id} className="flex items-center justify-between gap-3 px-5 py-3 text-sm">
                        <span className="min-w-0 truncate font-semibold">{p.label}</span>
                        <span className="num shrink-0 font-bold text-bounty">{fmtMoney(num(p.amount))}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </Panel>
            </div>
          </>
        )}
      </div>
    </AdminShell>
  );
}
