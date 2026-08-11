import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { PubShell } from "@/components/workspaces";
import {
  Btn,
  EmptyState,
  Field,
  Modal,
  Panel,
  Quote,
  RowSkeleton,
  StatusPill,
  fmtInt,
  fmtMoney,
  inputCls,
  useFakeLoad,
} from "@/components/kit";
import { PlacementDetail } from "@/components/placement-detail";
import { PlacementCard } from "@/components/cards";
import { IconApp, IconSparkle } from "@/components/icons";
import { miniApps, statsFor } from "@/lib/mock-data";

export const Route = createFileRoute("/partner/mini-apps")({
  head: () => ({
    meta: [
      { title: "Mini Apps — AdsKinz partner" },
      { name: "description", content: "Connect a Telegram Mini App, enable interstitial formats and follow impressions and clicks per app." },
      { property: "og:title", content: "Mini Apps — AdsKinz partner" },
      { property: "og:description", content: "No subscriber threshold — integrate the Kinz-ID SDK and start earning." },
    ],
  }),
  component: MiniAppsPage,
});

function MiniAppsPage() {
  const { t } = useTranslation();
  const { loading } = useFakeLoad();
  const [open, setOpen] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [origin, setOrigin] = useState("");
  const [botId, setBotId] = useState("");
  const [err, setErr] = useState<Record<string, string>>({});

  const submit = () => {
    const e: Record<string, string> = {};
    if (name.trim().length < 3) e["name"] = t("pub.form.errName");
    if (!/^https:\/\/t\.me\/[A-Za-z0-9_]+\/[A-Za-z0-9_-]+/.test(url)) e["url"] = t("pub.form.errDirect");
    if (!/^https:\/\/[^\s]+\.[^\s]+/.test(origin)) e["origin"] = t("pub.form.errOrigin");
    if (!/^(@[A-Za-z0-9_]{4,}|\d{6,})$/.test(botId.trim())) e["botId"] = t("pub.form.errBotId");
    setErr(e);
    if (!Object.keys(e).length) {
      setOpen(false);
      setName("");
      setUrl("");
      setOrigin("");
      setBotId("");
    }
  };

  const app = miniApps.find((m) => m.id === selected);
  const stats = selected ? statsFor(selected) : undefined;

  if (app && stats) {
    return (
      <PubShell title={t("pub.detail.appTitle")}>
        <PlacementDetail
          title={app.name}
          backLabel={t("pub.detail.backApps")}
          onBack={() => setSelected(null)}
          status={app.status}
          subtitle={app.url}
          stats={stats}
          actions={
            <>
              <Btn variant="secondary" className="min-h-10 px-3 text-xs">{t("pub.detail.regenerateKey")}</Btn>
              <Btn variant="secondary" className="min-h-10 px-3 text-xs">{t("pub.detail.pause")}</Btn>
            </>
          }
          configuration={[
            { label: t("pub.detail.id"), value: app.id },
            { label: t("pub.detail.connectedOn"), value: stats.connectedOn },
            { label: t("pub.form.miniUrl"), value: app.url },
            { label: t("pub.detail.formats"), value: app.formats.join(", ") },
            { label: t("pub.form.kinzKey"), value: app.kinzKey },
            {
              label: t("pub.detail.integration"),
              value: app.status === "active" ? t("pub.detail.integrationOk") : t("pub.detail.integrationMissing"),
            },
            { label: t("pub.detail.lastAd"), value: stats.lastAd },
          ]}
        />
      </PubShell>
    );
  }

  return (
    <PubShell title={t("pub.nav.miniapps")} action={<Btn tone="bounty" onClick={() => setOpen(true)}><IconSparkle width={16} height={16} />{t("pub.addMiniApp")}</Btn>}>
      <div className="space-y-5">
        <Quote tone="signal" label={t("pub.nav.miniapps")} >{t("pub.quotes.sdk")}</Quote>

        {loading ? (
          <Panel className="p-0"><RowSkeleton rows={3} /></Panel>
        ) : miniApps.length === 0 ? (
          <Panel className="p-0">
            <EmptyState title={t("pub.miniEmptyTitle")} sub={t("pub.miniEmptySub")} action={<Btn tone="bounty" onClick={() => setOpen(true)}>{t("pub.addMiniApp")}</Btn>} />
          </Panel>
        ) : (
          <div className="grid gap-4 lg:grid-cols-2">
            {miniApps.map((m) => {
              const s = statsFor(m.id);
              return (
                <PlacementCard
                  key={m.id}
                  name={m.name}
                  handle={m.url}
                  status={m.status}
                  people={s?.impressions30 ?? 0}
                  peopleLabel={t("pub.impressions30")}
                  earnings={m.earnings30}
                  onOpen={() => setSelected(m.id)}
                />
              );
            })}
          </div>
        )}
      </div>

      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title={t("pub.addMiniApp")}
        sub={t("pub.addMiniAppSub")}
        footer={
          <>
            <Btn tone="bounty" onClick={submit}>{t("common.submit")}</Btn>
            <Btn variant="secondary" onClick={() => setOpen(false)}>{t("common.cancel")}</Btn>
          </>
        }
      >
        <div className="space-y-4">
          <Field label={t("pub.form.miniName")} error={err["name"]} htmlFor="mn">
            <input id="mn" value={name} onChange={(e) => setName(e.target.value)} className={inputCls(!!err["name"])} />
          </Field>
          <Field label={t("pub.form.miniDirect")} hint={t("pub.form.miniDirectHint")} error={err["url"]} htmlFor="mu">
            <input id="mu" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://t.me/MyTgBot/app" className={`num ${inputCls(!!err["url"])}`} />
          </Field>
          <Field label={t("pub.form.miniOrigin")} hint={t("pub.form.miniOriginHint")} error={err["origin"]} htmlFor="mo">
            <input id="mo" value={origin} onChange={(e) => setOrigin(e.target.value)} placeholder="https://myapp.com" className={`num ${inputCls(!!err["origin"])}`} />
          </Field>
          <Field label={t("pub.form.miniBotId")} hint={t("pub.form.miniBotIdHint")} error={err["botId"]} htmlFor="mb">
            <input id="mb" value={botId} onChange={(e) => setBotId(e.target.value)} placeholder="@MyTgBot" className={`num ${inputCls(!!err["botId"])}`} />
          </Field>
          <div>
            <p className="text-sm font-semibold">{t("pub.form.miniFormats")}</p>
            <div className="mt-2 flex flex-wrap gap-4">
              {["interstitial", "pop"].map((f) => (
                <label key={f} className="flex items-center gap-2 text-sm font-semibold">
                  <input type="checkbox" defaultChecked className="size-4 accent-[var(--bounty)]" />
                  {t(`adv.wizard.${f === "pop" ? "subPop" : "subInterstitial"}`)}
                </label>
              ))}
            </div>
          </div>
          <Field label={t("pub.form.kinzKey")} htmlFor="mk">
            <div className="flex gap-2">
              <input id="mk" readOnly value="kinz_test_new_key" className={`num ${inputCls()}`} />
              <Btn variant="secondary" className="shrink-0">{t("pub.form.kinzGenerate")}</Btn>
            </div>
          </Field>
          <Quote tone="neutral" label={t("pub.form.docsLink")}>{t("pub.quotes.sdk")}</Quote>
        </div>
      </Modal>
    </PubShell>
  );
}
