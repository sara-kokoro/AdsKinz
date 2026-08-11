import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { AdminShell } from "@/components/workspaces";
import { Btn, Panel, StatusPill, fmtMoney } from "@/components/kit";
import { TelegramPostPreview } from "@/components/telegram-preview";
import { adminCampaignQueue } from "@/lib/mock-data";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/kingcey/campaigns")({
  head: () => ({
    meta: [
      { title: "Campaign moderation — AdsKinz admin" },
      { name: "description", content: "Manual review of every advertiser submission: creative, targeting, budget and account history." },
      { property: "og:title", content: "Campaign moderation — AdsKinz admin" },
      { property: "og:description", content: "Full submission detail for manual approval or rejection." },
      { name: "robots", content: "noindex" },
    ],
  }),
  component: ModCampaigns,
});

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex flex-wrap justify-between gap-2 border-b border-seam py-2 text-sm last:border-0">
      <span className="text-paper-dim">{k}</span>
      <span className="num max-w-[60%] text-right font-semibold break-all">{v}</span>
    </div>
  );
}

function ModCampaigns() {
  const { t } = useTranslation();
  const [sel, setSel] = useState(adminCampaignQueue[0]?.id ?? "");
  const item = adminCampaignQueue.find((c) => c.id === sel);

  return (
    <AdminShell title={t("admin.nav.campaigns")} badges={{ campaigns: adminCampaignQueue.length }}>
      <div className="grid gap-5 lg:grid-cols-[320px_1fr]">
        <Panel className="p-0">
          <ul className="divide-y divide-seam">
            {adminCampaignQueue.map((c) => (
              <li key={c.id}>
                <button onClick={() => setSel(c.id)} className={cn("w-full px-4 py-4 text-left", sel === c.id && "bg-panel-2")}>
                  <p className="font-bold">{c.name}</p>
                  <p className="num text-xs text-paper-dim">{c.id} · {c.submission.advertiser.name}</p>
                  <div className="mt-2"><StatusPill status={c.status} /></div>
                </button>
              </li>
            ))}
          </ul>
        </Panel>

        {item && (
          <div className="space-y-5">
            <Panel>
              <h2 className="font-display text-lg font-bold">{item.name}</h2>
              <div className="mt-3 grid gap-x-8 md:grid-cols-2">
                <Row k={t("admin.advertiser")} v={item.submission.advertiser.name} />
                <Row k={t("admin.email")} v={item.submission.advertiser.email} />
                <Row k={t("admin.accountCreated")} v={item.submission.advertiser.createdAt} />
                <Row k={t("admin.pastCampaigns")} v={String(item.submission.advertiser.pastCampaigns)} />
                <Row k={t("adv.balance")} v={fmtMoney(item.submission.advertiser.balance)} />
                <Row k={t("admin.submittedAt")} v={item.submission.submittedAt} />
                <Row k={t("admin.ip")} v={item.submission.ip} />
                <Row k={t("adv.format")} v={item.format} />
                <Row k={t("adv.targeting")} v={item.submission.targeting} />
                <Row k={t("adv.budget")} v={fmtMoney(item.budget)} />
                <Row k={t("adv.dailyBudget")} v={item.submission.dailyBudget ? fmtMoney(item.submission.dailyBudget) : "—"} />
                <Row k={t("adv.cpm")} v={fmtMoney(item.cpm)} />
                <Row k={t("adv.button")} v={item.submission.buttonLabel} />
                <Row k={t("adv.destination")} v={item.submission.destinationUrl} />
                <Row k={t("adv.trackingId")} v={item.submission.trackingId} />
                <Row k={t("admin.imageAlt")} v={item.submission.imageAlt} />
              </div>
              <div className="mt-4 rounded-xl border border-seam bg-panel-2 p-4 text-sm whitespace-pre-line">{item.submission.copy}</div>
            </Panel>

            <Panel>
              <p className="mb-3 text-xs font-semibold text-paper-dim">{t("adv.preview")}</p>
              <TelegramPostPreview copy={item.submission.copy} buttonLabel={item.submission.buttonLabel} channel={item.name} />
            </Panel>

            <Panel className="flex flex-wrap items-center gap-3">
              <Btn tone="bounty">{t("admin.approve")}</Btn>
              <Btn tone="danger">{t("admin.reject")}</Btn>
              <input className="min-h-11 flex-1 rounded-xl border border-seam bg-transparent px-3 text-sm" placeholder={t("admin.rejectReason")} aria-label={t("admin.rejectReason")} />
            </Panel>
          </div>
        )}
      </div>
    </AdminShell>
  );
}
