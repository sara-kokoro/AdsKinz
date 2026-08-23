import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { AdvShell } from "@/components/workspaces";
import { Btn, EmptyState, ErrorBanner, Panel, RowSkeleton, SectionTitle, StatusPill, fmtMoney } from "@/components/kit";
import { IconAlert, IconCopy, IconList, IconWallet, IconShield } from "@/components/icons";
import { NetworkUsdtMark, UsdtMark } from "@/components/usdt";
import { useDepositAddress, useDeposits, useVerifyDeposit } from "@/lib/queries";
import { ApiError, num } from "@/lib/api";
import { cn } from "@/lib/utils";
import { useAuthGuard } from "@/lib/auth";

export const Route = createFileRoute("/traffic/deposits")({
  head: () => ({
    meta: [
      { title: "Deposits — AdsKinz traffic" },
      { name: "description", content: "Top up your AdsKinz balance in USDT on TON, TRC20 or BNB. No minimum deposit." },
      { property: "og:title", content: "Deposits — AdsKinz traffic" },
      { property: "og:description", content: "Crypto-only top-ups with on-chain confirmation status." },
    ],
  }),
  component: Deposits,
});

const NETWORKS = [
  { id: "ton", key: "adv.deposits.ton" },
  { id: "trc20", key: "adv.deposits.trc" },
  { id: "bnb", key: "adv.deposits.bnb" },
];

function Deposits() {
  useAuthGuard("advertiser");
  const { t } = useTranslation();
  const [net, setNet] = useState("ton");
  const deposits = useDeposits();
  const addr = useDepositAddress(net);
  const [copied, setCopied] = useState(false);
  const verify = useVerifyDeposit();
  const [verifyNotice, setVerifyNotice] = useState<string | null>(null);
  const [verifyError, setVerifyError] = useState<string | null>(null);

  const runVerify = () => {
    setVerifyNotice(null);
    setVerifyError(null);
    verify.mutate(net, {
      onSuccess: (res) => {
        setVerifyNotice(
          res.deposits_credited > 0
            ? t("adv.deposits.verifyFoundCredited", { count: res.deposits_credited })
            : res.transfers_seen > 0
              ? t("adv.deposits.verifyFoundPending")
              : t("adv.deposits.verifyNothingYet"),
        );
      },
      onError: (e) => setVerifyError(e instanceof ApiError ? e.message : t("common.loadError")),
    });
  };

  const items = deposits.data?.items ?? [];
  const balance = num(deposits.data?.balance);

  const copy = async () => {
    if (!addr.data?.address) return;
    try {
      await navigator.clipboard.writeText(addr.data.address);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard unavailable */
    }
  };

  return (
    <AdvShell title={t("adv.deposits.title")}>
      <div className="grid gap-5 lg:grid-cols-[1.1fr_1fr]">
        <div className="space-y-5">
          <Panel>
            <p className="flex items-center gap-2 text-xs font-semibold text-paper-dim">
              <IconWallet width={14} height={14} />
              {t("adv.balance")}
            </p>
            <p className="num mt-1 flex items-center gap-2 text-3xl font-extrabold text-bounty">
              <UsdtMark size={40} />
              {fmtMoney(balance)}
            </p>
            <p className="mt-2 text-xs text-paper-dim">{t("adv.deposits.noMinimum")}</p>
          </Panel>

          <Panel>
            <SectionTitle>
              <span className="inline-flex items-center gap-2">
                <IconShield width={16} height={16} />
                {t("adv.deposits.method")}
              </span>
            </SectionTitle>
            <div className="flex flex-wrap gap-2">
              {NETWORKS.map((n) => (
                <button
                  key={n.id}
                  onClick={() => setNet(n.id)}
                  aria-pressed={net === n.id}
                  className={cn(
                    "flex min-h-14 items-center gap-2.5 rounded-xl border px-4 py-2 text-sm font-semibold",
                    net === n.id ? "border-signal bg-signal-soft text-signal" : "border-seam text-paper-dim",
                  )}
                >
                  <NetworkUsdtMark network={n.id} size={32} />
                  {t(n.key)}
                </button>
              ))}
            </div>

            {addr.isError && <div className="mt-4"><ErrorBanner onRetry={() => addr.refetch()} /></div>}

            {addr.data?.warning && (
              <p className="mt-4 rounded-xl border border-seam bg-bounty-soft p-3 text-xs font-semibold text-bounty">
                {addr.data.warning}
              </p>
            )}

            <div className="mt-5">
              <p className="text-xs font-semibold text-paper-dim">{t("adv.deposits.address")}</p>
              <div className="mt-2 flex items-center gap-2 rounded-xl border border-seam p-3">
                <span className="num flex-1 text-xs break-all">
                  {addr.isPending ? "…" : (addr.data?.address ?? "—")}
                </span>
                <button aria-label="Copy address" onClick={copy} className="text-paper-dim hover:text-paper">
                  <IconCopy width={16} height={16} />
                </button>
              </div>
              {copied && <p className="mt-1.5 text-xs font-semibold text-bounty">{t("common.copied", "Copied")}</p>}
            </div>

            {addr.data?.memo && (
              <div className="mt-4 rounded-xl border border-bounty/60 bg-bounty-soft p-3">
                <p className="text-xs font-bold text-bounty">{t("adv.deposits.memo")}</p>
                <p className="num mt-1.5 text-sm font-bold">{addr.data.memo}</p>
                {addr.data.memo_required && (
                  <p className="mt-2 flex gap-2 text-xs text-bounty">
                    <IconAlert width={14} height={14} />
                    {t("adv.deposits.memoWarning")}
                  </p>
                )}
              </div>
            )}

            {addr.data && (
              <p className="mt-4 text-xs text-paper-dim">
                {addr.data.confirmations_required} confirmations · fee {fmtMoney(num(addr.data.fee_usdt))}
                {addr.data.fee_note ? ` — ${addr.data.fee_note}` : ""}
              </p>
            )}

            <Btn
              variant="secondary"
              className="mt-4 w-full"
              onClick={runVerify}
              disabled={verify.isPending || !addr.data?.address}
            >
              {verify.isPending ? t("adv.deposits.verifying") : t("adv.deposits.verify")}
            </Btn>
            {verifyNotice && <p className="mt-2 text-xs font-semibold text-bounty">{verifyNotice}</p>}
            {verifyError && <p className="mt-2 text-xs font-semibold text-danger">{verifyError}</p>}
          </Panel>
        </div>

        <Panel className="p-0">
          <div className="border-b border-seam px-5 py-4">
            <h2 className="flex items-center gap-2 font-display text-base font-bold">
              <IconList width={16} height={16} />
              {t("adv.deposits.history")}
            </h2>
          </div>
          {deposits.isPending ? (
            <div className="p-5"><RowSkeleton /></div>
          ) : deposits.isError ? (
            <div className="p-5"><ErrorBanner onRetry={() => deposits.refetch()} /></div>
          ) : items.length === 0 ? (
            <EmptyState title={t("adv.deposits.emptyTitle")} sub={t("adv.deposits.emptySub")} />
          ) : (
            <ul className="divide-y divide-seam">
              {items.map((d) => (
                <li key={d.id} className="flex flex-wrap items-center gap-3 px-5 py-4">
                  <div>
                    <p className="num font-bold text-bounty">{fmtMoney(num(d.amount))}</p>
                    <p className="text-xs text-paper-dim">
                      {d.networkLabel || d.network} · {d.createdAt?.slice(0, 10) ?? "—"}
                    </p>
                  </div>
                  <div className="ml-auto flex items-center gap-3">
                    <span className="num max-w-[10rem] truncate text-xs text-paper-dim">{d.txHash ?? ""}</span>
                    <StatusPill status={d.status} />
                  </div>
                </li>
              ))}
            </ul>
          )}
          <div className="border-t border-seam px-5 py-4">
            <p className="text-xs text-paper-dim">
              {t("adv.deposits.newBalance")}: <span className="num font-bold text-bounty">{fmtMoney(balance)}</span>
            </p>
          </div>
        </Panel>
      </div>
      <div className="mt-5">
        <Btn variant="secondary" onClick={() => { void deposits.refetch(); void addr.refetch(); }}>
          {t("common.retry")}
        </Btn>
      </div>
    </AdvShell>
  );
}