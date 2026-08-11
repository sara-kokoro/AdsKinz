import { useTranslation } from "react-i18next";
import { Panel, Quote, SectionTitle, Sparkline, StatusPill, fmtInt, fmtMoney } from "@/components/kit";
import { IconArrowUp } from "@/components/icons";
import type { PlacementStats } from "@/lib/mock-data";

const ctr = (c: number, i: number) => (i === 0 ? "0.00%" : `${((c / i) * 100).toFixed(2)}%`);

function Stat({ label, value, tone }: { label: string; value: string; tone?: "bounty" }) {
  return (
    <div className="rounded-xl border border-seam p-4">
      <p className="text-[11px] font-semibold text-paper-dim">{label}</p>
      <p className={`num mt-1.5 text-xl font-bold ${tone === "bounty" ? "text-bounty" : ""}`}>{value}</p>
    </div>
  );
}

/** Full detail view for one channel or Mini App, shared by both publisher pages. */
export function PlacementDetail({
  title,
  backLabel,
  onBack,
  status,
  subtitle,
  stats,
  configuration,
  actions,
}: {
  title: string;
  backLabel: string;
  onBack: () => void;
  status: string;
  subtitle: string;
  stats: PlacementStats;
  configuration: { label: string; value: string }[];
  actions?: React.ReactNode | undefined;
}) {
  const { t } = useTranslation();
  return (
    <div className="space-y-5">
      <button
        onClick={onBack}
        className="inline-flex items-center gap-2 text-sm font-semibold text-paper-dim transition-colors hover:text-paper"
      >
        <IconArrowUp className="-rotate-90" width={16} height={16} />
        {backLabel}
      </button>

      <Panel className="flex flex-wrap items-center gap-4">
        <div className="num flex size-12 items-center justify-center rounded-xl bg-panel-2 text-sm font-bold">
          {title.slice(0, 2).toUpperCase()}
        </div>
        <div className="min-w-40">
          <h2 className="font-display text-xl font-bold tracking-tight">{title}</h2>
          <p className="text-xs text-paper-dim">{subtitle}</p>
        </div>
        <div className="ml-auto flex flex-wrap items-center gap-3">
          <StatusPill status={status} />
          {actions}
        </div>
      </Panel>

      <Panel>
        <SectionTitle>{t("pub.detail.performance")}</SectionTitle>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Stat label={t("pub.impressions30")} value={fmtInt(stats.impressions30)} />
          <Stat label={t("pub.clicks30")} value={fmtInt(stats.clicks30)} />
          <Stat label={t("pub.ctr")} value={ctr(stats.clicks30, stats.impressions30)} />
          <Stat label={t("pub.earn30")} value={fmtMoney(stats.earnings30)} tone="bounty" />
          <Stat label={t("pub.detail.adsDelivered")} value={fmtInt(stats.adsDelivered30)} />
          <Stat label={t("pub.detail.avgCpm")} value={fmtMoney(stats.avgCpm)} />
          <Stat label={t("pub.detail.fillRate")} value={`${stats.fillRate}%`} />
          <Stat
            label={t("pub.detail.revenuePerAd")}
            value={fmtMoney(stats.adsDelivered30 ? stats.earnings30 / stats.adsDelivered30 : 0)}
          />
        </div>
        <div className="mt-4">
          <Sparkline points={stats.daily} tone="bounty" />
        </div>
      </Panel>

      <div className="grid gap-5 lg:grid-cols-2">
        <Panel>
          <SectionTitle>{t("pub.detail.configuration")}</SectionTitle>
          <dl className="divide-y divide-seam">
            {configuration.map((c) => (
              <div key={c.label} className="flex items-start gap-4 py-2.5">
                <dt className="text-sm text-paper-dim">{c.label}</dt>
                <dd className="num ml-auto max-w-[60%] text-right text-sm font-semibold break-all">{c.value}</dd>
              </div>
            ))}
          </dl>
        </Panel>

        <Panel className="p-0">
          <div className="p-5 pb-2">
            <SectionTitle>{t("pub.detail.activity")}</SectionTitle>
          </div>
          {stats.activity.length === 0 ? (
            <p className="px-5 pb-5 text-sm text-paper-dim">{t("pub.detail.noActivity")}</p>
          ) : (
            <ul className="divide-y divide-seam">
              {stats.activity.map((a) => (
                <li key={a.id} className="flex flex-wrap items-center gap-3 px-5 py-3.5">
                  <div className="min-w-40">
                    <p className="text-sm font-semibold">{a.campaign}</p>
                    <p className="num text-xs text-paper-dim">{a.at}</p>
                  </div>
                  <div className="num ml-auto flex items-center gap-4 text-xs">
                    <span>{fmtInt(a.impressions)} · {t("pub.impressions30").split(" ")[0]}</span>
                    <span>{fmtInt(a.clicks)} · {t("pub.clicks30").split(" ")[0]}</span>
                    <span className="font-bold text-bounty">{fmtMoney(a.revenue)}</span>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>

      <Quote tone="signal" label={t("common.viewDetails")}>{t("pub.quotes.detail")}</Quote>
    </div>
  );
}


