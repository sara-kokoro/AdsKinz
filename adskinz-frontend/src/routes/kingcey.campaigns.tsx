import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { AdminShell } from "@/components/workspaces";
import { Btn, EmptyState, ErrorBanner, Panel, RowSkeleton, StatusPill, fmtMoney } from "@/components/kit";
import { TelegramPostPreview } from "@/components/telegram-preview";
import { useAdminQueue, useModerate } from "@/lib/queries";
import { num, ApiError } from "@/lib/api";
import { useAuthGuard } from "@/lib/auth";
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

type QueueCampaign = {
  id: string;
  name: string;
  status: string;
  format: string;
  cpm: string;
  budget: string;
  dailyBudget: string | null;
  destinationUrl: string | null;
  buttonLabel: string | null;
  copy: string | null;
  language: string;
  trackingId: string | null;
  createdAt: string | null;
  advertiserEmail?: string | null;
  advertiserId?: string | null;
};

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex flex-wrap justify-between gap-2 border-b border-seam py-2 text-sm last:border-0">
      <span className="text-paper-dim">{k}</span>
      <span className="num max-w-[60%] text-right font-semibold break-all">{v || "—"}</span>
    </div>
  );
}

function ModCampaigns() {
  useAuthGuard("admin");
  const { t } = useTranslation();
  const { data, isLoading, isError, refetch } = useAdminQueue<QueueCampaign>("campaigns");
  const moderate = useModerate("campaigns");
  const [sel, setSel] = useState<string | null>(null);
  const [reason, setReason] = useState("");
  const [err, setErr] = useState<string | null>(null);

  const items = data?.items ?? [];
  const item = items.find((c) => c.id === sel) ?? items[0];

  const act = (action: "approve" | "reject") => {
    if (!item) return;
    setErr(null);
    if (action === "reject" && !reason.trim()) {
      setErr("A rejection reason is required.");
      return;
    }
    moderate.mutate(
      action === "reject" ? { id: item.id, action, reason: reason.trim() } : { id: item.id, action },
      {
        onError: (e) => setErr(e instanceof ApiError ? e.message : "Action failed."),
        onSuccess: () => setReason(""),
      },
    );
  };

  return (
    <AdminShell title={t("admin.nav.campaigns")} badges={{ campaigns: data?.total ?? 0 }}>
      {isError && <ErrorBanner onRetry={refetch} />}
      {isLoading ? (
        <Panel className="p-0"><RowSkeleton rows={5} /></Panel>
      ) : items.length === 0 ? (
        <Panel className="p-0"><EmptyState title="Nothing pending" sub="No campaigns are waiting for review." positive /></Panel>
      ) : (
        <div className="grid gap-5 lg:grid-cols-[320px_1fr]">
          <Panel className="p-0">
            <ul className="divide-y divide-seam">
              {items.map((c) => (
                <li key={c.id}>
                  <button onClick={() => setSel(c.id)} className={cn("w-full px-4 py-4 text-left", (item?.id === c.id) && "bg-panel-2")}>
                    <p className="font-bold">{c.name}</p>
                    <p className="num text-xs text-paper-dim">{c.id}{c.advertiserEmail ? ` · ${c.advertiserEmail}` : ""}</p>
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
                  <Row k={t("admin.advertiser")} v={item.advertiserEmail ?? item.advertiserId ?? "—"} />
                  <Row k={t("admin.submittedAt")} v={item.createdAt ?? "—"} />
                  <Row k={t("adv.format")} v={item.format} />
                  <Row k={t("adv.budget")} v={fmtMoney(num(item.budget))} />
                  <Row k={t("adv.dailyBudget")} v={item.dailyBudget ? fmtMoney(num(item.dailyBudget)) : "—"} />
                  <Row k={t("adv.cpm")} v={fmtMoney(num(item.cpm))} />
                  <Row k={t("adv.button")} v={item.buttonLabel ?? "—"} />
                  <Row k={t("adv.destination")} v={item.destinationUrl ?? "—"} />
                  <Row k={t("adv.trackingId")} v={item.trackingId ?? "—"} />
                  <Row k={t("pub.form.lang")} v={item.language} />
                </div>
                <div className="mt-4 rounded-xl border border-seam bg-panel-2 p-4 text-sm whitespace-pre-line">{item.copy}</div>
              </Panel>

              <Panel>
                <p className="mb-3 text-xs font-semibold text-paper-dim">{t("adv.preview")}</p>
                <TelegramPostPreview copy={item.copy ?? ""} buttonLabel={item.buttonLabel ?? ""} channel={item.name} />
              </Panel>

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
