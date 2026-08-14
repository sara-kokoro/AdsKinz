# Quickstart

Get an ad showing in your Telegram Mini App in under 10 minutes.

## 1. Get a Kinz-ID

Register your Mini App at [partner.adskinz.io](https://partner.adskinz.io) → **Mini Apps** → **Add a Mini App**. Choose which formats to enable (`interstitial`, `popInterstitial`, or both). Once approved, you'll get a `kinzId` — a string that identifies your Mini App to AdsKinz. Keep it, you'll need it in step 2.

## 2. Load the SDK

Add this script tag to your Mini App's HTML, before your own application code:

```html
<script src="https://sdk.adskinz.io/js/kinz.min.js"></script>
```

## 3. Initialize a controller

```html
<script>
  const AdController = window.AdsKinz.init({
    kinzId: "your-kinz-id",
    format: "interstitial" // or "popInterstitial"
  });
</script>
```

## 4. Show an ad

Call `.show()` at a natural break point in your app's flow — after a level completes, before unlocking a feature, on a button tap. Never call it automatically on page load without user action; ads shown without a trigger point convert poorly and are more likely to be flagged by our anti-fraud system.

```javascript
button.addEventListener("click", () => {
  AdController.show()
    .then((result) => {
      // The user watched the ad through to completion (or closed a skippable one).
      // result.state tells you which — see error-handling.md for the full list.
      unlockFeature();
    })
    .catch((error) => {
      // No ad was available, or the user closed it early. Never punish the user
      // for a failed or skipped ad — treat it the same as if they'd declined.
      console.log("Ad not shown:", error.code);
    });
});
```

That's the whole integration for a basic case. For React apps, see [react-hook.md](/react-hook.md) instead of wiring the global object by hand.

## Testing before going live

Your Mini App must be added and approved in your AdsKinz dashboard before `.show()` will return real ads — until then, calls resolve with a `NO_FILL` error, which is expected and not a bug in your integration.
