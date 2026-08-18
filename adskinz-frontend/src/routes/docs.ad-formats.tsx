import { createFileRoute } from "@tanstack/react-router";
import { Callout, DocPage, DocTable, NextPrev } from "@/components/docs-kit";

export const Route = createFileRoute("/docs/ad-formats")({
  head: () => ({
    meta: [
      { title: "Ad Formats — Kinz-ID SDK | AdsKinz" },
      {
        name: "description",
        content: "interstitial vs popInterstitial: screen coverage, minimum view time, dismissibility and the best trigger points for each format.",
      },
      { property: "og:title", content: "Ad Formats — Kinz-ID SDK | AdsKinz" },
      { property: "og:description", content: "Choose between full-screen interstitials and dismissible pop interstitials." },
    ],
  }),
  component: AdFormats,
});

function AdFormats() {
  return (
    <DocPage
      title="Ad Formats"
      lede="Kinz-ID serves two Mini App ad formats. Both go through the same .show() call — the format is fixed at init() time, per controller."
    >
      <section>
        <h2 className="font-display text-xl font-bold">
          <code>interstitial</code>
        </h2>
        <p className="mt-2 text-sm leading-relaxed text-paper-dim">
          A full-screen ad shown between two natural steps in your flow — between finishing a task and seeing its result, or between levels
          in a game.
        </p>
        <ul className="mt-3 list-disc space-y-2 pl-5 text-sm leading-relaxed text-paper-dim">
          <li>Takes over the full viewport.</li>
          <li>Not dismissible before a short minimum view time; after that a close control appears.</li>
          <li>Best trigger points: level transitions, loading screens, post-action confirmations.</li>
          <li>
            Resolves <code>"completed"</code> once the minimum view time and any video finished, or <code>"closed"</code> if dismissed after
            the close control appears.
          </li>
        </ul>
      </section>

      <section>
        <h2 className="font-display text-xl font-bold">
          <code>popInterstitial</code>
        </h2>
        <p className="mt-2 text-sm leading-relaxed text-paper-dim">
          A smaller overlay window shown on top of your existing UI without fully replacing it — the user can see, but not interact with, the
          app behind it.
        </p>
        <ul className="mt-3 list-disc space-y-2 pl-5 text-sm leading-relaxed text-paper-dim">
          <li>Doesn't take over navigation, but captures input until dismissed.</li>
          <li>Dismissible immediately — no minimum forced view time.</li>
          <li>Best trigger points: a moment you choose deliberately, such as app open or a specific in-app action.</li>
          <li>
            Resolves <code>"closed"</code> in the large majority of real usage; that is the expected outcome, not a failure state.
          </li>
        </ul>
      </section>

      <section>
        <h2 className="font-display text-xl font-bold">Choosing between them</h2>
        <div className="mt-3">
          <DocTable
            head={["", "interstitial", "popInterstitial"]}
            rows={[
              ["Screen coverage", "Full", "Partial overlay"],
              ["Minimum view time", "Yes", "No"],
              ["Best for", "Natural break points (level end, task complete)", "Publisher-chosen moments (app open, specific action)"],
              ["Typical resolve state", <code key="a">"completed"</code>, <code key="b">"closed"</code>],
            ]}
          />
        </div>
        <p className="mt-3 text-sm leading-relaxed text-paper-dim">
          If you're integrating only one format to start, <code>interstitial</code> at a natural transition point is the simpler and more
          predictable choice.
        </p>
      </section>

      <Callout tone="danger" title="What you cannot do">
        There is no way to skip the close control on <code>interstitial</code> beyond the fixed minimum view time, and no way to make{" "}
        <code>popInterstitial</code> non-dismissible. These constraints are intentional and identical for every publisher — they keep the ad
        experience predictable for end users across every Mini App running AdsKinz.
      </Callout>

      <NextPrev prev={{ to: "/docs/react-hook", label: "React Hook" }} next={{ to: "/docs/error-handling", label: "Error Handling" }} />
    </DocPage>
  );
}
