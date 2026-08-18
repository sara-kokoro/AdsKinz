import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { AdminShell } from "@/components/workspaces";
import { Btn, EmptyState, ErrorBanner, Panel, RowSkeleton, StatusPill, fmtInt } from "@/components/kit";
import { useAdminQueue, useModerate } from "@/lib/queries";
import { ApiError } from "@/lib/api";
import { useAuthGuard } from "@/lib/auth";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/kingcey/channels")({
  head: () => ({
    meta: [
      { title: "Channel moderation — AdsKinz admin" },
      { name: "description", content: "Manual review of publisher channel submissions: links, bot status, slots and account history." },
      { property: "og:title", content: "Channel moderation — AdsKinz admin" },
      { property: "og:description", content: "Everything a publisher submitted, in one review panel." },
      { name: "robots", content: "noindex" },
    ],
  }),
  component: ModChannels,
});

type QueueChannel = {
  id: string;
  name: string;
  status: string;
  language: string;
  subscribers: number;
  maxAdsPerDay: number;
  publicLink: string | null;
  privateLink: string | null;
  adminUsername: string | null;
  botAdminVerified: boolean;
  createdAt: string | null;
  publisherEmail?: string | null;
};

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex flex-wrap justify-between gap-2 border-b border-seam py-2 text-sm last:border-0">
      <span className="text-paper-dim">{k}</span>
      <span className="num max-w-[60%] text-right font-semibold break-all">{v || "—"}</span>
    </div>
  );
}

function ModChannels() {
  useAuthGuard("admin");
  const { t } = useTranslation();
  const { data, isLoading, isError, refetch } = useAdminQueue<QueueChannel>("channels");
  const moderate = useModerate("channels");
  const [sel, setSel] = useState<string | null>(null);
  const [reason, setReason] = useState("");
  const [err, setErr] = useState<string | null>(null);

  const items = data?.items ?? [];
  const ch = items.find((c) => c.id === sel) ?? items[0];

  const act = (action: "approve" | "reject") => {
    if (!ch) return;
    setErr(null);
    if (action === "reject" && !reason.trim()) {
      setErr("A rejection reason is required.");
      return;
    }
    moderate.mutate(
      action === "reject" ? { id: ch.id, action, reason: reason.trim() } : { id: ch.id, action },
      { onError: (e) => setErr(e instanceof ApiError ? e.message : "Action failed."), onSuccess: () => setReason("") },
    );
  };

  return (
    <AdminShell title={t("admin.nav.channels")} badges={{ channels: data?.total ?? 0 }}>
      {isError && <ErrorBanner onRetry={refetch} />}
      {isLoading ? (
        <Panel className="p-0"><RowSkeleton rows={5} /></Panel>
      ) : items.length === 0 ? (
        <Panel className="p-0"><EmptyState title="Nothing pending" sub="No channels are waiting for review." positive /></Panel>
      ) : (
        <div className="grid gap-5 lg:grid-cols-[320px_1fr]">
          <Panel className="p-0">
            <ul className="divide-y divide-seam">
              {items.map((c) => (
                <li key={c.id}>
                  <button onClick={() => setSel(c.id)} className={cn("w-full px-4 py-4 text-left", ch?.id === c.id && "bg-panel-2")}>
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
                  <Row k={t("admin.publisher")} v={ch.publisherEmail ?? "—"} />
                  <Row k={t("pub.subscribers")} v={fmtInt(ch.subscribers)} />
                  <Row k={t("pub.form.lang")} v={ch.language} />
                  <Row k={t("pub.form.frequency")} v={`${ch.maxAdsPerDay}${t("common.perDay")}`} />
                  <Row k={t("pub.form.publicLink")} v={ch.publicLink ?? "—"} />
                  <Row k={t("admin.inviteLink")} v={ch.privateLink ?? "—"} />
                  <Row k={t("pub.form.adminUsername")} v={ch.adminUsername ?? "—"} />
                  <Row k={t("admin.botAdmin")} v={ch.botAdminVerified ? t("common.yes") : t("common.no")} />
                  <Row k={t("admin.submittedAt")} v={ch.createdAt ?? "—"} />
                </div>
              </Panel>
            )}
            <Panel className="flex flex-wrap items-center gap-3">
              <Btn tone="bounty" disabled={moderate.isPending} onClick={() => act("approve")}>
                {moderate.isPending ? "Working…" : t("admin.approve")}
              </Btn>
              <Btn tone="danger" disabled={moderate.isPending} onClick={() => act("reject")}>
                {moderate.isPending ? "Working…" : t("admin.reject")}
              </Btn>
              <input
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                className="min-h-11 flex-1 rounded-xl border border-seam bg-transparent px-3 text-sm"
                placeholder={t("admin.rejectReason")}
                aria-label={t("admin.rejectReason")}
              />
            </Panel>
            {err && <p className="text-sm font-semibold text-danger">{err}</p>}
          </div>
        </div>
      )}
    </AdminShell>
  );
}
