import { createFileRoute, Link, useParams } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { PubShell } from "@/components/workspaces";
import {
  BotBadge,
  Btn,
  ErrorBanner,
  Field,
  FieldError,
  HourGrid,
  Panel,
  Quote,
  RowSkeleton,
  SectionTitle,
  StatusPill,
  fmtInt,
  fmtMoney,
  inputCls,
} from "@/components/kit";
import { Avatar } from "@/components/cards";
import { IconClock } from "@/components/icons";
import { ApiError, num } from "@/lib/api";
import { useAuthGuard } from "@/lib/auth";
import {
  useChannels,
  useChannelStats,
  useStartChannel,
  useUpdateChannel,
  useVerifyChannelBot,
} from "@/lib/queries";

export const Route = createFileRoute("/partner/channels/$id")({
  head: () => ({
    meta: [
      { title: "Channel details — AdsKinz partner" },
      { name: "description", content: "Live stats, ad frequency and posting hours for one Telegram channel." },
    ],
  }),
  component: ChannelDetail,
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

function ChannelDetail() {
  useAuthGuard("publisher");
  const { t } = useTranslation();
  const { id } = useParams({ from: "/partner/channels/$id" });

  const { data: channels, isLoading: channelsLoading } = useChannels();
  const channel = channels?.find((c) => c.id === id) ?? null;

  const statsQ = useChannelStats(id);
  const startChannel = useStartChannel();
  const updateChannel = useUpdateChannel();
  const verifyBot = useVerifyChannelBot();

  const [frequency, setFrequency] = useState("2");
  const [hours, setHours] = useState<number[]>([]);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (!channel) return;
    setFrequency(String(channel.maxAdsPerDay || 1));
    setHours(channel.preferredHours ?? []);
  }, [channel?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const save = () => {
    if (!channel) return;
    setSaveError(null);
    setSaved(false);
    updateChannel.mutate(
      {
        id: channel.id,
        maxAdsPerDay: Number(frequency) || 1,
        preferredHours: hours.length ? hours : null,
      },
      {
        onSuccess: () => setSaved(true),
        onError: (err) => setSaveError(err instanceof ApiError ? err.message : "Something went wrong."),
      },
    );
  };

  const liveBotOk =
    verifyBot.isSuccess && verifyBot.variables === id ? verifyBot.data.botAdminVerified : channel?.botAdminVerified;

  return (
    <PubShell title={channel?.name ?? t("pub.detail.channelTitle")}>
      <div className="space-y-5">
        <Link to="/partner/channels" className="inline-block text-sm font-semibold text-signal hover:underline">
          ← {t("pub.detail.back")}
        </Link>

        {channelsLoading && !channel ? (
          <Panel className="p-0"><RowSkeleton rows={4} /></Panel>
        ) : !channel ? (
          <Panel>
            <p className="text-sm text-paper-dim">Canal introuvable.</p>
            <Link to="/partner/channels" className="mt-2 inline-block text-sm font-semibold text-signal hover:underline">
              {t("pub.detail.back")}
            </Link>
          </Panel>
        ) : (
          <>
            <Panel className="space-y-3">
              <div className="flex flex-wrap items-center gap-3">
                <Avatar name={channel.name} size={52} src={channel.logoUrl} />
                <div className="min-w-0 flex-1">
                  <p className="truncate font-display text-xl font-bold">{channel.name}</p>
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

              {channel.status === "building_trust" && channel.trustHoursLeft > 0 && (
                <Quote tone="bounty" label={t("status.building_trust")}>
                  {t("pub.quotes.trust")} · {channel.trustHoursLeft}h left
                </Quote>
              )}
            </Panel>

            <Panel>
              <SectionTitle>{t("pub.detail.overview")}</SectionTitle>
              {statsQ.isLoading ? (
                <RowSkeleton rows={2} />
              ) : statsQ.isError || !statsQ.data ? (
                <ErrorBanner onRetry={() => void statsQ.refetch()} />
              ) : (
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                  <StatTile
                    label={t("pub.detail.lifetime")}
                    value={fmtMoney(num(statsQ.data.lifetimeEarnings))}
                  />
                  <StatTile
                    label={t("pub.detail.last24h")}
                    value={fmtMoney(num(statsQ.data.last24hEarnings))}
                  />
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
            </Panel>

            <Panel className="space-y-4">
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
                <p className="flex items-start gap-1.5 text-xs text-paper-dim">
                  <IconClock width={12} height={12} className="mt-0.5 shrink-0" />
                  {t("pub.form.botMissing")}
                </p>
              )}
            </Panel>

            <Panel className="space-y-4">
              <SectionTitle>{t("pub.detail.configuration")}</SectionTitle>
              {saveError && <FieldError>{saveError}</FieldError>}

              <div>
                <p className="text-sm font-semibold">{t("pub.form.logo")}</p>
                <div className="mt-2 flex items-center gap-3">
                  <Avatar name={channel.name} size={56} src={channel.logoUrl} />
                  <p className="text-xs text-paper-dim">
                    Récupéré automatiquement depuis la photo de profil du canal sur Telegram — pas
                    d'upload à faire. Il se met à jour tout seul si vous changez la photo du canal.
                  </p>
                </div>
              </div>

              <Field label={t("pub.form.frequency")} hint="1 à 3 publicités par jour." htmlFor="dfreq">
                <select
                  id="dfreq"
                  value={frequency}
                  onChange={(e) => setFrequency(e.target.value)}
                  className={`num ${inputCls()}`}
                >
                  <option value="1">1</option>
                  <option value="2">2</option>
                  <option value="3">3</option>
                </select>
              </Field>

              <div>
                <p className="text-sm font-semibold">{t("pub.form.slots")}</p>
                <p className="mt-1 text-xs text-paper-dim">
                  Heures UTC où les pubs peuvent être publiées. Aucune sélection = toute heure.
                </p>
                <div className="mt-2">
                  <HourGrid value={hours} onChange={setHours} />
                </div>
              </div>

              <div className="flex items-center gap-3 pt-1">
                <Btn tone="bounty" onClick={save} disabled={updateChannel.isPending}>
                  {updateChannel.isPending ? "…" : t("common.save")}
                </Btn>
                {saved && !updateChannel.isPending && (
                  <span className="text-xs font-semibold text-success">Enregistré</span>
                )}
              </div>
            </Panel>
          </>
        )}
      </div>
    </PubShell>
  );
}
