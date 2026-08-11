import { useTranslation } from "react-i18next";
import {
  BudgetBar,
  EmptyState,
  ErrorBanner,
  Panel,
  RowSkeleton,
  StatusPill,
  fmtInt,
  fmtMoney,
} from "@/components/kit";
import type { Campaign } from "@/lib/mock-data";
import { Link } from "@tanstack/react-router";
import { Btn } from "@/components/kit";

function FormatBadge({ format }: { format: Campaign["format"] }) {
  const label = format === "channel" ? "Channel post" : format === "interstitial" ? "Interstitial" : "Pop interstitial";
  return (
    <span className="rounded-md border border-seam px-2 py-0.5 text-[11px] font-semibold text-paper-dim">{label}</span>
  );
}

export function CampaignTable({
  data,
  loading,
  error,
  onRetry,
}: {
  data: Campaign[];
  loading: boolean;
  error: boolean;
  onRetry: () => void;
}) {
  const { t } = useTranslation();

  if (error) {
    return (
      <div className="p-5">
        <ErrorBanner onRetry={onRetry} />
      </div>
    );
  }
  if (loading) return <RowSkeleton rows={5} />;
  if (data.length === 0) {
    return (
      <EmptyState
        title={t("adv.emptyTitle")}
        sub={t("adv.emptySub")}
        action={
          <Link to="/traffic/campaigns/new">
            <Btn>{t("adv.emptyCta")}</Btn>
          </Link>
        }
      />
    );
  }

  return (
    <>
      {/* table on >=640px */}
      <div className="hidden overflow-x-auto sm:block">
        <table className="w-full text-left text-sm">
          <thead className="text-xs font-semibold text-paper-dim">
            <tr className="border-b border-seam">
              <th className="px-5 py-3">{t("adv.colCampaign")}</th>
              <th className="px-5 py-3">{t("adv.colStatus")}</th>
              <th className="px-5 py-3">{t("adv.colFormat")}</th>
              <th className="px-5 py-3">{t("adv.colCpm")}</th>
              <th className="px-5 py-3 min-w-44">{t("adv.colBudget")}</th>
              <th className="px-5 py-3">{t("adv.colClicks")}</th>
              <th className="px-5 py-3 text-right"><span className="sr-only">{t("adv.detail.view")}</span></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-seam">
            {data.map((c) => (
              <tr key={c.id} className="transition-colors hover:bg-panel-2">
                <td className="px-5 py-4">
                  <Link to="/traffic/campaigns/$id" params={{ id: c.id }} className="font-semibold hover:text-signal">
                    {c.name}
                  </Link>
                  <p className="text-xs text-paper-dim">{c.language}</p>
                  {c.rejectionReason && <p className="mt-1 text-xs text-danger">{c.rejectionReason}</p>}
                </td>
                <td className="px-5 py-4"><StatusPill status={c.status} /></td>
                <td className="px-5 py-4"><FormatBadge format={c.format} /></td>
                <td className="num px-5 py-4 font-semibold">{fmtMoney(c.cpm)}</td>
                <td className="px-5 py-4">
                  <p className="num text-xs font-semibold text-bounty">
                    {fmtMoney(c.spent)} / {fmtMoney(c.budget, 0)}
                  </p>
                  <div className="mt-2"><BudgetBar used={c.spent} total={c.budget} /></div>
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

      {/* stacked cards under 640px */}
      <div className="divide-y divide-seam sm:hidden">
        {data.map((c) => (
          <div key={c.id} className="space-y-3 p-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="font-semibold">{c.name}</p>
                <p className="text-xs text-paper-dim">{c.language}</p>
              </div>
              <StatusPill status={c.status} />
            </div>
            <div className="flex flex-wrap items-center gap-3 text-xs text-paper-dim">
              <FormatBadge format={c.format} />
              <span className="num">CPM {fmtMoney(c.cpm)}</span>
              <span className="num">{fmtInt(c.clicks)} clicks</span>
            </div>
            <div>
              <p className="num text-xs font-semibold text-bounty">
                {fmtMoney(c.spent)} / {fmtMoney(c.budget, 0)}
              </p>
              <div className="mt-2"><BudgetBar used={c.spent} total={c.budget} /></div>
            </div>
            {c.rejectionReason && <p className="text-xs text-danger">{c.rejectionReason}</p>}
            <Link to="/traffic/campaigns/$id" params={{ id: c.id }} className="inline-block text-xs font-semibold text-signal">
              {t("adv.detail.view")} →
            </Link>
          </div>
        ))}
      </div>
    </>
  );
}

export function TablePanel({ title, children, aside }: { title: string; children: React.ReactNode; aside?: React.ReactNode }) {
  return (
    <Panel className="p-0">
      <div className="flex flex-wrap items-center gap-3 border-b border-seam px-5 py-4">
        <h2 className="font-display text-base font-bold">{title}</h2>
        <div className="ml-auto">{aside}</div>
      </div>
      {children}
    </Panel>
  );
}
