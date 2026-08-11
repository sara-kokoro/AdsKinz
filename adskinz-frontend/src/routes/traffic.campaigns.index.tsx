import { createFileRoute, Link } from "@tanstack/react-router";
import { useTranslation } from "react-i18next";
import { AdvShell } from "@/components/workspaces";
import { CampaignCard, Segmented } from "@/components/cards";
import { Btn, EmptyState, Panel, Quote, RowSkeleton, useFakeLoad } from "@/components/kit";
import { IconTrend } from "@/components/icons";
import { campaigns } from "@/lib/mock-data";
import { useState } from "react";

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
  const { loading } = useFakeLoad();
  const [filter, setFilter] = useState<"all" | "active" | "pending_review" | "stopped">("all");

  const list = campaigns.filter((c) =>
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

        {loading ? (
          <Panel className="p-0"><RowSkeleton rows={4} /></Panel>
        ) : list.length === 0 ? (
          <Panel className="p-0">
            <EmptyState
              title={t("adv.emptyTitle")}
              sub={t("adv.emptySub")}
              action={<Link to="/traffic/campaigns/new"><Btn>{t("adv.emptyCta")}</Btn></Link>}
            />
          </Panel>
        ) : (
          <div className="grid gap-4 lg:grid-cols-2">
            {list.map((c) => (
              <CampaignCard
                key={c.id}
                name={c.name}
                status={c.status}
                views={c.impressions}
                clicks={c.clicks}
                spent={c.spent}
                budget={c.budget}
                labels={{ views: t("x.cards.views"), clicks: t("x.cards.clicks"), budget: t("x.cards.budget") }}
                actions={
                  <>
                    <Btn variant="secondary" className="w-full justify-center">
                      {c.status === "active" ? t("x.cards.pause") : t("x.cards.resume")}
                    </Btn>
                    <Link to="/traffic/campaigns/$id" params={{ id: c.id }} className="w-full">
                      <Btn variant="secondary" className="w-full justify-center text-signal">
                        <IconTrend width={16} height={16} />
                        {t("x.cards.stats")}
                      </Btn>
                    </Link>
                  </>
                }
              />
            ))}
          </div>
        )}
      </div>
    </AdvShell>
  );
}
