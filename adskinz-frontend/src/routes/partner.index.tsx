import { createFileRoute, Link } from "@tanstack/react-router";
import { useTranslation } from "react-i18next";
import { PubShell } from "@/components/workspaces";
import {
  Btn,
  CountUp,
  ErrorBanner,
  KpiSkeleton,
  Panel,
  Quote,
  SectionTitle,
  Sparkline,
  fmtInt,
  fmtMoney,
} from "@/components/kit";
import { UsdtMark } from "@/components/usdt";
import { ArtChannelPayout } from "@/components/illustrations";
import { LottieAnimation } from "@/components/lottie-animation";
import { num } from "@/lib/api";
import { usePublisherStats } from "@/lib/queries";
import { useAuthGuard } from "@/lib/auth";

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

function PubDashboard() {
  useAuthGuard("publisher");
  const { t } = useTranslation();
  const { data, isLoading, isError, refetch, isFetching } = usePublisherStats();

  const available = num(data?.availableBalance);
  const held = num(data?.heldBalance);
  const lifetime = num(data?.lifetimeEarnings);
  const impressions30 = data?.impressions30 ?? 0;
  const clicks30 = data?.clicks30 ?? 0;
  const activeChannels = data?.activeChannels ?? 0;
  const activeMiniApps = data?.activeMiniApps ?? 0;
  const daily = data?.daily?.length ? data.daily : [0, 0];
  const ctr = impressions30 === 0 ? 0 : (clicks30 / impressions30) * 100;

  const kpis = [
    { label: t("pub.totalImpressions"), value: fmtInt(impressions30) },
    { label: t("pub.totalClicks"), value: fmtInt(clicks30) },
    { label: t("pub.ctr"), value: `${ctr.toFixed(2)}%` },
    { label: t("pub.nav.channels"), value: fmtInt(activeChannels) },
    { label: t("pub.nav.miniapps"), value: fmtInt(activeMiniApps) },
    { label: "Held balance", value: fmtMoney(held) },
  ];

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
          <div className="min-w-56 flex-1">
            <p className="text-sm font-semibold text-paper-dim">{t("pub.heroMetric")}</p>
            <p className="mt-2 flex items-center gap-2 font-display text-4xl font-extrabold text-bounty sm:text-5xl">
              <UsdtMark size={32} />
              {isLoading ? "…" : <CountUp value={lifetime} money />}
              <LottieAnimation src="/money-bag.json" className="h-10 w-10 shrink-0" />
            </p>
            <p className="num mt-2 text-sm text-paper-dim">
              {t("pub.balance")}: <span className="font-bold text-paper">{fmtMoney(available)}</span>
            </p>
          </div>
          <ArtChannelPayout className="max-w-[220px]" />
        </Panel>

        {isError && <ErrorBanner onRetry={() => void refetch()} />}

        <Quote tone="bounty" label={t("pub.nav.withdrawals")}>{t("pub.quotes.payout")}</Quote>

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {isLoading
            ? [0, 1, 2, 3, 4, 5].map((i) => <KpiSkeleton key={i} />)
            : kpis.map((k) => (
                <Panel key={k.label}>
                  <div className="flex items-center gap-2">
                    <p className="text-xs font-semibold text-paper-dim">{k.label}</p>
                    {k.label === t("pub.totalImpressions") && (
                      <LottieAnimation src="/view.json" className="h-5 w-5 shrink-0" pauseSeconds={8} />
                    )}
                  </div>
                  <p className="num mt-2 text-2xl font-bold">{k.value}</p>
                </Panel>
              ))}
        </div>

        <Panel className="p-0">
          <div className="p-5">
            <SectionTitle sub="Daily impressions over the last period.">{t("pub.perfTitle")}</SectionTitle>
            {isLoading ? (
              <div className="h-24 animate-pulse rounded-md bg-panel-2" />
            ) : (
              <Sparkline points={daily} tone="bounty" className="h-24" />
            )}
            {isFetching && !isLoading && <p className="mt-2 text-xs text-paper-dim">Refreshing…</p>}
          </div>
        </Panel>

        <Quote tone="neutral" label={t("pub.nav.dashboard")}>{t("pub.quotes.quality")}</Quote>
      </div>
    </PubShell>
  );
}