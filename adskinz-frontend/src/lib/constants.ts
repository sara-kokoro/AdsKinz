/** Static product constants (no mock data): shared by advertiser & publisher UIs. */
export type CampaignStatus =
  | "pending_review"
  | "active"
  | "paused"
  | "paused_balance"
  | "stopped"
  | "rejected";
export type ChannelStatus =
  | "pending_moderation"
  | "approved_not_started"
  | "building_trust"
  | "active"
  | "suspended"
  | "rejected";
export type MiniAppStatus = "pending_moderation" | "active" | "suspended";
export type WithdrawalStatus = "pending" | "approved" | "paid" | "rejected";
export type DepositStatus = "awaiting_confirmation" | "confirmed";

/** Advertiser ad-copy cap — mirrors AD_TEXT_MAX_LENGTH in the backend's
 * app/schemas/advertiser.py. Kept well under Telegram's 1024-char photo
 * caption limit so the localised "#AdsKinz" footer always still fits. */
export const AD_TEXT_MAX_LENGTH = 900;

export const BUTTON_LABELS = [
  "Open", "View", "Learn more", "Join", "Play", "Shop now", "Download", "Get started",
  "Sign up", "Try now", "Claim now", "Watch", "Read more", "Subscribe", "Install",
  "Buy now", "Get offer", "Continue", "Explore", "Discover", "Register", "Book now",
  "Order now", "Start now", "Visit", "Connect wallet", "Claim airdrop", "Join channel",
  "Enter app", "Unlock", "Get bonus",
];

export const AD_LANGUAGES = [
  { code: "all", label: "All languages" },
  { code: "en", label: "English" },
  { code: "fr", label: "French" },
  { code: "ru", label: "Russian" },
  { code: "zh", label: "Chinese (Simplified)" },
  { code: "es", label: "Spanish" },
  { code: "pt", label: "Portuguese" },
  { code: "ar", label: "Arabic" },
  { code: "hi", label: "Hindi" },
  { code: "id", label: "Indonesian" },
  { code: "tr", label: "Turkish" },
  { code: "uk", label: "Ukrainian" },
];
