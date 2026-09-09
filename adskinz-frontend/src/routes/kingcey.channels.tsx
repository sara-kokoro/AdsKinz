import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { AdminShell } from "@/components/workspaces";
import {
  Btn, EmptyState, ErrorBanner, LoadMoreSentinel, Panel, RowSkeleton, StatusPill, fmtInt, fmtMoney, inputCls,
} from "@/components/kit";
import { useAdminChannelsCatalog, useAdminQueue, useModerate, useResumeChannelAdmin, useScanChannelCategories, useSuspendChannelAdmin } from "@/lib/queries";
import { ApiError, num } from "@/lib/api";
import { useAuthGuard } from "@/lib/auth";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/kingcey/channels")({
  head: () => ({
    meta: [
      { title: "Channels — AdsKinz admin" },
      { name: "description", content: "Review pending channel submissions, or browse and search the full channel catalog." },
      { property: "og:title", content: "Channels — AdsKinz admin" },
      { property: "og:description", content: "Moderation queue and full catalog for publisher channels." },
      { name: "robots", content: "noindex" },
    ],
  }),
  component: AdminChannels,
});

type QueueChannel = {
  id: string;
  name: string;
  publisher: string;
  publisherId: string;
  language: string;
  subscribers: number;
  maxAdsPerDay: number;
  publicLink: string | null;
  privateLink: string | null;
  adminUsername: string | null;
  botAdminVerified: boolean;
  submittedAt: string | null;
  category: string | null;
  categorySource: string | null;
};

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex flex-wrap justify-between gap-2 border-b border-seam py-2 text-sm last:border-0">
      <span className="text-paper-dim">{k}</span>
      <span className="num max-w-[60%] text-right font-semibold break-all">{v || "—"}</span>
    </div>
  );
}

const CAN_SUSPEND = new Set(["active", "building_trust", "approved_not_started"]);

function AdminChannels() {
  useAuthGuard("admin");
  const { t } = useTranslation();
  const [tab, setTab] = useState<"pending" | "catalog">("pending");
  const scanCategories = useScanChannelCategories();

  return (
    <AdminShell title={t("admin.nav.channels")}>
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div className="inline-flex gap-1 rounded-xl border border-seam p-1">
        <button
          onClick={() => setTab("pending")}
          className={cn("rounded-lg px-4 py-2 text-sm font-semibold", tab === "pending" ? "bg-panel-2" : "text-paper-dim")}
        >
          En attente
        </button>
        <button
          onClick={() => setTab("catalog")}
          className={cn("rounded-lg px-4 py-2 text-sm font-semibold", tab === "catalog" ? "bg-panel-2" : "text-paper-dim")}
        >
          Tous les canaux
        </button>
        </div>
        <Btn
          variant="secondary"
          disabled={scanCategories.isPending}
          onClick={() => scanCategories.mutate()}
        >
          {scanCategories.isPending ? "Scan en cours…" : "Scanner les catégories"}
        </Btn>
      </div>
      {scanCategories.isSuccess && (
        <p className="mb-4 text-xs text-paper-dim">
          {scanCategories.data.classified}/{scanCategories.data.scanned} canaux classés
          ({scanCategories.data.unclassified} non classés).
        </p>
      )}
      {tab === "pending" ? <PendingChannels /> : <ChannelCatalog />}
    </AdminShell>
  );
}

function PendingChannels() {
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

  if (isError) return <ErrorBanner onRetry={refetch} />;
  if (isLoading) return <Panel className="p-0"><RowSkeleton rows={5} /></Panel>;
  if (items.length === 0) return <Panel className="p-0"><EmptyState title="Nothing pending" sub="No channels are waiting for review." positive /></Panel>;

  return (
    <div className="grid gap-5 lg:grid-cols-[320px_1fr]">
      <Panel className="p-0">
        <ul className="divide-y divide-seam">
          {items.map((c) => (
            <li key={c.id}>
              <button onClick={() => setSel(c.id)} className={cn("w-full px-4 py-4 text-left", ch?.id === c.id && "bg-panel-2")}>
                <p className="font-bold">{c.name}</p>
                <p className="num text-xs text-paper-dim">{c.id}</p>
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
              <Row k={t("admin.publisher")} v={ch.publisher} />
              <Row k={t("pub.subscribers")} v={fmtInt(ch.subscribers)} />
              <Row k={t("pub.form.lang")} v={ch.language} />
              <Row k={t("channelCategory.pick")} v={ch.category ? t(`channelCategory.${ch.category}`, { defaultValue: ch.category }) : "—"} />
              <Row k={t("pub.form.frequency")} v={`${ch.maxAdsPerDay}${t("common.perDay")}`} />
              <Row k={t("pub.form.publicLink")} v={ch.publicLink ?? "—"} />
              <Row k={t("admin.inviteLink")} v={ch.privateLink ?? "—"} />
              <Row k={t("pub.form.adminUsername")} v={ch.adminUsername ?? "—"} />
              <Row k={t("admin.botAdmin")} v={ch.botAdminVerified ? t("common.yes") : t("common.no")} />
              <Row k={t("admin.submittedAt")} v={ch.submittedAt ?? "—"} />
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
  );
}

function ChannelCatalog() {
  const [search, setSearch] = useState("");
  const { data, isLoading, isError, isFetchingNextPage, fetchNextPage, hasNextPage, refetch } =
    useAdminChannelsCatalog(search);
  const suspend = useSuspendChannelAdmin();
  const resume = useResumeChannelAdmin();

  const items = data?.pages.flatMap((p) => p.items) ?? [];
  const total = data?.pages[0]?.total ?? 0;

  return (
    <div className="space-y-4">
      <input
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        placeholder="Rechercher un canal (nom, @username, lien)…"
        className={inputCls()}
      />
      {!isLoading && (
        <p className="text-xs text-paper-dim">
          {fmtInt(items.length)} / {fmtInt(total)} canaux
        </p>
      )}
      {isError && <ErrorBanner onRetry={refetch} />}
      {isLoading ? (
        <Panel className="p-0"><RowSkeleton rows={6} /></Panel>
      ) : items.length === 0 ? (
        <Panel className="p-0"><EmptyState title="Aucun canal" sub="Aucun canal ne correspond à cette recherche." /></Panel>
      ) : (
        <Panel className="p-0">
          <ul className="divide-y divide-seam">
            {items.map((c) => (
              <li key={c.id} className="flex flex-wrap items-center justify-between gap-3 p-4">
                <div className="min-w-0">
                  <p className="truncate font-bold">{c.name}</p>
                  <p className="text-xs text-paper-dim">{c.publisherEmail}</p>
                  <div className="mt-2 flex flex-wrap items-center gap-3">
                    <StatusPill status={c.status} />
                    <span className="num text-xs text-paper-dim">{fmtInt(c.subscribers)} abonnés</span>
                    <span className="num text-xs text-paper-dim">{fmtMoney(num(c.lifetimeEarnings))} générés</span>
                    {c.category && (
                      <span className="rounded-full border border-seam px-2 py-0.5 text-xs text-paper-dim">
                        {t(`channelCategory.${c.category}`, { defaultValue: c.category })}
                      </span>
                    )}
                  </div>
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  {c.status === "suspended" ? (
                    <Btn tone="bounty" disabled={resume.isPending} onClick={() => resume.mutate(c.id)}>
                      {resume.isPending ? "…" : "Reprendre"}
                    </Btn>
                  ) : CAN_SUSPEND.has(c.status) ? (
                    <Btn tone="danger" disabled={suspend.isPending} onClick={() => suspend.mutate(c.id)}>
                      {suspend.isPending ? "…" : "Suspendre"}
                    </Btn>
                  ) : null}
                </div>
              </li>
            ))}
          </ul>
          <LoadMoreSentinel
            onVisible={() => hasNextPage && !isFetchingNextPage && fetchNextPage()}
            loading={isFetchingNextPage}
            done={!hasNextPage}
          />
        </Panel>
      )}
    </div>
  );
}
