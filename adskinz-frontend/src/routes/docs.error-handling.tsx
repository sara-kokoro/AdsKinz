import { createFileRoute } from "@tanstack/react-router";
import { Callout, CodeBlock, DocPage, DocTable, NextPrev } from "@/components/docs-kit";

export const Route = createFileRoute("/docs/error-handling")({
  head: () => ({
    meta: [
      { title: "Error Handling — Kinz-ID SDK | AdsKinz" },
      {
        name: "description",
        content: "NO_FILL, NETWORK_ERROR, NOT_INITIALIZED and RATE_LIMITED: what each Kinz-ID rejection code means and exactly how to handle it.",
      },
      { property: "og:title", content: "Error Handling — Kinz-ID SDK | AdsKinz" },
      { property: "og:description", content: "Handle every .show() rejection gracefully so a missing ad never blocks your app." },
    ],
  }),
  component: ErrorHandling,
});

function ErrorHandling() {
  return (
    <DocPage
      title="Error Handling"
      lede="Every rejection from .show() includes a code. Handle all of them gracefully — an ad failing to show should never block or degrade your app's core functionality."
    >
      <DocTable
        head={["Code", "Meaning", "What to do"]}
        rows={[
          [<code key="a">NO_FILL</code>, "No eligible campaign for this Mini App, language and format right now.", "Treat like a closed ad; continue."],
          [<code key="b">NETWORK_ERROR</code>, "The SDK couldn't reach the ad-serving endpoint.", "Proceed without the ad; never retry in a loop."],
          [<code key="c">NOT_INITIALIZED</code>, "show() ran before init(), or the kinzId is invalid.", "Fix the integration order / re-copy the kinzId."],
          [<code key="d">RATE_LIMITED</code>, "Ads requested unusually frequently in a short window.", "Show ads on discrete user actions; contact support if it persists."],
        ]}
      />

      <section>
        <h2 className="font-display text-xl font-bold">
          <code>NO_FILL</code>
        </h2>
        <p className="mt-2 text-sm leading-relaxed text-paper-dim">
          No eligible campaign was available for this Mini App, language and format at the moment of the request. Normal and expected,
          especially for newly-approved Mini Apps or less common language targets — not a bug in your integration.
        </p>
        <CodeBlock
          lang="javascript"
          code={`.catch((err) => {
  if (err.code === "NO_FILL") {
    proceedWithoutAd();
  }
})`}
        />
      </section>

      <section>
        <h2 className="font-display text-xl font-bold">
          <code>NETWORK_ERROR</code>
        </h2>
        <p className="mt-2 text-sm leading-relaxed text-paper-dim">
          The SDK couldn't reach the AdsKinz ad-serving endpoint — usually connectivity on the user's device. Handle it like{" "}
          <code>NO_FILL</code>: proceed without the ad. Do not retry automatically in a loop; retry on the next natural user action instead.
        </p>
      </section>

      <section>
        <h2 className="font-display text-xl font-bold">
          <code>NOT_INITIALIZED</code>
        </h2>
        <p className="mt-2 text-sm leading-relaxed text-paper-dim">
          <code>.show()</code> was called before <code>init()</code> completed, or <code>init()</code> was never called with a valid{" "}
          <code>kinzId</code>. This one usually does indicate an integration bug: check that <code>window.AdsKinz.init()</code> runs before
          any <code>.show()</code> call, and re-copy your <code>kinzId</code> from the partner workspace if unsure.
        </p>
      </section>

      <section>
        <h2 className="font-display text-xl font-bold">
          <code>RATE_LIMITED</code>
        </h2>
        <p className="mt-2 text-sm leading-relaxed text-paper-dim">
          Your Mini App requested ads unusually frequently in a short window. This protects the end-user experience and keeps our anti-fraud
          systems from flagging your traffic. During testing it usually means <code>.show()</code> is being called automatically or in a
          loop. In production under normal usage, contact support — the limit may need adjusting for your traffic pattern.
        </p>
      </section>

      <Callout tone="signal" title="General principle">
        Never show these codes to the end user, and never let them block the feature the ad was gating. Attempt the ad, and whether it
        resolves or rejects, let the user continue.
      </Callout>

      <NextPrev prev={{ to: "/docs/ad-formats", label: "Ad Formats" }} next={{ to: "/docs/faq", label: "FAQ" }} />
    </DocPage>
  );
}
