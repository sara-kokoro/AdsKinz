import { createFileRoute } from "@tanstack/react-router";
import { Callout, CodeBlock, DocPage, DocTable, NextPrev } from "@/components/docs-kit";

export const Route = createFileRoute("/docs/sdk-reference")({
  head: () => ({
    meta: [
      { title: "SDK Reference — Kinz-ID | AdsKinz" },
      {
        name: "description",
        content: "Full Kinz-ID SDK reference: window.AdsKinz.init() options, AdController.show() resolve and reject shapes, and lifecycle events.",
      },
      { property: "og:title", content: "SDK Reference — Kinz-ID | AdsKinz" },
      { property: "og:description", content: "init(), show(), events and error codes for the AdsKinz Mini App SDK." },
    ],
  }),
  component: SdkReference,
});

function SdkReference() {
  return (
    <DocPage title="SDK Reference" lede="Everything window.AdsKinz exposes: one init function, one controller method, and optional lifecycle events.">
      <section>
        <h2 className="font-display text-xl font-bold">
          <code>window.AdsKinz.init(options)</code>
        </h2>
        <p className="mt-2 text-sm leading-relaxed text-paper-dim">
          Creates and returns an ad controller for one placement. Call it once per format you use — if your Mini App shows both an
          interstitial and a pop interstitial at different points, create two controllers.
        </p>
        <h3 className="mt-5 font-display text-base font-bold">Parameters</h3>
        <div className="mt-2">
          <DocTable
            head={["Option", "Type", "Required", "Description"]}
            rows={[
              [<code key="a">kinzId</code>, <code key="b">string</code>, "yes", "The identifier issued when your Mini App was approved in the partner workspace."],
              [
                <code key="c">format</code>,
                <code key="d">"interstitial" | "popInterstitial"</code>,
                "yes",
                "Which ad format this controller serves. Must be a format you enabled for this Mini App.",
              ],
              [<code key="e">debug</code>, <code key="f">boolean</code>, "no", "When true, logs SDK lifecycle events to the console. Default false."],
            ]}
          />
        </div>
        <h3 className="mt-5 font-display text-base font-bold">Returns</h3>
        <p className="mt-2 text-sm leading-relaxed text-paper-dim">
          An <code>AdController</code> object with a single method, <code>.show()</code>.
        </p>
        <CodeBlock
          lang="javascript"
          code={`const AdController = window.AdsKinz.init({
  kinzId: "kz_live_9f3a2c1b",
  format: "interstitial"
});`}
        />
      </section>

      <section>
        <h2 className="font-display text-xl font-bold">
          <code>AdController.show()</code>
        </h2>
        <p className="mt-2 text-sm leading-relaxed text-paper-dim">Requests and displays one ad. Returns a Promise.</p>

        <h3 className="mt-5 font-display text-base font-bold">Resolves with</h3>
        <CodeBlock lang="typescript" code={`{\n  state: "completed" | "closed"\n}`} />
        <ul className="mt-3 list-disc space-y-2 pl-5 text-sm leading-relaxed text-paper-dim">
          <li>
            <code>"completed"</code> — the user watched the ad to the end (or a non-skippable format finished naturally).
          </li>
          <li>
            <code>"closed"</code> — the user closed the ad before it finished. For <code>popInterstitial</code> this is normal and expected,
            not an error: the format is designed to be dismissible.
          </li>
        </ul>

        <h3 className="mt-5 font-display text-base font-bold">Rejects with</h3>
        <CodeBlock lang="typescript" code={`{\n  code: "NO_FILL" | "NETWORK_ERROR" | "NOT_INITIALIZED" | "RATE_LIMITED"\n}`} />

        <h3 className="mt-5 font-display text-base font-bold">Behavior notes</h3>
        <ul className="mt-2 list-disc space-y-2 pl-5 text-sm leading-relaxed text-paper-dim">
          <li>
            Calling <code>.show()</code> while an ad from the same controller is already showing is a no-op — the existing Promise is
            returned again, not a new request.
          </li>
          <li>
            The SDK reads <code>window.Telegram.WebApp.initDataUnsafe.user.language_code</code> to request a creative already translated
            into the user's language. Unsupported languages fall back to English server-side — nothing to configure.
          </li>
        </ul>
      </section>

      <section>
        <h2 className="font-display text-xl font-bold">Events</h2>
        <p className="mt-2 text-sm leading-relaxed text-paper-dim">
          For finer-grained lifecycle hooks than the Promise alone provides:
        </p>
        <CodeBlock
          lang="javascript"
          code={`AdController.on("show", () => { /* ad started rendering */ });
AdController.on("complete", () => { /* user finished watching */ });
AdController.on("close", () => { /* user dismissed early */ });`}
        />
        <Callout tone="neutral" title="Optional">
          Most integrations only need the <code>.show()</code> Promise.
        </Callout>
      </section>

      <NextPrev prev={{ to: "/docs/quickstart", label: "Quickstart" }} next={{ to: "/docs/react-hook", label: "React Hook" }} />
    </DocPage>
  );
}
