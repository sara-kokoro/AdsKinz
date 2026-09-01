import { createFileRoute } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { AdminShell } from "@/components/workspaces";
import { Avatar, Segmented } from "@/components/cards";
import { Btn, EmptyState, ErrorBanner, Panel, RowSkeleton, StatusPill, fmtMoney } from "@/components/kit";
import { UsdtMark } from "@/components/usdt";
import { useBep20Sweeps, useRetryBep20Sweep } from "@/lib/queries";
import { ApiError, num } from "@/lib/api";
import { useAuthGuard } from "@/lib/auth";
import type { Bep20SweepItem } from "@/lib/types";

export const Route = createFileRoute("/kingcey/sweeps")({
  head: () => ({
    meta: [
      { title: "Sweeps — AdsKinz admin" },
      { name: "description", content: "BEP20 USDT deposits waiting to reach the treasury, with manual retry." },
      { name: "robots", content: "noindex" },
    ],
  }),
  component: AdminSweeps,
});

type Tab = "all" | "pending" | "in_progress" | "swept" | "failed";

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex flex-wrap justify-between gap-2 border-b border-seam py-2 text-sm last:border-0">
      <span className="text-paper-dim">{k}</span>
      <span className="num max-w-[62%] text-right font-semibold break-all">{v || "—"}</span>
    </div>
  );
}

function SweepCard({ s }: { s: Bep20SweepItem }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [okMsg, setOkMsg] = useState<string | null>(null);
  const retry = useRetryBep20Sweep();

  const onRetry = () => {
    setErr(null);
    setOkMsg(null);
    retry.mutate(s.id, {
      onError: (e) => setErr(e instanceof ApiError ? e.message : "Retry failed."),
      onSuccess: (res) => {
        if (res.status === "swept") setOkMsg(t("x.admin.sweeps.retrySuccess"));
        else setErr(res.message);
      },
    });
  };

  return (
    <div className="glass p-4">
      <button onClick={() => setOpen((v) => !v)} aria-expanded={open} className="flex w-full items-center gap-4 text-left">
        <Avatar name={s.advertiserEmail} size={44} />
        <div className="min-w-0 flex-1">
          <p className="truncate font-bold">{s.advertiserEmail}</p>
          <p className="num truncate text-xs text-paper-dim">{s.derivedAddress}</p>
        </div>
        <div className="text-right">
          <p className="num flex items-center justify-end gap-1.5 font-bold text-bounty">
            <UsdtMark size={14} />
            {fmtMoney(num(s.grossAmountUsd ?? "0"))}
          </p>
          <div className="mt-1"><StatusPill status={s.status} /></div>
        </div>
      </button>

      {open && (
        <div className="mt-4 space-y-4">
          <div className="grid gap-x-8 md:grid-cols-2">
            <Row k={t("x.admin.sweeps.derivedAddress")} v={s.derivedAddress} />
            <Row k={t("x.admin.sweeps.treasury")} v={s.treasuryAddress} />
            <Row k={t("x.admin.sweeps.gasTopup")} v={s.gasTopupTxHash ?? ""} />
            <Row k={t("x.admin.sweeps.sweepTx")} v={s.sweepTxHash ?? ""} />
            <Row k={t("x.admin.sweeps.dustReturn")} v={s.dustReturnTxHash ?? ""} />
            <Row k={t("x.admin.requestedAt")} v={s.createdAt} />
          </div>
          {s.error && (
            <p className="rounded-lg border border-danger/30 bg-danger/10 p-3 text-sm text-danger">
              <span className="font-semibold">{t("x.admin.sweeps.errorLabel")}: </span>
              {s.error}
            </p>
          )}
          {s.status !== "swept" && (
            <div className="flex flex-wrap items-center gap-3">
              <Btn tone="bounty" disabled={retry.isPending} onClick={onRetry}>
                {retry.isPending ? t("x.admin.sweeps.retrying") : t("x.admin.sweeps.retry")}
              </Btn>
            </div>
          )}
          {err && <p className="text-sm font-semibold text-danger">{err}</p>}
          {okMsg && <p className="text-sm font-semibold text-signal">{okMsg}</p>}
        </div>
      )}
    </div>
  );
}

function AdminSweeps() {
  useAuthGuard("admin");
  const { t } = useTranslation();
  const [tab, setTab] = useState<Tab>("failed");
  const { data, isLoading, isError, refetch } = useBep20Sweeps(tab === "all" ? undefined : tab);

  const list = useMemo(() => data ?? [], [data]);
  const total = list.reduce((a, s) => a + num(s.grossAmountUsd ?? "0"), 0);

  return (
    <AdminShell title={t("x.admin.sweeps.title")}>
      {isError && <ErrorBanner onRetry={refetch} />}
      <div className="space-y-5">
        <Panel className="glass flex flex-wrap items-end gap-4">
          <div>
            <p className="text-xs font-semibold text-paper-dim">{t("x.admin.sweeps.subtitle")}</p>
            <p className="num mt-1 flex items-center gap-2 text-3xl font-extrabold text-bounty">
              <UsdtMark size={24} />
              {fmtMoney(total)}
            </p>
          </div>
          <div className="ml-auto text-right">
            <p className="text-xs font-semibold text-paper-dim">{t("x.admin.count")}</p>
            <p className="num mt-1 text-2xl font-bold">{list.length}</p>
          </div>
        </Panel>

        <Segmented
          value={tab}
          onChange={setTab}
          options={[
            { v: "failed" as const, l: t("x.admin.sweeps.statusFailed") },
            { v: "pending" as const, l: t("x.admin.sweeps.statusPending") },
            { v: "in_progress" as const, l: t("x.admin.sweeps.statusInProgress") },
            { v: "swept" as const, l: t("x.admin.sweeps.statusSwept") },
            { v: "all" as const, l: t("x.admin.all") },
          ]}
        />

        {isLoading ? (
          <Panel className="p-0"><RowSkeleton rows={4} /></Panel>
        ) : list.length === 0 ? (
          <Panel className="p-0"><EmptyState title={t("x.admin.sweeps.noneFound")} positive /></Panel>
        ) : (
          <div className="grid gap-4 xl:grid-cols-2">
            {list.map((s) => <SweepCard key={s.id} s={s} />)}
          </div>
        )}
      </div>
    </AdminShell>
  );
}
