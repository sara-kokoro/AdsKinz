import { createFileRoute } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { AdminShell } from "@/components/workspaces";
import { Avatar, Segmented } from "@/components/cards";
import { Btn, EmptyState, Panel, Quote, StatusPill, fmtInt, fmtMoney, inputCls } from "@/components/kit";
import { platformUsers, type PlatformUser } from "@/lib/mock-data";

export const Route = createFileRoute("/kingcey/users")({
  head: () => ({
    meta: [
      { title: "Users — AdsKinz admin" },
      { name: "description", content: "Every advertiser and publisher account, with contact details, balances and blocking controls." },
      { property: "og:title", content: "Users — AdsKinz admin" },
      { property: "og:description", content: "Search accounts, inspect activity and block abusive users." },
      { name: "robots", content: "noindex" },
    ],
  }),
  component: AdminUsers,
});

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex flex-wrap justify-between gap-2 border-b border-seam py-2 text-sm last:border-0">
      <span className="text-paper-dim">{k}</span>
      <span className="num max-w-[62%] text-right font-semibold break-all">{v || "—"}</span>
    </div>
  );
}

function Detail({ u, onBack }: { u: PlatformUser; onBack: () => void }) {
  const { t } = useTranslation();
  const blocked = u.status === "blocked";
  return (
    <div className="space-y-5">
      <button onClick={onBack} className="text-xs font-semibold text-signal">← {t("common.back")}</button>
      <Panel className="glass flex flex-wrap items-center gap-4">
        <Avatar name={u.name} size={56} />
        <div>
          <h2 className="font-display text-xl font-bold">{u.name}</h2>
          <p className="num text-xs text-paper-dim">{u.id} · {u.telegram}</p>
        </div>
        <div className="ml-auto flex items-center gap-3">
          <StatusPill status={blocked ? "rejected" : "active"} />
        </div>
      </Panel>

      <Panel>
        <div className="grid gap-x-8 md:grid-cols-2">
          <Row k={t("x.admin.role")} v={u.role === "advertiser" ? t("x.admin.advertiser") : t("x.admin.publisher")} />
          <Row k={t("admin.email")} v={u.email} />
          <Row k={t("x.admin.telegram")} v={u.telegram} />
          <Row k={t("x.admin.country")} v={u.country} />
          <Row k={t("x.admin.joined")} v={u.createdAt} />
          <Row k={t("x.admin.lastSeen")} v={u.lastSeen} />
          <Row k={t("admin.ip")} v={u.ip} />
          <Row k={t("adv.balance")} v={fmtMoney(u.balance)} />
          <Row k={u.role === "advertiser" ? t("x.admin.lifetimeSpend") : t("x.admin.lifetimeEarnings")} v={fmtMoney(u.lifetime)} />
          <Row k={t("x.admin.assets")} v={fmtInt(u.assets)} />
        </div>
      </Panel>

      {u.note && <Quote tone="danger" label={t("common.reason")}>{u.note}</Quote>}

      <Panel className="flex flex-wrap items-center gap-3">
        <Btn tone={blocked ? "bounty" : "danger"}>{blocked ? t("x.admin.unblock") : t("x.admin.block")}</Btn>
        <input className="min-h-11 flex-1 rounded-xl border border-seam bg-transparent px-3 text-sm" placeholder={t("common.reason")} aria-label={t("common.reason")} />
      </Panel>
    </div>
  );
}

function AdminUsers() {
  const { t } = useTranslation();
  const [role, setRole] = useState<"all" | "advertiser" | "publisher" | "blocked">("all");
  const [q, setQ] = useState("");
  const [sel, setSel] = useState<string | null>(null);

  const list = useMemo(
    () =>
      platformUsers.filter((u) => {
        const roleOk = role === "all" || (role === "blocked" ? u.status === "blocked" : u.role === role);
        const s = q.trim().toLowerCase();
        const qOk = !s || [u.name, u.email, u.id, u.telegram].some((v) => v.toLowerCase().includes(s));
        return roleOk && qOk;
      }),
    [role, q],
  );

  const user = platformUsers.find((u) => u.id === sel);

  return (
    <AdminShell title={t("x.admin.users")} badges={{ users: platformUsers.filter((u) => u.status === "blocked").length }}>
      {user ? (
        <Detail u={user} onBack={() => setSel(null)} />
      ) : (
        <div className="space-y-5">
          <div className="flex flex-wrap items-center gap-3">
            <Segmented
              value={role}
              onChange={setRole}
              options={[
                { v: "all" as const, l: t("x.admin.all") },
                { v: "advertiser" as const, l: t("x.admin.advertiser") },
                { v: "publisher" as const, l: t("x.admin.publisher") },
                { v: "blocked" as const, l: t("x.admin.blocked") },
              ]}
            />
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder={t("x.admin.searchUser")}
              aria-label={t("x.admin.searchUser")}
              className={`max-w-72 ${inputCls()}`}
            />
          </div>

          {list.length === 0 ? (
            <Panel className="p-0"><EmptyState title={t("x.admin.empty")} /></Panel>
          ) : (
            <div className="grid gap-4 xl:grid-cols-2">
              {list.map((u) => (
                <button key={u.id} onClick={() => setSel(u.id)} className="glass flex items-center gap-4 p-4 text-left transition-transform hover:-translate-y-0.5">
                  <Avatar name={u.name} size={48} />
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-bold">{u.name}</p>
                    <p className="num truncate text-xs text-paper-dim">{u.email} · {u.id}</p>
                    <p className="mt-1 text-xs text-paper-dim">
                      {u.role === "advertiser" ? t("x.admin.advertiser") : t("x.admin.publisher")} · {u.country}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="num font-bold text-bounty">{fmtMoney(u.balance)}</p>
                    <div className="mt-1"><StatusPill status={u.status === "blocked" ? "rejected" : "active"} /></div>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </AdminShell>
  );
}
