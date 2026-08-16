import { createFileRoute } from "@tanstack/react-router";
import { DocPage, NextPrev } from "@/components/docs-kit";
import { Panel } from "@/components/kit";

export const Route = createFileRoute("/docs/changelog")({
  head: () => ({
    meta: [
      { title: "Changelog — Kinz-ID SDK | AdsKinz" },
      { name: "description", content: "Release history of the Kinz-ID Mini App SDK, starting with v1.0.0: init(), show(), formats, languages and error codes." },
      { property: "og:title", content: "Changelog — Kinz-ID SDK | AdsKinz" },
      { property: "og:description", content: "What shipped in each version of the AdsKinz Mini App SDK." },
    ],
  }),
  component: Changelog,
});

function Changelog() {
  return (
    <DocPage title="Changelog" lede="Release history of the Kinz-ID Mini App SDK.">
      <Panel>
        <div className="flex items-center gap-3">
          <span className="num rounded-full bg-signal-soft px-3 py-1 text-sm font-bold text-signal">v1.0.0</span>
          <span className="text-sm font-semibold text-paper-dim">initial release</span>
        </div>
        <ul className="mt-4 list-disc space-y-2 pl-5 text-sm leading-relaxed text-paper-dim">
          <li>
            <code>window.AdsKinz.init(&#123; kinzId, format &#125;)</code>
          </li>
          <li>
            <code>.show()</code> supporting <code>interstitial</code> and <code>popInterstitial</code>
          </li>
          <li>
            Automatic language detection via Telegram <code>initData</code>, with server-side pre-translated creatives in English, French,
            Russian and Chinese
          </li>
          <li>
            Error codes: <code>NO_FILL</code>, <code>NETWORK_ERROR</code>, <code>NOT_INITIALIZED</code>, <code>RATE_LIMITED</code>
          </li>
        </ul>
      </Panel>
      <NextPrev prev={{ to: "/docs/faq", label: "FAQ" }} />
    </DocPage>
  );
}
