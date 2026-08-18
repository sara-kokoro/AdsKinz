import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { AdminShell } from "@/components/workspaces";
import { Avatar } from "@/components/cards";
import { Btn, EmptyState, ErrorBanner, Panel, Quote, RowSkeleton, StatusPill } from "@/components/kit";
import { useAdminQueue, useModerate } from "@/lib/queries";
import { ApiError } from "@/lib/api";
import { useAuthGuard } from "@/lib/auth";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/kingcey/mini-apps")({
  head: () => ({
    meta: [
      { title: "Mini App moderation — AdsKinz admin" },
      { name: "description", content: "Review every Mini App submission: link, formats, SDK integration and publisher history." },
      { property: "og:title", content: "Mini App moderation — AdsKinz admin" },
      { property: "og:description", content: "Approve or reject Telegram Mini App placements." },
      { name: "robots", content: "noindex" },
    ],
  }),
  component: ModMiniApps,
});

type QueueMiniApp = {
  id: string;
  name: string;
  status: string;
  url: string;
  formats: string[];
  integrationDetected: boolean;
  createdAt: string | null;
  publisherEmail?: string | null;
};

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex flex-wrap justify-between gap-2 border-b border-seam py-2 text-sm last:border-0">
      <span className="text-paper-dim">{k}</span>
      <span className="num max-w-[62%] text-right font-semibold break-all">{v || "—"}</span>
    </div>
  );
}

function ModMiniApps() {
  useAuthGuard("admin");
  const { t } = useTranslation();
  const { data, isLoading, isError, refetch } = useAdminQueue<QueueMiniApp>("mini-apps");
  const moderate = useModerate("mini-apps");
  const [sel, setSel] = useState<string | null>(null);
  const [reason, setReason] = useState("");
  const [err, setErr] = useState<string | null>(null);

  const items = data?.items ?? [];
  const app = items.find((m) => m.id === sel) ?? items[0];

  const act = (action: "approve" | "reject") => {
    if (!app) return;
    setErr(null);
    if (action === "reject" && !reason.trim()) {
      setErr("A rejection reason is required.");
      return;
    }
    moderate.mutate(
      action === "reject" ? { id: app.id, action, reason: reason.trim() } : { id: app.id, action },
      { onError: (e) => setErr(e instanceof ApiError ? e.message : "Action failed."), onSuccess: () => setReason("") },
    );
  };

  return (
    <AdminShell title={t("x.admin.miniApps")} badges={{ miniapps: data?.total ?? 0 }}>
      {isError && <ErrorBanner onRetry={refetch} />}
      {isLoading ? (
        <Panel className="p-0"><RowSkeleton rows={5} /></Panel>
      ) : (
        <div className="grid gap-5 lg:grid-cols-[320px_1fr]">
          <Panel className="p-0">
            {items.length === 0 ? (
              <EmptyState title={t("x.admin.empty")} positive />
            ) : (
              <ul className="divide-y divide-seam">
                {items.map((m) => (
                  <li key={m.id}>
                    <button onClick={() => setSel(m.id)} className={cn("flex w-full items-center gap-3 px-4 py-4 text-left", app?.id === m.id && "bg-panel-2")}>
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
                  <Row k={t("admin.publisher")} v={app.publisherEmail ?? "—"} />
                  <Row k={t("x.admin.directLink")} v={app.url} />
                  <Row k={t("x.admin.integration")} v={app.integrationDetected ? t("common.yes") : t("common.no")} />
                  <Row k={t("adv.format")} v={app.formats.join(", ")} />
                  <Row k={t("admin.submittedAt")} v={app.createdAt ?? "—"} />
                </div>
              </Panel>

              {!app.integrationDetected && (
                <Quote tone="danger" label={t("x.admin.integration")}>{t("common.no")}</Quote>
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
          )}
        </div>
      )}
    </AdminShell>
  );
}
