import { createFileRoute } from "@tanstack/react-router";
import { Callout, CodeBlock, DocPage, NextPrev } from "@/components/docs-kit";
import { SDK_SCRIPT_URL } from "@/lib/api";

export const Route = createFileRoute("/docs/react-hook")({
  head: () => ({
    meta: [
      { title: "React Hook — Kinz-ID SDK | AdsKinz" },
      {
        name: "description",
        content: "A ready-to-copy useAdsKinz hook for React, TanStack Start and Next.js Mini Apps, with SSR-safe guards and stable controller refs.",
      },
      { property: "og:title", content: "React Hook — Kinz-ID SDK | AdsKinz" },
      { property: "og:description", content: "Wrap window.AdsKinz in a hook that survives re-renders and server rendering." },
    ],
  }),
  component: ReactHook,
});

function ReactHook() {
  return (
    <DocPage
      title="React Hook"
      lede="For Mini Apps built with React (TanStack Start, Next.js, or plain Vite React), wrap the global window.AdsKinz object in a hook instead of calling it directly in components — the controller reference stays stable across re-renders and cleans up correctly."
    >
      <section>
        <h2 className="font-display text-xl font-bold">
          <code>useAdsKinz</code>
        </h2>
        <CodeBlock
          lang="typescript"
          code={`import { useCallback, useEffect, useRef } from "react";

interface UseAdsKinzOptions {
  kinzId: string;
  format: "interstitial" | "popInterstitial";
  onError?: (error: { code: string }) => void;
}

export function useAdsKinz({ kinzId, format, onError }: UseAdsKinzOptions) {
  const controllerRef = useRef<any>(undefined);

  useEffect(() => {
    if (typeof window === "undefined" || !window.AdsKinz) return;
    controllerRef.current = window.AdsKinz.init({ kinzId, format });
  }, [kinzId, format]);

  const showAd = useCallback(async () => {
    if (!controllerRef.current) {
      onError?.({ code: "NOT_INITIALIZED" });
      return;
    }
    try {
      return await controllerRef.current.show();
    } catch (error) {
      onError?.(error as { code: string });
    }
  }, [onError]);

  return showAd;
}`}
        />
      </section>

      <section>
        <h2 className="font-display text-xl font-bold">Usage in a component</h2>
        <CodeBlock
          lang="tsx"
          code={`function UnlockButton() {
  const showAd = useAdsKinz({
    kinzId: "kz_live_9f3a2c1b",
    format: "interstitial",
    onError: (err) => console.log("Ad skipped or unavailable:", err.code),
  });

  return (
    <button
      onClick={async () => {
        await showAd();
        unlockFeature(); // called whether the ad completed or was closed
      }}
    >
      Continue
    </button>
  );
}`}
        />
        <Callout tone="bounty" title="Never gate strictly on completed">
          Especially for <code>popInterstitial</code>, <code>"closed"</code> is the normal outcome. Let the user continue either way.
        </Callout>
      </section>

      <section>
        <h2 className="font-display text-xl font-bold">Loading the script in a React app</h2>
        <p className="mt-2 text-sm leading-relaxed text-paper-dim">
          The SDK ships as a script tag, not an npm package. Add it once in your root document or head component instead of injecting it per
          component:
        </p>
        <CodeBlock lang="html" code={`<script src="${SDK_SCRIPT_URL}" defer></script>`} />
        <p className="mt-3 text-sm leading-relaxed text-paper-dim">
          With server-side rendering (TanStack Start, Next.js), guard any direct reference to <code>window.AdsKinz</code> behind a{" "}
          <code>typeof window !== "undefined"</code> check, as the hook above already does — the SDK object does not exist during server
          rendering.
        </p>
      </section>

      <NextPrev prev={{ to: "/docs/sdk-reference", label: "SDK Reference" }} next={{ to: "/docs/ad-formats", label: "Ad Formats" }} />
    </DocPage>
  );
}
