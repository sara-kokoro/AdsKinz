import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { AdvShell } from "@/components/workspaces";
import { Btn, FieldError, ImageUpload, Panel, Quote, SectionTitle, fmtMoney, inputCls } from "@/components/kit";
import { TelegramPostPreview } from "@/components/telegram-preview";
import { IconCheck, IconSparkle } from "@/components/icons";
import { AD_LANGUAGES, BUTTON_LABELS } from "@/lib/constants";
import { ApiError } from "@/lib/api";
import { useCreateCampaign, useGenerateCopy } from "@/lib/queries";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/traffic/campaigns/new")({
  head: () => ({
    meta: [
      { title: "New campaign — AdsKinz traffic" },
      { name: "description", content: "Create a native Telegram campaign: format, creative, targeting, budget and review." },
      { property: "og:title", content: "New campaign — AdsKinz traffic" },
      { property: "og:description", content: "Launch a native Telegram campaign from $50." },
    ],
  }),
  component: Wizard,
});

const STEPS = ["step1", "step2", "step3", "step4", "step5"] as const;

function Wizard() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [step, setStep] = useState(0);

  const [format, setFormat] = useState<"channel" | "interstitial" | "pop">("channel");
  const [image, setImage] = useState<{ url: string; name: string } | null>(null);
  const [copy, setCopy] = useState("");
  const [brief, setBrief] = useState("");
  const [briefOpen, setBriefOpen] = useState(false);
  const [label, setLabel] = useState("Learn more");
  const [url, setUrl] = useState("");
  const [lang, setLang] = useState("all");
  const [budget, setBudget] = useState("");
  const [daily, setDaily] = useState("");
  const [cpm, setCpm] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [submitError, setSubmitError] = useState<string | null>(null);

  const generateCopy = useGenerateCopy();
  const createCampaign = useCreateCampaign();

  const generate = () => {
    generateCopy.mutate(
      { brief: brief || format, language: lang === "all" ? "en" : lang, tone: "confident" },
      {
        onSuccess: (res) => setCopy(res.copy),
        onError: (err) => setErrors((e) => ({ ...e, copy: err instanceof ApiError ? err.message : t("common.loadError") })),
      },
    );
  };

  const validate = () => {
    const e: Record<string, string> = {};
    if (step === 1) {
      if (!copy.trim()) e["copy"] = t("adv.wizard.errCopy");
      if (!/^https:\/\/.+\..+/.test(url)) e["url"] = t("adv.wizard.errUrl");
    }
    if (step === 3) {
      if (Number(budget) < 50 || !budget) e["budget"] = t("adv.wizard.errMinBudget");
      if (Number(cpm) < 2 || !cpm) e["cpm"] = t("adv.wizard.errMinCpm");
    }
    setErrors(e);
    return Object.keys(e).length === 0;
  };

  const next = () => {
    if (!validate()) return;
    setStep((s) => Math.min(STEPS.length - 1, s + 1));
  };

  const budgetTooLow = budget !== "" && Number(budget) < 50;

  const competitiveness =
    Number(cpm) >= 4.5 ? "compHigh" : Number(cpm) >= 2.8 ? "compMid" : "compLow";

  const submit = () => {
    setSubmitError(null);
    createCampaign.mutate(
      {
        name: `${format} campaign — ${new Date().toISOString().slice(0, 10)}`,
        format,
        copy,
        button_label: label,
        destinationUrl: url,
        language: lang,
        budget: Number(budget),
        dailyBudget: daily ? Number(daily) : null,
        cpm: Number(cpm),
        imageUrl: image?.url ?? null,
        ai_generated: generateCopy.isSuccess,
      },
      {
        onSuccess: (campaign) => {
          void navigate({ to: "/traffic/campaigns/$id", params: { id: campaign.id } });
        },
        onError: (err) => setSubmitError(err instanceof ApiError ? err.message : t("common.loadError")),
      },
    );
  };

  return (
    <AdvShell title={t("adv.wizard.title")}>
      <div className="mx-auto max-w-3xl space-y-5">
        <ol className="flex flex-wrap gap-2">
          {STEPS.map((s, i) => (
            <li
              key={s}
              className={cn(
                "num rounded-lg border border-seam px-3 py-1.5 text-xs font-semibold",
                i === step ? "bg-signal-soft text-signal" : i < step ? "text-paper" : "text-paper-dim",
              )}
            >
              {i + 1}. {t(`adv.wizard.${s}`)}
            </li>
          ))}
        </ol>

        <Panel>
          {step === 0 && (
            <div className="space-y-3">
              <SectionTitle>{t("adv.wizard.step1")}</SectionTitle>
              {[
                { v: "channel" as const, title: t("adv.wizard.formatChannel"), d: t("adv.wizard.formatChannelDesc") },
                { v: "interstitial" as const, title: `${t("adv.wizard.formatMini")} — ${t("adv.wizard.subInterstitial")}`, d: t("adv.wizard.formatMiniDesc") },
                { v: "pop" as const, title: `${t("adv.wizard.formatMini")} — ${t("adv.wizard.subPop")}`, d: t("adv.wizard.formatMiniDesc") },
              ].map((o) => (
                <button
                  key={o.v}
                  onClick={() => setFormat(o.v)}
                  aria-pressed={format === o.v}
                  className={cn(
                    "block w-full rounded-xl border p-4 text-left transition-colors",
                    format === o.v ? "border-signal bg-signal-soft" : "border-seam hover:bg-panel-2",
                  )}
                >
                  <p className="font-bold">{o.title}</p>
                  <p className="mt-1 text-sm text-paper-dim">{o.d}</p>
                </button>
              ))}
            </div>
          )}

          {step === 1 && (
            <div className="space-y-5">
              <SectionTitle sub={t("adv.wizard.copyHint")}>{t("adv.wizard.step2")}</SectionTitle>

              <Quote tone="signal" label={t("adv.wizard.step2")}>{t("adv.wizard.creativeQuote")}</Quote>

              <div>
                <p className="text-sm font-semibold">{t("adv.wizard.image")}</p>
                <div className="mt-2">
                  <ImageUpload value={image} onChange={setImage} />
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
                <textarea
                  id="copy"
                  rows={4}
                  value={copy}
                  onChange={(e) => setCopy(e.target.value)}
                  className="mt-2 w-full rounded-xl border border-seam bg-transparent p-3 text-sm"
                />
                <FieldError>{errors["copy"]}</FieldError>
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
                    placeholder="50.00"
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
                <input id="cpm" inputMode="decimal" value={cpm} onChange={(e) => setCpm(e.target.value)} placeholder="2.00" className="num mt-2 w-full rounded-xl border border-seam bg-transparent p-3 text-sm" />
                <p className="mt-1 text-xs text-paper-dim">{t("adv.wizard.cpmHint")}</p>
                <FieldError>{errors["cpm"]}</FieldError>
                {cpm && (
                  <p className="mt-3 text-xs text-paper-dim">
                    {t("adv.wizard.competitiveness")}:{" "}
                    <span className="font-bold text-paper">{t(`adv.wizard.${competitiveness}`)}</span>
                  </p>
                )}
              </div>
            </div>
          )}

          {step === 4 && (
            <div className="space-y-5">
              <SectionTitle sub={t("adv.wizard.previewTitle")}>{t("adv.wizard.step5")}</SectionTitle>
              <TelegramPostPreview copy={copy} buttonLabel={label} imageUrl={image?.url ?? null} imageAlt={image?.name} />
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
