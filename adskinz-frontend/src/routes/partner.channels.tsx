import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { PubShell } from "@/components/workspaces";
import {
  Btn,
  BotBadge,
  ErrorBanner,
  Field,
  FieldError,
  HourGrid,
  Modal,
  Panel,
  Quote,
  RowSkeleton,
  SectionTitle,
  StatusPill,
  fmtInt,
  fmtMoney,
  inputCls,
} from "@/components/kit";
import { IconAlert, IconClock, IconShield } from "@/components/icons";
import { Avatar } from "@/components/cards";
import { ArtChannelPayout, ArtTrustPeriod } from "@/components/illustrations";
import { ApiError, num } from "@/lib/api";
import { AD_LANGUAGES } from "@/lib/constants";
import {
  useBotStatus,
  useChannels,
  useChannelStats,
  useCreateChannel,
  useStartChannel,
  useUpdateChannel,
  useVerifyChannelBot,
  type ChannelCreateBody,
} from "@/lib/queries";
import type { Channel } from "@/lib/types";
import { useAuthGuard } from "@/lib/auth";

export const Route = createFileRoute("/partner/channels")({
  head: () => ({
    meta: [
      { title: "My Channels — AdsKinz partner" },
      { name: "description", content: "Connect Telegram channels, set ad frequency and follow impressions, clicks and earnings per channel." },
      { property: "og:title", content: "My Channels — AdsKinz partner" },
      { property: "og:description", content: "Up to 3 native ads per day, frequency chosen by you." },
    ],
  }),
  component: ChannelsPage,
});

function StatTile({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-xl border border-seam p-3">
      <p className="text-xs text-paper-dim">{label}</p>
      <p className="num mt-1 text-lg font-bold">{value}</p>
      {sub && <p className="num mt-0.5 text-[11px] text-paper-dim">{sub}</p>}
    </div>
  );
}

function ChannelCard({
  channel,
  onStart,
  starting,
  onView,
}: {
  channel: Channel;
  onStart: () => void;
  starting: boolean;
  onView: () => void;
}) {
  const { t } = useTranslation();
  return (
    <Panel className="space-y-3">
      <div className="flex items-start gap-3">
        <Avatar name={channel.name} size={44} src={channel.logoUrl} />
        <div className="min-w-0 flex-1">
          <p className="truncate font-display text-base font-bold">{channel.name}</p>
          <p className="num text-xs text-paper-dim">
            {fmtInt(channel.subscribers)} {t("pub.subscribers")} · {channel.language} · {channel.effectiveMaxAdsPerDay}
            {t("common.perDay")}
          </p>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <StatusPill status={channel.status} />
        <BotBadge ok={channel.botAdminVerified} />
      </div>

      {channel.status === "rejected" && channel.rejectionReason && (
        <Quote tone="danger" label={t("status.rejected")}>{channel.rejectionReason}</Quote>
      )}

      {channel.status === "approved_not_started" && (
        <div className="flex flex-wrap items-center gap-3 rounded-xl border border-seam bg-bounty-soft p-3">
          <p className="text-xs font-semibold text-bounty">{t("pub.approvedNotStarted")}</p>
          <Btn tone="bounty" className="ml-auto min-h-9 px-3 text-xs" onClick={onStart} disabled={starting}>
            {starting ? "…" : t("pub.start")}
          </Btn>
        </div>
      )}

      {channel.status === "building_trust" && (
        <div className="flex items-center gap-3 rounded-xl border border-seam p-3">
          <ArtTrustPeriod className="w-16 shrink-0" />
          <p className="text-xs text-paper-dim">
            {t("pub.trustWindow")}{" "}
            {channel.trustHoursLeft > 0 && (
              <span className="font-semibold text-paper">· {channel.trustHoursLeft}h left</span>
            )}
          </p>
        </div>
      )}

      <div className="flex items-center justify-between border-t border-seam pt-3">
        <p className="num text-sm font-bold text-success">{fmtMoney(num(channel.earnings))}</p>
        <button type="button" onClick={onView} className="text-xs font-semibold text-signal hover:underline">
          {t("pub.detail.viewStats")}
        </button>
      </div>
    </Panel>
  );
}

function ChannelDetailModal({ channel, onClose }: { channel: Channel; onClose: () => void }) {
  const { t } = useTranslation();
  const statsQ = useChannelStats(channel.id);
  const updateChannel = useUpdateChannel();
  const verifyBot = useVerifyChannelBot();
  const startChannel = useStartChannel();

  const [frequency, setFrequency] = useState(String(channel.maxAdsPerDay || 1));
  const [hours, setHours] = useState<number[]>(channel.preferredHours ?? []);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const liveBotOk =
    verifyBot.isSuccess && verifyBot.variables === channel.id ? verifyBot.data.botAdminVerified : channel.botAdminVerified;

  const save = () => {
    setSaveError(null);
    setSaved(false);
    updateChannel.mutate(
      { id: channel.id, maxAdsPerDay: Number(frequency) || 1, preferredHours: hours.length ? hours : null },
      {
        onSuccess: () => setSaved(true),
        onError: (err) => setSaveError(err instanceof ApiError ? err.message : "Something went wrong."),
      },
    );
  };

  return (
    <Modal open onClose={onClose} title={channel.name} sub={t("pub.detail.channelTitle")} wide>
      <div className="space-y-5">
        <div className="flex flex-wrap items-center gap-3">
          <Avatar name={channel.name} size={52} src={channel.logoUrl} />
          <div className="min-w-0 flex-1">
            <p className="num text-xs text-paper-dim">
              {channel.language} · {fmtInt(channel.subscribers)} {t("pub.subscribers")}
            </p>
          </div>
          <StatusPill status={channel.status} />
        </div>

        {channel.status === "rejected" && channel.rejectionReason && (
          <Quote tone="danger" label={t("status.rejected")}>{channel.rejectionReason}</Quote>
        )}

        {channel.status === "approved_not_started" && (
          <div className="flex flex-wrap items-center gap-3 rounded-xl border border-seam bg-bounty-soft p-3">
            <p className="text-xs font-semibold text-bounty">{t("pub.approvedNotStarted")}</p>
            <Btn
              tone="bounty"
              className="ml-auto min-h-9 px-3 text-xs"
              onClick={() => startChannel.mutate(channel.id)}
              disabled={startChannel.isPending}
            >
              {startChannel.isPending ? "…" : t("pub.start")}
            </Btn>
          </div>
        )}

        <div>
          <SectionTitle>{t("pub.detail.overview")}</SectionTitle>
          {statsQ.isLoading ? (
            <RowSkeleton rows={2} />
          ) : statsQ.isError || !statsQ.data ? (
            <ErrorBanner onRetry={() => void statsQ.refetch()} />
          ) : (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <StatTile label={t("pub.detail.lifetime")} value={fmtMoney(num(statsQ.data.lifetimeEarnings))} />
              <StatTile label={t("pub.detail.last24h")} value={fmtMoney(num(statsQ.data.last24hEarnings))} />
              <StatTile label={t("pub.detail.avgCpm")} value={fmtMoney(num(statsQ.data.effectiveCpm))} />
              <StatTile label={t("pub.detail.ctr")} value={`${statsQ.data.ctr}%`} />
              <StatTile
                label="Impressions"
                value={fmtInt(statsQ.data.lifetimeImpressions)}
                sub={`+${fmtInt(statsQ.data.last24hImpressions)} (24h)`}
              />
              <StatTile
                label={t("pub.detail.clicks")}
                value={fmtInt(statsQ.data.lifetimeClicks)}
                sub={`+${fmtInt(statsQ.data.last24hClicks)} (24h)`}
              />
              <StatTile label={t("pub.subscribers")} value={fmtInt(statsQ.data.subscribers)} />
              <StatTile label={t("pub.detail.livePosts")} value={fmtInt(statsQ.data.livePostsCount)} />
            </div>
          )}
        </div>

        <div>
          <SectionTitle>{t("pub.detail.botStatus")}</SectionTitle>
          <div className="flex flex-wrap items-center gap-2">
            <BotBadge ok={!!liveBotOk} />
            <Btn
              variant="secondary"
              className="min-h-8 px-3 text-xs"
              onClick={() => verifyBot.mutate(channel.id)}
              disabled={verifyBot.isPending}
            >
              {verifyBot.isPending ? "…" : t("pub.detail.verifyNow")}
            </Btn>
          </div>
          {!liveBotOk && (
            <p className="mt-2 flex items-start gap-1.5 text-xs text-paper-dim">
              <IconClock width={12} height={12} className="mt-0.5 shrink-0" />
              {t("pub.form.botMissing")}
            </p>
          )}
        </div>

        <div>
          <SectionTitle>{t("pub.detail.configuration")}</SectionTitle>
          {saveError && <FieldError>{saveError}</FieldError>}

          <div className="mb-4 flex items-center gap-3">
            <Avatar name={channel.name} size={48} src={channel.logoUrl} />
            <p className="text-xs text-paper-dim">
              {t("pub.form.logo")} — récupéré automatiquement depuis la photo de profil du canal sur Telegram, se
              met à jour tout seul.
            </p>
          </div>

          <Field label={t("pub.form.frequency")} hint="1 à 3 publicités par jour." htmlFor="mfreq">
            <select id="mfreq" value={frequency} onChange={(e) => setFrequency(e.target.value)} className={`num ${inputCls()}`}>
              <option value="1">1</option>
              <option value="2">2</option>
              <option value="3">3</option>
            </select>
          </Field>

          <div className="mt-4">
            <p className="text-sm font-semibold">{t("pub.form.slots")}</p>
            <p className="mt-1 text-xs text-paper-dim">Heures UTC où les pubs peuvent être publiées. Aucune sélection = toute heure.</p>
            <div className="mt-2">
              <HourGrid value={hours} onChange={setHours} />
            </div>
          </div>

          <div className="mt-4 flex items-center gap-3">
            <Btn tone="bounty" onClick={save} disabled={updateChannel.isPending}>
              {updateChannel.isPending ? "…" : t("common.save")}
            </Btn>
            {saved && !updateChannel.isPending && <span className="text-xs font-semibold text-success">Enregistré</span>}
          </div>
        </div>
      </div>
    </Modal>
  );
}

function ChannelsPage() {
  useAuthGuard("publisher");
  const { t } = useTranslation();
  const { data: channels, isLoading, isError, refetch } = useChannels();
  const { data: botStatus } = useBotStatus();
  const createChannel = useCreateChannel();
  const startChannel = useStartChannel();

  const CHANNEL_LANGUAGES = AD_LANGUAGES.filter((l) => l.code !== "all");

  const [open, setOpen] = useState(false);
  const [viewingId, setViewingId] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [link, setLink] = useState("");
  const [adminUsername, setAdminUsername] = useState("");
  const [language, setLanguage] = useState(CHANNEL_LANGUAGES[0]?.code ?? "en");
  const [frequency, setFrequency] = useState("2");
  const [err, setErr] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [createdBotNotice, setCreatedBotNotice] = useState<string | null>(null);

  const viewingChannel = channels?.find((c) => c.id === viewingId) ?? null;

  const resetForm = () => {
    setName("");
    setLink("");
    setAdminUsername("");
    setLanguage(CHANNEL_LANGUAGES[0]?.code ?? "en");
    setFrequency("2");
    setErr({});
    setFormError(null);
  };

  const submit = () => {
    const e: Record<string, string> = {};
    if (name.trim().length < 5) e["name"] = t("pub.form.errName");
    if (!/^https:\/\/t\.me\/.+/.test(link)) e["link"] = t("pub.form.errLink");
    if (!adminUsername.trim()) e["adminUsername"] = "Enter the admin's Telegram username.";
    setErr(e);
    if (Object.keys(e).length) return;

    const body: ChannelCreateBody = {
      name: name.trim(),
      publicLink: link.trim(),
      privateLink: link.trim(),
      adminUsername: adminUsername.trim(),
      language,
      maxAdsPerDay: Number(frequency) || 1,
    };
    setFormError(null);
    createChannel.mutate(body, {
      onSuccess: (created) => {
        setOpen(false);
        resetForm();
        if (!created.botAdminVerified) {
          setCreatedBotNotice(
            `Le bot @${botStatus?.botUsername ?? "AdsKinzBot"} n'est pas encore administrateur de « ${created.name} ». ` +
              "Ça n'empêche pas la modération : ajoutez-le comme admin quand vous voulez, puis revenez dans les réglages du canal pour vérifier.",
          );
        }
      },
      onError: (err) => setFormError(err instanceof ApiError ? err.message : "Something went wrong."),
    });
  };

  return (
    <PubShell title={t("pub.nav.channels")} action={<Btn tone="bounty" onClick={() => setOpen(true)}>{t("pub.addChannel")}</Btn>}>
      <div className="space-y-5">
        <Quote tone="signal" label={t("pub.form.frequency")}>{t("pub.quotes.frequency")}</Quote>

        {createdBotNotice && (
          <div className="flex flex-wrap items-start gap-2 rounded-xl border border-seam bg-panel-2 px-4 py-3 text-sm text-paper-dim">
            <IconAlert width={16} height={16} className="mt-0.5 shrink-0 text-signal" />
            <span className="flex-1">{createdBotNotice}</span>
            <button
              type="button"
              onClick={() => setCreatedBotNotice(null)}
              className="shrink-0 text-xs font-semibold text-paper-dim underline"
            >
              Compris
            </button>
          </div>
        )}

        {botStatus && !botStatus.allVerified && (
          <div className="flex flex-wrap items-center gap-2 rounded-xl border border-seam bg-danger-soft px-4 py-3 text-sm text-danger">
            <IconShield width={16} height={16} />
            <span className="font-semibold">@{botStatus.botUsername} is missing admin rights on one or more channels.</span>
          </div>
        )}

        {isError ? (
          <ErrorBanner onRetry={() => void refetch()} />
        ) : isLoading ? (
          <Panel className="p-0"><RowSkeleton rows={4} /></Panel>
        ) : !channels || channels.length === 0 ? (
          <Panel className="p-0">
            <div className="flex flex-col items-center px-6 py-10 text-center">
              <ArtChannelPayout className="max-w-[240px]" />
              <h3 className="mt-4 font-display text-lg font-bold">{t("pub.channelsEmptyTitle")}</h3>
              <p className="mt-1.5 max-w-sm text-sm text-paper-dim">{t("pub.channelsEmptySub")}</p>
              <div className="mt-5">
                <Btn tone="bounty" onClick={() => setOpen(true)}>{t("pub.channelsEmptyCta")}</Btn>
              </div>
            </div>
          </Panel>
        ) : (
          <div className="grid gap-4 sm:grid-cols-1 lg:grid-cols-2">
            {channels.map((c) => (
              <ChannelCard
                key={c.id}
                channel={c}
                starting={startChannel.isPending && startChannel.variables === c.id}
                onStart={() => startChannel.mutate(c.id)}
                onView={() => setViewingId(c.id)}
              />
            ))}
          </div>
        )}

        <Quote tone="bounty" label={t("status.building_trust")}>{t("pub.quotes.trust")}</Quote>
      </div>

      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title={t("pub.addChannel")}
        sub={t("pub.addChannelSub")}
        footer={
          <>
            <Btn tone="bounty" onClick={submit} disabled={createChannel.isPending}>
              {createChannel.isPending ? "…" : t("common.submit")}
            </Btn>
            <Btn variant="secondary" onClick={() => setOpen(false)}>{t("common.cancel")}</Btn>
          </>
        }
      >
        <div className="space-y-4">
          {formError && <FieldError>{formError}</FieldError>}
          <Field label={t("pub.form.channelName")} hint={t("pub.form.channelNameHint")} error={err["name"]} htmlFor="cn">
            <input id="cn" value={name} onChange={(e) => setName(e.target.value)} className={inputCls(!!err["name"])} />
          </Field>
          <Field label={t("pub.form.publicLink")} hint={t("pub.form.publicLinkHint")} error={err["link"]} htmlFor="cl">
            <input id="cl" value={link} onChange={(e) => setLink(e.target.value)} placeholder="https://t.me/…" className={inputCls(!!err["link"])} />
          </Field>
          <p className="text-xs text-paper-dim">Le logo du canal est récupéré automatiquement depuis Telegram — rien à uploader.</p>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t("pub.form.lang")} hint={t("pub.form.langHint")} htmlFor="cg">
              <select id="cg" value={language} onChange={(e) => setLanguage(e.target.value)} className={inputCls()}>
                {CHANNEL_LANGUAGES.map((l) => (
                  <option key={l.code} value={l.code}>{l.label}</option>
                ))}
              </select>
            </Field>
            <Field label={t("pub.form.adminUsername")} error={err["adminUsername"]} htmlFor="cu">
              <input id="cu" value={adminUsername} onChange={(e) => setAdminUsername(e.target.value)} placeholder="@username" className={inputCls(!!err["adminUsername"])} />
            </Field>
          </div>
          <Field label={t("pub.form.frequency")} hint="Combien de publicités le canal recevra chaque jour." htmlFor="cf">
            <select id="cf" value={frequency} onChange={(e) => setFrequency(e.target.value)} className={`num ${inputCls()}`}>
              <option value="1">1</option><option value="2">2</option><option value="3">3</option>
            </select>
          </Field>
          <Quote tone="neutral" label={t("pub.form.botStep")}>{t("pub.form.botMissing")}</Quote>
        </div>
      </Modal>

      {viewingChannel && <ChannelDetailModal channel={viewingChannel} onClose={() => setViewingId(null)} />}
    </PubShell>
  );
}

