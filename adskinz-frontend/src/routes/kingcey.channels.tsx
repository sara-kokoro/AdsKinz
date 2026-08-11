import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { AdminShell } from "@/components/workspaces";
import { Btn, Panel, StatusPill, fmtInt, fmtMoney } from "@/components/kit";
import { adminChannelQueue } from "@/lib/mock-data";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/kingcey/channels")({
  head: () => ({
    meta: [
      { title: "Channel & Mini App moderation — AdsKinz admin" },
      { name: "description", content: "Manual review of publisher submissions: links, bot status, slots and account history." },
      { property: "og:title", content: "Channel & Mini App moderation — AdsKinz admin" },
      { property: "og:description", content: "Everything a publisher submitted, in one review panel." },
      { name: "robots", content: "noindex" },
    ],
  }),
  component: ModChannels,
});

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex flex-wrap justify-between gap-2 border-b border-seam py-2 text-sm last:border-0">
      <span className="text-paper-dim">{k}</span>
      <span className="num max-w-[60%] text-right font-semibold break-all">{v}</span>
    </div>
  );
}

function ModChannels() {
  const { t } = useTranslation();
  const [sel, setSel] = useState(adminChannelQueue[0]?.id ?? "");
  const ch = adminChannelQueue.find((c) => c.id === sel);

  return (
    <AdminShell title={t("admin.nav.channels")} badges={{ channels: adminChannelQueue.length }}>
      <div className="grid gap-5 lg:grid-cols-[320px_1fr]">
        <Panel className="p-0">
          <ul className="divide-y divide-seam">
            {adminChannelQueue.map((c) => (
              <li key={c.id}>
                <button onClick={() => setSel(c.id)} className={cn("w-full px-4 py-4 text-left", sel === c.id && "bg-panel-2")}>
                  <p className="font-bold">{c.name}</p>
                  <p className="num text-xs text-paper-dim">{c.id}</p>
                  <div className="mt-2"><StatusPill status={c.status} /></div>
                </button>
              </li>
            ))}
          </ul>
        </Panel>

        <div className="space-y-5">
          {ch && (
            <Panel>
              <h2 className="font-display text-lg font-bold">{ch.name}</h2>
              <div className="mt-3 grid gap-x-8 md:grid-cols-2">
                <Row k={t("admin.publisher")} v={ch.submission.publisher.name} />
                <Row k={t("admin.email")} v={ch.submission.publisher.email} />
                <Row k={t("admin.accountCreated")} v={ch.submission.publisher.createdAt} />
                <Row k={t("admin.lifetimeEarnings")} v={fmtMoney(ch.submission.publisher.lifetimeEarnings)} />
                <Row k={t("pub.subscribers")} v={fmtInt(ch.subscribers)} />
                <Row k={t("pub.form.lang")} v={ch.language} />
                <Row k={t("pub.form.frequency")} v={`${ch.frequency}${t("common.perDay")}`} />
                <Row k={t("pub.form.publicLink")} v={ch.submission.publicLink} />
                <Row k={t("admin.inviteLink")} v={ch.submission.inviteLink} />
                <Row k={t("pub.form.adminUsername")} v={ch.submission.adminUsername} />
                <Row k={t("admin.botAdmin")} v={ch.submission.botIsAdmin ? t("common.yes") : t("common.no")} />
                <Row k={t("pub.form.slots")} v={ch.submission.slots.join(", ") || "—"} />
                <Row k={t("admin.submittedAt")} v={ch.submission.submittedAt} />
                <Row k={t("admin.ip")} v={ch.submission.ip} />
              </div>
              <p className="mt-4 rounded-xl border border-seam bg-panel-2 p-4 text-sm">{ch.submission.description}</p>
            </Panel>
          )}
          <Panel className="flex flex-wrap items-center gap-3">
            <Btn tone="bounty">{t("admin.approve")}</Btn>
            <Btn tone="danger">{t("admin.reject")}</Btn>
            <input className="min-h-11 flex-1 rounded-xl border border-seam bg-transparent px-3 text-sm" placeholder={t("admin.rejectReason")} aria-label={t("admin.rejectReason")} />
          </Panel>
        </div>
      </div>
    </AdminShell>
  );
}
