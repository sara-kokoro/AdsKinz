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

export type Campaign = {
  id: string;
  name: string;
  language: string;
  status: CampaignStatus;
  format: "channel" | "interstitial" | "pop";
  cpm: number;
  budget: number;
  spent: number;
  clicks: number;
  impressions: number;
  rejectionReason?: string;
};

export const campaigns: Campaign[] = [
  { id: "cmp_8412", name: "TON Wallet — Q3 acquisition", language: "All languages", status: "active", format: "channel", cpm: 4.2, budget: 1800, spent: 1244, clicks: 3821, impressions: 296_400 },
  { id: "cmp_8377", name: "Kinza Games launch", language: "Russian", status: "active", format: "interstitial", cpm: 3.1, budget: 950, spent: 402, clicks: 1187, impressions: 129_600 },
  { id: "cmp_8290", name: "Airdrop season teaser", language: "English", status: "paused_balance", format: "pop", cpm: 2.0, budget: 500, spent: 486, clicks: 640, impressions: 243_000 },
  { id: "cmp_8188", name: "DEX referral push", language: "Chinese (Simplified)", status: "pending_review", format: "channel", cpm: 5.0, budget: 1200, spent: 0, clicks: 0, impressions: 0 },
  { id: "cmp_8103", name: "Staking promo — legacy", language: "French", status: "stopped", format: "channel", cpm: 2.8, budget: 300, spent: 300, clicks: 512, impressions: 107_100 },
  { id: "cmp_8044", name: "Casino affiliate blast", language: "English", status: "rejected", format: "channel", cpm: 6.0, budget: 900, spent: 0, clicks: 0, impressions: 0, rejectionReason: "Landing page redirects to an unrelated gambling domain." },
];

export type AdvertiserSubmission = {
  advertiser: { name: string; email: string; balance: number; createdAt: string; pastCampaigns: number };
  imageAlt: string;
  copy: string;
  buttonLabel: string;
  destinationUrl: string;
  trackingId: string;
  targeting: string;
  dailyBudget: number | null;
  submittedAt: string;
  ip: string;
};

export type QueueCampaign = Campaign & { submission: AdvertiserSubmission };

export const adminCampaignQueue: QueueCampaign[] = [
  {
    id: "cmp_8188", name: "DEX referral push", language: "Chinese (Simplified)", status: "pending_review",
    format: "channel", cpm: 5.0, budget: 1200, spent: 0, clicks: 0, impressions: 0,
    submission: {
      advertiser: { name: "Northline Labs", email: "ops@northline.xyz", balance: 3120.5, createdAt: "2026-04-11", pastCampaigns: 6 },
      imageAlt: "Dark gradient card with a trading chart and the DEX logotype",
      copy: "Swap on-chain with **zero routing fees** this month. Liquidity across 14 networks, settled in seconds.",
      buttonLabel: "Try now",
      destinationUrl: "https://northline.xyz/swap?ref=tg",
      trackingId: "t8188xq",
      targeting: "Chinese (Simplified)",
      dailyBudget: 150,
      submittedAt: "2026-08-01 18:42 UTC",
      ip: "185.24.60.11",
    },
  },
  {
    id: "cmp_8201", name: "Mini App retention loop", language: "All languages", status: "pending_review",
    format: "interstitial", cpm: 3.4, budget: 640, spent: 0, clicks: 0, impressions: 0,
    submission: {
      advertiser: { name: "Peakflow Studio", email: "hello@peakflow.app", balance: 812, createdAt: "2026-07-02", pastCampaigns: 1 },
      imageAlt: "Full-bleed screenshot of a puzzle mini app with a streak counter",
      copy: "Your streak is waiting. Come back for **three bonus rounds** and a free skin.",
      buttonLabel: "Play",
      destinationUrl: "https://t.me/peakflow_bot/app",
      trackingId: "t8201aa",
      targeting: "All languages",
      dailyBudget: null,
      submittedAt: "2026-08-02 04:10 UTC",
      ip: "91.108.4.77",
    },
  },
];

export type Channel = {
  id: string;
  name: string;
  subscribers: number;
  language: string;
  frequency: number;
  status: ChannelStatus;
  views30: number;
  earnings30: number;
  trustHoursLeft?: number;
  rejectionReason?: string;
};

export const channels: Channel[] = [
  { id: "ch_211", name: "Crypto Signals Daily", subscribers: 128_400, language: "English", frequency: 3, status: "active", views30: 1_940_000, earnings30: 2140.4 },
  { id: "ch_198", name: "Мемы и Рынки", subscribers: 41_200, language: "Russian", frequency: 2, status: "building_trust", views30: 88_000, earnings30: 96.2, trustHoursLeft: 39 },
  { id: "ch_180", name: "Airdrop Radar FR", subscribers: 12_800, language: "French", frequency: 1, status: "approved_not_started", views30: 0, earnings30: 0 },
  { id: "ch_164", name: "Trading Desk CN", subscribers: 9_400, language: "Chinese (Simplified)", frequency: 2, status: "pending_moderation", views30: 0, earnings30: 0 },
  { id: "ch_151", name: "NFT Flip Room", subscribers: 22_100, language: "English", frequency: 3, status: "suspended", views30: 310_000, earnings30: 412.8, rejectionReason: "@AdsKinzBot lost administrator rights on the channel." },
];

export type ChannelSubmission = {
  publisher: { name: string; email: string; createdAt: string; channels: number; lifetimeEarnings: number };
  publicLink: string;
  inviteLink: string;
  adminUsername: string;
  botIsAdmin: boolean;
  slots: string[];
  submittedAt: string;
  ip: string;
  description: string;
};

export type QueueChannel = Channel & { submission: ChannelSubmission };

export const adminChannelQueue: QueueChannel[] = [
  {
    id: "ch_164", name: "Trading Desk CN", subscribers: 9_400, language: "Chinese (Simplified)",
    frequency: 2, status: "pending_moderation", views30: 0, earnings30: 0,
    submission: {
      publisher: { name: "Wen Hao", email: "wenhao@tradingdesk.cn", createdAt: "2026-06-19", channels: 2, lifetimeEarnings: 318.9 },
      publicLink: "https://t.me/tradingdesk_cn",
      inviteLink: "https://t.me/+Xh2kQ0dVvE1jZTVk",
      adminUsername: "@wenhao_td",
      botIsAdmin: true,
      slots: ["09:00 UTC", "15:00 UTC"],
      submittedAt: "2026-08-01 22:07 UTC",
      ip: "203.0.113.42",
      description: "Daily intraday setups and macro notes for CN-speaking futures traders.",
    },
  },
  {
    id: "ch_170", name: "Solana Alpha Room", subscribers: 6_120, language: "English",
    frequency: 3, status: "pending_moderation", views30: 0, earnings30: 0,
    submission: {
      publisher: { name: "Marek Doyle", email: "marek@alpharoom.io", createdAt: "2026-07-28", channels: 1, lifetimeEarnings: 0 },
      publicLink: "https://t.me/solana_alpha_room",
      inviteLink: "https://t.me/+9qLmR3nTbA0xNjM0",
      adminUsername: "@marekdoyle",
      botIsAdmin: false,
      slots: [],
      submittedAt: "2026-08-02 01:55 UTC",
      ip: "45.83.220.9",
      description: "Early-stage Solana project coverage, 4 posts a day.",
    },
  },
];

export type MiniApp = {
  id: string;
  name: string;
  url: string;
  formats: ("interstitial" | "pop")[];
  status: MiniAppStatus;
  views30: number;
  earnings30: number;
  kinzKey: string;
};

export const miniApps: MiniApp[] = [
  { id: "ma_44", name: "TapForge", url: "https://t.me/tapforge_bot/app", formats: ["interstitial", "pop"], status: "active", views30: 740_000, earnings30: 902.1, kinzKey: "kinz_live_9f2c41ab" },
  { id: "ma_51", name: "Puzzle Kingdom", url: "https://t.me/puzzlekingdom_bot/app", formats: ["pop"], status: "pending_moderation", views30: 0, earnings30: 0, kinzKey: "kinz_test_18de77c0" },
];

export type MiniAppSubmission = {
  publisher: { name: string; email: string; createdAt: string; lifetimeEarnings: number };
  category: string;
  directLink: string;
  originalLink: string;
  botId: string;
  monthlyActiveUsers: number;
  integrationDetected: boolean;
  sdkVersion: string;
  submittedAt: string;
  ip: string;
  description: string;
};

export type QueueMiniApp = MiniApp & { submission: MiniAppSubmission };

export const adminMiniAppQueue: QueueMiniApp[] = [
  {
    id: "ma_51", name: "Puzzle Kingdom", url: "https://t.me/puzzlekingdom_bot/app",
    formats: ["pop"], status: "pending_moderation", views30: 0, earnings30: 0, kinzKey: "kinz_test_18de77c0",
    submission: {
      publisher: { name: "Ana Ruiz", email: "ana@puzzlekingdom.gg", createdAt: "2026-05-30", lifetimeEarnings: 44.2 },
      category: "Casual game",
      directLink: "https://t.me/puzzlekingdom_bot/app",
      originalLink: "https://puzzlekingdom.gg",
      botId: "7734120988",
      monthlyActiveUsers: 62_000,
      integrationDetected: true,
      sdkVersion: "kinz-sdk 1.4.2",
      submittedAt: "2026-08-01 12:31 UTC",
      ip: "88.12.44.190",
      description: "Match-3 mini app, pop interstitial requested between levels only.",
    },
  },
  {
    id: "ma_58", name: "Coin Runner", url: "https://t.me/coinrunner_bot/app",
    formats: ["interstitial", "pop"], status: "pending_moderation", views30: 0, earnings30: 0, kinzKey: "kinz_test_5b90ca31",
    submission: {
      publisher: { name: "Dario Neves", email: "dario@coinrunner.io", createdAt: "2026-07-18", lifetimeEarnings: 0 },
      category: "Arcade",
      directLink: "https://t.me/coinrunner_bot/app",
      originalLink: "https://coinrunner.io",
      botId: "8120044517",
      monthlyActiveUsers: 18_400,
      integrationDetected: false,
      sdkVersion: "—",
      submittedAt: "2026-08-06 09:20 UTC",
      ip: "94.140.8.16",
      description: "Endless runner, interstitial between runs and one pop on session start.",
    },
  },
];

export type Withdrawal = {
  id: string;
  publisher: string;
  publisherId: string;
  email: string;
  amount: number;
  method: "USDT TON";
  network: "TON";
  address: string;
  memo: string;
  requestedAt: string;
  processedAt?: string;
  txHash?: string;
  requestedAgoHours: number;
  status: WithdrawalStatus;
  rejectionReason?: string;
};

export const withdrawals: Withdrawal[] = [
  { id: "wd_902", publisher: "Crypto Signals Daily", publisherId: "usr_2041", email: "ops@cryptosignals.io", amount: 1240.0, method: "USDT TON", network: "TON", address: "UQBk7f2mQpLd9xN1sVr4Ke0Zt3Ha7hZ2", memo: "binance-4471", requestedAt: "2026-08-07 03:12 UTC", requestedAgoHours: 2, status: "pending" },
  { id: "wd_901", publisher: "TapForge", publisherId: "usr_2088", email: "team@tapforge.gg", amount: 620.5, method: "USDT TON", network: "TON", address: "UQC1pR8vZq3Nb7Ld0Ms6Yc2Ef9Tm4Ke", memo: "", requestedAt: "2026-08-07 00:41 UTC", requestedAgoHours: 5, status: "pending" },
  { id: "wd_898", publisher: "Мемы и Рынки", publisherId: "usr_2113", email: "memy@markets.ru", amount: 96.2, method: "USDT TON", network: "TON", address: "UQAz5Hn2Wq8Kd1Rt7Bv3Lc0Xe6Pm9Tn0", memo: "okx-99120", requestedAt: "2026-08-06 19:05 UTC", requestedAgoHours: 11, status: "pending" },
  { id: "wd_889", publisher: "Airdrop Radar FR", publisherId: "usr_2150", email: "hello@airdropradar.fr", amount: 88.0, method: "USDT TON", network: "TON", address: "UQAz9Hn2Wq8Kd1Rt7Bv3Lc0Xe6Pm9Tn0", memo: "", requestedAt: "2026-08-06 08:22 UTC", requestedAgoHours: 21, status: "approved" },
  { id: "wd_884", publisher: "Trading Signaux", publisherId: "usr_2177", email: "contact@tradingsig.fr", amount: 210.4, method: "USDT TON", network: "TON", address: "UQDe4Kp1Xs7Mv2Nb9Rc3Th6Ld0Zq2Ppl", memo: "bybit-7712", requestedAt: "2026-08-05 14:47 UTC", processedAt: "2026-08-05 16:02 UTC", requestedAgoHours: 39, status: "approved" },
  { id: "wd_871", publisher: "NFT Flip Room", publisherId: "usr_2202", email: "flip@nftroom.io", amount: 310.0, method: "USDT TON", network: "TON", address: "UQDe2Kp1Xs7Mv2Nb9Rc3Th6Ld0Zq2Ppl", memo: "", requestedAt: "2026-08-04 10:31 UTC", processedAt: "2026-08-04 12:10 UTC", txHash: "a41f9c7d…8b2c", requestedAgoHours: 67, status: "paid" },
  { id: "wd_860", publisher: "Startup News", publisherId: "usr_2244", email: "desk@startupnews.fr", amount: 118.4, method: "USDT TON", network: "TON", address: "UQFm3Lp8Zx1Nd6Rv2Kc9Th4Ge0Bq7Wn5", memo: "kraken-2231", requestedAt: "2026-07-22 09:14 UTC", processedAt: "2026-07-22 11:40 UTC", txHash: "77de10ad…4f91", requestedAgoHours: 380, status: "paid" },
  { id: "wd_812", publisher: "Crypto Daily FR", publisherId: "usr_2261", email: "team@cryptodailyfr.com", amount: 248.2, method: "USDT TON", network: "TON", address: "UQGx7Rt2Mv9Kp4Nc1Ld8Zq3He6Bs0Yw2", memo: "", requestedAt: "2026-03-18 16:58 UTC", processedAt: "2026-03-18 18:30 UTC", txHash: "b9c210fe…7a03", requestedAgoHours: 3400, status: "paid" },
  { id: "wd_790", publisher: "Fast Cash Bot", publisherId: "usr_2290", email: "admin@fastcashbot.top", amount: 940.0, method: "USDT TON", network: "TON", address: "UQHh1Nq5Bd8Ks2Lv7Rc4Tm0Ze9Pw3Xa6", memo: "", requestedAt: "2026-08-03 22:09 UTC", processedAt: "2026-08-04 07:55 UTC", requestedAgoHours: 100, status: "rejected", rejectionReason: "Traffic flagged by anti-fraud: 82% of clicks from a single ASN." },
];

/* ---------- platform users (admin) ---------- */

export type PlatformUser = {
  id: string;
  name: string;
  email: string;
  telegram: string;
  role: "advertiser" | "publisher";
  status: "active" | "blocked";
  country: string;
  createdAt: string;
  lastSeen: string;
  ip: string;
  balance: number;
  lifetime: number;
  assets: number;
  note?: string;
};

export const platformUsers: PlatformUser[] = [
  { id: "usr_2041", name: "Crypto Signals Daily", email: "ops@cryptosignals.io", telegram: "@cryptosignals", role: "publisher", status: "active", country: "Estonia", createdAt: "2026-01-14", lastSeen: "2026-08-07 04:52 UTC", ip: "185.24.60.11", balance: 1240.0, lifetime: 8462.75, assets: 1 },
  { id: "usr_2088", name: "TapForge", email: "team@tapforge.gg", telegram: "@tapforge", role: "publisher", status: "active", country: "Poland", createdAt: "2026-04-08", lastSeen: "2026-08-07 02:31 UTC", ip: "91.108.4.77", balance: 620.5, lifetime: 3120.9, assets: 1 },
  { id: "usr_2113", name: "Мемы и Рынки", email: "memy@markets.ru", telegram: "@memymarkets", role: "publisher", status: "active", country: "Kazakhstan", createdAt: "2026-07-21", lastSeen: "2026-08-06 21:04 UTC", ip: "203.0.113.42", balance: 96.2, lifetime: 96.2, assets: 1 },
  { id: "usr_2290", name: "Fast Cash Bot", email: "admin@fastcashbot.top", telegram: "@fastcashbot", role: "publisher", status: "blocked", country: "Unknown", createdAt: "2026-07-30", lastSeen: "2026-08-04 07:12 UTC", ip: "45.83.220.9", balance: 0, lifetime: 940.0, assets: 2, note: "Blocked after anti-fraud score 0.94 on click patterns." },
  { id: "usr_3010", name: "Northline Labs", email: "ops@northline.xyz", telegram: "@northlineops", role: "advertiser", status: "active", country: "Singapore", createdAt: "2026-04-11", lastSeen: "2026-08-07 05:10 UTC", ip: "146.70.12.5", balance: 3120.5, lifetime: 24_800.0, assets: 6 },
  { id: "usr_3044", name: "Peakflow Studio", email: "hello@peakflow.app", telegram: "@peakflow", role: "advertiser", status: "active", country: "Portugal", createdAt: "2026-07-02", lastSeen: "2026-08-06 18:44 UTC", ip: "88.12.44.190", balance: 812.0, lifetime: 1240.0, assets: 1 },
  { id: "usr_3077", name: "Vegas Affiliates", email: "buy@vegasaff.click", telegram: "@vegasaff", role: "advertiser", status: "blocked", country: "Unknown", createdAt: "2026-06-02", lastSeen: "2026-08-01 20:58 UTC", ip: "196.20.44.7", balance: 0, lifetime: 900.0, assets: 3, note: "Repeated gambling redirects that breach the creative policy." },
];


export type Deposit = {
  id: string;
  amount: number;
  network: "USDT TON" | "USDT TRC20" | "USDT BNB";
  status: DepositStatus;
  date: string;
  txHash: string;
};

export const deposits: Deposit[] = [
  { id: "dp_551", amount: 500, network: "USDT TON", status: "confirmed", date: "2026-07-30", txHash: "a41f…8b2c" },
  { id: "dp_558", amount: 120, network: "USDT TRC20", status: "awaiting_confirmation", date: "2026-08-02", txHash: "c93e…10ad" },
];

export type Anomaly = {
  id: string;
  subject: string;
  kind: "campaign" | "channel";
  reason: string;
  detectedAt: string;
  score: number;
};

export const anomalies: Anomaly[] = [
  { id: "an_31", subject: "NFT Flip Room", kind: "channel", reason: "Click-through rate 11.4x the language median over 3 hours", detectedAt: "2026-08-01 23:14 UTC", score: 0.94 },
  { id: "an_29", subject: "Airdrop season teaser", kind: "campaign", reason: "82% of clicks from a single ASN within 12 minutes", detectedAt: "2026-08-01 09:02 UTC", score: 0.87 },
];

export type AuditEntry = { id: string; at: string; actor: string; action: string; target: string };

export const auditLog: AuditEntry[] = [
  { id: "au_1204", at: "2026-08-02 05:41 UTC", actor: "kingcey", action: "Approved withdrawal", target: "wd_871 — $88.00" },
  { id: "au_1203", at: "2026-08-02 05:12 UTC", actor: "kingcey", action: "Quarantined channel", target: "ch_151 NFT Flip Room" },
  { id: "au_1202", at: "2026-08-01 20:58 UTC", actor: "kingcey", action: "Rejected campaign", target: "cmp_8044 — Casino affiliate blast" },
  { id: "au_1201", at: "2026-08-01 17:30 UTC", actor: "kingcey", action: "Approved channel", target: "ch_198 Мемы и Рынки" },
];

export const advertiserSummary = {
  balance: 412.35,
  activeBudget: 4450,
  totalImpressions: 4_821_640,
  impressionsMonth: 1_284_900,
  clicks30: 3841,
  ctr: 0.42,
  spend: 12_480.9,
};

export const publisherSummary = {
  balance: 128.4,
  totalEarnings: 8462.75,
  ads30: 214,
  views30: 2_038_000,
  monthEarnings: 512.6,
  withdrawUnlockHours: 18,
};

export const financeSummary = {
  today: { profit: 1284.4, volume: 3669.7 },
  week: { profit: 8422.1, volume: 24_063.1 },
  month: { profit: 31_902.6, volume: 91_150.3 },
  year: { profit: 288_441.0, volume: 824_117.1 },
};

export const spark = (seed: number, n = 24) =>
  Array.from({ length: n }, (_, i) => 40 + Math.sin(i / 2.3 + seed) * 14 + (i * seed) % 11);

/* ---------- per-placement performance (publisher dashboard + detail views) ---------- */

export type PlacementStats = {
  id: string;
  name: string;
  kind: "channel" | "miniapp";
  impressions30: number;
  clicks30: number;
  earnings30: number;
  avgCpm: number;
  fillRate: number;
  connectedOn: string;
  lastAd: string;
  nextSlot: string;
  adsDelivered30: number;
  daily: number[];
  activity: { id: string; at: string; campaign: string; impressions: number; clicks: number; revenue: number }[];
};

export const placementStats: PlacementStats[] = [
  {
    id: "ch_211", name: "Crypto Signals Daily", kind: "channel",
    impressions30: 1_940_000, clicks30: 21_340, earnings30: 2140.4, avgCpm: 4.1, fillRate: 96,
    connectedOn: "2026-01-14", lastAd: "2026-08-02 09:00 UTC", nextSlot: "2026-08-02 18:00 UTC", adsDelivered30: 84,
    daily: spark(3, 30),
    activity: [
      { id: "dl_9001", at: "2026-08-02 09:00 UTC", campaign: "TON Wallet — Q3 acquisition", impressions: 41_200, clicks: 512, revenue: 168.9 },
      { id: "dl_8994", at: "2026-08-01 18:00 UTC", campaign: "Kinza Games launch", impressions: 38_400, clicks: 402, revenue: 119.0 },
      { id: "dl_8981", at: "2026-08-01 09:00 UTC", campaign: "DEX referral push", impressions: 40_100, clicks: 610, revenue: 200.5 },
    ],
  },
  {
    id: "ch_198", name: "Мемы и Рынки", kind: "channel",
    impressions30: 88_000, clicks30: 1210, earnings30: 96.2, avgCpm: 2.4, fillRate: 61,
    connectedOn: "2026-07-21", lastAd: "2026-08-01 15:00 UTC", nextSlot: "2026-08-02 15:00 UTC", adsDelivered30: 12,
    daily: spark(6, 30),
    activity: [
      { id: "dl_8890", at: "2026-08-01 15:00 UTC", campaign: "Kinza Games launch", impressions: 9800, clicks: 141, revenue: 23.5 },
    ],
  },
  {
    id: "ch_180", name: "Airdrop Radar FR", kind: "channel",
    impressions30: 0, clicks30: 0, earnings30: 0, avgCpm: 0, fillRate: 0,
    connectedOn: "2026-07-30", lastAd: "—", nextSlot: "—", adsDelivered30: 0,
    daily: spark(9, 30).map(() => 0),
    activity: [],
  },
  {
    id: "ch_164", name: "Trading Desk CN", kind: "channel",
    impressions30: 0, clicks30: 0, earnings30: 0, avgCpm: 0, fillRate: 0,
    connectedOn: "2026-08-01", lastAd: "—", nextSlot: "—", adsDelivered30: 0,
    daily: spark(11, 30).map(() => 0),
    activity: [],
  },
  {
    id: "ch_151", name: "NFT Flip Room", kind: "channel",
    impressions30: 310_000, clicks30: 8940, earnings30: 412.8, avgCpm: 3.2, fillRate: 44,
    connectedOn: "2026-03-02", lastAd: "2026-07-31 21:00 UTC", nextSlot: "—", adsDelivered30: 31,
    daily: spark(13, 30),
    activity: [
      { id: "dl_8712", at: "2026-07-31 21:00 UTC", campaign: "Airdrop season teaser", impressions: 21_400, clicks: 1980, revenue: 42.1 },
    ],
  },
  {
    id: "ma_44", name: "TapForge", kind: "miniapp",
    impressions30: 740_000, clicks30: 12_880, earnings30: 902.1, avgCpm: 2.9, fillRate: 92,
    connectedOn: "2026-04-08", lastAd: "2026-08-02 06:12 UTC", nextSlot: "—", adsDelivered30: 740,
    daily: spark(5, 30),
    activity: [
      { id: "dl_9012", at: "2026-08-02 06:12 UTC", campaign: "Mini App retention loop", impressions: 24_100, clicks: 388, revenue: 62.4 },
      { id: "dl_9004", at: "2026-08-01 20:41 UTC", campaign: "TON Wallet — Q3 acquisition", impressions: 30_050, clicks: 501, revenue: 88.2 },
    ],
  },
  {
    id: "ma_51", name: "Puzzle Kingdom", kind: "miniapp",
    impressions30: 0, clicks30: 0, earnings30: 0, avgCpm: 0, fillRate: 0,
    connectedOn: "2026-08-01", lastAd: "—", nextSlot: "—", adsDelivered30: 0,
    daily: spark(7, 30).map(() => 0),
    activity: [],
  },
];

export const statsFor = (id: string) => placementStats.find((p) => p.id === id);
