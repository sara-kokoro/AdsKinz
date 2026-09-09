import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { AdminShell } from "@/components/workspaces";
import {
  Btn, EmptyState, ErrorBanner, LoadMoreSentinel, Modal, Panel, RowSkeleton, StatusPill, fmtDate, fmtInt, fmtMoney, inputCls,
} from "@/components/kit";
import {
  useAdminUserDetail, useAdminUsersCatalog, useBlockAccount, useResumeChannelAdmin, useSuspendChannelAdmin,
} from "@/lib/queries";
import { ApiError, num } from "@/lib/api";
import { useAuthGuard } from "@/lib/auth";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/kingcey/users")({
  head: () => ({
    meta: [
      { title: "Users — AdsKinz admin" },
      { name: "description", content: "Search and browse every advertiser and publisher account, with block/unblock and per-channel controls." },
      { property: "og:title", content: "Users — AdsKinz admin" },
      { property: "og:description", content: "Full, searchable account catalog." },
      { name: "robots", content: "noindex" },
    ],
  }),
  component: AdminUsers,
});

const CAN_SUSPEND = new Set(["active", "building_trust", "approved_not_started"]);

function initials(email: string) {
  const name = email.split("@")[0] ?? email;
  return name.slice(0, 2).toUpperCase();
}

function AdminUsers() {
  useAuthGuard("admin");
  const { t } = useTranslation();
  const [role, setRole] = useState<"advertiser" | "publisher">("advertiser");
  const [search, setSearch] = useState("");
  const [openId, setOpenId] = useState<string | null>(null);

  const { data, isLoading, isError, isFetchingNextPage, fetchNextPage, hasNextPage, refetch } =
    useAdminUsersCatalog(role, search);

  const items = data?.pages.flatMap((p) => p.items) ?? [];
  const total = data?.pages[0]?.total ?? 0;

  return (
    <AdminShell title={t("x.admin.users")}>
      <div className="space-y-4">
        <div className="flex flex-wrap items-center gap-3">
          <div className="inline-flex gap-1 rounded-xl border border-seam p-1">
            <button
              onClick={() => setRole("advertiser")}
              className={cn("rounded-lg px-4 py-2 text-sm font-semibold", role === "advertiser" ? "bg-panel-2" : "text-paper-dim")}
            >
              {t("x.admin.advertiser")}
            </button>
            <button
              onClick={() => setRole("publisher")}
              className={cn("rounded-lg px-4 py-2 text-sm font-semibold", role === "publisher" ? "bg-panel-2" : "text-paper-dim")}
            >
              {t("x.admin.publisher")}
            </button>
          </div>
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Rechercher par email…"
            className={cn(inputCls(), "max-w-xs flex-1")}
          />
        </div>

        {!isLoading && (
          <p className="text-xs text-paper-dim">
            {fmtInt(items.length)} / {fmtInt(total)} utilisateurs
          </p>
        )}

        {isError && <ErrorBanner onRetry={refetch} />}
        {isLoading ? (
          <Panel className="p-0"><RowSkeleton rows={6} /></Panel>
        ) : items.length === 0 ? (
          <Panel className="p-0"><EmptyState title="Aucun utilisateur" sub="Aucun compte ne correspond à cette recherche." /></Panel>
        ) : (
          <Panel className="p-0">
            <ul className="divide-y divide-seam">
              {items.map((u) => (
                <li key={u.id}>
                  <button onClick={() => setOpenId(u.id)} className="flex w-full items-center gap-3 p-4 text-left hover:bg-panel-2">
                    <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-signal-soft text-sm font-bold text-signal">
                      {initials(u.email)}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate font-semibold">{u.email}</span>
                      {u.displayName && <span className="block truncate text-xs text-paper-dim">{u.displayName}</span>}
                    </span>
                    <span className="num shrink-0 text-right text-sm font-bold">{fmtMoney(num(u.balance))}</span>
                    <span className="shrink-0"><StatusPill status={u.isBlocked ? "blocked" : "active"} /></span>
                  </button>
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

      <UserDetailModal role={role} id={openId} onClose={() => setOpenId(null)} />
    </AdminShell>
  );
}

function UserDetailModal({
  role,
  id,
  onClose,
}: {
  role: "advertiser" | "publisher";
  id: string | null;
  onClose: () => void;
}) {
  const { data, isLoading, isError, refetch } = useAdminUserDetail(id ? role : null, id);
  const block = useBlockAccount();
  const suspend = useSuspendChannelAdmin();
  const resume = useResumeChannelAdmin();
  const [reason, setReason] = useState("");
  const [err, setErr] = useState<string | null>(null);

  const toggleBlock = () => {
    if (!data) return;
    setErr(null);
    if (!data.isBlocked && !reason.trim()) {
      setErr("Un motif est requis pour bloquer ce compte.");
      return;
    }
    block.mutate(
      { role, id: data.id, blocked: !data.isBlocked, reason: reason.trim() },
      { onSuccess: () => setReason(""), onError: (e) => setErr(e instanceof ApiError ? e.message : "Action échouée.") },
    );
  };

  return (
    <Modal open={Boolean(id)} onClose={onClose} title={data?.email ?? "…"} wide>
      {isError && <ErrorBanner onRetry={refetch} />}
      {isLoading || !data ? (
        <Panel className="p-0"><RowSkeleton rows={4} /></Panel>
      ) : (
        <div className="space-y-5">
          <Panel>
            <div className="grid gap-x-8 gap-y-1 md:grid-cols-2">
              <div className="flex justify-between border-b border-seam py-2 text-sm">
                <span className="text-paper-dim">Statut</span>
                <StatusPill status={data.isBlocked ? "blocked" : "active"} />
              </div>
              <div className="flex justify-between border-b border-seam py-2 text-sm">
                <span className="text-paper-dim">Username Telegram</span>
                {data.telegramUsername ? (
                  <a
                    href={`https://t.me/${data.telegramUsername.replace(/^@/, "")}`}
                    target="_blank"
                    rel="noreferrer"
                    className="font-semibold text-signal hover:underline"
                  >
                    @{data.telegramUsername.replace(/^@/, "")}
                  </a>
                ) : (
                  <span className="font-semibold text-paper-dim">—</span>
                )}
              </div>
              <div className="flex justify-between border-b border-seam py-2 text-sm">
                <span className="text-paper-dim">Solde</span>
                <span className="num font-semibold">{fmtMoney(num(data.balance))}</span>
              </div>
              <div className="flex justify-between border-b border-seam py-2 text-sm">
                <span className="text-paper-dim">{role === "advertiser" ? "Dépensé (total)" : "Gagné (total)"}</span>
                <span className="num font-semibold">{fmtMoney(num(data.lifetimeValue))}</span>
              </div>
              <div className="flex justify-between border-b border-seam py-2 text-sm">
                <span className="text-paper-dim">Inscrit le</span>
                <span className="num font-semibold">{data.createdAt ? fmtDate(data.createdAt) : "—"}</span>
              </div>
              {data.isBlocked && data.blockedReason && (
                <div className="flex justify-between py-2 text-sm md:col-span-2">
                  <span className="text-paper-dim">Motif du blocage</span>
                  <span className="max-w-[70%] text-right font-semibold">{data.blockedReason}</span>
                </div>
              )}
            </div>
          </Panel>

          <Panel className="flex flex-wrap items-center gap-3">
            {!data.isBlocked && (
              <input
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="Motif du blocage…"
                className="min-h-11 flex-1 rounded-xl border border-seam bg-transparent px-3 text-sm"
              />
            )}
            <Btn tone={data.isBlocked ? "bounty" : "danger"} disabled={block.isPending} onClick={toggleBlock}>
              {block.isPending ? "…" : data.isBlocked ? "Débloquer" : "Bloquer"}
            </Btn>
            {err && <p className="w-full text-sm font-semibold text-danger">{err}</p>}
          </Panel>

          {role === "publisher" && (
            <Panel className="p-0">
              <div className="p-4 pb-0"><h3 className="font-display font-bold">Canaux ({data.channels.length})</h3></div>
              {data.channels.length === 0 ? (
                <p className="p-4 text-sm text-paper-dim">Aucun canal.</p>
              ) : (
                <ul className="divide-y divide-seam">
                  {data.channels.map((c) => (
                    <li key={c.id} className="flex flex-wrap items-center justify-between gap-3 p-4">
                      <div className="min-w-0">
                        <p className="truncate font-bold">{c.name}</p>
                        {c.publicLink && <p className="truncate text-xs text-signal">{c.publicLink}</p>}
                        <p className="num text-xs text-paper-dim">{c.id}</p>
                        <div className="mt-2 flex flex-wrap items-center gap-3">
                          <StatusPill status={c.status} />
                          <span className="num text-xs text-paper-dim">{fmtInt(c.subscribers)} abonnés</span>
                        </div>
                      </div>
                      <div className="shrink-0">
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
              )}
            </Panel>
          )}
        </div>
      )}
    </Modal>
  );
}
