import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { PubShell } from "@/components/workspaces";
import {
  Btn,
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
import { IconAlert, IconCheck, IconClock, IconShield } from "@/components/icons";
import { Avatar } from "@/components/cards";
import { ArtChannelPayout, ArtTrustPeriod } from "@/components/illustrations";
import { ApiError, num } from "@/lib/api";
import {
  useBotStatus,
  useChannels,
  useCreateChannel,
  useStartChannel,
  useUpdateChannel,
  type ChannelCreateBody,
} from "@/lib/queries";
import type { Channel } from "@/lib/types";
import { cn } from "@/lib/utils";

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

function BotBadge({ ok }: { ok: boolean }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border border-seam px-2.5 py-1 text-[11px] font-semibold",
        ok ? "bg-success-soft text-success" : "bg-danger-soft text-danger",
      )}
    >
      {ok ? <IconCheck width={11} height={11} /> : <IconAlert width={11} height={11} />}
      {ok ? "Bot is administrator" : "Bot admin rights missing"}
    </span>
  );
}

function ChannelCard({
  channel,
  botOk,
  onStart,
  starting,
  onOpen,
}: {
  channel: Channel;
  botOk: boolean;
  onStart: () => void;
  starting: boolean;
  onOpen: () => void;
}) {
  const { t } = useTranslation();
  return (
    <Panel className="space-y-3">
      <div className="flex flex-wrap items-center gap-3">
        <Avatar name={channel.name} size={44} />
        <div className="min-w-0 flex-1">
          <p className="truncate font-display text-base font-bold">{channel.name}</p>
          <p className="num truncate text-xs text-paper-dim">
            {fmtInt(channel.subscribers)} {t("pub.subscribers")} · {channel.language} · {channel.effectiveMaxAdsPerDay}
            {t("common.perDay")}
          </p>
        </div>
        <StatusPill status={channel.status} />
      </div>

      <BotBadge ok={channel.botAdminVerified} />

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

      <div className="flex items-center justify-between">
        <p className="num text-sm font-bold text-success">{fmtMoney(num(channel.earnings))}</p>
        <button onClick={onOpen} className="text-xs font-semibold text-signal hover:underline">
          {t("pub.detail.edit")}
        </button>
      </div>
    </Panel>
  );
}

function ChannelsPage() {
  const { t } = useTranslation();
  const { data: channels, isLoading, isError, refetch } = useChannels();
  const { data: botStatus } = useBotStatus();
  const createChannel = useCreateChannel();
  const startChannel = useStartChannel();
  const updateChannel = useUpdateChannel();

  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<Channel | null>(null);
  const [name, setName] = useState("");
  const [link, setLink] = useState("");
  const [adminUsername, setAdminUsername] = useState("");
  const [language, setLanguage] = useState("English");
  const [subscribers, setSubscribers] = useState("500");
  const [frequency, setFrequency] = useState("2");
  const [err, setErr] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string | null>(null);

  const [editFreq, setEditFreq] = useState("2");
  const [editHours, setEditHours] = useState("");
  const [editError, setEditError] = useState<string | null>(null);

  const botOkFor = (id: string) => botStatus?.items.find((i) => i.channelId === id)?.isAdmin ?? true;

  const resetForm = () => {
    setName("");
    setLink("");
    setAdminUsername("");
    setLanguage("English");
    setSubscribers("500");
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
      subscribers: Number(subscribers) || 0,
      maxAdsPerDay: Number(frequency) || 0,
    };
    setFormError(null);
    createChannel.mutate(body, {
      onSuccess: () => {
        setOpen(false);
        resetForm();
      },
      onError: (err) => setFormError(err instanceof ApiError ? err.message : "Something went wrong."),
    });
  };

  const openEdit = (c: Channel) => {
    setEditing(c);
    setEditFreq(String(c.maxAdsPerDay));
    setEditHours((c.preferredHours ?? []).join(", "));
    setEditError(null);
  };

  const submitEdit = () => {
    if (!editing) return;
    const hours = editHours
      .split(",")
      .map((h) => h.trim())
      .filter(Boolean)
      .map(Number)
      .filter((n) => Number.isFinite(n) && n >= 0 && n <= 23);
    setEditError(null);
    updateChannel.mutate(
      { id: editing.id, maxAdsPerDay: Number(editFreq) || 0, preferredHours: hours.length ? hours : null },
      {
        onSuccess: () => setEditing(null),
        onError: (err) => setEditError(err instanceof ApiError ? err.message : "Something went wrong."),
      },
    );
  };

  return (
    <PubShell title={t("pub.nav.channels")} action={<Btn tone="bounty" onClick={() => setOpen(true)}>{t("pub.addChannel")}</Btn>}>
      <div className="space-y-5">
        <Quote tone="signal" label={t("pub.form.frequency")}>{t("pub.quotes.frequency")}</Quote>

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
                onOpen={() => openEdit(c)}
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
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t("pub.form.lang")} hint={t("pub.form.langHint")} htmlFor="cg">
              <select id="cg" value={language} onChange={(e) => setLanguage(e.target.value)} className={inputCls()}>
                <option>English</option><option>French</option><option>Russian</option><option>Chinese (Simplified)</option>
              </select>
            </Field>
            <Field label={t("pub.form.adminUsername")} error={err["adminUsername"]} htmlFor="cu">
              <input id="cu" value={adminUsername} onChange={(e) => setAdminUsername(e.target.value)} placeholder="@username" className={inputCls(!!err["adminUsername"])} />
            </Field>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t("pub.form.frequency")} htmlFor="cf">
              <select id="cf" value={frequency} onChange={(e) => setFrequency(e.target.value)} className={`num ${inputCls()}`}>
                <option>0</option><option>1</option><option>2</option><option>3</option>
              </select>
            </Field>
            <Field label="Subscribers" htmlFor="csub">
              <input id="csub" inputMode="numeric" value={subscribers} onChange={(e) => setSubscribers(e.target.value)} className={`num ${inputCls()}`} />
            </Field>
          </div>
          <Quote tone="neutral" label={t("pub.form.botStep")}>{t("pub.form.botMissing")}</Quote>
        </div>
      </Modal>

      <Modal
        open={!!editing}
        onClose={() => setEditing(null)}
        title={editing ? editing.name : ""}
        sub="Adjust delivery frequency and preferred hours."
        footer={
          <>
            <Btn tone="bounty" onClick={submitEdit} disabled={updateChannel.isPending}>
              {updateChannel.isPending ? "…" : t("common.save")}
            </Btn>
            <Btn variant="secondary" onClick={() => setEditing(null)}>{t("common.cancel")}</Btn>
          </>
        }
      >
        {editing && (
          <div className="space-y-4">
            {editError && <FieldError>{editError}</FieldError>}
            <Field label={t("pub.form.frequency")} htmlFor="ef">
              <select id="ef" value={editFreq} onChange={(e) => setEditFreq(e.target.value)} className={`num ${inputCls()}`}>
                <option>0</option><option>1</option><option>2</option><option>3</option>
              </select>
            </Field>
            <Field label={t("pub.form.slots")} hint="Comma-separated UTC hours, e.g. 9, 18" htmlFor="eh">
              <input id="eh" value={editHours} onChange={(e) => setEditHours(e.target.value)} className={`num ${inputCls()}`} />
            </Field>
            <div className="rounded-xl border border-seam p-3 text-xs text-paper-dim">
              <p className="flex items-center gap-1.5 font-semibold text-paper">
                <IconClock width={12} height={12} /> {t("pub.detail.botStatus")}
              </p>
              <div className="mt-2"><BotBadge ok={editing.botAdminVerified} /></div>
            </div>
          </div>
        )}
      </Modal>
    </PubShell>
  );
}
