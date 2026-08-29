import { createFileRoute, Link } from "@tanstack/react-router";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { PubShell } from "@/components/workspaces";
import {
  Btn,
  ErrorBanner,
  Field,
  FieldError,
  Modal,
  Panel,
  Quote,
  RowSkeleton,
  StatusPill,
  fmtMoney,
  inputCls,
} from "@/components/kit";
import { Avatar } from "@/components/cards";
import { IconCheck, IconCopy, IconSparkle } from "@/components/icons";
import { ArtMiniAppPlacement } from "@/components/illustrations";
import { ApiError, num } from "@/lib/api";
import {
  useArchiveMiniApp,
  useCreateMiniApp,
  useMiniAppKey,
  useMiniApps,
  useResumeMiniApp,
  useSuspendMiniApp,
} from "@/lib/queries";
import type { MiniApp } from "@/lib/types";
import { useAuthGuard } from "@/lib/auth";

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

function KeyPanel({ app }: { app: MiniApp }) {
  const { t } = useTranslation();
  const { data, isLoading, isError, refetch } = useMiniAppKey(app.id);
  const [copied, setCopied] = useState<"key" | "snippet" | null>(null);
  const suspendApp = useSuspendMiniApp();
  const resumeApp = useResumeMiniApp();
  const archiveApp = useArchiveMiniApp();
  const [confirmArchive, setConfirmArchive] = useState(false);

  const copy = async (text: string, which: "key" | "snippet") => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(which);
      setTimeout(() => setCopied(null), 1500);
    } catch {
      /* clipboard unavailable */
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <StatusPill status={app.status} />
        {app.botVerificationEnabled && (
          <span className="inline-flex items-center gap-1.5 rounded-full border border-seam bg-success-soft px-2.5 py-1 text-[11px] font-semibold text-success">
            <IconCheck width={11} height={11} /> {t("pub.form.miniBotToken")}
          </span>
        )}
      </div>

      {(app.botId || app.botUsername || app.originalUrl) && (
        <div className="grid gap-2 text-xs text-paper-dim sm:grid-cols-2">
          {app.originalUrl && <p><span className="font-semibold text-paper">{t("pub.form.miniOriginalUrl")}:</span> {app.originalUrl}</p>}
          {app.botUsername && <p><span className="font-semibold text-paper">{t("pub.form.miniBotUsername")}:</span> {app.botUsername}</p>}
          {app.botId && <p><span className="font-semibold text-paper">{t("pub.form.miniBotId")}:</span> {app.botId}</p>}
        </div>
      )}

      {app.status === "suspended" && <Quote tone="neutral">{t("pub.detail.suspended")}</Quote>}
      {app.status === "archived" && <Quote tone="neutral">{t("pub.detail.archived")}</Quote>}

      {isLoading ? (
        <div className="h-24 animate-pulse rounded-xl bg-panel-2" />
      ) : isError || !data ? (
        <ErrorBanner onRetry={() => void refetch()} />
      ) : (
        <>
          <Field label="Kinz-ID key" htmlFor="mkkey">
            <div className="flex gap-2">
              <input id="mkkey" readOnly value={data.kinzKey} className={`num ${inputCls()}`} />
              <Btn variant="secondary" className="shrink-0" onClick={() => copy(data.kinzKey, "key")}>
                {copied === "key" ? <IconCheck width={14} height={14} /> : <IconCopy width={14} height={14} />}
              </Btn>
            </div>
          </Field>
          <Field label="Integration snippet" htmlFor="mksnip">
            <div className="flex items-start gap-2">
              <textarea
                id="mksnip"
                readOnly
                value={data.snippet}
                rows={4}
                className={`num ${inputCls()} resize-none font-mono text-xs`}
              />
              <Btn variant="secondary" className="shrink-0" onClick={() => copy(data.snippet, "snippet")}>
                {copied === "snippet" ? <IconCheck width={14} height={14} /> : <IconCopy width={14} height={14} />}
              </Btn>
            </div>
          </Field>
          <Link to="/docs/quickstart" className="text-xs font-semibold text-signal hover:underline">
            {t_docs()}
          </Link>
        </>
      )}

      <div className="flex flex-wrap items-center gap-2 border-t border-seam pt-4">
        {app.status !== "archived" && (
          <>
            {app.status === "suspended" ? (
              <Btn variant="secondary" onClick={() => resumeApp.mutate(app.id)} disabled={resumeApp.isPending}>
                {resumeApp.isPending ? "…" : t("pub.detail.resume")}
              </Btn>
            ) : (
              <Btn variant="secondary" onClick={() => suspendApp.mutate(app.id)} disabled={suspendApp.isPending}>
                {suspendApp.isPending ? "…" : t("pub.detail.suspend")}
              </Btn>
            )}
            {!confirmArchive ? (
              <Btn variant="ghost" className="text-danger" onClick={() => setConfirmArchive(true)}>
                {t("pub.detail.archive")}
              </Btn>
            ) : (
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-xs text-paper-dim">{t("pub.detail.archiveConfirmApp")}</span>
                <Btn
                  variant="secondary"
                  className="text-danger"
                  onClick={() => archiveApp.mutate(app.id)}
                  disabled={archiveApp.isPending}
                >
                  {archiveApp.isPending ? "…" : t("pub.detail.archive")}
                </Btn>
                <Btn variant="ghost" onClick={() => setConfirmArchive(false)}>{t("common.cancel")}</Btn>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

function t_docs() {
  useAuthGuard("publisher");
  return "Read the Kinz-ID quickstart docs →";
}

function MiniAppCard({ app, onOpen }: { app: MiniApp; onOpen: () => void }) {
  const { t } = useTranslation();
  return (
    <Panel className="space-y-3">
      <div className="flex flex-wrap items-center gap-3">
        <Avatar name={app.name} size={44} />
        <div className="min-w-0 flex-1">
          <p className="truncate font-display text-base font-bold">{app.name}</p>
          <p className="num truncate text-xs text-paper-dim">{app.url}</p>
        </div>
        <StatusPill status={app.status} />
      </div>
      <p className="text-xs text-paper-dim">{t("pub.detail.formats")}: {app.formats.join(", ") || "—"}</p>
      {app.status === "rejected" && app.rejectionReason && (
        <Quote tone="danger" label={t("status.rejected")}>{app.rejectionReason}</Quote>
      )}
      {!app.integrationDetected && app.status !== "rejected" && (
        <Quote tone="neutral">{t("pub.detail.integrationMissing")}</Quote>
      )}
      <div className="flex items-center justify-between">
        <p className="num text-sm font-bold text-success">{fmtMoney(num(app.earnings))}</p>
        <button onClick={onOpen} className="text-xs font-semibold text-signal hover:underline">
          {t("pub.form.kinzKey")}
        </button>
      </div>
    </Panel>
  );
}

function MiniAppsPage() {
  const { t } = useTranslation();
  const { data: miniApps, isLoading, isError, refetch } = useMiniApps();
  const createMiniApp = useCreateMiniApp();

  const [open, setOpen] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [originalUrl, setOriginalUrl] = useState("");
  const [botUsername, setBotUsername] = useState("");
  const [botId, setBotId] = useState("");
  const [botToken, setBotToken] = useState("");
  const [formats, setFormats] = useState<string[]>(["interstitial", "popInterstitial"]);
  const [err, setErr] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string | null>(null);

  const toggleFormat = (f: string) =>
    setFormats((cur) => (cur.includes(f) ? cur.filter((x) => x !== f) : [...cur, f]));

  const resetForm = () => {
    setName("");
    setUrl("");
    setOriginalUrl("");
    setBotUsername("");
    setBotId("");
    setBotToken("");
    setFormats(["interstitial", "popInterstitial"]);
    setErr({});
    setFormError(null);
  };

  const submit = () => {
    const e: Record<string, string> = {};
    if (name.trim().length < 3) e["name"] = t("pub.form.errName");
    if (!/^https:\/\/t\.me\/[A-Za-z0-9_]+\/[A-Za-z0-9_-]+/.test(url)) e["url"] = t("pub.form.errDirect");
    if (formats.length === 0) e["formats"] = "Select at least one format.";
    setErr(e);
    if (Object.keys(e).length) return;

    setFormError(null);
    createMiniApp.mutate(
      {
        name: name.trim(),
        url: url.trim(),
        originalUrl: originalUrl.trim() || null,
        botUsername: botUsername.trim() || null,
        botId: botId.trim() || null,
        botToken: botToken.trim() || null,
        formats,
      },
      {
        onSuccess: () => {
          setOpen(false);
          resetForm();
        },
        onError: (err) => setFormError(err instanceof ApiError ? err.message : "Something went wrong."),
      },
    );
  };

  const selectedApp = miniApps?.find((m) => m.id === selected) ?? null;

  return (
    <PubShell title={t("pub.nav.miniapps")} action={<Btn tone="bounty" onClick={() => setOpen(true)}><IconSparkle width={16} height={16} />{t("pub.addMiniApp")}</Btn>}>
      <div className="space-y-5">
        <Quote tone="signal" label={t("pub.nav.miniapps")}>{t("pub.quotes.sdk")}</Quote>

        {isError ? (
          <ErrorBanner onRetry={() => void refetch()} />
        ) : isLoading ? (
          <Panel className="p-0"><RowSkeleton rows={3} /></Panel>
        ) : !miniApps || miniApps.length === 0 ? (
          <Panel className="p-0">
            <div className="flex flex-col items-center px-6 py-10 text-center">
              <ArtMiniAppPlacement className="max-w-[260px]" />
              <h3 className="mt-4 font-display text-lg font-bold">{t("pub.miniEmptyTitle")}</h3>
              <p className="mt-1.5 max-w-sm text-sm text-paper-dim">{t("pub.miniEmptySub")}</p>
              <div className="mt-5">
                <Btn tone="bounty" onClick={() => setOpen(true)}>{t("pub.addMiniApp")}</Btn>
              </div>
            </div>
          </Panel>
        ) : (
          <div className="grid gap-4 sm:grid-cols-1 lg:grid-cols-2">
            {miniApps.map((m) => (
              <MiniAppCard key={m.id} app={m} onOpen={() => setSelected(m.id)} />
            ))}
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
            <Btn tone="bounty" onClick={submit} disabled={createMiniApp.isPending}>
              {createMiniApp.isPending ? "…" : t("common.submit")}
            </Btn>
            <Btn variant="secondary" onClick={() => setOpen(false)}>{t("common.cancel")}</Btn>
          </>
        }
      >
        <div className="space-y-4">
          {formError && <FieldError>{formError}</FieldError>}
          <Field label={t("pub.form.miniName")} error={err["name"]} htmlFor="mn">
            <input id="mn" value={name} onChange={(e) => setName(e.target.value)} className={inputCls(!!err["name"])} />
          </Field>
          <Field label={t("pub.form.miniDirect")} hint={t("pub.form.miniDirectHint")} error={err["url"]} htmlFor="mu">
            <input id="mu" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://t.me/MyTgBot/app" className={`num ${inputCls(!!err["url"])}`} />
          </Field>
          <Field label={t("pub.form.miniOriginalUrl")} hint={t("pub.form.miniOriginalUrlHint")} htmlFor="mou">
            <input id="mou" value={originalUrl} onChange={(e) => setOriginalUrl(e.target.value)} placeholder="https://myminiapp.com" className={inputCls()} />
          </Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t("pub.form.miniBotUsername")} htmlFor="mbu">
              <input id="mbu" value={botUsername} onChange={(e) => setBotUsername(e.target.value)} placeholder="@MyTgBot" className={inputCls()} />
            </Field>
            <Field label={t("pub.form.miniBotId")} htmlFor="mbi">
              <input id="mbi" value={botId} onChange={(e) => setBotId(e.target.value)} className={`num ${inputCls()}`} />
            </Field>
          </div>
          <Field label={t("pub.form.miniBotToken")} hint={t("pub.form.miniBotTokenHint")} htmlFor="mbt">
            <input id="mbt" type="password" value={botToken} onChange={(e) => setBotToken(e.target.value)} className={inputCls()} />
          </Field>
          <div>
            <p className="text-sm font-semibold">{t("pub.form.miniFormats")}</p>
            <div className="mt-2 flex flex-wrap gap-4">
              <label className="flex items-center gap-2 text-sm font-semibold">
                <input
                  type="checkbox"
                  checked={formats.includes("interstitial")}
                  onChange={() => toggleFormat("interstitial")}
                  className="size-4 accent-[var(--bounty)]"
                />
                {t("adv.wizard.subInterstitial")}
              </label>
              <label className="flex items-center gap-2 text-sm font-semibold">
                <input
                  type="checkbox"
                  checked={formats.includes("popInterstitial")}
                  onChange={() => toggleFormat("popInterstitial")}
                  className="size-4 accent-[var(--bounty)]"
                />
                {t("adv.wizard.subPop")}
              </label>
            </div>
            <FieldError>{err["formats"]}</FieldError>
          </div>
          <Quote tone="neutral" label={t("pub.form.docsLink")}>{t("pub.quotes.sdk")}</Quote>
          <Link to="/docs/quickstart" className="inline-block text-xs font-semibold text-signal hover:underline">
            {t_docs()}
          </Link>
        </div>
      </Modal>

      <Modal
        open={!!selectedApp}
        onClose={() => setSelected(null)}
        title={selectedApp?.name ?? ""}
        sub="Kinz-ID key and integration snippet for this Mini App."
      >
        {selectedApp && <KeyPanel app={selectedApp} />}
      </Modal>
    </PubShell>
  );
}
