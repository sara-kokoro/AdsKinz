import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { AdvShell } from "@/components/workspaces";
import { Btn, EmptyState, Panel, SectionTitle, StatusPill, fmtMoney } from "@/components/kit";
import { IconAlert, IconCopy, IconList, IconWallet, IconShield } from "@/components/icons";
import { UsdtMark } from "@/components/usdt";
import { advertiserSummary, deposits } from "@/lib/mock-data";
import { ENDPOINTS } from "@/lib/api";
import { cn } from "@/lib/utils";

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
  { id: "ton", key: "adv.deposits.ton", address: "UQBn4kZ2xLpQm7v9cTd1RsWq8YhX3aFj0PLd7hZ2" },
  { id: "trc20", key: "adv.deposits.trc", address: "TQ9m4KeVb1nR7sXp2LdCf8YhZ0aUw3Jt6P" },
  { id: "bnb", key: "adv.deposits.bnb", address: "0x7f3aB1c92De54607Ff21bC8a4E90d5cB6721aE04" },
];

function Deposits() {
  const { t } = useTranslation();
  const [net, setNet] = useState("ton");
  // INTEGRATION: GET ENDPOINTS.depositAddress?network=<net> — derived address + memo
  void ENDPOINTS.depositAddress;
  const active = NETWORKS.find((n) => n.id === net)!;

  return (
    <AdvShell title={t("adv.deposits.title")}>
      <div className="grid gap-5 lg:grid-cols-[1.1fr_1fr]">
        <div className="space-y-5">
          <Panel>
            <p className="flex items-center gap-2 text-xs font-semibold text-paper-dim"><IconWallet width={14} height={14} />{t("adv.balance")}</p>
            <p className="num mt-1 flex items-center gap-2 text-3xl font-extrabold text-bounty">
              <UsdtMark size={26} />
              {fmtMoney(advertiserSummary.balance)}
            </p>
            <p className="mt-2 text-xs text-paper-dim">{t("adv.deposits.noMinimum")}</p>
          </Panel>

          <Panel>
            <SectionTitle><span className="inline-flex items-center gap-2"><IconShield width={16} height={16} />{t("adv.deposits.method")}</span></SectionTitle>
            <div className="flex flex-wrap gap-2">
              {NETWORKS.map((n) => (
                <button
                  key={n.id}
                  onClick={() => setNet(n.id)}
                  aria-pressed={net === n.id}
                  className={cn(
                    "flex min-h-11 items-center gap-2 rounded-xl border px-4 text-sm font-semibold",
                    net === n.id ? "border-signal bg-signal-soft text-signal" : "border-seam text-paper-dim",
                  )}
                >
                  <UsdtMark size={16} />
                  {t(n.key)}
                </button>
              ))}
            </div>

            {net === "trc20" && (
              <p className="mt-4 rounded-xl border border-seam bg-bounty-soft p-3 text-xs font-semibold text-bounty">
                {t("adv.deposits.trcWarning")}
              </p>
            )}

            <div className="mt-5">
              <p className="text-xs font-semibold text-paper-dim">{t("adv.deposits.address")}</p>
              <div className="mt-2 flex items-center gap-2 rounded-xl border border-seam p-3">
                <span className="num flex-1 text-xs break-all">{active.address}</span>
                <button aria-label="Copy address" className="text-paper-dim hover:text-paper">
                  <IconCopy width={16} height={16} />
                </button>
              </div>
            </div>

            {net === "ton" && (
              <div className="mt-4 rounded-xl border border-bounty/60 bg-bounty-soft p-3">
                <p className="text-xs font-bold text-bounty">{t("adv.deposits.memo")}</p>
                <p className="num mt-1.5 text-sm font-bold">adskinz-4192837</p>
                <p className="mt-2 flex gap-2 text-xs text-bounty">
                  <IconAlert width={14} height={14} />
                  {t("adv.deposits.memoWarning")}
                </p>
              </div>
            )}

            <div className="mt-5 flex aspect-square w-40 items-center justify-center rounded-xl border border-seam text-xs text-paper-dim">
              QR
            </div>
          </Panel>
        </div>

        <Panel className="p-0">
          <div className="border-b border-seam px-5 py-4">
            <h2 className="flex items-center gap-2 font-display text-base font-bold"><IconList width={16} height={16} />{t("adv.deposits.history")}</h2>
          </div>
          {deposits.length === 0 ? (
            <EmptyState title={t("adv.deposits.emptyTitle")} sub={t("adv.deposits.emptySub")} />
          ) : (
            <ul className="divide-y divide-seam">
              {deposits.map((d) => (
                <li key={d.id} className="flex flex-wrap items-center gap-3 px-5 py-4">
                  <div>
                    <p className="num font-bold text-bounty">{fmtMoney(d.amount)}</p>
                    <p className="text-xs text-paper-dim">
                      {d.network} · {d.date}
                    </p>
                  </div>
                  <div className="ml-auto flex items-center gap-3">
                    <span className="num text-xs text-paper-dim">{d.txHash}</span>
                    <StatusPill status={d.status} />
                  </div>
                </li>
              ))}
            </ul>
          )}
          <div className="border-t border-seam px-5 py-4">
            <p className="text-xs text-paper-dim">
              {t("adv.deposits.updated")} — {t("adv.deposits.newBalance")}:{" "}
              <span className="num font-bold text-bounty">{fmtMoney(advertiserSummary.balance)}</span>
            </p>
          </div>
        </Panel>
      </div>
      <div className="mt-5">
        <Btn variant="secondary">{t("common.retry")}</Btn>
      </div>
    </AdvShell>
  );
}
