import { createFileRoute, Link } from "@tanstack/react-router";
import { useTranslation } from "react-i18next";
import { useState } from "react";
import { AdvShell } from "@/components/workspaces";
import { CampaignCard, Segmented } from "@/components/cards";
import { Btn, EmptyState, ErrorBanner, Panel, Quote, RowSkeleton } from "@/components/kit";
import { IconTrend } from "@/components/icons";
import { ArtCampaignEmpty } from "@/components/illustrations";
import { useCampaigns, useUpdateCampaign } from "@/lib/queries";
import { num } from "@/lib/api";

export const Route = createFileRoute("/traffic/campaigns/")({
  head: () => ({
    meta: [
      { title: "Campaigns — AdsKinz traffic" },
      { name: "description", content: "All your Telegram campaigns as cards: status, views, clicks, budget consumption and quick actions." },
      { property: "og:title", content: "Campaigns — AdsKinz traffic" },
      { property: "og:description", content: "Manage native Telegram channel and Mini App campaigns." },
    ],
  }),
  component: CampaignsPage,
});

function CampaignsPage() {
  const { t } = useTranslation();
  const [filter, setFilter] = useState<"all" | "active" | "pending_review" | "stopped">("all");
  const campaignsQ = useCampaigns(filter === "all" ? undefined : filter);

  const list = (campaignsQ.data ?? []).filter((c) =>
    filter === "all"
      ? true
      : filter === "stopped"
        ? ["stopped", "rejected", "paused", "paused_balance"].includes(c.status)
        : c.status === filter,
  );

  return (
    <AdvShell
      title={t("adv.nav.campaigns")}
      action={
        <Link to="/traffic/campaigns/new">
          <Btn>{t("adv.newCampaign")}</Btn>
        </Link>
      }
    >
      <div className="space-y-5">
        <Quote tone="signal" label={t("adv.nav.campaigns")}>{t("adv.wizard.editNotice")}</Quote>

        <Segmented
          value={filter}
          onChange={setFilter}
          options={[
            { v: "all" as const, l: t("common.all") },
            { v: "active" as const, l: t("status.active") },
            { v: "pending_review" as const, l: t("status.pending_review") },
            { v: "stopped" as const, l: t("status.stopped") },
          ]}
        />

        {campaignsQ.isError ? (
          <Panel><ErrorBanner onRetry={() => campaignsQ.refetch()} message={(campaignsQ.error as Error)?.message} /></Panel>
        ) : campaignsQ.isLoading ? (
          <Panel className="p-0"><RowSkeleton rows={4} /></Panel>
        ) : list.length === 0 ? (
          <Panel className="p-0">
            <EmptyState
              title={t("adv.emptyTitle")}
              sub={t("adv.emptySub")}
              action={
                <div className="flex flex-col items-center gap-4">
                  <ArtCampaignEmpty />
                  <Link to="/traffic/campaigns/new"><Btn>{t("adv.emptyCta")}</Btn></Link>
                </div>
              }
            />
          </Panel>
        ) : (
          <div className="grid gap-4 lg:grid-cols-2">
            {list.map((c) => (
              <CampaignRow key={c.id} id={c.id} name={c.name} status={c.status} views={c.impressions} clicks={c.clicks} spent={num(c.spent)} budget={num(c.budget) || 1} />
            ))}
          </div>
        )}
      </div>
    </AdvShell>
  );
}

function CampaignRow({
  id,
  name,
  status,
  views,
  clicks,
  spent,
  budget,
}: {
  id: string;
  name: string;
  status: string;
  views: number;
  clicks: number;
  spent: number;
  budget: number;
}) {
  const { t } = useTranslation();
  const update = useUpdateCampaign(id);

  return (
    <CampaignCard
      name={name}
      status={status}
      views={views}
      clicks={clicks}
      spent={spent}
      budget={budget}
      labels={{ views: t("x.cards.views"), clicks: t("x.cards.clicks"), budget: t("x.cards.budget") }}
      actions={
        <>
          <Btn
            variant="secondary"
            className="w-full justify-center"
            disabled={update.isPending || !["active", "paused"].includes(status)}
            onClick={() => update.mutate({ status: status === "active" ? "paused" : "active" })}
          >
            {status === "active" ? t("x.cards.pause") : t("x.cards.resume")}
          </Btn>
          <Link to="/traffic/campaigns/$id" params={{ id }} className="w-full">
            <Btn variant="secondary" className="w-full justify-center text-signal">
              <IconTrend width={16} height={16} />
              {t("x.cards.stats")}
            </Btn>
          </Link>
        </>
      }
    />
  );
}
