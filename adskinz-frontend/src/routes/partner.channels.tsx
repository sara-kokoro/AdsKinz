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
import { channels, statsFor } from "@/lib/mock-data";

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

function ChannelsPage() {
  const { t } = useTranslation();
  const { loading } = useFakeLoad();
  const [open, setOpen] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [link, setLink] = useState("");
  const [err, setErr] = useState<Record<string, string>>({});

  const submit = () => {
    const e: Record<string, string> = {};
    if (name.trim().length < 5) e["name"] = t("pub.form.errName");
    if (!/^https:\/\/t\.me\/.+/.test(link)) e["link"] = t("pub.form.errLink");
    setErr(e);
    if (!Object.keys(e).length) {
      setOpen(false);
      setName("");
      setLink("");
    }
  };

  const channel = channels.find((c) => c.id === selected);
  const stats = selected ? statsFor(selected) : undefined;

  if (channel && stats) {
    return (
      <PubShell title={t("pub.detail.channelTitle")}>
        <PlacementDetail
          title={channel.name}
          backLabel={t("pub.detail.back")}
          onBack={() => setSelected(null)}
          status={channel.status}
          subtitle={`${fmtInt(channel.subscribers)} ${t("pub.subscribers")} · ${channel.language} · ${channel.frequency}${t("common.perDay")}`}
          stats={stats}
          actions={
            <>
              <Btn variant="secondary" className="min-h-10 px-3 text-xs">{t("pub.detail.edit")}</Btn>
              <Btn variant="secondary" className="min-h-10 px-3 text-xs">{t("pub.detail.pause")}</Btn>
            </>
          }
          configuration={[
            { label: t("pub.detail.id"), value: channel.id },
            { label: t("pub.detail.connectedOn"), value: stats.connectedOn },
            { label: t("pub.form.lang"), value: channel.language },
            { label: t("pub.form.frequency"), value: `${channel.frequency}${t("common.perDay")}` },
            { label: t("pub.detail.botStatus"), value: channel.status === "suspended" ? t("pub.form.botMissing") : t("pub.form.botOk") },
            { label: t("pub.detail.lastAd"), value: stats.lastAd },
            { label: t("pub.detail.nextSlot"), value: stats.nextSlot },
          ]}
        />
      </PubShell>
    );
  }

  return (
    <PubShell title={t("pub.nav.channels")} action={<Btn tone="bounty" onClick={() => setOpen(true)}>{t("pub.addChannel")}</Btn>}>
      <div className="space-y-5">
        <Quote tone="signal" label={t("pub.form.frequency")}>{t("pub.quotes.frequency")}</Quote>

        {loading ? (
          <Panel className="p-0"><RowSkeleton rows={4} /></Panel>
        ) : channels.length === 0 ? (
          <Panel className="p-0">
            <EmptyState title={t("pub.channelsEmptyTitle")} sub={t("pub.channelsEmptySub")} action={<Btn tone="bounty" onClick={() => setOpen(true)}>{t("pub.channelsEmptyCta")}</Btn>} />
          </Panel>
        ) : (
          <div className="grid gap-4 lg:grid-cols-2">
            {channels.map((c) => (
              <PlacementCard
                key={c.id}
                name={c.name}
                handle={`@${c.id} · ${c.language} · ${c.frequency}${t("common.perDay")}`}
                status={c.status}
                people={c.subscribers}
                peopleLabel={t("pub.subscribers")}
                earnings={c.earnings30}
                onOpen={() => setSelected(c.id)}
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
            <Btn tone="bounty" onClick={submit}>{t("common.submit")}</Btn>
            <Btn variant="secondary" onClick={() => setOpen(false)}>{t("common.cancel")}</Btn>
          </>
        }
      >
        <div className="space-y-4">
          <Field label={t("pub.form.channelName")} hint={t("pub.form.channelNameHint")} error={err["name"]} htmlFor="cn">
            <input id="cn" value={name} onChange={(e) => setName(e.target.value)} className={inputCls(!!err["name"])} />
          </Field>
          <Field label={t("pub.form.publicLink")} hint={t("pub.form.publicLinkHint")} error={err["link"]} htmlFor="cl">
            <input id="cl" value={link} onChange={(e) => setLink(e.target.value)} placeholder="https://t.me/…" className={inputCls(!!err["link"])} />
          </Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t("pub.form.lang")} hint={t("pub.form.langHint")} htmlFor="cg">
              <select id="cg" className={inputCls()}>
                <option>English</option><option>French</option><option>Russian</option><option>Chinese (Simplified)</option>
              </select>
            </Field>
            <Field label={t("pub.form.adminUsername")} htmlFor="cu">
              <input id="cu" placeholder="@username" className={inputCls()} />
            </Field>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t("pub.form.frequency")} htmlFor="cf">
              <select id="cf" className={`num ${inputCls()}`}>
                <option>0</option><option>1</option><option>2</option><option>3</option>
              </select>
            </Field>
            <Field label={t("pub.form.slots")} htmlFor="cs">
              <input id="cs" placeholder="09:00 UTC, 18:00 UTC" className={`num ${inputCls()}`} />
            </Field>
          </div>
          <Quote tone="neutral" label={t("pub.form.botStep")}>{t("pub.form.botMissing")}</Quote>
        </div>
      </Modal>
    </PubShell>
  );
}
