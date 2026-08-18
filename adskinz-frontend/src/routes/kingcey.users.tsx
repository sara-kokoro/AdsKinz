import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { AdminShell } from "@/components/workspaces";
import { Btn, ErrorBanner, Field, KpiSkeleton, Panel, Quote, SectionTitle, fmtInt, fmtMoney, inputCls } from "@/components/kit";
import { useAdminOverview, useAdminFinances, useBlockAccount } from "@/lib/queries";
import { num, ApiError } from "@/lib/api";
import { useAuthGuard } from "@/lib/auth";

export const Route = createFileRoute("/kingcey/users")({
  head: () => ({
    meta: [
      { title: "Users — AdsKinz admin" },
      { name: "description", content: "Advertiser and publisher account counts and top accounts, with block/unblock controls." },
      { property: "og:title", content: "Users — AdsKinz admin" },
      { property: "og:description", content: "Account summary and blocking controls." },
      { name: "robots", content: "noindex" },
    ],
  }),
  component: AdminUsers,
});

function AdminUsers() {
  useAuthGuard("admin");
  const { t } = useTranslation();
  const overview = useAdminOverview();
  const finances = useAdminFinances("30d");
  const block = useBlockAccount();

  const [role, setRole] = useState<"advertiser" | "publisher">("advertiser");
  const [id, setId] = useState("");
  const [blocked, setBlocked] = useState(true);
  const [reason, setReason] = useState("");
  const [result, setResult] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    setErr(null);
    setResult(null);
    if (!id.trim()) {
      setErr("Account id is required.");
      return;
    }
    if (blocked && !reason.trim()) {
      setErr("A reason is required when blocking an account.");
      return;
    }
    block.mutate(
      { role, id: id.trim(), blocked, reason: reason.trim() },
      {
        onSuccess: (r) => setResult(r.message ?? "Done."),
        onError: (e2) => setErr(e2 instanceof ApiError ? e2.message : "Action failed."),
      },
    );
  };

  return (
    <AdminShell title={t("x.admin.users")}>
      <div className="space-y-5">
        <Quote tone="bounty" label="Limitation">
          The AdsKinz API does not expose a full account listing endpoint. This page shows the counts and top
          accounts that are available, plus a direct block/unblock action by account id — it does not fabricate a
          user table.
        </Quote>

        {(overview.isError || finances.isError) && (
          <ErrorBanner onRetry={() => { overview.refetch(); finances.refetch(); }} />
        )}

        {overview.isLoading ? (
          <div className="grid gap-4 sm:grid-cols-2">
            <KpiSkeleton />
            <KpiSkeleton />
          </div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2">
            <Panel>
              <p className="text-xs font-semibold text-paper-dim">{t("x.admin.advertiser")}s</p>
              <p className="num mt-2 text-3xl font-bold">{fmtInt(overview.data?.advertisers ?? 0)}</p>
            </Panel>
            <Panel>
              <p className="text-xs font-semibold text-paper-dim">{t("x.admin.publisher")}s</p>
              <p className="num mt-2 text-3xl font-bold">{fmtInt(overview.data?.publishers ?? 0)}</p>
            </Panel>
          </div>
        )}

        <div className="grid gap-5 lg:grid-cols-2">
          <Panel className="p-0">
            <div className="p-5 pb-0"><SectionTitle>Top advertisers (30d)</SectionTitle></div>
            {finances.isLoading ? (
              <div className="p-5"><KpiSkeleton /></div>
            ) : (finances.data?.topAdvertisers.length ?? 0) === 0 ? (
              <p className="px-5 pb-5 text-sm text-paper-dim">No data.</p>
            ) : (
              <ul className="divide-y divide-seam">
                {finances.data?.topAdvertisers.map((a) => (
                  <li key={a.id} className="flex items-center justify-between gap-3 px-5 py-3 text-sm">
                    <span className="min-w-0 truncate font-semibold">{a.label}</span>
                    <span className="num shrink-0 font-bold text-bounty">{fmtMoney(num(a.amount))}</span>
                  </li>
                ))}
              </ul>
            )}
          </Panel>
          <Panel className="p-0">
            <div className="p-5 pb-0"><SectionTitle>Top publishers (30d)</SectionTitle></div>
            {finances.isLoading ? (
              <div className="p-5"><KpiSkeleton /></div>
            ) : (finances.data?.topPublishers.length ?? 0) === 0 ? (
              <p className="px-5 pb-5 text-sm text-paper-dim">No data.</p>
            ) : (
              <ul className="divide-y divide-seam">
                {finances.data?.topPublishers.map((p) => (
                  <li key={p.id} className="flex items-center justify-between gap-3 px-5 py-3 text-sm">
                    <span className="min-w-0 truncate font-semibold">{p.label}</span>
                    <span className="num shrink-0 font-bold text-bounty">{fmtMoney(num(p.amount))}</span>
                  </li>
                ))}
              </ul>
            )}
          </Panel>
        </div>

        <Panel>
          <SectionTitle sub="Block or unblock an advertiser or publisher account by id.">Block / unblock account</SectionTitle>
          <form onSubmit={submit} className="grid gap-4 sm:grid-cols-2">
            <Field label="Role">
              <select className={inputCls()} value={role} onChange={(e) => setRole(e.target.value as "advertiser" | "publisher")}>
                <option value="advertiser">{t("x.admin.advertiser")}</option>
                <option value="publisher">{t("x.admin.publisher")}</option>
              </select>
            </Field>
            <Field label="Account id">
              <input className={inputCls()} value={id} onChange={(e) => setId(e.target.value)} placeholder="uuid" />
            </Field>
            <Field label="Action">
              <select className={inputCls()} value={blocked ? "block" : "unblock"} onChange={(e) => setBlocked(e.target.value === "block")}>
                <option value="block">{t("x.admin.block")}</option>
                <option value="unblock">{t("x.admin.unblock")}</option>
              </select>
            </Field>
            <Field label="Reason" hint={blocked ? "Required when blocking." : "Optional."}>
              <input className={inputCls()} value={reason} onChange={(e) => setReason(e.target.value)} placeholder={t("common.reason")} />
            </Field>
            <div className="sm:col-span-2 flex items-center gap-3">
              <Btn tone={blocked ? "danger" : "bounty"} type="submit" disabled={block.isPending}>
                {block.isPending ? "Working…" : blocked ? t("x.admin.block") : t("x.admin.unblock")}
              </Btn>
              {result && <p className="text-sm font-semibold text-signal">{result}</p>}
              {err && <p className="text-sm font-semibold text-danger">{err}</p>}
            </div>
          </form>
        </Panel>
      </div>
    </AdminShell>
  );
}
