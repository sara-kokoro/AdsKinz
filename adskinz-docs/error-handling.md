# Error Handling

Every rejection from `.show()` includes a `code`. Handle all of them gracefully — an ad failing to show should never block or degrade your app's core functionality.

## `NO_FILL`

No eligible campaign was available for this Mini App, language, and format at the moment of the request. This is a normal, expected outcome, especially for newly-approved Mini Apps or less common language targets — not a bug in your integration.

**What to do:** treat exactly like a closed ad. Continue your app's flow without the ad.

```javascript
.catch((err) => {
  if (err.code === "NO_FILL") {
    proceedWithoutAd();
  }
})
```

## `NETWORK_ERROR`

The SDK couldn't reach AdsKinz's ad-serving endpoint — usually a connectivity issue on the user's device, rarely a problem on your end.

**What to do:** same as `NO_FILL` — proceed without the ad. Do not retry automatically in a loop; if you want to retry, do it on the next natural user action, not immediately.

## `NOT_INITIALIZED`

`.show()` was called before `init()` completed, or `init()` was never called with a valid `kinzId`. This one usually does indicate an integration bug on your side.

**What to do:** check that `window.AdsKinz.init()` runs before any `.show()` call, and that your `kinzId` is correct — copy it again from partner.adskinz.io if you're unsure.

## `RATE_LIMITED`

Your Mini App requested ads unusually frequently in a short window. This exists to protect the end-user experience and to keep AdsKinz's anti-fraud systems from flagging your Mini App as suspicious traffic.

**What to do:** if you see this during normal testing, you're likely calling `.show()` automatically or in a loop rather than on discrete user actions — see [ad-formats.md](/ad-formats.md) for guidance on trigger points. If you see it in production under normal usage, contact support — the limit may need adjusting for your app's traffic pattern.

## General principle

None of these error codes should ever be shown to the end user directly, and none of them should block the feature the ad was gating. The expected pattern everywhere is: attempt to show the ad, and whether it resolves or rejects, let the user continue.
