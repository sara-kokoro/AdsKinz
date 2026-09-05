import { useEffect, useRef, useState } from "react";

/**
 * A Lottie animation that loads and plays calmly:
 *  - The player library itself (a small custom element from a CDN) is only
 *    fetched the first time any LottieAnimation actually mounts, not on
 *    every page load — and only via a dynamic <script> tag, so it never
 *    blocks the initial page render.
 *  - The animation JSON only starts loading once the component scrolls
 *    into view (IntersectionObserver), not immediately on mount.
 *  - It plays through once, then pauses for a while before playing again —
 *    a slow "breathing" cadence rather than a tight infinite loop, so it
 *    reads as a quiet detail instead of something spinning constantly.
 *
 * Usage: <LottieAnimation src="/money-bag.json" className="h-16 w-16" />
 */

const PLAYER_SRC = "https://cdn.jsdelivr.net/npm/@lottiefiles/lottie-player@2.0.8/dist/lottie-player.js";
let playerScriptPromise: Promise<void> | null = null;

function loadPlayerScript(): Promise<void> {
  if (typeof window === "undefined") return Promise.resolve();
  if (customElements.get("lottie-player")) return Promise.resolve();
  if (playerScriptPromise) return playerScriptPromise;
  playerScriptPromise = new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = PLAYER_SRC;
    script.async = true;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error("lottie-player failed to load"));
    document.head.appendChild(script);
  });
  return playerScriptPromise;
}

// Narrow type for the custom element's relevant bits — the real element
// comes from the CDN script, this just describes what this file touches.
type LottiePlayerEl = HTMLElement & {
  load: (src: string) => void;
  play: () => void;
  addEventListener(type: "complete", listener: () => void): void;
  removeEventListener(type: "complete", listener: () => void): void;
};

export function LottieAnimation({
  src,
  className,
  pauseSeconds = 6,
}: {
  /** Path to the animation JSON, e.g. "/money-bag.json" (served from public/). */
  src: string;
  className?: string;
  /** How long to rest between plays. */
  pauseSeconds?: number;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const playerRef = useRef<LottiePlayerEl | null>(null);
  const [visible, setVisible] = useState(false);
  const [ready, setReady] = useState(false);

  // Only start doing any work once this element is actually on screen.
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setVisible(true);
          observer.disconnect();
        }
      },
      { rootMargin: "100px" },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (!visible) return;
    let cancelled = false;
    loadPlayerScript()
      .then(() => {
        if (!cancelled) setReady(true);
      })
      .catch(() => {
        /* Silent: the illustration is decorative, never worth an error state. */
      });
    return () => {
      cancelled = true;
    };
  }, [visible]);

  useEffect(() => {
    if (!ready) return;
    const player = playerRef.current;
    if (!player) return;

    let timer: ReturnType<typeof setTimeout> | undefined;
    const playOnceThenRest = () => {
      player.play();
    };
    const onComplete = () => {
      timer = setTimeout(playOnceThenRest, pauseSeconds * 1000);
    };
    player.addEventListener("complete", onComplete);
    playOnceThenRest();

    return () => {
      player.removeEventListener("complete", onComplete);
      if (timer) clearTimeout(timer);
    };
  }, [ready, pauseSeconds]);

  return (
    <div ref={containerRef} className={className}>
      {ready ? (
        // @ts-expect-error -- lottie-player is a web component registered by the CDN script, not a typed React element
        <lottie-player ref={playerRef} src={src} autoplay={false} loop={false} style={{ width: "100%", height: "100%" }} />
      ) : null}
    </div>
  );
}
