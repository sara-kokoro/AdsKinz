import { createFileRoute, Link } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { PubShell } from "@/components/workspaces";
import {
  Btn,
  CountUp,
  KpiSkeleton,
  Panel,
  Quote,
  RowSkeleton,
  SectionTitle,
  Sparkline,
  fmtInt,
  fmtMoney,
  inputCls,
  useFakeLoad,
} from "@/components/kit";
import { UsdtMark } from "@/components/usdt";
import { placementStats, publisherSummary, spark } from "@/lib/mock-data";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/partner/")({
  head: () => ({
    meta: [
      { title: "Publisher dashboard — AdsKinz partner" },
      { name: "description", content: "Earnings, impressions and clicks delivered by each of your Telegram channels and Mini Apps." },
      { property: "og:title", content: "Publisher dashboard — AdsKinz partner" },
      { property: "og:description", content: "Monetize your Telegram channel or Mini App with native ads." },
    ],
  }),
  component: PubDashboard,
});

const ctrOf = (c: number, i: number) => (i === 0 ? 0 : (c / i) * 100);
const REF_DAY = new Date("2026-08-02T00:00:00Z");
const dayDiff = (a: string, b: string) =>
  Math.round((new Date(b).getTime() - new Date(a).getTime()) / 86_400_000) + 1;

type Period = "7" | "30" | "custom";
type Kind = "all" | "channel" | "miniapp";
type SortKey = "impressions" | "clicks" | "ctr" | "earnings" | "name";

/** Share of the 30-day totals that falls inside the selected window. */
function windowFactor(daily: number[], days: number) {
  const total = daily.reduce((s, v) => s + v, 0);
  if (total === 0) return 0;
  const slice = daily.slice(Math.max(0, daily.length - days));
  return slice.reduce((s, v) => s + v, 0) / total;
}

function PubDashboard() {
  const { t } = useTranslation();
  const { loading } = useFakeLoad();

  const [period, setPeriod] = useState<Period>("30");
  const [from, setFrom] = useState("2026-07-19");
  const [to, setTo] = useState(REF_DAY.toISOString().slice(0, 10));
  const [kind, setKind] = useState<Kind>("all");
  const [sort, setSort] = useState<SortKey>("impressions");
  const [desc, setDesc] = useState(true);

  const days = useMemo(() => {
    if (period === "7") return 7;
    if (period === "30") return 30;
    const d = dayDiff(from, to);
    return Number.isFinite(d) ? Math.min(30, Math.max(1, d)) : 30;
  }, [period, from, to]);

  const rows = useMemo(() => {
    const list = placementStats
      .filter((p) => kind === "all" || p.kind === kind)
      .map((p) => {
        const f = days >= 30 ? 1 : windowFactor(p.daily, days);
        const impressions = Math.round(p.impressions30 * f);
        const clicks = Math.round(p.clicks30 * f);
        return {
          id: p.id,
          name: p.name,
          kind: p.kind,
          impressions,
          clicks,
          ctr: ctrOf(clicks, impressions),
          earnings: p.earnings30 * f,
        };
      });
    list.sort((a, b) => {
      const v = sort === "name" ? a.name.localeCompare(b.name) : a[sort] - b[sort];
      return desc ? -v : v;
    });
    return list;
  }, [days, kind, sort, desc]);

  const totalImpressions = rows.reduce((s, p) => s + p.impressions, 0);
  const totalClicks = rows.reduce((s, p) => s + p.clicks, 0);
  const totalEarnings = rows.reduce((s, p) => s + p.earnings, 0);

  const kpis = [
    { label: t("pub.totalImpressions"), value: fmtInt(totalImpressions), seed: 4 },
    { label: t("pub.totalClicks"), value: fmtInt(totalClicks), seed: 5 },
    { label: t("pub.kpiMonth"), value: fmtMoney(publisherSummary.monthEarnings), seed: 6 },
  ];

  const reset = () => {
    setPeriod("30");
    setKind("all");
    setSort("impressions");
    setDesc(true);
  };

  const chip = (active: boolean) =>
    cn(
      "min-h-9 rounded-full border px-3 text-xs font-semibold transition-colors",
      active ? "border-signal bg-signal-soft text-signal" : "border-seam text-paper-dim hover:text-paper",
    );

  const sortBtn = (key: SortKey, label: string) => (
    <button
      type="button"
      onClick={() => (sort === key ? setDesc((d) => !d) : (setSort(key), setDesc(true)))}
      className={cn("inline-flex items-center gap-1", sort === key ? "text-signal" : "hover:text-paper")}
      aria-label={`${t("pub.f.sort")}: ${label}`}
    >
      {label}
      <span aria-hidden className="text-[10px]">{sort === key ? (desc ? "▼" : "▲") : "↕"}</span>
    </button>
  );

  return (
    <PubShell
      title={t("pub.nav.dashboard")}
      action={
        <Link to="/partner/channels">
          <Btn tone="bounty">{t("pub.addChannel")}</Btn>
        </Link>
      }
    >
      <div className="space-y-5">
        <Panel className="hero-halo flex flex-wrap items-center gap-6">
          <div className="min-w-56">
            <p className="text-sm font-semibold text-paper-dim">{t("pub.heroMetric")}</p>
            <p className="mt-2 flex items-center gap-2 font-display text-4xl font-extrabold text-bounty sm:text-5xl">
              <UsdtMark size={32} />
              <CountUp value={publisherSummary.totalEarnings} money />
            </p>
          </div>
          <div className="min-w-48 flex-1">
            <Sparkline points={spark(2, 36)} tone="bounty" />
          </div>
        </Panel>

        <Quote tone="bounty" label={t("pub.nav.withdrawals")}>{t("pub.quotes.payout")}</Quote>

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {loading
            ? [0, 1, 2].map((i) => <KpiSkeleton key={i} />)
            : kpis.map((k) => (
                <Panel key={k.label}>
                  <p className="text-xs font-semibold text-paper-dim">{k.label}</p>
                  <p className="num mt-2 text-2xl font-bold">{k.value}</p>
                  <div className="mt-3"><Sparkline points={spark(k.seed)} tone="bounty" /></div>
                </Panel>
              ))}
        </div>

        <Panel className="p-0">
          <div className="p-5 pb-0">
            <SectionTitle sub={t("pub.perfSub")}>{t("pub.perfTitle")}</SectionTitle>
          </div>

          {/* filters */}
          <div className="space-y-3 border-b border-seam px-5 pb-4">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs font-semibold text-paper-dim">{t("pub.f.period")}</span>
              <button type="button" className={chip(period === "7")} onClick={() => setPeriod("7")}>{t("pub.f.d7")}</button>
              <button type="button" className={chip(period === "30")} onClick={() => setPeriod("30")}>{t("pub.f.d30")}</button>
              <button type="button" className={chip(period === "custom")} onClick={() => setPeriod("custom")}>{t("pub.f.custom")}</button>

              <span className="ml-3 text-xs font-semibold text-paper-dim">{t("pub.f.type")}</span>
              <button type="button" className={chip(kind === "all")} onClick={() => setKind("all")}>{t("pub.f.all")}</button>
              <button type="button" className={chip(kind === "channel")} onClick={() => setKind("channel")}>{t("pub.f.channels")}</button>
              <button type="button" className={chip(kind === "miniapp")} onClick={() => setKind("miniapp")}>{t("pub.f.miniapps")}</button>

              <button type="button" onClick={reset} className="ml-auto text-xs font-semibold text-signal hover:underline">
                {t("pub.f.reset")}
              </button>
            </div>

            {period === "custom" && (
              <div className="grid gap-3 sm:max-w-md sm:grid-cols-2">
                <label className="text-xs font-semibold text-paper-dim">
                  {t("pub.f.from")}
                  <input type="date" value={from} max={to} onChange={(e) => setFrom(e.target.value)} className={`num mt-1 ${inputCls()}`} />
                </label>
                <label className="text-xs font-semibold text-paper-dim">
                  {t("pub.f.to")}
                  <input type="date" value={to} min={from} onChange={(e) => setTo(e.target.value)} className={`num mt-1 ${inputCls()}`} />
                </label>
              </div>
            )}

            <p className="num text-xs text-paper-dim">
              {t("pub.f.showing", { count: rows.length, days })}
            </p>
          </div>

          {loading ? (
            <RowSkeleton rows={5} />
          ) : rows.length === 0 ? (
            <p className="p-8 text-center text-sm text-paper-dim">{t("pub.f.none")}</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[720px] text-sm">
                <thead>
                  <tr className="border-b border-seam text-left text-xs font-semibold text-paper-dim">
                    <th scope="col" className="px-5 py-3">{sortBtn("name", t("pub.colPlacement"))}</th>
                    <th scope="col" className="px-5 py-3 text-right">{sortBtn("impressions", t("pub.f.byImpr"))}</th>
                    <th scope="col" className="px-5 py-3 text-right">{sortBtn("clicks", t("pub.f.byClicks"))}</th>
                    <th scope="col" className="px-5 py-3 text-right">{sortBtn("ctr", t("pub.f.byCtr"))}</th>
                    <th scope="col" className="px-5 py-3 text-right">{sortBtn("earnings", t("pub.f.byEarn"))}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-seam">
                  {rows.map((p) => (
                    <tr key={p.id} className="transition-colors hover:bg-panel-2">
                      <td className="px-5 py-3.5">
                        <Link
                          to={p.kind === "channel" ? "/partner/channels" : "/partner/mini-apps"}
                          className="font-bold hover:text-signal"
                        >
                          {p.name}
                        </Link>
                        <p className="text-xs text-paper-dim">
                          {p.kind === "channel" ? t("pub.typeChannel") : t("pub.typeMiniApp")}
                        </p>
                      </td>
                      <td className="num px-5 py-3.5 text-right font-semibold">{fmtInt(p.impressions)}</td>
                      <td className="num px-5 py-3.5 text-right font-semibold">{fmtInt(p.clicks)}</td>
                      <td className="num px-5 py-3.5 text-right text-paper-dim">{p.ctr.toFixed(2)}%</td>
                      <td className="num px-5 py-3.5 text-right font-semibold text-bounty">{fmtMoney(p.earnings)}</td>
                    </tr>
                  ))}
                </tbody>
                <tfoot>
                  <tr className="border-t border-seam text-xs font-bold">
                    <td className="px-5 py-3">{t("pub.f.all")}</td>
                    <td className="num px-5 py-3 text-right">{fmtInt(totalImpressions)}</td>
                    <td className="num px-5 py-3 text-right">{fmtInt(totalClicks)}</td>
                    <td className="num px-5 py-3 text-right text-paper-dim">{ctrOf(totalClicks, totalImpressions).toFixed(2)}%</td>
                    <td className="num px-5 py-3 text-right text-bounty">
                      <span className="inline-flex items-center gap-1.5"><UsdtMark size={13} />{fmtMoney(totalEarnings)}</span>
                    </td>
                  </tr>
                </tfoot>
              </table>
            </div>
          )}
        </Panel>

        <Quote tone="neutral" label={t("pub.nav.dashboard")}>{t("pub.quotes.quality")}</Quote>
      </div>
    </PubShell>
  );
}
