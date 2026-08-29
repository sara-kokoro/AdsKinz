import { createFileRoute, Link } from "@tanstack/react-router";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { PubShell } from "@/components/workspaces";
import {
  Btn,
  BotBadge,
  EmptyState,
  ErrorBanner,
  Field,
  FieldError,
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
import { IconAlert, IconShield } from "@/components/icons";
import { Avatar } from "@/components/cards";
import { ArtChannelPayout, ArtTrustPeriod } from "@/components/illustrations";
import { ApiError, num } from "@/lib/api";
import { AD_LANGUAGES } from "@/lib/constants";
import {
  useBotStatus,
  useChannels,
  useCreateChannel,
  useStartChannel,
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

function ChannelCard({
  channel,
  botOk,
  onStart,
  starting,
}: {
  channel: Channel;
  botOk: boolean;
  onStart: () => void;
  starting: boolean;
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
        <Link
          to="/partner/channels/$id"
          params={{ id: channel.id }}
          className="text-xs font-semibold text-signal hover:underline"
        >
          {t("pub.detail.viewStats")}
        </Link>
      </div>
    </Panel>
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
  const [name, setName] = useState("");
  const [link, setLink] = useState("");
  const [adminUsername, setAdminUsername] = useState("");
  const [language, setLanguage] = useState(CHANNEL_LANGUAGES[0]?.code ?? "en");
  const [frequency, setFrequency] = useState("2");
  const [err, setErr] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [createdBotNotice, setCreatedBotNotice] = useState<string | null>(null);

  const botOkFor = (id: string) => botStatus?.items.find((i) => i.channelId === id)?.isAdmin ?? true;

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
                botOk={botOkFor(c.id)}
                starting={startChannel.isPending && startChannel.variables === c.id}
                onStart={() => startChannel.mutate(c.id)}
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
    </PubShell>
  );
}
