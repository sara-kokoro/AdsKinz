import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { PubShell } from "@/components/workspaces";
import {
  Btn,
  EmptyState,
  ErrorBanner,
  Field,
  FieldError,
  Panel,
  Quote,
  RowSkeleton,
  SectionTitle,
  StatusPill,
  fmtMoney,
  inputCls,
} from "@/components/kit";
import { IconList, IconShield, IconWallet } from "@/components/icons";
import { UsdtMark } from "@/components/usdt";
import { ApiError, num } from "@/lib/api";
import { useCreateWithdrawal, useWithdrawals } from "@/lib/queries";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/partner/withdrawals")({
  head: () => ({
    meta: [
      { title: "Withdrawals — AdsKinz partner" },
      { name: "description", content: "Request USDT TON payouts and follow each withdrawal step by step." },
      { property: "og:title", content: "Withdrawals — AdsKinz partner" },
      { property: "og:description", content: "USDT TON payouts with clear eligibility rules." },
    ],
  }),
  component: WithdrawalsPage,
});

function fmtDate(iso: string | null) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString();
}

function WithdrawalsPage() {
  const { t } = useTranslation();
  const { data, isLoading, isError, refetch } = useWithdrawals();
  const createWithdrawal = useCreateWithdrawal();

  const [amount, setAmount] = useState("");
  const [address, setAddress] = useState("");
  const [memo, setMemo] = useState("");
  const [err, setErr] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const [showHistory, setShowHistory] = useState(false);

  const available = num(data?.availableBalance);
  const held = num(data?.heldBalance);
  const minimum = num(data?.minimum, 50);
  const eligible = data?.eligible ?? false;

  const submit = () => {
    const e: Record<string, string> = {};
    const amt = Number(amount);
    if (!amount || !Number.isFinite(amt) || amt < minimum || amt > available) e["amount"] = t("pub.wd.errAmount");
    if (!/^U[Qf][A-Za-z0-9_-]{10,}$/.test(address)) e["address"] = t("pub.wd.errAddress");
    setErr(e);
    if (Object.keys(e).length) return;

    setFormError(null);
    createWithdrawal.mutate(
      { amount: amt, address: address.trim(), memo: memo.trim() || null },
      {
        onSuccess: () => {
          setDone(true);
          setAmount("");
          setAddress("");
          setMemo("");
        },
        onError: (err) => setFormError(err instanceof ApiError ? err.message : "Something went wrong."),
      },
    );
  };

  return (
    <PubShell title={t("pub.nav.withdrawals")}>
      <div className="space-y-5">
        <div className="grid gap-4 sm:grid-cols-2">
          <Panel>
            <p className="flex items-center gap-2 text-xs font-semibold text-paper-dim">
              <IconWallet width={14} height={14} />
              {t("pub.wd.available")}
            </p>
            <p className="num mt-1.5 flex items-center gap-2 text-3xl font-extrabold text-bounty">
              <UsdtMark size={26} />
              {isLoading ? "…" : fmtMoney(available)}
            </p>
            <p className="mt-2 text-xs text-paper-dim">{t("pub.wd.availableHint")}</p>
          </Panel>
          <Panel>
            <p className="text-xs font-semibold text-paper-dim">Held balance</p>
            <p className="num mt-1.5 text-3xl font-extrabold text-paper-dim">{isLoading ? "…" : fmtMoney(held)}</p>
            <p className="mt-2 text-xs text-paper-dim">Recent, unreleased earnings not yet available to withdraw.</p>
          </Panel>
        </div>

        {isError && <ErrorBanner onRetry={() => void refetch()} />}

        <Quote tone="bounty" label={t("pub.wd.method")}>{t("pub.quotes.payout")}</Quote>

        <Panel>
          <SectionTitle sub={t("pub.withdrawThreshold")}>
            <span className="inline-flex items-center gap-2">{t("pub.wd.requestTitle")}</span>
          </SectionTitle>
          {done ? (
            <div className="flex items-center gap-2 rounded-xl border border-seam bg-success-soft p-4 text-sm font-semibold text-success">
              {t("pub.wd.submitted")}
            </div>
          ) : (
            <div className="space-y-4">
              {!eligible && data?.ineligibleReason && (
                <Quote tone="neutral">
                  {data.ineligibleReason}
                  {data.eligibleAt ? ` · ${fmtDate(data.eligibleAt)}` : ""}
                </Quote>
              )}
              {formError && <FieldError>{formError}</FieldError>}
              <Field label={t("pub.wd.amount")} hint={t("pub.wd.amountHint")} error={err["amount"]} htmlFor="wa">
                <div className="flex gap-2">
                  <input
                    id="wa"
                    inputMode="decimal"
                    value={amount}
                    onChange={(e) => setAmount(e.target.value)}
                    placeholder={minimum.toFixed(2)}
                    className={`num ${inputCls(!!err["amount"])}`}
                  />
                  <Btn variant="secondary" className="shrink-0" onClick={() => setAmount(String(available))}>
                    {t("pub.wd.max")}
                  </Btn>
                </div>
              </Field>
              <Field label={t("pub.wd.address")} hint={t("pub.wd.addressHint")} error={err["address"]} htmlFor="wad">
                <input id="wad" value={address} onChange={(e) => setAddress(e.target.value)} placeholder="UQ…" className={`num ${inputCls(!!err["address"])}`} />
              </Field>
              <Field label={t("pub.wd.memo")} hint={t("pub.wd.memoHint")} htmlFor="wmemo">
                <input id="wmemo" value={memo} onChange={(e) => setMemo(e.target.value)} placeholder="—" className={`num ${inputCls()}`} />
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
                <Btn tone="bounty" onClick={submit} disabled={!eligible || available < minimum || createWithdrawal.isPending}>
                  {createWithdrawal.isPending ? "…" : t("pub.wd.request")}
                </Btn>
                {available < minimum && (
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
            <span className="num ml-auto text-xs text-paper-dim">{data?.items.length ?? 0}</span>
          </button>
          {showHistory &&
            (isLoading ? (
              <RowSkeleton rows={3} />
            ) : !data || data.items.length === 0 ? (
              <EmptyState title={t("pub.withdrawalsEmpty")} />
            ) : (
              <ul className="divide-y divide-seam border-t border-seam">
                {data.items.map((w) => (
                  <li key={w.id} className="space-y-2 px-5 py-4">
                    <div className="flex flex-wrap items-center gap-4">
                      <div>
                        <p className={cn("num font-bold", w.status === "paid" ? "text-success" : "text-bounty")}>
                          {fmtMoney(num(w.amount))}
                        </p>
                        <p className="num text-xs text-paper-dim">{w.method} · {w.address}</p>
                      </div>
                      <div className="ml-auto flex items-center gap-4">
                        <span className="num text-xs text-paper-dim">{fmtDate(w.requestedAt)}</span>
                        <StatusPill status={w.status} />
                      </div>
                    </div>
                    {w.rejectionReason && <p className="text-xs text-danger">{w.rejectionReason}</p>}
                    {w.txHash && <p className="num text-xs text-paper-dim">Tx: {w.txHash}</p>}
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
