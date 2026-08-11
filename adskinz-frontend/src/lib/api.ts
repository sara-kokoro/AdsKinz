/**
 * Central API integration points.
 * The FastAPI backend (Koyeb) plugs in here. Everything below is mocked in
 * src/lib/mock-data.ts until the real endpoints are wired.
 */
export const API_BASE = import.meta.env["VITE_API_BASE"] ?? "competent-rebekkah-davelam-58380a6b.koyeb.app";

export const ENDPOINTS = {
  // Auth — email/password only. No fiat providers anywhere in the product.
  login: `${API_BASE}/auth/login`,
  register: `${API_BASE}/auth/register`,
  adminLogin: `${API_BASE}/admin/auth/login`,
  adminTotp: `${API_BASE}/admin/auth/totp`, // mandatory second factor for kingcey

  // Advertiser
  campaigns: `${API_BASE}/advertiser/campaigns`,
  campaignStats: `${API_BASE}/advertiser/stats`,
  // Groq-backed ad copy generation
  generateCopy: `${API_BASE}/advertiser/creatives/generate`,
  // Pre-generated campaign translations, stored at creation time.
  // No realtime translation call happens per impression.
  campaignTranslations: `${API_BASE}/advertiser/campaigns/:id/translations`,

  // Deposits — crypto only: USDT TON (memo tag), USDT TRC20, USDT BNB.
  // Deposit addresses are derived server-side per user.
  depositAddress: `${API_BASE}/billing/deposit-address`, // ?network=ton|trc20|bnb
  deposits: `${API_BASE}/billing/deposits`,

  // Publisher
  channels: `${API_BASE}/publisher/channels`,
  botAdminCheck: `${API_BASE}/publisher/channels/bot-status`,
  miniApps: `${API_BASE}/publisher/mini-apps`,
  kinzKey: `${API_BASE}/publisher/mini-apps/:id/key`,
  withdrawals: `${API_BASE}/publisher/withdrawals`,

  // Admin
  adminQueueCampaigns: `${API_BASE}/admin/queue/campaigns`,
  adminQueueChannels: `${API_BASE}/admin/queue/channels`,
  adminQueueMiniApps: `${API_BASE}/admin/queue/mini-apps`,
  adminQueueWithdrawals: `${API_BASE}/admin/queue/withdrawals`,
  adminFinances: `${API_BASE}/admin/finances`,
  adminAnomalies: `${API_BASE}/admin/anomalies`,
  adminAudit: `${API_BASE}/admin/audit`,
} as const;

/**
 * Mini App runtime: the SDK reads initData.user.language_code and asks the
 * backend for the creative already translated into that language.
 */
export const MINI_APP_SERVE = `${API_BASE}/sdk/serve`; // ?key=<kinz-id>&lang=<language_code>

/** Click tracking wrapper. Real redirect + budget decrement happen backend-side. */
export const trackingUrl = (id: string) => `adskinz.io/t/${id}`;
