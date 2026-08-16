import { createFileRoute } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { AdminShell } from "@/components/workspaces";
import { Avatar, Segmented } from "@/components/cards";
import { Btn, EmptyState, ErrorBanner, Panel, Quote, RowSkeleton, StatusPill, fmtInt, fmtMoney } from "@/components/kit";
import { UsdtMark } from "@/components/usdt";
import { useAdminQueue, useModerate } from "@/lib/queries";
import { ApiError, num } from "@/lib/api";
import { useAuthGuard } from "@/lib/auth";

export const Route = createFileRoute("/kingcey/withdrawals")({
  head: () => ({
    meta: [
      { title: "Withdrawals — AdsKinz admin" },
      { name: "description", content: "Payout requests sorted by status, with requester, address and memo tag." },
      { property: "og:title", content: "Withdrawals — AdsKinz admin" },
      { property: "og:description", content: "Approve, reject or settle USDT payouts." },
      { name: "robots", content: "noindex" },
    ],
  }),
  component: AdminWithdrawals,
});

type QueueWithdrawal = {
  id: string;
  amount: string;
  address: string;
  memo: string | null;
  method: string;
  status: string;
  rejectionReason: string | null;
  txHash: string | null;
  requestedAt: string | null;
  paidAt: string | null;
  publisherEmail?: string | null;
};

type Status = "pending" | "approved" | "paid" | "rejected";

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex flex-wrap justify-between gap-2 border-b border-seam py-2 text-sm last:border-0">
      <span className="text-paper-dim">{k}</span>
      <span className="num max-w-[62%] text-right font-semibold break-all">{v || "—"}</span>
    </div>
  );
}

function WithdrawalCard({ w }: { w: QueueWithdrawal }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [txHash, setTxHash] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const moderate = useModerate("withdrawals");

  const act = (action: "approve" | "reject" | "mark-paid") => {
    setErr(null);
    if (action === "reject" && !reason.trim()) {
      setErr("A rejection reason is required.");
      return;
    }
    if (action === "mark-paid" && !txHash.trim()) {
      setErr("A transaction hash is required.");
      return;
    }
    const body =
      action === "reject"
        ? { id: w.id, action, reason: reason.trim() }
        : action === "mark-paid"
          ? { id: w.id, action, txHash: txHash.trim() }
          : { id: w.id, action };
    moderate.mutate(body, {
      onError: (e) => setErr(e instanceof ApiError ? e.message : "Action failed."),
      onSuccess: () => { setReason(""); setTxHash(""); },
    });
  };

  return (
    <div className="glass p-4">
      <button onClick={() => setOpen((v) => !v)} aria-expanded={open} className="flex w-full items-center gap-4 text-left">
        <Avatar name={w.publisherEmail ?? w.address} size={44} />
        <div className="min-w-0 flex-1">
          <p className="truncate font-bold">{w.publisherEmail ?? w.id}</p>
          <p className="num truncate text-xs text-paper-dim">{w.id} · {w.requestedAt ?? "—"}</p>
        </div>
        <div className="text-right">
          <p className="num flex items-center justify-end gap-1.5 font-bold text-bounty">
            <UsdtMark size={14} />
            {fmtMoney(num(w.amount))}
          </p>
          <div className="mt-1"><StatusPill status={w.status} /></div>
        </div>
      </button>

      {open && (
        <div className="mt-4 space-y-4">
          <div className="grid gap-x-8 md:grid-cols-2">
            <Row k={t("x.admin.requestedBy")} v={w.publisherEmail ?? "—"} />
            <Row k={t("x.admin.requestedAt")} v={w.requestedAt ?? "—"} />
            <Row k={t("x.admin.processedAt")} v={w.paidAt ?? ""} />
            <Row k={t("x.admin.network")} v={w.method} />
            <Row k={t("x.admin.address")} v={w.address} />
            <Row k={t("x.admin.memo")} v={w.memo ?? ""} />
            <Row k={t("x.admin.txHash")} v={w.txHash ?? ""} />
          </div>
          {w.rejectionReason && <Quote tone="danger" label={t("common.reason")}>{w.rejectionReason}</Quote>}
          {w.status !== "paid" && w.status !== "rejected" && (
            <div className="flex flex-wrap items-center gap-3">
              {w.status === "pending" && (
                <Btn tone="bounty" disabled={moderate.isPending} onClick={() => act("approve")}>
                  {moderate.isPending ? "Working…" : t("admin.approve")}
                </Btn>
              )}
              {w.status === "approved" && (
                <>
                  <Btn tone="bounty" disabled={moderate.isPending} onClick={() => act("mark-paid")}>
                    {moderate.isPending ? "Working…" : t("x.admin.markPaid")}
                  </Btn>
                  <input
                    value={txHash}
                    onChange={(e) => setTxHash(e.target.value)}
                    className="min-h-11 flex-1 rounded-xl border border-seam bg-transparent px-3 text-sm"
                    placeholder="Transaction hash"
                    aria-label="Transaction hash"
                  />
                </>
              )}
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
            </div>
          )}
          {err && <p className="text-sm font-semibold text-danger">{err}</p>}
        </div>
      )}
    </div>
  );
}

function AdminWithdrawals() {
  useAuthGuard("admin");
  const { t } = useTranslation();
  const [tab, setTab] = useState<Status | "all">("pending");
  const { data, isLoading, isError, refetch } = useAdminQueue<QueueWithdrawal>("withdrawals");

  const items = data?.items ?? [];
  const counts = data?.counts ?? {};
  const list = useMemo(() => (tab === "all" ? items : items.filter((w) => w.status === tab)), [items, tab]);
  const total = list.reduce((a, w) => a + num(w.amount), 0);

  return (
    <AdminShell title={t("admin.nav.withdrawals")} badges={{ withdrawals: counts["pending"] ?? 0 }}>
      {isError && <ErrorBanner onRetry={refetch} />}
      <div className="space-y-5">
        <Panel className="glass flex flex-wrap items-end gap-4">
          <div>
            <p className="text-xs font-semibold text-paper-dim">{t("x.admin.totalRequested")}</p>
            <p className="num mt-1 flex items-center gap-2 text-3xl font-extrabold text-bounty">
              <UsdtMark size={24} />
              {fmtMoney(total)}
            </p>
          </div>
          <div className="ml-auto text-right">
            <p className="text-xs font-semibold text-paper-dim">{t("x.admin.count")}</p>
            <p className="num mt-1 text-2xl font-bold">{fmtInt(list.length)}</p>
          </div>
        </Panel>

        <div className="flex flex-wrap items-center gap-3">
          <Segmented
            value={tab}
            onChange={setTab}
            options={[
              { v: "pending" as const, l: t("x.admin.pending"), badge: counts["pending"] ?? 0 },
              { v: "approved" as const, l: t("x.admin.approved"), badge: counts["approved"] ?? 0 },
              { v: "paid" as const, l: t("x.admin.paid"), badge: counts["paid"] ?? 0 },
              { v: "rejected" as const, l: t("x.admin.rejected"), badge: counts["rejected"] ?? 0 },
              { v: "all" as const, l: t("x.admin.all") },
            ]}
          />
        </div>

        {isLoading ? (
          <Panel className="p-0"><RowSkeleton rows={4} /></Panel>
        ) : list.length === 0 ? (
          <Panel className="p-0"><EmptyState title={t("x.admin.noneInPeriod")} positive /></Panel>
        ) : (
          <div className="grid gap-4 xl:grid-cols-2">
            {list.map((w) => <WithdrawalCard key={w.id} w={w} />)}
          </div>
        )}
      </div>
    </AdminShell>
  );
}
