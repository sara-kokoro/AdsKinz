import { createFileRoute } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { AdminShell } from "@/components/workspaces";
import { Avatar, Segmented } from "@/components/cards";
import { Btn, EmptyState, Panel, Quote, StatusPill, fmtInt, fmtMoney, inputCls } from "@/components/kit";
import { UsdtMark } from "@/components/usdt";
import { withdrawals, type Withdrawal, type WithdrawalStatus } from "@/lib/mock-data";

export const Route = createFileRoute("/kingcey/withdrawals")({
  head: () => ({
    meta: [
      { title: "Withdrawals — AdsKinz admin" },
      { name: "description", content: "Payout requests sorted by status and period, with requester, memo tag and destination address." },
      { property: "og:title", content: "Withdrawals — AdsKinz admin" },
      { property: "og:description", content: "Approve, reject or settle USDT TON payouts." },
      { name: "robots", content: "noindex" },
    ],
  }),
  component: AdminWithdrawals,
});

/** Fixed "now" for the mock dataset so period buckets stay deterministic. */
const NOW = new Date("2026-08-07T05:00:00Z");
const asDate = (v: string) => new Date(v.replace(" UTC", "Z").replace(" ", "T"));
const dayKey = (d: Date) => d.toISOString().slice(0, 10);

type Period = "today" | "yesterday" | "d2" | "week" | "month" | "semester" | "year" | "day" | "all";

function inPeriod(w: Withdrawal, p: Period, exactDay: string) {
  const d = asDate(w.requestedAt);
  const diffDays = Math.floor((Date.parse(dayKey(NOW)) - Date.parse(dayKey(d))) / 86_400_000);
  switch (p) {
    case "today": return diffDays === 0;
    case "yesterday": return diffDays === 1;
    case "d2": return diffDays === 2;
    case "week": return diffDays < 7;
    case "month": return d.getUTCMonth() === NOW.getUTCMonth() && d.getUTCFullYear() === NOW.getUTCFullYear();
    case "semester": return d.getUTCFullYear() === NOW.getUTCFullYear() && Math.floor(d.getUTCMonth() / 6) === Math.floor(NOW.getUTCMonth() / 6);
    case "year": return d.getUTCFullYear() === NOW.getUTCFullYear();
    case "day": return exactDay ? dayKey(d) === exactDay : true;
    default: return true;
  }
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex flex-wrap justify-between gap-2 border-b border-seam py-2 text-sm last:border-0">
      <span className="text-paper-dim">{k}</span>
      <span className="num max-w-[62%] text-right font-semibold break-all">{v || "—"}</span>
    </div>
  );
}

function WithdrawalCard({ w }: { w: Withdrawal }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  return (
    <div className="glass p-4">
      <button onClick={() => setOpen((v) => !v)} aria-expanded={open} className="flex w-full items-center gap-4 text-left">
        <Avatar name={w.publisher} size={44} />
        <div className="min-w-0 flex-1">
          <p className="truncate font-bold">{w.publisher}</p>
          <p className="num truncate text-xs text-paper-dim">{w.publisherId} · {w.requestedAt}</p>
        </div>
        <div className="text-right">
          <p className="num flex items-center justify-end gap-1.5 font-bold text-bounty">
            <UsdtMark size={14} />
            {fmtMoney(w.amount)}
          </p>
          <div className="mt-1"><StatusPill status={w.status} /></div>
        </div>
      </button>

      {open && (
        <div className="mt-4 space-y-4">
          <div className="grid gap-x-8 md:grid-cols-2">
            <Row k={t("x.admin.requestedBy")} v={`${w.publisher} · ${w.publisherId}`} />
            <Row k={t("admin.email")} v={w.email} />
            <Row k={t("x.admin.requestedAt")} v={w.requestedAt} />
            <Row k={t("x.admin.processedAt")} v={w.processedAt ?? ""} />
            <Row k={t("x.admin.network")} v={`${w.method} (${w.network})`} />
            <Row k={t("x.admin.address")} v={w.address} />
            <Row k={t("x.admin.memo")} v={w.memo} />
            <Row k={t("x.admin.txHash")} v={w.txHash ?? ""} />
          </div>
          {w.rejectionReason && <Quote tone="danger" label={t("common.reason")}>{w.rejectionReason}</Quote>}
          {w.status !== "paid" && w.status !== "rejected" && (
            <div className="flex flex-wrap items-center gap-3">
              {w.status === "pending" && <Btn tone="bounty">{t("admin.approve")}</Btn>}
              {w.status === "approved" && <Btn tone="bounty">{t("x.admin.markPaid")}</Btn>}
              <Btn tone="danger">{t("admin.reject")}</Btn>
              <input className="min-h-11 flex-1 rounded-xl border border-seam bg-transparent px-3 text-sm" placeholder={t("admin.rejectReason")} aria-label={t("admin.rejectReason")} />
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function AdminWithdrawals() {
  const { t } = useTranslation();
  const [tab, setTab] = useState<WithdrawalStatus | "all">("pending");
  const [period, setPeriod] = useState<Period>("all");
  const [exactDay, setExactDay] = useState("");

  const byPeriod = useMemo(() => withdrawals.filter((w) => inPeriod(w, period, exactDay)), [period, exactDay]);
  const count = (s: WithdrawalStatus) => byPeriod.filter((w) => w.status === s).length;
  const list = tab === "all" ? byPeriod : byPeriod.filter((w) => w.status === tab);
  const total = list.reduce((a, w) => a + w.amount, 0);

  return (
    <AdminShell
      title={t("admin.nav.withdrawals")}
      badges={{ withdrawals: withdrawals.filter((w) => w.status === "pending").length }}
    >
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
              { v: "pending" as const, l: t("x.admin.pending"), badge: count("pending") },
              { v: "approved" as const, l: t("x.admin.approved"), badge: count("approved") },
              { v: "paid" as const, l: t("x.admin.paid"), badge: count("paid") },
              { v: "rejected" as const, l: t("x.admin.rejected"), badge: count("rejected") },
              { v: "all" as const, l: t("x.admin.all") },
            ]}
          />
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <Segmented
            value={period}
            onChange={setPeriod}
            options={[
              { v: "today" as const, l: t("x.admin.today") },
              { v: "yesterday" as const, l: t("x.admin.yesterday") },
              { v: "d2" as const, l: t("x.admin.beforeYesterday") },
              { v: "week" as const, l: t("x.admin.thisWeek") },
              { v: "month" as const, l: t("x.admin.thisMonth") },
              { v: "semester" as const, l: t("x.admin.semester") },
              { v: "year" as const, l: t("x.admin.thisYear") },
              { v: "day" as const, l: t("x.admin.exactDay") },
              { v: "all" as const, l: t("x.admin.all") },
            ]}
          />
          {period === "day" && (
            <input
              type="date"
              value={exactDay}
              onChange={(e) => setExactDay(e.target.value)}
              aria-label={t("x.admin.exactDay")}
              className={`num max-w-44 ${inputCls()}`}
            />
          )}
        </div>

        {list.length === 0 ? (
          <Panel className="p-0"><EmptyState title={t("x.admin.noneInPeriod")} /></Panel>
        ) : (
          <div className="grid gap-4 xl:grid-cols-2">
            {list.map((w) => <WithdrawalCard key={w.id} w={w} />)}
          </div>
        )}
      </div>
    </AdminShell>
  );
}
