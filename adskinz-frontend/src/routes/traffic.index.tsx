import { createFileRoute, Link } from "@tanstack/react-router";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { AdvShell } from "@/components/workspaces";
import {
  Btn,
  CountUp,
  ErrorBanner,
  KpiSkeleton,
  Panel,
  Quote,
  RowSkeleton,
  Sparkline,
  StatusPill,
  BudgetBar,
  EmptyState,
  fmtInt,
  fmtMoney,
} from "@/components/kit";
import { ArtCampaignBroadcast, ArtCampaignEmpty } from "@/components/illustrations";
import { ReferralCard } from "@/components/controls";
import { useAdvertiserReferrals, useAdvertiserStats, useCampaigns, useSubscribePremium, useTogglePremiumAutoRenew } from "@/lib/queries";
import { num } from "@/lib/api";
import { cn } from "@/lib/utils";
import { useAuthGuard } from "@/lib/auth";

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
  useAuthGuard("advertiser");
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
  const stats = useAdvertiserStats();
  const referrals = useAdvertiserReferrals();
  const campaignsQ = useCampaigns();

  const s = stats.data;

  const kpis = s
    ? [
        { label: t("adv.kpiClicks"), value: fmtInt(s.clicks30), note: t("adv.kpiClicksNote") },
        { label: t("adv.kpiCtr"), value: `${s.ctr.toFixed(2)}%`, note: t("adv.kpiCtrNote") },
        { label: t("adv.kpiSpend"), value: fmtMoney(num(s.spend)), note: t("adv.kpiSpendNote") },
      ]
    : [];

  const recent = (campaignsQ.data ?? []).slice(0, 6);

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

        {stats.isError ? (
          <ErrorBanner onRetry={() => stats.refetch()} message={(stats.error as Error)?.message} />
        ) : stats.isLoading ? (
          <Panel>
            <div className="h-28 animate-pulse rounded-md bg-panel-2" />
          </Panel>
        ) : (
          <Panel className="hero-halo flex flex-wrap items-center gap-6">
            <div className="min-w-56">
              <p className="text-sm font-semibold text-paper-dim">{t("x.adv.heroMonth")}</p>
              <p className="mt-2 font-display text-4xl font-extrabold sm:text-5xl">
                <CountUp value={s?.impressionsMonth ?? 0} />
              </p>
              <p className="mt-2 text-xs text-paper-dim">{t("x.adv.heroMonthNote")}</p>
            </div>
            <div className="min-w-48 flex-1">
              {s && s.daily.length > 1 ? (
                <Sparkline points={s.daily} />
              ) : (
                <ArtCampaignBroadcast className="max-w-[280px]" />
              )}
            </div>
          </Panel>
        )}

        <Quote tone="signal" label={t("adv.aggregateNote").split(".")[0]}>{t("adv.quotes.privacy")}</Quote>

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {stats.isLoading
            ? [0, 1, 2].map((i) => <KpiSkeleton key={i} />)
            : kpis.map((k) => (
                <Panel key={k.label}>
                  <p className="text-xs font-semibold text-paper-dim">{k.label}</p>
                  <p className="num mt-2 text-2xl font-bold">{k.value}</p>
                  <p className="mt-2 text-xs text-paper-dim">{k.note}</p>
                </Panel>
              ))}
        </div>

        <PremiumPanel data={s} />

        <ReferralCard data={referrals.data} isLoading={referrals.isLoading} label="Parrainage annonceurs" />

        <Quote tone="bounty" label={t("adv.nav.campaigns")}>{t("adv.quotes.pacing")}</Quote>

        <Panel className="p-0">
          <div className="flex flex-wrap items-center gap-3 border-b border-seam px-5 py-4">
            <h2 className="font-display text-base font-bold">{t("adv.tableTitle")}</h2>
            <span className="ml-auto text-xs text-paper-dim">{t("adv.aggregateNote")}</span>
          </div>

          {campaignsQ.isError ? (
            <div className="p-5">
              <ErrorBanner onRetry={() => campaignsQ.refetch()} message={(campaignsQ.error as Error)?.message} />
            </div>
          ) : campaignsQ.isLoading ? (
            <RowSkeleton rows={5} />
          ) : recent.length === 0 ? (
            <EmptyState
              title={t("adv.emptyTitle")}
              sub={t("adv.emptySub")}
              action={
                <div className="flex flex-col items-center gap-4">
                  <ArtCampaignEmpty />
                  <Link to="/traffic/campaigns/new">
                    <Btn>{t("adv.emptyCta")}</Btn>
                  </Link>
                </div>
              }
            />
          ) : (
            <>
              <div className="hidden overflow-x-auto sm:block">
                <table className="w-full text-left text-sm">
                  <thead className="text-xs font-semibold text-paper-dim">
                    <tr className="border-b border-seam">
                      <th className="px-5 py-3">{t("adv.colCampaign")}</th>
                      <th className="px-5 py-3">{t("adv.colStatus")}</th>
                      <th className="px-5 py-3">{t("adv.colCpm")}</th>
                      <th className="px-5 py-3 min-w-44">{t("adv.colBudget")}</th>
                      <th className="px-5 py-3">{t("adv.colClicks")}</th>
                      <th className="px-5 py-3 text-right"><span className="sr-only">{t("adv.detail.view")}</span></th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-seam">
                    {recent.map((c) => (
                      <tr key={c.id} className="transition-colors hover:bg-panel-2">
                        <td className="px-5 py-4">
                          <Link to="/traffic/campaigns/$id" params={{ id: c.id }} className="font-semibold hover:text-signal">
                            {c.name}
                          </Link>
                          <p className="text-xs text-paper-dim">{c.language}</p>
                          {c.rejectionReason && <p className="mt-1 text-xs text-danger">{c.rejectionReason}</p>}
                        </td>
                        <td className="px-5 py-4"><StatusPill status={c.status} /></td>
                        <td className="num px-5 py-4 font-semibold">{fmtMoney(num(c.cpm))}</td>
                        <td className="px-5 py-4">
                          <p className="num text-xs font-semibold text-bounty">
                            {fmtMoney(num(c.spent))} / {fmtMoney(num(c.budget), 0)}
                          </p>
                          <div className="mt-2"><BudgetBar used={num(c.spent)} total={num(c.budget) || 1} /></div>
                        </td>
                        <td className="num px-5 py-4 font-semibold">{fmtInt(c.clicks)}</td>
                        <td className="px-5 py-4 text-right">
                          <Link to="/traffic/campaigns/$id" params={{ id: c.id }} className="text-xs font-semibold text-signal hover:underline">
                            {t("adv.detail.view")}
                          </Link>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="divide-y divide-seam sm:hidden">
                {recent.map((c) => (
                  <div key={c.id} className="space-y-3 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="font-semibold">{c.name}</p>
                        <p className="text-xs text-paper-dim">{c.language}</p>
                      </div>
                      <StatusPill status={c.status} />
                    </div>
                    <div>
                      <p className="num text-xs font-semibold text-bounty">
                        {fmtMoney(num(c.spent))} / {fmtMoney(num(c.budget), 0)}
                      </p>
                      <div className="mt-2"><BudgetBar used={num(c.spent)} total={num(c.budget) || 1} /></div>
                    </div>
                    {c.rejectionReason && <p className="text-xs text-danger">{c.rejectionReason}</p>}
                    <Link to="/traffic/campaigns/$id" params={{ id: c.id }} className="inline-block text-xs font-semibold text-signal">
                      {t("adv.detail.view")} →
                    </Link>
                  </div>
                ))}
              </div>
            </>
          )}
        </Panel>
      </div>
    </AdvShell>
  );
}

function PremiumPanel({ data }: { data: import("@/lib/types").AdvertiserStats | undefined }) {
  const subscribe = useSubscribePremium();
  const toggleAutoRenew = useTogglePremiumAutoRenew();

  if (!data) return null;

  const price = num(data.premiumMonthlyPrice) || 9.99;
  const balance = num(data.balance);
  const canAfford = balance >= price;
  const expiresAt = data.premiumExpiresAt ? new Date(data.premiumExpiresAt) : null;

  return (
    <Panel className="border-bounty/40">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="flex items-center gap-2 text-sm font-bold text-bounty">
            ✦ Premium {data.isPremium && <span className="rounded-full bg-bounty/15 px-2 py-0.5 text-xs">Actif</span>}
          </p>
          <p className="mt-1 text-sm text-paper-dim">
            {data.isPremium
              ? `Actif jusqu'au ${expiresAt?.toLocaleDateString("fr-FR") ?? "—"} · ${fmtMoney(price)}/mois, prélevé sur ton solde`
              : `${fmtMoney(price)}/mois, prélevé sur ton solde. Débloque la génération d'affiches IA pour tes campagnes.`}
          </p>
          {!canAfford && !data.isPremium && (
            <p className="mt-1 text-xs text-danger">Solde insuffisant ({fmtMoney(balance)} disponible).</p>
          )}
        </div>
        <div className="flex items-center gap-3">
          {data.isPremium && (
            <label className="flex items-center gap-2 text-xs text-paper-dim">
              <input
                type="checkbox"
                checked={data.premiumAutoRenew}
                onChange={(e) => toggleAutoRenew.mutate(e.target.checked)}
              />
              Renouvellement auto
            </label>
          )}
          <Btn
            disabled={subscribe.isPending || (!canAfford && !data.isPremium)}
            onClick={() => subscribe.mutate()}
          >
            {subscribe.isPending ? "…" : data.isPremium ? "Renouveler maintenant" : "Passer Premium"}
          </Btn>
        </div>
      </div>
      {subscribe.isError && (
        <p className="mt-2 text-xs text-danger">
          {subscribe.error instanceof Error ? subscribe.error.message : "Une erreur est survenue."}
        </p>
      )}
    </Panel>
  );
}