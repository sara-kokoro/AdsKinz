import { createFileRoute, Link } from "@tanstack/react-router";
import { DocPage, NextPrev } from "@/components/docs-kit";
import { Panel } from "@/components/kit";

export const Route = createFileRoute("/docs/faq")({
  head: () => ({
    meta: [
      { title: "FAQ — Kinz-ID SDK | AdsKinz" },
      {
        name: "description",
        content: "Answers to the most common Kinz-ID integration questions: one kinzId per app, testing before approval, browser support, and preloading.",
      },
      { property: "og:title", content: "FAQ — Kinz-ID SDK | AdsKinz" },
      { property: "og:description", content: "Common integration questions from Telegram Mini App developers." },
    ],
  }),
  component: Faq,
});

const QA: { q: string; a: React.ReactNode }[] = [
  {
    q: "Do I need a different kinzId for each format?",
    a: (
      <>
        No — one <code>kinzId</code> identifies your Mini App as a whole. You create a separate <code>init()</code> call (a separate
        controller) per format, but they share the same <code>kinzId</code>.
      </>
    ),
  },
  {
    q: "Can I test the SDK before my Mini App is approved?",
    a: (
      <>
        <code>.show()</code> rejects with <code>NO_FILL</code> until your Mini App is approved. That lets you verify your integration code
        runs without errors before real ads are available.
      </>
    ),
  },
  {
    q: "Does the SDK work outside of Telegram (a regular browser tab)?",
    a: (
      <>
        The SDK expects the Telegram Mini App environment, since it reads <code>window.Telegram.WebApp.initDataUnsafe</code> for language
        targeting. Outside that context language detection falls back to English, but the rest of the SDK still functions for testing.
      </>
    ),
  },
  {
    q: "How is revenue calculated and paid out?",
    a: (
      <>
        That's a publisher dashboard question, not an SDK one — see earnings and withdrawals in your{" "}
        <Link to="/partner" className="font-semibold text-signal hover:underline">
          partner workspace
        </Link>
        .
      </>
    ),
  },
  {
    q: "Is there a way to preload an ad before calling show()?",
    a: (
      <>
        Not in v1.0.0 — <code>.show()</code> requests and displays in one step. A separate preload method may be added later if publisher
        demand justifies the added complexity.
      </>
    ),
  },
  {
    q: "What happens if I call init() twice with the same format?",
    a: <>Each call creates an independent controller. Not harmful, but unnecessary — reuse the same controller reference instead.</>,
  },
];

function Faq() {
  return (
    <DocPage title="FAQ" lede="Common integration questions from Mini App developers.">
      <div className="space-y-3">
        {QA.map((item) => (
          <Panel key={item.q}>
            <h2 className="font-display text-base font-bold">{item.q}</h2>
            <p className="mt-2 text-sm leading-relaxed text-paper-dim">{item.a}</p>
          </Panel>
        ))}
      </div>
      <NextPrev prev={{ to: "/docs/error-handling", label: "Error Handling" }} next={{ to: "/docs/changelog", label: "Changelog" }} />
    </DocPage>
  );
}
