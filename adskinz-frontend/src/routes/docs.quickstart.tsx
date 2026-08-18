import { createFileRoute } from "@tanstack/react-router";
import { Callout, CodeBlock, DocPage, NextPrev } from "@/components/docs-kit";
import { SDK_SCRIPT_URL } from "@/lib/api";

export const Route = createFileRoute("/docs/quickstart")({
  head: () => ({
    meta: [
      { title: "Quickstart — Kinz-ID SDK | AdsKinz" },
      {
        name: "description",
        content: "Show your first AdsKinz ad in a Telegram Mini App in under 10 minutes: get a kinzId, load the SDK, init a controller, call show().",
      },
      { property: "og:title", content: "Quickstart — Kinz-ID SDK | AdsKinz" },
      { property: "og:description", content: "Four steps from zero to a live interstitial in your Telegram Mini App." },
    ],
  }),
  component: Quickstart,
});

function Quickstart() {
  return (
    <DocPage title="Quickstart" lede="Get an ad showing in your Telegram Mini App in under 10 minutes.">
      <section>
        <h2 className="font-display text-xl font-bold">1. Get a Kinz-ID</h2>
        <p className="mt-2 text-sm leading-relaxed text-paper-dim">
          Register your Mini App in the AdsKinz partner workspace → <strong className="text-paper">Mini Apps</strong> →{" "}
          <strong className="text-paper">Add a Mini App</strong>. Choose which formats to enable (<code>interstitial</code>,{" "}
          <code>popInterstitial</code>, or both). Once approved you receive a <code>kinzId</code> that identifies your Mini App to AdsKinz.
        </p>
      </section>

      <section>
        <h2 className="font-display text-xl font-bold">2. Load the SDK</h2>
        <p className="mt-2 text-sm leading-relaxed text-paper-dim">
          Add this script tag to your Mini App HTML, before your own application code:
        </p>
        <CodeBlock lang="html" code={`<script src="${SDK_SCRIPT_URL}"></script>`} />
      </section>

      <section>
        <h2 className="font-display text-xl font-bold">3. Initialize a controller</h2>
        <CodeBlock
          lang="html"
          code={`<script>
  const AdController = window.AdsKinz.init({
    kinzId: "your-kinz-id",
    format: "interstitial" // or "popInterstitial"
  });
</script>`}
        />
      </section>

      <section>
        <h2 className="font-display text-xl font-bold">4. Show an ad</h2>
        <p className="mt-2 text-sm leading-relaxed text-paper-dim">
          Call <code>.show()</code> at a natural break point in your flow — after a level completes, before unlocking a feature, on a button
          tap. Never call it automatically on page load without user action: ads shown without a trigger point convert poorly and are more
          likely to be flagged by our anti-fraud system.
        </p>
        <CodeBlock
          lang="javascript"
          code={`button.addEventListener("click", () => {
  AdController.show()
    .then((result) => {
      // result.state is "completed" or "closed"
      unlockFeature();
    })
    .catch((error) => {
      // No ad available, or the user closed it early.
      // Never punish the user for a failed or skipped ad.
      console.log("Ad not shown:", error.code);
    });
});`}
        />
      </section>

      <Callout tone="signal" title="Testing before going live">
        Your Mini App must be added and approved in your AdsKinz dashboard before <code>.show()</code> returns real ads — until then calls
        reject with <code>NO_FILL</code>, which is expected and not a bug in your integration.
      </Callout>

      <NextPrev prev={{ to: "/docs", label: "Overview" }} next={{ to: "/docs/sdk-reference", label: "SDK Reference" }} />
    </DocPage>
  );
}
