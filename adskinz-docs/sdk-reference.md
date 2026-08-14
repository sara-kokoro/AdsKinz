# SDK Reference

## `window.AdsKinz.init(options)`

Creates and returns an ad controller for one placement. Call this once per format you use — if your Mini App shows both an interstitial and a pop interstitial at different points, create two controllers.

### Parameters

| Option | Type | Required | Description |
|---|---|---|---|
| `kinzId` | `string` | yes | The identifier issued when your Mini App was approved on partner.adskinz.io. |
| `format` | `"interstitial"` \| `"popInterstitial"` | yes | Which ad format this controller serves. Must be a format you enabled for this Mini App. |
| `debug` | `boolean` | no | When `true`, logs SDK lifecycle events to the console. Default `false`. |

### Returns

An `AdController` object with a single method, `.show()`.

```javascript
const AdController = window.AdsKinz.init({
  kinzId: "kz_live_9f3a2c1b",
  format: "interstitial"
});
```

---

## `AdController.show()`

Requests and displays one ad. Returns a Promise.

### Resolves with

```typescript
{
  state: "completed" | "closed"
}
```

- `"completed"` — the user watched the ad through to the end (or it was a non-skippable format that finished naturally).
- `"closed"` — the user actively closed the ad before it finished. For `popInterstitial`, this is a normal and expected outcome, not an error — the format is designed to be dismissible.

### Rejects with

```typescript
{
  code: "NO_FILL" | "NETWORK_ERROR" | "NOT_INITIALIZED" | "RATE_LIMITED"
}
```

See [error-handling.md](/error-handling.md) for what each code means and how to handle it.

### Behavior notes

- Calling `.show()` while an ad from the same controller is already showing is a no-op — the existing Promise from the first call is returned again, not a new request.
- The SDK automatically reads `window.Telegram.WebApp.initDataUnsafe.user.language_code` to request a creative already translated into the user's language. If that language isn't one of AdsKinz's four supported languages (English, French, Russian, Chinese), English is served as a fallback — this happens server-side, nothing to configure on your end.

---

## Events

For Mini Apps that want finer-grained lifecycle hooks than the Promise alone provides:

```javascript
AdController.on("show", () => { /* ad started rendering */ });
AdController.on("complete", () => { /* user finished watching */ });
AdController.on("close", () => { /* user dismissed early */ });
```

These are optional — most integrations only need the `.show()` Promise.
