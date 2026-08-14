# Ad Formats

Kinz-ID currently serves two Mini App ad formats. Both are requested and shown through the same `.show()` call described in [sdk-reference.md](/sdk-reference.md) — the format is fixed at `init()` time per controller.

## `interstitial`

A full-screen ad shown between two natural steps in your app's flow — for example, between finishing a task and seeing its result, or between levels in a game.

- Takes over the full viewport.
- Not user-dismissible before a short minimum view time; after that, a close control appears.
- Best trigger points: level transitions, loading screens you'd otherwise show a spinner on, post-action confirmations.
- Resolves `"completed"` once the minimum view time and any video content has finished, or `"closed"` if the user dismisses after the close control appears.

## `popInterstitial`

A smaller overlay window, shown on top of your existing UI without fully replacing it — the user can see (but not interact with) the app behind it.

- Non-blocking in the sense that it doesn't take over full navigation, but it does capture input until dismissed.
- Dismissible immediately — there is no minimum forced view time for this format.
- Best trigger points: a moment chosen deliberately by you as the publisher — for example, opening the app, or after a specific in-app action — rather than a hard transition point.
- Resolves `"closed"` in the large majority of real usage; do not treat `"closed"` as a failure state for this format, it's the expected normal outcome.

## Choosing between them

| | `interstitial` | `popInterstitial` |
|---|---|---|
| Screen coverage | Full | Partial overlay |
| Minimum view time | Yes | No |
| Best for | Natural break points (level end, task complete) | Publisher-chosen moments (app open, specific action) |
| Typical resolve state | `"completed"` | `"closed"` |

If you're only integrating one format to start, `interstitial` at a natural transition point is usually the simpler and more predictable choice — `popInterstitial` gives you more placement flexibility but expects you to already have a clear moment in mind for it.

## What you cannot do

There is no way to force an ad to skip the close control on `interstitial` beyond the fixed minimum view time, and no way to make `popInterstitial` non-dismissible. These constraints are intentional and consistent across all publishers — they exist to keep the ad experience predictable for end users across every Mini App running AdsKinz, not just yours.
