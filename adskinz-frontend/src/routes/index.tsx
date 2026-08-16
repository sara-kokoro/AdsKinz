import { createFileRoute, Link } from "@tanstack/react-router";
import { Trans, useTranslation } from "react-i18next";
import { LanguageSelect, ThemeToggle } from "@/components/controls";
import { Logo } from "@/components/dashboard-shell";
import { IconApp, IconChannel, IconSparkle } from "@/components/icons";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "AdsKinz — Native advertising inside Telegram" },
      {
        name: "description",
        content:
          "Native ads inside Telegram channels and Mini Apps. Campaigns from $50, 12 languages, USDT payouts for publishers from $50.",
      },
      { property: "og:title", content: "AdsKinz — Native advertising inside Telegram" },
      {
        property: "og:description",
        content: "Native ads inside Telegram channels and Mini Apps. Campaigns from $50, 12 languages, USDT payouts for publishers from $50.",
      },
    ],
  }),
  component: Landing,
});

function Nav() {
  const { t } = useTranslation();
  return (
    <header className="sticky top-0 z-30 border-b border-seam bg-ink/90 backdrop-blur">
      <div className="mx-auto flex min-h-16 max-w-6xl flex-wrap items-center gap-4 px-4 py-3">
        <Logo />
        <nav className="hidden items-center gap-6 text-sm font-semibold text-paper-dim md:flex">
          <a href="#formats" className="hover:text-paper">{t("nav.advertisers")}</a>
          <a href="#audience" className="hover:text-paper">{t("nav.publishers")}</a>
          <a href="#formats" className="hover:text-paper">{t("nav.sdk")}</a>
          <Link to="/docs" className="hover:text-paper">{t("nav.docs")}</Link>
        </nav>
        <div className="ml-auto flex items-center gap-2">
          <LanguageSelect compact />
          <ThemeToggle />
          <Link
            to="/login"
            className="hidden min-h-9 items-center rounded-xl border border-seam px-3 text-sm font-semibold sm:inline-flex"
          >
            {t("common.login")}
          </Link>
          <a
            href="/login?returnTo=%2Ftraffic%2Fcampaigns%2Fnew&role=advertiser"
            className="inline-flex min-h-11 items-center rounded-xl bg-signal px-4 text-sm font-bold text-white transition-all hover:brightness-110"
          >
            {t("common.launchCampaign")}
          </a>
        </div>
      </div>
    </header>
  );
}

function TelegramMock() {
  const { t } = useTranslation();
  const bubble = "rounded-2xl border border-seam bg-panel px-4 py-3 text-sm leading-relaxed";
  return (
    <div className="surface hero-halo mx-auto w-full max-w-md space-y-3 p-4">
      <div className="flex items-center gap-3 pb-1">
        <div className="num flex size-10 items-center justify-center rounded-full bg-signal-soft text-xs font-bold text-signal">
          CS
        </div>
        <div>
          <p className="text-sm font-bold">{t("landing.mock.channel")}</p>
          <p className="num text-xs text-paper-dim">{t("landing.mock.subs")}</p>
        </div>
      </div>
      <p className={bubble}>{t("landing.mock.msg1")}</p>
      <div className={bubble}>
        <div className="flex items-start gap-2">
          <p className="flex-1">{t("landing.mock.msg2")}</p>
          <span className="animate-ad-reveal rounded-md border border-seam px-1.5 py-0.5 text-[10px] font-semibold text-paper-dim">
            {t("landing.mock.adTag")}
          </span>
        </div>
        <div className="mt-3 rounded-xl border border-seam py-2 text-center text-xs font-bold text-signal">
          {t("landing.mock.cta")}
        </div>
      </div>
      <p className={bubble}>{t("landing.mock.msg3")}</p>
    </div>
  );
}

function Landing() {
  const { t } = useTranslation();

  const stats = [
    { label: t("landing.stats.languages"), value: "12" },
    { label: t("landing.stats.cpm"), value: "$2.00" },
    { label: t("landing.stats.formats"), value: "3" },
    { label: t("landing.stats.launch"), value: t("landing.stats.launchValue") },
  ];

  const formats = [
    {
      tag: t("landing.formats.channel"),
      icon: <IconChannel className="text-signal" />,
      title: t("landing.formats.nativeTitle"),
      desc: t("landing.formats.nativeDesc"),
      s1: [t("landing.formats.statCpm"), "$2.00"],
      s2: [t("landing.formats.statMaxPerDay"), "3"],
    },
    {
      tag: t("landing.formats.miniapp"),
      icon: <IconApp className="text-signal" />,
      title: t("landing.formats.interstitialTitle"),
      desc: t("landing.formats.interstitialDesc"),
      s1: [t("landing.formats.statIntegration"), t("landing.formats.statIntegrationValue")],
      s2: [t("landing.formats.statSetup"), t("landing.formats.statSetupValue")],
    },
    {
      tag: t("landing.formats.miniapp"),
      icon: <IconApp className="text-signal" />,
      title: t("landing.formats.popTitle"),
      desc: t("landing.formats.popDesc"),
      s1: [t("landing.formats.statIntegration"), t("landing.formats.statIntegrationValue")],
      s2: [t("landing.formats.statSetup"), t("landing.formats.statSetupValue")],
    },
  ];

  const steps = [1, 2, 3, 4].map((n) => ({
    n,
    title: t(`landing.how.s${n}t`),
    desc: t(`landing.how.s${n}d`),
  }));

  const faq = [1, 2, 3, 4, 5].map((n) => ({ q: t(`landing.faq.q${n}`), a: t(`landing.faq.a${n}`) }));

  return (
    <div className="min-h-screen bg-ink">
      <Nav />
      <main>
        {/* Hero */}
        <section className="mx-auto max-w-6xl px-4 pt-14 pb-10 text-center sm:pt-20">
          <p className="text-xs font-bold tracking-[0.18em] text-signal uppercase">{t("landing.eyebrow")}</p>
          <h1 className="mx-auto mt-5 max-w-3xl font-display text-4xl leading-[1.05] font-extrabold tracking-tight sm:text-6xl">
            {t("landing.heroLine1")}
            <br />
            {t("landing.heroLine2")}
          </h1>
          <p className="mx-auto mt-5 max-w-2xl text-base text-paper-dim sm:text-lg">
            {t("landing.heroSub_pre")}
            <strong className="font-extrabold text-paper">{t("landing.heroSub_native")}</strong>
            {t("landing.heroSub_mid")}
            <strong className="num font-bold text-bounty">{t("landing.heroSub_amount")}</strong>
            {t("landing.heroSub_post")}
          </p>
          <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <a
              href="/login?returnTo=%2Ftraffic%2Fcampaigns%2Fnew&role=advertiser"
              className="inline-flex min-h-11 w-full items-center justify-center rounded-xl bg-signal px-6 text-sm font-bold text-white transition-all hover:brightness-110 sm:w-auto"
            >
              {t("common.launchCampaign")}
            </a>
            <a
              href="/login?returnTo=%2Fpartner%2Fchannels&role=publisher"
              className="inline-flex min-h-11 w-full items-center justify-center rounded-xl border border-seam px-6 text-sm font-semibold transition-colors hover:bg-panel sm:w-auto"
            >
              {t("common.becomePublisher")}
            </a>
          </div>

          <div className="mt-12">
            <TelegramMock />
          </div>

          <div className="mx-auto mt-12 grid max-w-3xl grid-cols-2 gap-px overflow-hidden rounded-2xl border border-seam bg-seam sm:grid-cols-4">
            {stats.map((s) => (
              <div key={s.label} className="bg-ink px-4 py-5">
                <p className="num font-display text-2xl font-bold">{s.value}</p>
                <p className="mt-1 text-xs font-semibold text-paper-dim">{s.label}</p>
              </div>
            ))}
          </div>
        </section>

        {/* Formats */}
        <section id="formats" className="mx-auto max-w-6xl px-4 py-16">
          <h2 className="font-display text-3xl font-extrabold tracking-tight">{t("landing.formats.title")}</h2>
          <p className="mt-2 max-w-2xl text-paper-dim">{t("landing.formats.subtitle")}</p>
          <div className="mt-8 grid gap-4 md:grid-cols-3">
            {formats.map((f) => (
              <article key={f.title} className="surface flex flex-col p-5">
                <div className="flex items-center gap-2">
                  {f.icon}
                  <span className="rounded-md border border-seam px-2 py-0.5 text-[11px] font-semibold text-paper-dim">
                    {f.tag}
                  </span>
                </div>
                <h3 className="mt-4 font-display text-xl font-bold">{f.title}</h3>
                <p className="mt-2 flex-1 text-sm leading-relaxed text-paper-dim">{f.desc}</p>
                <div className="mt-5 grid grid-cols-2 gap-4 border-t border-seam pt-4">
                  {[f.s1, f.s2].map(([label, value]) => (
                    <div key={label}>
                      <p className="text-[11px] font-semibold text-paper-dim">{label}</p>
                      <p className="num mt-0.5 text-sm font-bold">{value}</p>
                    </div>
                  ))}
                </div>
              </article>
            ))}
          </div>
        </section>

        {/* How it works */}
        <section className="mx-auto max-w-6xl px-4 py-16">
          <h2 className="font-display text-3xl font-extrabold tracking-tight">{t("landing.how.title")}</h2>
          <div className="mt-8 grid gap-6 md:grid-cols-4">
            {steps.map((s) => (
              <div key={s.n}>
                <div className="num flex size-10 items-center justify-center rounded-full border-2 border-signal text-sm font-bold text-signal">
                  {s.n}
                </div>
                <h3 className="mt-4 text-base font-bold">{s.title}</h3>
                <p className="mt-1.5 text-sm leading-relaxed text-paper-dim">{s.desc}</p>
              </div>
            ))}
          </div>
        </section>

        {/* Dual audience */}
        <section id="audience" className="mx-auto max-w-6xl px-4 py-16">
          <div className="grid gap-4 md:grid-cols-2">
            <article className="surface flex flex-col p-6">
              <span className="text-xs font-bold tracking-[0.16em] text-signal uppercase">
                {t("landing.audience.advTitle")}
              </span>
              <h3 className="mt-3 font-display text-2xl font-extrabold">{t("landing.audience.advSub")}</h3>
              <ul className="mt-5 flex-1 space-y-2.5 text-sm">
                {["advB1", "advB2", "advB3"].map((k) => (
                  <li key={k} className="flex gap-2.5">
                    <span className="mt-2 size-1.5 shrink-0 rounded-full bg-signal" aria-hidden />
                    <span className="text-paper-dim">{t(`landing.audience.${k}`)}</span>
                  </li>
                ))}
              </ul>
              <a
                href="/login?returnTo=%2Ftraffic%2Fcampaigns%2Fnew&role=advertiser"
                className="mt-6 inline-flex min-h-11 w-full items-center justify-center rounded-xl bg-signal text-sm font-bold text-white"
              >
                {t("common.launchCampaign")}
              </a>
            </article>
            <article className="surface flex flex-col p-6">
              <span className="text-xs font-bold tracking-[0.16em] text-bounty uppercase">
                {t("landing.audience.pubTitle")}
              </span>
              <h3 className="mt-3 font-display text-2xl font-extrabold">{t("landing.audience.pubSub")}</h3>
              <ul className="mt-5 flex-1 space-y-2.5 text-sm">
                {["pubB1", "pubB2", "pubB3"].map((k) => (
                  <li key={k} className="flex gap-2.5">
                    <span className="mt-2 size-1.5 shrink-0 rounded-full bg-bounty" aria-hidden />
                    <span className="text-paper-dim">{t(`landing.audience.${k}`)}</span>
                  </li>
                ))}
              </ul>
              <a
                href="/login?returnTo=%2Fpartner%2Fchannels&role=publisher"
                className="mt-6 inline-flex min-h-11 w-full items-center justify-center rounded-xl border border-seam text-sm font-bold"
              >
                {t("common.becomePublisher")}
              </a>
            </article>
          </div>
        </section>

        {/* FAQ */}
        <section id="faq" className="mx-auto max-w-3xl px-4 py-16">
          <h2 className="font-display text-3xl font-extrabold tracking-tight">{t("landing.faq.title")}</h2>
          <div className="mt-8 divide-y divide-seam border-y border-seam">
            {faq.map((f) => (
              <div key={f.q} className="py-5">
                <h3 className="text-base font-bold">{f.q}</h3>
                <p className="mt-2 text-sm leading-relaxed text-paper-dim">
                  <Trans>{f.a}</Trans>
                </p>
              </div>
            ))}
          </div>
        </section>

        <section className="mx-auto max-w-6xl px-4 pb-20">
          <div className="surface flex flex-wrap items-center gap-4 p-6">
            <IconSparkle className="text-signal" />
            <p className="font-display text-lg font-bold">{t("landing.eyebrow")}</p>
            <a
              href="/login?returnTo=%2Ftraffic%2Fcampaigns%2Fnew&role=advertiser"
              className="ml-auto inline-flex min-h-11 items-center rounded-xl bg-signal px-5 text-sm font-bold text-white"
            >
              {t("common.getStarted")}
            </a>
          </div>
        </section>
      </main>

      <footer className="border-t border-seam">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-4 px-4 py-8 text-sm text-paper-dim">
          <Logo />
          <div className="ml-auto flex flex-wrap gap-5 font-semibold">
            <Link to="/docs">docs</Link>
            <Link to="/traffic">traffic</Link>
            <Link to="/partner">partner</Link>
            <Link to="/kingcey">kingcey</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
