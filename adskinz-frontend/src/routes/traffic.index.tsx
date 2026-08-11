import { createFileRoute, Link } from "@tanstack/react-router";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { AdvShell } from "@/components/workspaces";
import { CampaignTable, TablePanel } from "@/components/campaign-table";
import {
  Btn,
  CountUp,
  ErrorBanner,
  KpiSkeleton,
  Panel,
  Quote,
  Sparkline,
  fmtMoney,
  useFakeLoad,
} from "@/components/kit";
import { IconAlert } from "@/components/icons";
import { advertiserSummary, campaigns, spark } from "@/lib/mock-data";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/traffic/")({
  head: () => ({
    meta: [
      { title: "Advertiser dashboard — AdsKinz traffic" },
      { name: "description", content: "Impressions, clicks, spend and campaign status across your Telegram campaigns." },
      { property: "og:title", content: "Advertiser dashboard — AdsKinz traffic" },
      { property: "og:description", content: "Track native Telegram campaign performance in one place." },
    ],
  }),
  component: AdvDashboard,
});

function Period() {
  const { t } = useTranslation();
  const [p, setP] = useState("30");
  const opts = [
    { v: "7", l: t("common.days7") },
    { v: "30", l: t("common.days30") },
    { v: "all", l: t("common.all") },
  ];
  return (
    <div className="inline-flex rounded-xl border border-seam p-0.5">
      {opts.map((o) => (
        <button
          key={o.v}
          onClick={() => setP(o.v)}
          aria-pressed={p === o.v}
          className={cn(
            "min-h-9 rounded-[10px] px-3 text-xs font-bold transition-colors",
            p === o.v ? "bg-panel-2 text-signal" : "text-paper-dim hover:text-paper",
          )}
        >
          {o.l}
        </button>
      ))}
    </div>
  );
}

function AdvDashboard() {
  const { t } = useTranslation();
  const { loading, error, retry } = useFakeLoad();
  const lowBalance = advertiserSummary.balance < advertiserSummary.activeBudget * 0.1;

  const kpis = [
    { label: t("adv.kpiClicks"), value: advertiserSummary.clicks30.toLocaleString("en-US"), note: t("adv.kpiClicksNote"), seed: 1 },
    { label: t("adv.kpiCtr"), value: `${advertiserSummary.ctr.toFixed(2)}%`, note: t("adv.kpiCtrNote"), seed: 2 },
    { label: t("adv.kpiSpend"), value: fmtMoney(advertiserSummary.spend), note: t("adv.kpiSpendNote"), seed: 3 },
  ];

  return (
    <AdvShell
      title={t("adv.nav.dashboard")}
      action={
        <div className="flex items-center gap-2">
          <Period />
          <Link to="/traffic/campaigns/new">
            <Btn>{t("adv.newCampaign")}</Btn>
          </Link>
        </div>
      }
    >
      <div className="space-y-5">
        {lowBalance && (
          <div className="flex flex-wrap items-center gap-3 rounded-xl border border-seam bg-bounty-soft px-4 py-3 text-sm">
            <IconAlert className="text-bounty" width={16} height={16} />
            <span className="font-semibold text-bounty">{t("adv.lowBalance")}</span>
            <Link to="/traffic/deposits" className="ml-auto">
              <Btn tone="bounty" className="min-h-9 px-3 text-xs">
                {t("adv.topUp")}
              </Btn>
            </Link>
          </div>
        )}

        {error ? (
          <ErrorBanner onRetry={retry} />
        ) : loading ? (
          <Panel>
            <div className="h-28 animate-pulse rounded-md bg-panel-2" />
          </Panel>
        ) : (
          <Panel className="hero-halo flex flex-wrap items-center gap-6">
            <div className="min-w-56">
              <p className="text-sm font-semibold text-paper-dim">{t("x.adv.heroMonth")}</p>
              <p className="mt-2 font-display text-4xl font-extrabold sm:text-5xl">
                <CountUp value={advertiserSummary.impressionsMonth} />
              </p>
              <p className="mt-2 text-xs text-paper-dim">{t("x.adv.heroMonthNote")}</p>
            </div>
            <div className="min-w-48 flex-1">
              <Sparkline points={spark(1, 36)} />
            </div>
          </Panel>
        )}

        <Quote tone="signal" label={t("adv.aggregateNote").split(".")[0]}>{t("adv.quotes.privacy")}</Quote>

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {loading
            ? [0, 1, 2].map((i) => <KpiSkeleton key={i} />)
            : kpis.map((k) => (
                <Panel key={k.label}>
                  <p className="text-xs font-semibold text-paper-dim">{k.label}</p>
                  <p className="num mt-2 text-2xl font-bold">{k.value}</p>
                  <div className="mt-3">
                    <Sparkline points={spark(k.seed)} />
                  </div>
                  <p className="mt-2 text-xs text-paper-dim">{k.note}</p>
                </Panel>
              ))}
        </div>

        <Quote tone="bounty" label={t("adv.nav.campaigns")}>{t("adv.quotes.pacing")}</Quote>

        <TablePanel title={t("adv.tableTitle")} aside={<span className="text-xs text-paper-dim">{t("adv.aggregateNote")}</span>}>
          <CampaignTable data={campaigns} loading={loading} error={error} onRetry={retry} />
        </TablePanel>
      </div>
    </AdvShell>
  );
}
