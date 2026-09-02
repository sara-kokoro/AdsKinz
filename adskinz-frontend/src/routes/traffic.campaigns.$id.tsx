import { createFileRoute, Link, useParams } from "@tanstack/react-router";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { AdvShell } from "@/components/workspaces";
import {
  AutoTextarea, BudgetBar, Btn, ErrorBanner, Field, FieldError, ImageUpload, Modal, Panel, Quote, SectionTitle,
  StatusPill, fmtInt, fmtMoney, inputCls,
} from "@/components/kit";
import { UsdtMark } from "@/components/usdt";
import { ArtFunnel } from "@/components/illustrations";
import { IconPencil, IconSparkle } from "@/components/icons";
import { TelegramPostPreview } from "@/components/telegram-preview";
import { AD_LANGUAGES, AD_TEXT_MAX_LENGTH, BUTTON_LABELS } from "@/lib/constants";
import { validateAdMarkdown } from "@/lib/markdown";
import { ApiError, num, trackingUrl } from "@/lib/api";
import { useCampaign, useCampaignTranslations, useGenerateCopy, useUpdateCampaign } from "@/lib/queries";
import { useAuthGuard } from "@/lib/auth";
import { cn } from "@/lib/utils";

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

const MIN_BUDGET = 10;

function CampaignDetail() {
  useAuthGuard("advertiser");
  const { t } = useTranslation();
  const { id } = useParams({ from: "/traffic/campaigns/$id" });
  const campaignQ = useCampaign(id);
  const translationsQ = useCampaignTranslations(id);
  const update = useUpdateCampaign(id);
  const generateCopy = useGenerateCopy();

  const [editing, setEditing] = useState(false);
  const [name, setName] = useState("");
  const [title, setTitle] = useState("");
  const [brandName, setBrandName] = useState("");
  const [cpm, setCpm] = useState("");
  const [budget, setBudget] = useState("");
  const [language, setLanguage] = useState("");
  const [copy, setCopy] = useState("");
  const [brief, setBrief] = useState("");
  const [briefOpen, setBriefOpen] = useState(false);
  const [buttonLabel, setButtonLabel] = useState("");
  const [destinationUrl, setDestinationUrl] = useState("");
  const [image, setImage] = useState<{ url: string; name: string } | null>(null);
  const [topUp, setTopUp] = useState(false);
  const [amount, setAmount] = useState("100");
  const [notice, setNotice] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const c = campaignQ.data;

  const startEdit = () => {
    if (!c) return;
    setName(c.name);
    setTitle(c.title ?? "");
    setBrandName(c.brandName ?? "");
    setCpm(c.cpm);
    setBudget(c.budget);
    setLanguage(c.language);
    setCopy(c.copy ?? "");
    setBrief("");
    setBriefOpen(false);
    setButtonLabel(c.buttonLabel ?? "");
    setDestinationUrl(c.destinationUrl ?? "");
    setImage(c.imageUrl ? { url: c.imageUrl, name: "current-image" } : null);
    setErr(null);
    setEditing(true);
  };

  if (campaignQ.isLoading) {
    return (
      <AdvShell title={t("adv.nav.campaigns")}>
        <Panel><div className="h-40 animate-pulse rounded-md bg-panel-2" /></Panel>
      </AdvShell>
    );
  }

  if (campaignQ.isError || !c) {
    return (
      <AdvShell title={t("adv.nav.campaigns")}>
        <Panel>
          {campaignQ.isError ? (
            <ErrorBanner onRetry={() => campaignQ.refetch()} message={(campaignQ.error as Error)?.message} />
          ) : (
            <p className="text-sm text-paper-dim">{t("adv.detail.notFound")}</p>
          )}
          <div className="mt-4">
            <Link to="/traffic/campaigns"><Btn variant="secondary">{t("adv.detail.back")}</Btn></Link>
          </div>
        </Panel>
      </AdvShell>
    );
  }

  const spent = num(c.spent);
  const budgetTotal = num(c.budget);
  const remaining = Math.max(0, budgetTotal - spent);
  const ctr = c.impressions ? ((c.clicks / c.impressions) * 100).toFixed(2) : c.ctr.toFixed(2);

  const generate = () => {
    generateCopy.mutate(
      { brief: brief || title || name, language: language === "all" ? "en" : language || "en", tone: "punchy" },
      {
        onSuccess: (res) => setCopy(res.copy),
        onError: (e) => setErr(e instanceof ApiError ? e.message : t("common.loadError")),
      },
    );
  };

  const saveEdit = () => {
    if (Number(budget) < MIN_BUDGET) {
      setErr(t("adv.wizard.budgetMin"));
      return;
    }
    if (copy.length > AD_TEXT_MAX_LENGTH) {
      setErr(`${copy.length}/${AD_TEXT_MAX_LENGTH} caractères — raccourcis le texte.`);
      return;
    }
    const markdownError = validateAdMarkdown(copy);
    if (markdownError) {
      setErr(markdownError);
      return;
    }
    setErr(null);
    update.mutate(
      {
        name,
        title: title || null,
        brandName: brandName || null,
        cpm: Number(cpm),
        budget: Number(budget),
        language,
        copy,
        buttonLabel,
        destinationUrl,
        imageUrl: image?.url ?? null,
      },
      {
        onSuccess: () => { setEditing(false); setNotice(t("adv.detail.saved")); },
        onError: (e) => setErr(e instanceof ApiError ? e.message : t("common.loadError")),
      },
    );
  };

  const addFunds = () => {
    const n = Number(amount);
    if (!Number.isFinite(n) || n < MIN_BUDGET) {
      setErr(t("adv.wizard.budgetMin"));
      return;
    }
    setErr(null);
    update.mutate(
      { addBudget: n },
      {
        onSuccess: () => { setTopUp(false); setNotice(t("adv.detail.funded")); },
        onError: (e) => setErr(e instanceof ApiError ? e.message : t("common.loadError")),
      },
    );
  };

  const togglePause = () => {
    update.mutate({ status: c.status === "active" ? "paused" : "active" });
  };

  return (
    <AdvShell
      title={c.name}
      action={
        <div className="flex flex-wrap gap-2">
          <Btn tone="bounty" onClick={() => { setErr(null); setTopUp(true); }}>{t("adv.detail.topUp")}</Btn>
          {["active", "paused"].includes(c.status) && (
            <Btn variant="secondary" onClick={togglePause} disabled={update.isPending}>
              {c.status === "active" ? t("adv.detail.pause") : t("adv.detail.relaunch")}
            </Btn>
          )}
          <Btn variant="secondary" aria-label={t("adv.detail.edit")} title={t("adv.detail.edit")} className="w-11 px-0" onClick={startEdit}>
            <IconPencil className="size-4" />
          </Btn>
        </div>
      }
    >
      <div className="space-y-5 overflow-x-hidden">
        <Link to="/traffic/campaigns" className="inline-block text-sm font-semibold text-signal hover:underline">
          ← {t("adv.detail.back")}
        </Link>

        {notice && <Quote tone="bounty" label={t("adv.nav.campaigns")}>{notice}</Quote>}

        <Panel className="flex flex-wrap items-center gap-5">
          <div className="w-full sm:w-auto sm:min-w-52">
            <p className="text-xs font-semibold text-paper-dim">{t("adv.detail.remaining")}</p>
            <p className="num mt-1 flex items-center gap-2 font-display text-3xl font-extrabold text-bounty">
              <UsdtMark size={26} />
              {fmtMoney(remaining)}
            </p>
            <p className="num mt-1 text-xs text-paper-dim">
              {fmtMoney(spent)} / {fmtMoney(budgetTotal, 0)}
            </p>
            <div className="mt-3 w-full max-w-56"><BudgetBar used={spent} total={budgetTotal || 1} /></div>
          </div>
          <div className="hidden min-w-44 flex-1 sm:block"><ArtFunnel /></div>
          <StatusPill status={c.status} />
        </Panel>

        {c.status === "paused_balance" && (
          <Quote tone="danger" label={t("adv.detail.topUp")}>{t("adv.detail.topUpSub")}</Quote>
        )}
        {c.rejectionReason && (
          <Quote tone="danger" label={t("status.rejected")}>{c.rejectionReason}</Quote>
        )}

        <div className="grid gap-5 lg:grid-cols-2">
          <Panel>
            <SectionTitle>{t("adv.detail.overview")}</SectionTitle>
            <dl className="text-sm">
              {[
                [t("adv.colCampaign"), c.name],
                ["ID", c.id],
                [t("adv.colFormat"), c.format],
                [t("adv.targeting"), c.language],
                [t("adv.colCpm"), fmtMoney(num(c.cpm))],
                [t("adv.colClicks"), fmtInt(c.clicks)],
                [t("pub.impressions30"), fmtInt(c.impressions)],
                [t("pub.ctr"), `${ctr}%`],
                [t("admin.detail.trackedUrl"), c.trackingId ? trackingUrl(c.trackingId) : "—"],
              ].map(([k, v]) => (
                <div key={k} className="border-b border-seam py-2 last:border-0">
                  <dt className="text-xs text-paper-dim">{k}</dt>
                  <dd className="num mt-0.5 break-all font-semibold">{v}</dd>
                </div>
              ))}
            </dl>
          </Panel>

          <Panel>
            <SectionTitle>{t("adv.detail.settings")}</SectionTitle>
            <dl className="text-sm">
              {[
                [t("adv.wizard.bannerTitle"), c.title || "—"],
                [t("adv.wizard.brandName"), c.brandName || "—"],
                [t("adv.wizard.buttonLabel"), c.buttonLabel || "—"],
                [t("adv.wizard.destination"), c.destinationUrl || "—"],
              ].map(([k, v]) => (
                <div key={k} className="border-b border-seam py-2 last:border-0">
                  <dt className="text-xs text-paper-dim">{k}</dt>
                  <dd className="mt-0.5 break-all font-semibold">{v}</dd>
                </div>
              ))}
            </dl>
            <p className="mt-3 text-sm leading-relaxed whitespace-pre-wrap text-paper-dim">{c.copy}</p>
          </Panel>
        </div>

        <Modal
          open={editing}
          onClose={() => { setEditing(false); setErr(null); }}
          title={t("adv.detail.edit")}
          sub={t("adv.detail.editSub")}
          footer={
            <>
              <Btn onClick={saveEdit} disabled={update.isPending}>{t("adv.detail.save")}</Btn>
              <Btn variant="secondary" onClick={() => { setEditing(false); setErr(null); }}>{t("common.cancel")}</Btn>
            </>
          }
        >
          <div className="grid gap-6 lg:grid-cols-[1fr_20rem]">
            <div className="space-y-4">
              <Field label={t("adv.colCampaign")} htmlFor="cname">
                <input id="cname" value={name} onChange={(e) => setName(e.target.value)} className={inputCls()} />
              </Field>
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label={t("adv.wizard.bannerTitle")} htmlFor="ctitle">
                  <input id="ctitle" value={title} onChange={(e) => setTitle(e.target.value)} maxLength={56} className={inputCls()} />
                </Field>
                <Field label={t("adv.wizard.brandName")} htmlFor="cbrand">
                  <input id="cbrand" value={brandName} onChange={(e) => setBrandName(e.target.value)} maxLength={40} className={inputCls()} />
                </Field>
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label={t("adv.colCpm")} htmlFor="ccpm">
                  <input id="ccpm" type="number" step="0.1" value={cpm} onChange={(e) => setCpm(e.target.value)} className={`num ${inputCls()}`} />
                </Field>
                <Field label={t("adv.budget")} error={Number(budget) < MIN_BUDGET ? t("adv.wizard.budgetMin") : undefined} htmlFor="cbud">
                  <input id="cbud" type="number" value={budget} onChange={(e) => setBudget(e.target.value)} className={`num ${inputCls(Number(budget) < MIN_BUDGET)}`} />
                </Field>
              </div>
              <Field label={t("adv.targeting")} htmlFor="clang">
                <select id="clang" value={language} onChange={(e) => setLanguage(e.target.value)} className={inputCls()}>
                  {AD_LANGUAGES.map((l) => (
                    <option key={l.code} value={l.code}>{l.label}</option>
                  ))}
                </select>
              </Field>
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <label className="text-sm font-semibold" htmlFor="ccopy">{t("adv.wizard.copy")}</label>
                  <Btn
                    variant="secondary"
                    className="ml-auto min-h-9 px-3 text-xs"
                    onClick={() => (briefOpen ? generate() : setBriefOpen(true))}
                    disabled={generateCopy.isPending}
                  >
                    <IconSparkle width={14} height={14} />
                    {copy && briefOpen ? t("adv.wizard.regenerate") : t("adv.wizard.generateAi")}
                  </Btn>
                </div>
                {briefOpen && (
                  <input
                    value={brief}
                    onChange={(e) => setBrief(e.target.value)}
                    placeholder={t("adv.wizard.briefPlaceholder")}
                    aria-label={t("adv.wizard.brief")}
                    className={cn("mt-2", inputCls())}
                  />
                )}
                <AutoTextarea id="ccopy" minRows={3} value={copy} onChange={setCopy} maxLength={AD_TEXT_MAX_LENGTH} className="mt-2" />
                <div className="mt-1.5 flex justify-end">
                  <span
                    className={cn(
                      "text-xs tabular-nums",
                      copy.length > AD_TEXT_MAX_LENGTH * 0.9 ? "text-danger font-semibold" : "text-paper-dim",
                    )}
                  >
                    {copy.length}/{AD_TEXT_MAX_LENGTH}
                  </span>
                </div>
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label={t("adv.wizard.buttonLabel")} htmlFor="cbtn">
                  <select id="cbtn" value={buttonLabel} onChange={(e) => setButtonLabel(e.target.value)} className={inputCls()}>
                    {BUTTON_LABELS.map((l) => (
                      <option key={l} value={l}>{l}</option>
                    ))}
                  </select>
                </Field>
                <Field label={t("adv.wizard.destination")} htmlFor="curl">
                  <input
                    id="curl"
                    value={destinationUrl}
                    onChange={(e) => setDestinationUrl(e.target.value)}
                    placeholder="https://t.me/..."
                    className={inputCls()}
                  />
                </Field>
              </div>
              <Field label={t("adv.wizard.image")} htmlFor="cimg">
                <ImageUpload value={image} onChange={setImage} />
              </Field>
              {err && <FieldError>{err}</FieldError>}
            </div>
            <div className="hidden lg:block">
              <p className="mb-2 text-xs font-semibold text-paper-dim">{t("adv.wizard.preview")}</p>
              <TelegramPostPreview
                title={title}
                brandName={brandName}
                copy={copy || "…"}
                buttonLabel={buttonLabel || "Go"}
                imageUrl={image?.url ?? null}
              />
            </div>
          </div>
        </Modal>

        <Panel>
          <SectionTitle>{t("nav.docs")} — Translations</SectionTitle>
          {translationsQ.isLoading ? (
            <div className="h-16 animate-pulse rounded-md bg-panel-2" />
          ) : translationsQ.isError ? (
            <ErrorBanner onRetry={() => translationsQ.refetch()} message={(translationsQ.error as Error)?.message} />
          ) : !translationsQ.data || translationsQ.data.translations.length === 0 ? (
            <p className="text-sm text-paper-dim">{t("common.none")}</p>
          ) : (
            <ul className="divide-y divide-seam">
              {translationsQ.data.translations.map((tr) => (
                <li key={tr.lang_code} className="py-3">
                  <p className="text-xs font-semibold text-paper-dim uppercase">{tr.lang_code}</p>
                  <p className="mt-1 text-sm">{tr.translated_text}</p>
                  {tr.translated_button_label && <p className="mt-1 text-xs text-signal">{tr.translated_button_label}</p>}
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>

      <Modal
        open={topUp}
        onClose={() => setTopUp(false)}
        title={t("adv.detail.topUpTitle")}
        sub={t("adv.detail.topUpSub")}
        footer={
          <>
            <Btn tone="bounty" onClick={addFunds} disabled={update.isPending}>{t("adv.detail.addFunds")}</Btn>
            <Btn variant="secondary" onClick={() => setTopUp(false)}>{t("common.cancel")}</Btn>
          </>
        }
      >
        <Field label={t("adv.detail.amount")} error={Number(amount) < MIN_BUDGET ? t("adv.wizard.budgetMin") : undefined} htmlFor="amt">
          <div className="flex items-center gap-2">
            <UsdtMark size={20} />
            <input id="amt" type="number" value={amount} onChange={(e) => setAmount(e.target.value)} className={`num ${inputCls(Number(amount) < MIN_BUDGET)}`} />
          </div>
        </Field>
        {err && <FieldError>{err}</FieldError>}
      </Modal>
    </AdvShell>
  );
}