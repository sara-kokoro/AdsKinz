import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { PubShell } from "@/components/workspaces";
import {
  Btn,
  EmptyState,
  Field,
  Panel,
  Quote,
  RowSkeleton,
  SectionTitle,
  StatusPill,
  fmtMoney,
  inputCls,
  useFakeLoad,
} from "@/components/kit";
import { IconCheck, IconClock, IconList, IconWallet, IconArrowUp, IconShield } from "@/components/icons";
import { UsdtMark } from "@/components/usdt";
import { publisherSummary, withdrawals } from "@/lib/mock-data";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/partner/withdrawals")({
  head: () => ({
    meta: [
      { title: "Withdrawals — AdsKinz partner" },
      { name: "description", content: "Request USDT TON payouts from a $50 balance and follow each withdrawal step by step." },
      { property: "og:title", content: "Withdrawals — AdsKinz partner" },
      { property: "og:description", content: "USDT TON payouts with clear eligibility rules." },
    ],
  }),
  component: WithdrawalsPage,
});

const STEPS = ["requested", "approved", "paid"] as const;

function Progress({ status }: { status: string }) {
  const { t } = useTranslation();
  const idx = status === "paid" ? 2 : status === "approved" ? 1 : 0;
  const rejected = status === "rejected";
  return (
    <ol className="flex items-center gap-2">
      {STEPS.map((s, i) => (
        <li key={s} className="flex items-center gap-2">
          <span
            className={cn(
              "inline-flex items-center gap-1.5 rounded-full border border-seam px-2.5 py-1 text-[11px] font-semibold",
              rejected
                ? "text-paper-dim"
                : i <= idx
                  ? status === "paid" && i === 2
                    ? "bg-success-soft text-success"
                    : "bg-bounty-soft text-bounty"
                  : "text-paper-dim",
            )}
          >
            {i <= idx && !rejected ? <IconCheck width={11} height={11} /> : <IconClock width={11} height={11} />}
            {t(`pub.wd.steps.${s}`)}
          </span>
          {i < STEPS.length - 1 && <span className="h-px w-4 bg-seam" aria-hidden />}
        </li>
      ))}
    </ol>
  );
}

function WithdrawalsPage() {
  const { t } = useTranslation();
  const { loading } = useFakeLoad();
  const locked = publisherSummary.withdrawUnlockHours > 0;
  const available = publisherSummary.balance;

  const [amount, setAmount] = useState("");
  const [address, setAddress] = useState("");
  const [memo, setMemo] = useState("");
  const [err, setErr] = useState<Record<string, string>>({});
  const [done, setDone] = useState(false);
  const [showHistory, setShowHistory] = useState(false);

  const amountInvalid = amount !== "" && (Number(amount) < 50 || Number(amount) > available);

  const submit = () => {
    const e: Record<string, string> = {};
    if (!amount || Number(amount) < 50 || Number(amount) > available) e["amount"] = t("pub.wd.errAmount");
    if (!/^U[Qf][A-Za-z0-9_-]{10,}$/.test(address)) e["address"] = t("pub.wd.errAddress");
    setErr(e);
    if (!Object.keys(e).length) setDone(true);
  };

  return (
    <PubShell title={t("pub.nav.withdrawals")}>
      <div className="space-y-5">
        <Panel>
          <p className="flex items-center gap-2 text-xs font-semibold text-paper-dim">
            <IconWallet width={14} height={14} />
            {t("pub.wd.available")}
          </p>
          <p className="num mt-1.5 flex items-center gap-2 text-3xl font-extrabold text-bounty">
            <UsdtMark size={26} />
            {fmtMoney(available)}
          </p>
          <p className="mt-2 text-xs text-paper-dim">{t("pub.wd.availableHint")}</p>
        </Panel>

        <Quote tone="bounty" label={t("pub.wd.method")}>{t("pub.quotes.payout")}</Quote>

        <Panel>
          <SectionTitle sub={t("pub.withdrawThreshold")}>
            <span className="inline-flex items-center gap-2">
              <IconArrowUp width={16} height={16} />
              {t("pub.wd.requestTitle")}
            </span>
          </SectionTitle>
          {done ? (
            <div className="flex items-center gap-2 rounded-xl border border-seam bg-success-soft p-4 text-sm font-semibold text-success">
              <IconCheck width={16} height={16} />
              {t("pub.wd.submitted")}
            </div>
          ) : (
            <div className="space-y-4">
              <Field
                label={t("pub.wd.amount")}
                hint={t("pub.wd.amountHint")}
                error={err["amount"]}
                htmlFor="wa"
              >
                <div className="flex gap-2">
                  <input
                    id="wa"
                    inputMode="decimal"
                    value={amount}
                    onChange={(e) => setAmount(e.target.value)}
                    placeholder="50.00"
                    className={`num ${inputCls(!!err["amount"] || amountInvalid)}`}
                  />
                  <Btn variant="secondary" className="shrink-0" onClick={() => setAmount(String(available))}>
                    {t("pub.wd.max")}
                  </Btn>
                </div>
              </Field>
              <Field label={t("pub.wd.address")} hint={t("pub.wd.addressHint")} error={err["address"]} htmlFor="wad">
                <input
                  id="wad"
                  value={address}
                  onChange={(e) => setAddress(e.target.value)}
                  placeholder="UQ…"
                  className={`num ${inputCls(!!err["address"])}`}
                />
              </Field>
              <Field label={t("pub.wd.memo")} hint={t("pub.wd.memoHint")} htmlFor="wmemo">
                <input
                  id="wmemo"
                  value={memo}
                  onChange={(e) => setMemo(e.target.value)}
                  placeholder="—"
                  className={`num ${inputCls()}`}
                />
              </Field>
              <div className="rounded-xl border border-seam p-4">
                <p className="flex items-center gap-1.5 text-[11px] font-semibold text-paper-dim">
                  <IconShield width={13} height={13} />
                  {t("pub.wd.method")}
                </p>
                <p className="num mt-1 flex items-center gap-2 font-bold">
                  <UsdtMark size={16} />
                  USDT TON
                </p>
              </div>
              <Quote tone="neutral">{t("pub.wd.fees")}</Quote>
              <div className="flex flex-wrap items-center gap-3">
                <Btn tone="bounty" onClick={submit} disabled={locked || available < 50}>
                  {locked ? t("pub.withdrawLocked", { hours: publisherSummary.withdrawUnlockHours }) : t("pub.wd.request")}
                </Btn>
                {available < 50 && (
                  <p className="text-xs text-paper-dim">{t("pub.belowThreshold", { amount: fmtMoney(available) })}</p>
                )}
              </div>
            </div>
          )}
        </Panel>

        <Panel className="p-0">
          <button
            onClick={() => setShowHistory((v) => !v)}
            aria-expanded={showHistory}
            className="flex min-h-12 w-full items-center gap-2 px-5 py-4 text-left text-sm font-bold transition-colors hover:bg-panel-2"
          >
            <IconList width={16} height={16} />
            {showHistory ? t("pub.wd.hideHistory") : t("pub.wd.showHistory")}
            <span className="num ml-auto text-xs text-paper-dim">{withdrawals.length}</span>
          </button>
          {showHistory &&
            (loading ? (
              <RowSkeleton rows={3} />
            ) : withdrawals.length === 0 ? (
              <EmptyState title={t("pub.withdrawalsEmpty")} />
            ) : (
              <ul className="divide-y divide-seam border-t border-seam">
                {withdrawals.map((w) => (
                  <li key={w.id} className="space-y-3 px-5 py-4">
                    <div className="flex flex-wrap items-center gap-4">
                      <div>
                        <p className={cn("num font-bold", w.status === "paid" ? "text-success" : "text-bounty")}>
                          {fmtMoney(w.amount)}
                        </p>
                        <p className="num text-xs text-paper-dim">{w.method} · {w.address}</p>
                      </div>
                      <div className="ml-auto flex items-center gap-4">
                        <span className="num text-xs text-paper-dim">{t("pub.wd.requested")} · {w.requestedAgoHours}h</span>
                        <StatusPill status={w.status} />
                      </div>
                    </div>
                    <Progress status={w.status} />
                    {w.rejectionReason && <p className="text-xs text-danger">{w.rejectionReason}</p>}
                  </li>
                ))}
              </ul>
            ))}
        </Panel>

        <Quote tone="signal" label={t("pub.kpiViews")}>{t("pub.quotes.quality")}</Quote>
      </div>
    </PubShell>
  );
}
