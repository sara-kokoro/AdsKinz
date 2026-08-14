# FAQ

**Do I need a different `kinzId` for each format?**
No — one `kinzId` identifies your Mini App as a whole. You create a separate `init()` call (a separate controller) per format, but they share the same `kinzId`.

**Can I test the SDK before my Mini App is approved?**
`.show()` will resolve with a `NO_FILL` error until your Mini App is approved on partner.adskinz.io — this lets you verify your integration code runs without errors before real ads are available.

**Does the SDK work outside of Telegram (a regular browser tab)?**
The SDK expects to run inside the Telegram Mini App environment, since it reads `window.Telegram.WebApp.initDataUnsafe` for language targeting. Outside that context, language detection falls back to English but the rest of the SDK still functions for testing purposes.

**How is revenue calculated and paid out?**
That's a publisher dashboard question, not an SDK one — see your earnings and withdrawal details at partner.adskinz.io, not in this developer documentation.

**Is there a way to preload an ad before calling `.show()`?**
Not in v1.0.0 — `.show()` requests and displays in one step. A separate preload method may be added in a future version if publisher demand justifies the added complexity.

**What happens if I call `init()` twice with the same format?**
Each call creates an independent controller. This isn't harmful, but it's unnecessary — reuse the same controller reference across your component instead of re-initializing.
