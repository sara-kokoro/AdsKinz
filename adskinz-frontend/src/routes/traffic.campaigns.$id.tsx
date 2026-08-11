import { createFileRoute, Link, useParams } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { AdvShell } from "@/components/workspaces";
import {
  BudgetBar,
  Btn,
  Field,
  Modal,
  Panel,
  Quote,
  SectionTitle,
  StatusPill,
  Sparkline,
  fmtInt,
  fmtMoney,
  inputCls,
} from "@/components/kit";
import { UsdtMark } from "@/components/usdt";
import { AD_LANGUAGES, campaigns, spark } from "@/lib/mock-data";

export const Route = createFileRoute("/traffic/campaigns/$id")({
  head: () => ({
    meta: [
      { title: "Campaign details — AdsKinz traffic" },
      { name: "description", content: "Review a campaign's delivery, edit its settings and top up its budget to relaunch it." },
      { property: "og:title", content: "Campaign details — AdsKinz traffic" },
      { property: "og:description", content: "Edit targeting, CPM and budget, then relaunch in one click." },
    ],
  }),
  component: CampaignDetail,
});

const MIN_BUDGET = 50;

function CampaignDetail() {
  const { t } = useTranslation();
  const { id } = useParams({ from: "/traffic/campaigns/$id" });
  const base = useMemo(() => campaigns.find((c) => c.id === id), [id]);

  const [draft, setDraft] = useState(() => base && { ...base });
  const [editing, setEditing] = useState(false);
  const [topUp, setTopUp] = useState(false);
  const [amount, setAmount] = useState("100");
  const [notice, setNotice] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  if (!base || !draft) {
    return (
      <AdvShell title={t("adv.nav.campaigns")}>
        <Panel>
          <p className="text-sm text-paper-dim">{t("adv.detail.notFound")}</p>
          <div className="mt-4">
            <Link to="/traffic/campaigns"><Btn variant="secondary">{t("adv.detail.back")}</Btn></Link>
          </div>
        </Panel>
      </AdvShell>
    );
  }

  const remaining = Math.max(0, draft.budget - draft.spent);
  const ctr = draft.impressions ? ((draft.clicks / draft.impressions) * 100).toFixed(2) : "0.00";

  const saveEdit = () => {
    if (draft.budget < MIN_BUDGET) {
      setErr(t("adv.wizard.budgetMin"));
      return;
    }
    setErr(null);
    setEditing(false);
    setDraft((d) => d && { ...d, status: "pending_review" });
    setNotice(t("adv.detail.saved"));
  };

  const addFunds = () => {
    const n = Number(amount);
    if (!Number.isFinite(n) || n < MIN_BUDGET) {
      setErr(t("adv.wizard.budgetMin"));
      return;
    }
    setErr(null);
    setDraft((d) => d && { ...d, budget: d.budget + n, status: d.status === "rejected" ? d.status : "active" });
    setTopUp(false);
    setNotice(t("adv.detail.funded"));
  };

  return (
    <AdvShell
      title={draft.name}
      action={
        <div className="flex flex-wrap gap-2">
          <Btn tone="bounty" onClick={() => setTopUp(true)}>{t("adv.detail.topUp")}</Btn>
          <Btn variant="secondary" onClick={() => setEditing((v) => !v)}>{t("adv.detail.edit")}</Btn>
        </div>
      }
    >
      <div className="space-y-5">
        <Link to="/traffic/campaigns" className="inline-block text-sm font-semibold text-signal hover:underline">
          ← {t("adv.detail.back")}
        </Link>

        {notice && <Quote tone="bounty" label={t("adv.nav.campaigns")}>{notice}</Quote>}

        <Panel className="flex flex-wrap items-center gap-5">
          <div className="min-w-52">
            <p className="text-xs font-semibold text-paper-dim">{t("adv.detail.remaining")}</p>
            <p className="num mt-1 flex items-center gap-2 font-display text-3xl font-extrabold text-bounty">
              <UsdtMark size={26} />
              {fmtMoney(remaining)}
            </p>
            <p className="num mt-1 text-xs text-paper-dim">
              {fmtMoney(draft.spent)} / {fmtMoney(draft.budget, 0)}
            </p>
            <div className="mt-3 w-56"><BudgetBar used={draft.spent} total={draft.budget} /></div>
          </div>
          <div className="min-w-44 flex-1"><Sparkline points={spark(4, 30)} tone="signal" /></div>
          <StatusPill status={draft.status} />
        </Panel>

        {draft.status === "paused_balance" && (
          <Quote tone="danger" label={t("adv.detail.topUp")}>{t("adv.detail.topUpSub")}</Quote>
        )}

        <div className="grid gap-5 lg:grid-cols-2">
          <Panel>
            <SectionTitle>{t("adv.detail.overview")}</SectionTitle>
            <dl className="text-sm">
              {[
                [t("adv.colCampaign"), draft.name],
                ["ID", draft.id],
                [t("adv.colFormat"), draft.format],
                [t("adv.targeting"), draft.language],
                [t("adv.colCpm"), fmtMoney(draft.cpm)],
                [t("adv.colClicks"), fmtInt(draft.clicks)],
                [t("pub.impressions30"), fmtInt(draft.impressions)],
                [t("pub.ctr"), `${ctr}%`],
              ].map(([k, v]) => (
                <div key={k} className="flex justify-between gap-3 border-b border-seam py-2 last:border-0">
                  <dt className="text-paper-dim">{k}</dt>
                  <dd className="num font-semibold">{v}</dd>
                </div>
              ))}
            </dl>
            {draft.rejectionReason && <p className="mt-3 text-xs text-danger">{draft.rejectionReason}</p>}
          </Panel>

          <Panel>
            <SectionTitle>{t("adv.detail.settings")}</SectionTitle>
            <div className="space-y-4">
              <Field label={t("adv.colCampaign")} htmlFor="cname">
                <input
                  id="cname"
                  disabled={!editing}
                  value={draft.name}
                  onChange={(e) => setDraft((d) => d && { ...d, name: e.target.value })}
                  className={inputCls()}
                />
              </Field>
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label={t("adv.colCpm")} htmlFor="ccpm">
                  <input
                    id="ccpm"
                    type="number"
                    step="0.1"
                    disabled={!editing}
                    value={draft.cpm}
                    onChange={(e) => setDraft((d) => d && { ...d, cpm: Number(e.target.value) })}
                    className={`num ${inputCls()}`}
                  />
                </Field>
                <Field label={t("adv.budget")} error={draft.budget < MIN_BUDGET ? t("adv.wizard.budgetMin") : undefined} htmlFor="cbud">
                  <input
                    id="cbud"
                    type="number"
                    disabled={!editing}
                    value={draft.budget}
                    onChange={(e) => setDraft((d) => d && { ...d, budget: Number(e.target.value) })}
                    className={`num ${inputCls(draft.budget < MIN_BUDGET)}`}
                  />
                </Field>
              </div>
              <Field label={t("adv.targeting")} htmlFor="clang">
                <select
                  id="clang"
                  disabled={!editing}
                  value={draft.language}
                  onChange={(e) => setDraft((d) => d && { ...d, language: e.target.value })}
                  className={inputCls()}
                >
                  {AD_LANGUAGES.map((l) => (
                    <option key={l.code} value={l.label}>{l.label}</option>
                  ))}
                </select>
              </Field>
              {err && <p className="text-xs font-semibold text-danger">{err}</p>}
              {editing && (
                <div className="flex flex-wrap gap-2">
                  <Btn onClick={saveEdit}>{t("adv.detail.save")}</Btn>
                  <Btn variant="secondary" onClick={() => { setDraft({ ...base }); setEditing(false); setErr(null); }}>
                    {t("common.cancel")}
                  </Btn>
                </div>
              )}
            </div>
          </Panel>
        </div>
      </div>

      <Modal
        open={topUp}
        onClose={() => setTopUp(false)}
        title={t("adv.detail.topUpTitle")}
        sub={t("adv.detail.topUpSub")}
        footer={
          <>
            <Btn tone="bounty" onClick={addFunds}>{t("adv.detail.addFunds")}</Btn>
            <Btn variant="secondary" onClick={() => setTopUp(false)}>{t("common.cancel")}</Btn>
          </>
        }
      >
        <Field
          label={t("adv.detail.amount")}
          error={Number(amount) < MIN_BUDGET ? t("adv.wizard.budgetMin") : undefined}
          htmlFor="amt"
        >
          <div className="flex items-center gap-2">
            <UsdtMark size={20} />
            <input
              id="amt"
              type="number"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              className={`num ${inputCls(Number(amount) < MIN_BUDGET)}`}
            />
          </div>
        </Field>
      </Modal>
    </AdvShell>
  );
}
