import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { AdminShell } from "@/components/workspaces";
import { Avatar } from "@/components/cards";
import { Btn, EmptyState, Panel, Quote, StatusPill, fmtInt, fmtMoney } from "@/components/kit";
import { adminMiniAppQueue } from "@/lib/mock-data";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/kingcey/mini-apps")({
  head: () => ({
    meta: [
      { title: "Mini App moderation — AdsKinz admin" },
      { name: "description", content: "Review every Mini App submission: direct link, original site, bot ID, SDK integration and publisher history." },
      { property: "og:title", content: "Mini App moderation — AdsKinz admin" },
      { property: "og:description", content: "Approve or reject Telegram Mini App placements." },
      { name: "robots", content: "noindex" },
    ],
  }),
  component: ModMiniApps,
});

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex flex-wrap justify-between gap-2 border-b border-seam py-2 text-sm last:border-0">
      <span className="text-paper-dim">{k}</span>
      <span className="num max-w-[62%] text-right font-semibold break-all">{v || "—"}</span>
    </div>
  );
}

function ModMiniApps() {
  const { t } = useTranslation();
  const [sel, setSel] = useState(adminMiniAppQueue[0]?.id ?? "");
  const app = adminMiniAppQueue.find((m) => m.id === sel);

  return (
    <AdminShell title={t("x.admin.miniApps")} badges={{ miniapps: adminMiniAppQueue.length }}>
      <div className="grid gap-5 lg:grid-cols-[320px_1fr]">
        <Panel className="p-0">
          {adminMiniAppQueue.length === 0 ? (
            <EmptyState title={t("x.admin.empty")} />
          ) : (
            <ul className="divide-y divide-seam">
              {adminMiniAppQueue.map((m) => (
                <li key={m.id}>
                  <button onClick={() => setSel(m.id)} className={cn("flex w-full items-center gap-3 px-4 py-4 text-left", sel === m.id && "bg-panel-2")}>
                    <Avatar name={m.name} size={40} />
                    <div className="min-w-0">
                      <p className="truncate font-bold">{m.name}</p>
                      <p className="num truncate text-xs text-paper-dim">{m.id}</p>
                      <div className="mt-2"><StatusPill status={m.status} /></div>
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Panel>

        {app && (
          <div className="space-y-5">
            <Panel className="glass">
              <h2 className="font-display text-lg font-bold">{app.name}</h2>
              <div className="mt-3 grid gap-x-8 md:grid-cols-2">
                <Row k={t("admin.publisher")} v={app.submission.publisher.name} />
                <Row k={t("admin.email")} v={app.submission.publisher.email} />
                <Row k={t("admin.accountCreated")} v={app.submission.publisher.createdAt} />
                <Row k={t("admin.lifetimeEarnings")} v={fmtMoney(app.submission.publisher.lifetimeEarnings)} />
                <Row k={t("x.admin.directLink")} v={app.submission.directLink} />
                <Row k={t("x.admin.originalLink")} v={app.submission.originalLink} />
                <Row k={t("x.admin.botId")} v={app.submission.botId} />
                <Row k={t("pub.form.kinzKey")} v={app.kinzKey} />
                <Row k={t("x.admin.sdk")} v={app.submission.sdkVersion} />
                <Row k={t("x.admin.integration")} v={app.submission.integrationDetected ? t("common.yes") : t("common.no")} />
                <Row k={t("x.admin.mau")} v={fmtInt(app.submission.monthlyActiveUsers)} />
                <Row k={t("adv.format")} v={app.formats.join(", ")} />
                <Row k={t("admin.submittedAt")} v={app.submission.submittedAt} />
                <Row k={t("admin.ip")} v={app.submission.ip} />
              </div>
              <p className="mt-4 rounded-xl border border-seam bg-panel-2 p-4 text-sm">{app.submission.description}</p>
            </Panel>

            {!app.submission.integrationDetected && (
              <Quote tone="danger" label={t("x.admin.integration")}>{t("common.no")}</Quote>
            )}

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
