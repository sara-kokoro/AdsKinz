import { createFileRoute, Link } from "@tanstack/react-router";
import { useTranslation } from "react-i18next";
import { LanguageSelect, ThemeToggle } from "@/components/controls";
import { Logo } from "@/components/dashboard-shell";
import { IconSparkle } from "@/components/icons";

/* Hand-drawn format icons — each traces the actual UI shape it represents
 * (a channel message with a button, a full-screen frame, a floating card)
 * rather than a generic outline icon, so the icon itself explains the
 * format before the label does. */
function IconFormatNative({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 40 40" className={className} width="28" height="28" fill="none" aria-hidden>
      <rect x="4" y="6" width="32" height="20" rx="6" stroke="currentColor" strokeWidth="2" />
      <line x1="9" y1="13" x2="27" y2="13" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      <line x1="9" y1="18" x2="21" y2="18" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      <rect x="9" y="29" width="22" height="6" rx="3" stroke="currentColor" strokeWidth="2" />
    </svg>
  );
}
function IconFormatInterstitial({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 40 40" className={className} width="28" height="28" fill="none" aria-hidden>
      <rect x="8" y="3" width="24" height="34" rx="5" stroke="currentColor" strokeWidth="2" />
      <rect x="12" y="9" width="16" height="16" rx="2" stroke="currentColor" strokeWidth="2" />
      <line x1="12" y1="29" x2="24" y2="29" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      <line x1="12" y1="32.5" x2="20" y2="32.5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}
function IconFormatPop({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 40 40" className={className} width="28" height="28" fill="none" aria-hidden>
      <rect x="6" y="5" width="22" height="30" rx="4" stroke="currentColor" strokeWidth="2" opacity="0.45" />
      <rect x="15" y="17" width="19" height="14" rx="4" stroke="currentColor" strokeWidth="2" fill="var(--color-ink)" />
      <line x1="19" y1="22" x2="30" y2="22" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      <line x1="19" y1="26" x2="26" y2="26" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

/* Static decorative accent behind the hero mockup: a loose orbit of dots
 * connected by lines, evoking a channel's ad-selection pass without
 * literally illustrating it. No motion — the animation budget on this
 * page goes entirely to the feed reveal below. */
function HeroOrbit() {
  return (
    <svg
      viewBox="0 0 400 400"
      className="pointer-events-none absolute -top-10 right-0 -z-10 h-[420px] w-[420px] text-signal opacity-[0.14] sm:opacity-20"
      aria-hidden
    >
      <circle cx="200" cy="200" r="160" stroke="currentColor" strokeWidth="1" fill="none" />
      <circle cx="200" cy="200" r="110" stroke="currentColor" strokeWidth="1" fill="none" />
      <circle cx="200" cy="40" r="5" fill="currentColor" />
      <circle cx="352" cy="240" r="4" fill="currentColor" />
      <circle cx="70" cy="290" r="6" fill="currentColor" />
      <circle cx="120" cy="90" r="3" fill="currentColor" />
      <line x1="200" y1="40" x2="200" y2="90" stroke="currentColor" strokeWidth="1" />
      <line x1="352" y1="240" x2="310" y2="200" stroke="currentColor" strokeWidth="1" />
    </svg>
  );
}

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "AdsKinz — Native advertising inside Telegram" },
      {
        name: "description",
        content:
          "Native ads inside Telegram channels and Mini Apps. Campaigns from $20, 12 languages, USDT payouts for publishers from $50.",
      },
      { property: "og:title", content: "AdsKinz — Native advertising inside Telegram" },
      {
        property: "og:description",
        content: "Native ads inside Telegram channels and Mini Apps. Campaigns from $20, 12 languages, USDT payouts for publishers from $50.",
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
          <Link
            to="/traffic/campaigns/new"
            className="inline-flex min-h-11 items-center rounded-xl bg-signal px-4 text-sm font-bold text-white transition-all hover:brightness-110"
          >
            {t("common.launchCampaign")}
          </Link>
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
      <div className={`${bubble} animate-ad-reveal`}>
        <div className="flex items-start gap-2">
          <p className="flex-1">{t("landing.mock.msg2")}</p>
          <span className="rounded-md border border-seam px-1.5 py-0.5 text-[10px] font-semibold text-paper-dim">
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
    { label: t("landing.stats.channels"), value: "1,304" },
    { label: t("landing.stats.miniApps"), value: "89" },
    { label: t("landing.stats.impressionsWeek"), value: "+590K" },
    { label: t("landing.stats.cpm"), value: "$1.70" },
  ];

  const formats = [
    {
      tag: t("landing.formats.channel"),
      icon: <IconFormatNative className="text-signal" />,
      title: t("landing.formats.nativeTitle"),
      desc: t("landing.formats.nativeDesc"),
      s1: [t("landing.formats.statCpm"), "$2.00"],
      s2: [t("landing.formats.statMaxPerDay"), "3"],
    },
    {
      tag: t("landing.formats.miniapp"),
      icon: <IconFormatInterstitial className="text-signal" />,
      title: t("landing.formats.interstitialTitle"),
      desc: t("landing.formats.interstitialDesc"),
      s1: [t("landing.formats.statIntegration"), t("landing.formats.statIntegrationValue")],
      s2: [t("landing.formats.statSetup"), t("landing.formats.statSetupValue")],
    },
    {
      tag: t("landing.formats.miniapp"),
      icon: <IconFormatPop className="text-signal" />,
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

  type FaqGroup = { label: string; items: { q: string; a: string }[] };
  const faqGroups = t("landing.faq.groups", { returnObjects: true }) as FaqGroup[];

  return (
    <div className="min-h-screen bg-ink">
      <Nav />
      <main>
        {/* Hero */}
        <section className="mx-auto max-w-6xl px-4 pt-14 pb-10 sm:pt-20">
          <div className="grid items-center gap-10 lg:grid-cols-[1.05fr_0.95fr] lg:gap-6">
            <div className="text-center lg:text-left">
              <h1 className="mx-auto max-w-xl font-display text-4xl leading-[1.08] font-extrabold tracking-tight sm:text-5xl lg:mx-0 lg:text-6xl">
                {t("landing.heroTitle")}
              </h1>
              <p className="mx-auto mt-5 max-w-lg text-base leading-relaxed text-paper-dim sm:text-lg lg:mx-0">
                {t("landing.heroSub")}
              </p>
              <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row lg:justify-start">
                <Link
                  to="/traffic/campaigns/new"
                  className="inline-flex min-h-11 w-full items-center justify-center rounded-xl bg-signal px-6 text-sm font-bold text-white transition-all hover:brightness-110 sm:w-auto"
                >
                  {t("common.launchCampaign")}
                </Link>
                <Link
                  to="/login"
                  search={{ intent: "addAccount", role: "publisher" }}
                  className="inline-flex min-h-11 w-full items-center justify-center rounded-xl border border-seam px-6 text-sm font-semibold transition-colors hover:bg-panel sm:w-auto"
                >
                  {t("common.becomePublisher")}
                </Link>
              </div>
              <div className="mx-auto mt-10 grid max-w-md grid-cols-2 gap-px overflow-hidden rounded-2xl border border-seam bg-seam sm:grid-cols-4 lg:mx-0 lg:max-w-none">
                {stats.map((s) => (
                  <div key={s.label} className="bg-ink px-3 py-4 text-center lg:text-left">
                    <p className="num font-display text-xl font-bold sm:text-2xl">{s.value}</p>
                    <p className="mt-1 text-[11px] font-semibold text-paper-dim">{s.label}</p>
                  </div>
                ))}
              </div>
            </div>

            <div className="relative">
              <HeroOrbit />
              <TelegramMock />
            </div>
          </div>
        </section>

        {/* Formats */}
        <section id="formats" className="mx-auto max-w-6xl px-4 py-16">
          <h2 className="max-w-xl font-display text-3xl font-extrabold tracking-tight">{t("landing.formats.title")}</h2>
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
              <Link
                to="/traffic/campaigns/new"
                className="mt-6 inline-flex min-h-11 w-full items-center justify-center rounded-xl bg-signal text-sm font-bold text-white"
              >
                {t("common.launchCampaign")}
              </Link>
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
              <Link
                to="/login"
                search={{ intent: "addAccount", role: "publisher" }}
                className="mt-6 inline-flex min-h-11 w-full items-center justify-center rounded-xl border border-seam text-sm font-bold"
              >
                {t("common.becomePublisher")}
              </Link>
            </article>
          </div>
        </section>

        {/* FAQ */}
        <section id="faq" className="mx-auto max-w-3xl px-4 py-16">
          <h2 className="font-display text-3xl font-extrabold tracking-tight">{t("landing.faq.title")}</h2>
          <p className="mt-2 text-paper-dim">{t("landing.faq.sub")}</p>
          <div className="mt-8 space-y-8">
            {faqGroups.map((group) => (
              <div key={group.label}>
                <h3 className="text-xs font-bold tracking-wide text-signal">{group.label}</h3>
                <div className="mt-2 divide-y divide-seam border-y border-seam">
                  {group.items.map((f) => (
                    <details key={f.q} className="group py-4">
                      <summary className="flex cursor-pointer list-none items-center justify-between gap-3 text-sm font-bold">
                        {f.q}
                        <span className="shrink-0 text-paper-dim transition-transform group-open:rotate-45">+</span>
                      </summary>
                      <p className="mt-2 text-sm leading-relaxed text-paper-dim">{f.a}</p>
                    </details>
                  ))}
                </div>
              </div>
            ))}
          </div>
          <div className="mt-8 flex flex-wrap items-center gap-3 rounded-2xl border border-seam p-5">
            <p className="text-sm font-semibold">{t("landing.faq.more")}</p>
            <a
              href="https://t.me/AdsKinzBot"
              target="_blank"
              rel="noreferrer"
              className="ml-auto rounded-xl border border-seam px-4 py-2 text-sm font-semibold hover:bg-panel"
            >
              {t("landing.faq.moreBtn")}
            </a>
          </div>
        </section>

        <section className="mx-auto max-w-6xl px-4 pb-20">
          <div className="surface flex flex-wrap items-center gap-4 p-6">
            <IconSparkle className="text-signal" />
            <p className="font-display text-lg font-bold">{t("landing.finalCta")}</p>
            <Link
              to="/traffic/campaigns/new"
              className="ml-auto inline-flex min-h-11 items-center rounded-xl bg-signal px-5 text-sm font-bold text-white"
            >
              {t("common.getStarted")}
            </Link>
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
          </div>
        </div>
      </footer>
    </div>
  );
}
