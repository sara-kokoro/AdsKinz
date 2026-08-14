# React Hook

For Mini Apps built with React (including TanStack Start, Next.js, or plain CRA/Vite React), wrap the global `window.AdsKinz` object in a hook instead of calling it directly in components — this keeps the controller reference stable across re-renders and cleans up correctly.

## `useAdsKinz`

```typescript
import { useCallback, useEffect, useRef } from "react";

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
}
```

## Usage in a component

```tsx
function UnlockButton() {
  const showAd = useAdsKinz({
    kinzId: "kz_live_9f3a2c1b",
    format: "interstitial",
    onError: (err) => console.log("Ad skipped or unavailable:", err.code),
  });

  return (
    <button
      onClick={async () => {
        await showAd();
        unlockFeature(); // called whether the ad completed or was closed —
                          // never gate the reward strictly behind "completed"
                          // for popInterstitial, see ad-formats.md
      }}
    >
      Continue
    </button>
  );
}
```

## Loading the script in a React app

Since the SDK is loaded via a `<script>` tag rather than an npm package, add it once in your root document (`index.html`, or your framework's document head component) rather than dynamically injecting it per-component:

```html
<script src="https://sdk.adskinz.io/js/kinz.min.js" defer></script>
```

If your Mini App uses server-side rendering (TanStack Start, Next.js), guard any direct reference to `window.AdsKinz` behind a `typeof window !== "undefined"` check, as the hook above already does — the SDK object doesn't exist during server rendering.
