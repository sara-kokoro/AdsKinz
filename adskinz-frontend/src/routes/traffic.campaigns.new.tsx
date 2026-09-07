import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { AdvShell } from "@/components/workspaces";
import { AutoTextarea, Btn, FieldError, HtmlFormatToolbar, ImageUpload, Panel, Quote, SectionTitle, fmtMoney, inputCls } from "@/components/kit";
import { TelegramPostPreview } from "@/components/telegram-preview";
import { IconCheck, IconSparkle, IconChannel, IconApp, IconImage, IconGlobe, IconWallet, IconEye, IconTag } from "@/components/icons";
import { AD_LANGUAGES, AD_TEXT_MAX_LENGTH, BUTTON_LABELS } from "@/lib/constants";
import { validateAdHtml } from "@/lib/html-format";
import { ApiError, apiFetch } from "@/lib/api";
import type { Campaign } from "@/lib/types";
import { useCreateCampaign, useGenerateCopy } from "@/lib/queries";
import { cn } from "@/lib/utils";
import { useAuthGuard } from "@/lib/auth";

export const Route = createFileRoute("/traffic/campaigns/new")({
  head: () => ({
    meta: [
      { title: "New campaign — AdsKinz traffic" },
      { name: "description", content: "Create a native Telegram campaign: format, creative, targeting, budget and review." },
      { property: "og:title", content: "New campaign — AdsKinz traffic" },
      { property: "og:description", content: "Launch a native Telegram campaign from $10." },
    ],
  }),
  component: Wizard,
});

const STEPS = ["step1", "step2", "step3", "step4", "step5"] as const;
const STEP_ICONS = [IconChannel, IconImage, IconGlobe, IconWallet, IconEye] as const;

function Wizard() {
  useAuthGuard("advertiser");
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [step, setStep] = useState(0);

  const [format, setFormat] = useState<"channel" | "interstitial" | "pop">("channel");
  const [image, setImage] = useState<{ url: string; name: string } | null>(null);
  const [bannerTitle, setBannerTitle] = useState("");
  const [brandName, setBrandName] = useState("");
  const [copy, setCopy] = useState("");
  const copyTextareaRef = useRef<HTMLTextAreaElement>(null);
  const [brief, setBrief] = useState("");
  const [briefOpen, setBriefOpen] = useState(false);
  const [label, setLabel] = useState("Learn more");
  const [url, setUrl] = useState("");
  const [lang, setLang] = useState("all");
  const [budget, setBudget] = useState("");
  const [daily, setDaily] = useState("");
  const [cpm, setCpm] = useState("");
  const [cpc, setCpc] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [submitError, setSubmitError] = useState<string | null>(null);

  const generateCopy = useGenerateCopy();
  const createCampaign = useCreateCampaign();

  const copyIssue = (value: string): string | null => {
    if (value.length > AD_TEXT_MAX_LENGTH) {
      return `${value.length}/${AD_TEXT_MAX_LENGTH} caractères — raccourcis le texte.`;
    }
    return validateAdHtml(value);
  };

  const handleCopyChange = (value: string) => {
    setCopy(value);
    // Clear a stale error the moment the text becomes valid again; don't
    // interrupt typing by raising a new one mid-edit — that happens on blur.
    if (errors["copy"] && !copyIssue(value)) {
      setErrors((e) => {
        const { copy: _drop, ...rest } = e;
        return rest;
      });
    }
  };

  const handleCopyBlur = () => {
    const issue = copy.trim() ? copyIssue(copy) : null;
    setErrors((e) => (issue ? { ...e, copy: issue } : e));
  };

  const generate = () => {
    generateCopy.mutate(
      { brief: brief || format, language: lang === "all" ? "en" : lang, tone: "punchy" },
      {
        onSuccess: (res) => setCopy(res.copy),
        onError: (err) => setErrors((e) => ({ ...e, copy: err instanceof ApiError ? err.message : t("common.loadError") })),
      },
    );
  };

  const validate = () => {
    const e: Record<string, string> = {};
    if (step === 1) {
      if (!bannerTitle.trim()) e["bannerTitle"] = t("adv.wizard.errTitle");
      if (!copy.trim()) e["copy"] = t("adv.wizard.errCopy");
      else if (copy.length > AD_TEXT_MAX_LENGTH) e["copy"] = `${copy.length}/${AD_TEXT_MAX_LENGTH} caractères — raccourcis le texte.`;
      else {
        const htmlError = validateAdHtml(copy);
        if (htmlError) e["copy"] = htmlError;
      }
      if (!/^https:\/\/.+\..+/.test(url)) e["url"] = t("adv.wizard.errUrl");
    }
    if (step === 3) {
      // Budget is optional at creation time: a campaign can be created with
      // an isolated $0 budget and funded later via top-up, for advertisers
      // who don't have wallet balance ready right now. Only validate the
      // minimum when they actually typed an amount.
      if (budget !== "" && Number(budget) < 10) e["budget"] = t("adv.wizard.errMinBudget");
      if (Number(cpm) < 1.7 || !cpm) e["cpm"] = t("adv.wizard.errMinCpm");
      if (cpc !== "" && (Number(cpc) < 0.015 || Number(cpc) > 0.13)) e["cpc"] = t("adv.wizard.errCpcRange");
    }
    setErrors(e);
    return Object.keys(e).length === 0;
  };

  const next = () => {
    if (!validate()) return;
    setStep((s) => Math.min(STEPS.length - 1, s + 1));
  };

  const budgetTooLow = budget !== "" && Number(budget) < 10;

  const competitiveness =
    Number(cpm) >= 4.5 ? "compHigh" : Number(cpm) >= 2.8 ? "compMid" : "compLow";

  const submit = () => {
    setSubmitError(null);
    createCampaign.mutate(
      {
        name: `${format} campaign — ${new Date().toISOString().slice(0, 10)}`,
        format,
        title: bannerTitle,
        brandName: brandName || null,
        copy,
        button_label: label,
        destinationUrl: url,
        language: lang,
        dailyBudget: daily ? Number(daily) : null,
        cpm: Number(cpm),
        cpc: cpc ? Number(cpc) : null,
        imageUrl: image?.url ?? null,
        ai_generated: generateCopy.isSuccess,
      },
      {
        onSuccess: async (campaign) => {
          // Campaigns are created with an isolated $0 budget; funding it is a
          // separate step that actually moves money out of the wallet.
          const amount = Number(budget);
          if (amount > 0) {
            try {
              await apiFetch<Campaign>(`/advertiser/campaigns/${campaign.id}`, {
                method: "PATCH",
                body: { addBudget: amount },
              });
            } catch (err) {
              // The campaign exists either way — surface the funding error but
              // still take the advertiser to it so they can retry the top-up.
              setSubmitError(err instanceof ApiError ? err.message : t("common.loadError"));
            }
          }
          void navigate({ to: "/traffic/campaigns/$id", params: { id: campaign.id } });
        },
        onError: (err) => setSubmitError(err instanceof ApiError ? err.message : t("common.loadError")),
      },
    );
  };

  return (
    <AdvShell title={t("adv.wizard.title")}>
      <div className="mx-auto max-w-3xl space-y-5">
        <ol className="flex items-center gap-1.5 sm:gap-2">
          {STEPS.map((s, i) => {
            const StepIcon = STEP_ICONS[i];
            const state = i === step ? "current" : i < step ? "done" : "upcoming";
            return (
              <li key={s} className="flex flex-1 items-center gap-1.5 sm:gap-2">
                <div
                  className={cn(
                    "flex shrink-0 items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-semibold transition-colors",
                    state === "current" && "border-signal bg-signal-soft text-signal",
                    state === "done" && "border-seam bg-panel-2 text-paper",
                    state === "upcoming" && "border-seam text-paper-dim",
                  )}
                >
                  <span
                    className={cn(
                      "flex size-5 shrink-0 items-center justify-center rounded-full",
                      state === "current" && "bg-signal text-white",
                      state === "done" && "bg-signal text-white",
                      state === "upcoming" && "bg-panel text-paper-dim",
                    )}
                  >
                    {state === "done" ? <IconCheck width={12} height={12} /> : <StepIcon width={12} height={12} />}
                  </span>
                  <span className="hidden sm:inline">{t(`adv.wizard.${s}`)}</span>
                </div>
                {i < STEPS.length - 1 && (
                  <div className={cn("h-px flex-1", i < step ? "bg-signal" : "bg-seam")} />
                )}
              </li>
            );
          })}
        </ol>

        <Panel>
          {step === 0 && (
            <div className="space-y-3">
              <SectionTitle>{t("adv.wizard.step1")}</SectionTitle>
              {[
                { v: "channel" as const, icon: IconChannel, title: t("adv.wizard.formatChannel"), d: t("adv.wizard.formatChannelDesc") },
                { v: "interstitial" as const, icon: IconApp, title: `${t("adv.wizard.formatMini")} — ${t("adv.wizard.subInterstitial")}`, d: t("adv.wizard.formatMiniDesc") },
                { v: "pop" as const, icon: IconApp, title: `${t("adv.wizard.formatMini")} — ${t("adv.wizard.subPop")}`, d: t("adv.wizard.formatMiniDesc") },
              ].map((o) => (
                <button
                  key={o.v}
                  onClick={() => setFormat(o.v)}
                  aria-pressed={format === o.v}
                  className={cn(
                    "flex w-full items-start gap-3 rounded-xl border p-4 text-left transition-colors",
                    format === o.v ? "border-signal bg-signal-soft" : "border-seam hover:bg-panel-2",
                  )}
                >
                  <span
                    className={cn(
                      "flex size-9 shrink-0 items-center justify-center rounded-lg",
                      format === o.v ? "bg-signal text-white" : "bg-panel-2 text-paper-dim",
                    )}
                  >
                    <o.icon width={18} height={18} />
                  </span>
                  <span>
                    <p className="font-bold">{o.title}</p>
                    <p className="mt-1 text-sm text-paper-dim">{o.d}</p>
                  </span>
                </button>
              ))}
            </div>
          )}

          {step === 1 && (
            <div className="grid gap-6 lg:grid-cols-[1fr_18rem]">
            <div className="space-y-5">
              <SectionTitle sub={t("adv.wizard.copyHint")}>{t("adv.wizard.step2")}</SectionTitle>

              <Quote tone="signal" label={t("adv.wizard.step2")}>{t("adv.wizard.creativeQuote")}</Quote>

              <div>
                <p className="text-sm font-semibold">{t("adv.wizard.image")}</p>
                <div className="mt-2">
                  <ImageUpload value={image} onChange={setImage} />
                </div>
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <label className="text-sm font-semibold" htmlFor="bannerTitle">{t("adv.wizard.bannerTitle")}</label>
                  <input
                    id="bannerTitle"
                    value={bannerTitle}
                    onChange={(e) => setBannerTitle(e.target.value)}
                    maxLength={56}
                    className="mt-2 w-full rounded-xl border border-seam bg-transparent p-3 text-sm"
                  />
                  <FieldError>{errors["bannerTitle"]}</FieldError>
                </div>
                <div>
                  <label className="flex items-center gap-1.5 text-sm font-semibold" htmlFor="brandName">
                    <IconTag width={14} height={14} className="text-paper-dim" />
                    {t("adv.wizard.brandName")}
                  </label>
                  <input
                    id="brandName"
                    value={brandName}
                    onChange={(e) => setBrandName(e.target.value)}
                    maxLength={40}
                    className="mt-2 w-full rounded-xl border border-seam bg-transparent p-3 text-sm"
                  />
                </div>
              </div>

              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <label className="text-sm font-semibold" htmlFor="copy">{t("adv.wizard.copy")}</label>
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
                    className="mt-2 w-full rounded-xl border border-seam bg-transparent p-3 text-sm"
                  />
                )}
                <HtmlFormatToolbar textareaRef={copyTextareaRef} value={copy} onChange={handleCopyChange} />
                <AutoTextarea
                  ref={copyTextareaRef}
                  id="copy"
                  minRows={4}
                  value={copy}
                  onChange={handleCopyChange}
                  onBlur={handleCopyBlur}
                  maxLength={AD_TEXT_MAX_LENGTH}
                  invalid={!!errors["copy"]}
                  className="mt-1.5"
                />
                <div className="mt-1.5 flex items-start justify-between gap-2">
                  <FieldError>{errors["copy"]}</FieldError>
                  <span
                    className={cn(
                      "shrink-0 text-xs tabular-nums",
                      copy.length > AD_TEXT_MAX_LENGTH * 0.9 ? "text-danger font-semibold" : "text-paper-dim",
                    )}
                  >
                    {copy.length}/{AD_TEXT_MAX_LENGTH}
                  </span>
                </div>
              </div>

              <div>
                <p className="text-sm font-semibold">{t("adv.wizard.buttonLabel")}</p>
                <div className="mt-2 flex flex-wrap gap-2">
                  {BUTTON_LABELS.map((b) => (
                    <button
                      key={b}
                      onClick={() => setLabel(b)}
                      aria-pressed={label === b}
                      className={cn(
                        "rounded-lg border px-3 py-1.5 text-xs font-semibold transition-colors",
                        label === b ? "border-signal bg-signal-soft text-signal" : "border-seam text-paper-dim hover:text-paper",
                      )}
                    >
                      {b}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="text-sm font-semibold" htmlFor="url">{t("adv.wizard.destination")}</label>
                <input
                  id="url"
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  placeholder="https://"
                  className="mt-2 w-full rounded-xl border border-seam bg-transparent p-3 text-sm"
                />
                <FieldError>{errors["url"]}</FieldError>
              </div>
            </div>
            <div className="hidden lg:block">
              <p className="mb-2 text-xs font-semibold text-paper-dim">{t("adv.wizard.preview")}</p>
              <div className="sticky top-4">
                <TelegramPostPreview
                  title={bannerTitle}
                  brandName={brandName}
                  copy={copy || "…"}
                  buttonLabel={label}
                  imageUrl={image?.url ?? null}
                  imageAlt={image?.name}
                />
              </div>
            </div>
            </div>
          )}

          {step === 2 && (
            <div>
              <SectionTitle>{t("adv.wizard.step3")}</SectionTitle>
              <Quote tone="neutral" className="mb-4" label={t("adv.wizard.targetLanguage")}>{t("adv.quotes.privacy")}</Quote>
              <label className="text-sm font-semibold" htmlFor="lang">{t("adv.wizard.targetLanguage")}</label>
              <select
                id="lang"
                value={lang}
                onChange={(e) => setLang(e.target.value)}
                className="mt-2 w-full rounded-xl border border-seam bg-transparent p-3 text-sm"
              >
                {AD_LANGUAGES.map((l) => (
                  <option key={l.code} value={l.code}>
                    {l.label}
                    {l.code === "all" ? ` — ${t("adv.wizard.recommended")}` : ""}
                  </option>
                ))}
              </select>
            </div>
          )}

          {step === 3 && (
            <div className="space-y-5">
              <SectionTitle>{t("adv.wizard.step4")}</SectionTitle>
              <Quote tone={budgetTooLow ? "danger" : "bounty"} label={t("adv.wizard.totalBudget")}>
                {t("adv.wizard.budgetQuote")}
              </Quote>
              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <label className="text-sm font-semibold" htmlFor="budget">{t("adv.wizard.totalBudget")}</label>
                  <input
                    id="budget"
                    inputMode="decimal"
                    value={budget}
                    onChange={(e) => setBudget(e.target.value)}
                    placeholder="10.00"
                    aria-invalid={budgetTooLow}
                    className={`num mt-2 ${inputCls(budgetTooLow)}`}
                  />
                  {budget !== "" && (
                    <p className={budgetTooLow ? "mt-1.5 text-xs font-semibold text-danger" : "mt-1.5 text-xs font-semibold text-bounty"}>
                      {budgetTooLow ? t("adv.wizard.budgetTooLow") : t("adv.wizard.budgetOk")}
                    </p>
                  )}
                  <FieldError>{errors["budget"]}</FieldError>
                </div>
                <div>
                  <label className="text-sm font-semibold" htmlFor="daily">{t("adv.wizard.dailyBudget")}</label>
                  <input id="daily" inputMode="decimal" value={daily} onChange={(e) => setDaily(e.target.value)} className="num mt-2 w-full rounded-xl border border-seam bg-transparent p-3 text-sm" />
                </div>
              </div>
              <div>
                <label className="text-sm font-semibold" htmlFor="cpm">{t("adv.wizard.cpm")}</label>
                <input id="cpm" inputMode="decimal" value={cpm} onChange={(e) => setCpm(e.target.value)} placeholder="1.70" className="num mt-2 w-full rounded-xl border border-seam bg-transparent p-3 text-sm" />
                <p className="mt-1 text-xs text-paper-dim">{t("adv.wizard.cpmHint")}</p>
                <FieldError>{errors["cpm"]}</FieldError>
                {cpm && (
                  <p className="mt-3 text-xs text-paper-dim">
                    {t("adv.wizard.competitiveness")}:{" "}
                    <span className="font-bold text-paper">{t(`adv.wizard.${competitiveness}`)}</span>
                  </p>
                )}
              </div>
              <div>
                <label className="text-sm font-semibold" htmlFor="cpc">{t("adv.wizard.cpc")}</label>
                <input id="cpc" inputMode="decimal" value={cpc} onChange={(e) => setCpc(e.target.value)} placeholder="0.030" className="num mt-2 w-full rounded-xl border border-seam bg-transparent p-3 text-sm" />
                <p className="mt-1 text-xs text-paper-dim">{t("adv.wizard.cpcHint")}</p>
                <FieldError>{errors["cpc"]}</FieldError>
              </div>
            </div>
          )}

          {step === 4 && (
            <div className="space-y-5">
              <SectionTitle sub={t("adv.wizard.previewTitle")}>{t("adv.wizard.step5")}</SectionTitle>
              <TelegramPostPreview title={bannerTitle} brandName={brandName} copy={copy} buttonLabel={label} imageUrl={image?.url ?? null} imageAlt={image?.name} />
              <Quote tone="signal" label={t("adv.wizard.step5")}>{t("adv.quotes.review")}</Quote>
              <dl className="grid gap-3 border-t border-seam pt-4 text-sm sm:grid-cols-2">
                {[
                  [t("admin.detail.format"), format],
                  [t("adv.wizard.targetLanguage"), AD_LANGUAGES.find((l) => l.code === lang)?.label ?? ""],
                  [t("adv.wizard.totalBudget"), fmtMoney(Number(budget || 0))],
                  [t("adv.wizard.cpm"), fmtMoney(Number(cpm || 0))],
                  [t("admin.detail.destinationUrl"), url],
                ].map(([k, v]) => (
                  <div key={k}>
                    <dt className="text-xs font-semibold text-paper-dim">{k}</dt>
                    <dd className="num mt-0.5 break-all font-semibold">{v}</dd>
                  </div>
                ))}
              </dl>
              {submitError && <FieldError>{submitError}</FieldError>}
            </div>
          )}

          <div className="mt-6 flex items-center gap-3 border-t border-seam pt-5">
            {step > 0 && (
              <Btn variant="secondary" onClick={() => setStep((s) => s - 1)}>
                {t("common.back")}
              </Btn>
            )}
            {step < STEPS.length - 1 ? (
              <Btn className="ml-auto" onClick={next}>
                {t("common.continue")}
              </Btn>
            ) : (
              <Btn className="ml-auto" onClick={submit} disabled={createCampaign.isPending}>
                {t("adv.wizard.submitReview")}
              </Btn>
            )}
          </div>
        </Panel>

        <p className="text-center text-xs text-paper-dim">
          <Link to="/traffic/campaigns" className="underline">{t("adv.nav.campaigns")}</Link>
        </p>
      </div>
    </AdvShell>
  );
}