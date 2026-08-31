/** Response shapes returned by the AdsKinz API (decimals arrive as strings). */

export type Role = "advertiser" | "publisher" | "admin";

export type UserProfile = {
  id: string;
  email: string;
  role: Role;
  display_name: string | null;
  telegram_username: string | null;
  country: string | null;
  balance: string;
  created_at: string | null;
};

export type RegisterResponse = {
  email: string;
  message: string;
  requires_verification: boolean;
};

export type TokenResponse = {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  role: Role;
  user: UserProfile | null;
};

export type TokenRefreshResponse = {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  role: Role;
};

export type AdminRequestCodeResponse = {
  sent: boolean;
  expiresIn: number;
};

export type AdminSessionResponse = {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  role: string;
  admin_id: string;
  email: string;
};

export type Campaign = {
  id: string;
  name: string;
  language: string;
  status: string;
  format: string;
  cpm: string;
  budget: string;
  spent: string;
  clicks: number;
  impressions: number;
  rejectionReason: string | null;
  dailyBudget: string | null;
  destinationUrl: string | null;
  buttonLabel: string | null;
  title: string | null;
  brandName: string | null;
  copy: string | null;
  imageUrl: string | null;
  trackingId: string | null;
  createdAt: string | null;
  updatedAt: string | null;
  approvedAt: string | null;
  aiGenerated: boolean;
  remaining: string;
  ctr: number;
};

export type Paged<T> = { items: T[]; total: number };

export type AdvertiserStats = {
  balance: string;
  activeBudget: string;
  totalImpressions: number;
  impressionsMonth: number;
  clicks30: number;
  ctr: number;
  spend: string;
  activeCampaigns: number;
  pendingCampaigns: number;
  daily: number[];
};

export type CampaignTranslations = {
  campaign_id: string;
  source_language: string;
  generated: boolean;
  translations: { lang_code: string; translated_text: string; translated_button_label: string | null }[];
};

export type DepositAddress = {
  network: string;
  label: string;
  address: string;
  memo: string | null;
  memo_required: boolean;
  qr_payload: string;
  min_deposit: string;
  fee_usdt: string;
  fee_note: string | null;
  confirmations_required: number;
  warning: string;
};

export type Deposit = {
  id: string;
  network: string;
  networkLabel: string;
  amount: string | null;
  grossAmount: string | null;
  fee: string;
  status: string;
  txHash: string | null;
  address: string | null;
  memo: string | null;
  createdAt: string | null;
  confirmedAt: string | null;
};

export type DepositList = Paged<Deposit> & { balance: string };

export type Balance = {
  balance: string;
  activeBudget: string;
  lifetimeSpend: string;
  lowBalance: boolean;
  lowBalanceThreshold: string;
};

export type LedgerItem = {
  id: string;
  type: string;
  amount: string;
  balanceAfter: string | null;
  description: string | null;
  createdAt: string | null;
};

export type Channel = {
  id: string;
  name: string;
  language: string;
  subscribers: number;
  subscribersUpdatedAt: string | null;
  status: string;
  publicLink: string | null;
  privateLink: string | null;
  adminUsername: string | null;
  logoUrl: string | null;
  maxAdsPerDay: number;
  effectiveMaxAdsPerDay: number;
  preferredSlots: Record<string, number[]> | null;
  rejectionReason: string | null;
  botAdminVerified: boolean;
  trustHoursLeft: number;
  trustEndsAt: string | null;
  impressions: number;
  earnings: string;
  adsToday: number;
  createdAt: string | null;
  approvedAt: string | null;
  startedAt: string | null;
};

export type ChannelStats = {
  channelId: string;
  status: string;
  subscribers: number;
  subscribersUpdatedAt: string | null;
  lifetimeImpressions: number;
  lifetimeClicks: number;
  lifetimeEarnings: number;
  ctr: number;
  effectiveCpm: number;
  last24hImpressions: number;
  last24hClicks: number;
  last24hEarnings: number;
  adsToday: number;
  maxAdsPerDay: number;
  effectiveMaxAdsPerDay: number;
  livePostsCount: number;
  botAdminVerified: boolean;
  trustHoursLeft: number;
};

export type BotStatus = {
  botUsername: string;
  allVerified: boolean;
  items: {
    channelId: string;
    name: string;
    isAdmin: boolean;
    canPost: boolean;
    canDelete: boolean;
    checkedAt: string | null;
    error: string | null;
  }[];
};

export type MiniApp = {
  id: string;
  name: string;
  url: string;
  originalUrl: string | null;
  botId: string | null;
  botUsername: string | null;
  botVerificationEnabled: boolean;
  status: string;
  formats: string[];
  kinzKey: string | null;
  rejectionReason: string | null;
  integrationDetected: boolean;
  impressions: number;
  earnings: string;
  createdAt: string | null;
  archivedAt: string | null;
};

export type MiniAppKey = { id: string; kinzKey: string; snippet: string; docsUrl: string };

export type Withdrawal = {
  id: string;
  amount: string;
  address: string;
  memo: string | null;
  method: string;
  status: string;
  rejectionReason: string | null;
  txHash: string | null;
  requestedAt: string | null;
  paidAt: string | null;
};

export type WithdrawalList = Paged<Withdrawal> & {
  availableBalance: string;
  heldBalance: string;
  minimum: string;
  eligible: boolean;
  eligibleAt: string | null;
  ineligibleReason: string | null;
};

export type PublisherStats = {
  availableBalance: string;
  heldBalance: string;
  lifetimeEarnings: string;
  impressions30: number;
  clicks30: number;
  activeChannels: number;
  activeMiniApps: number;
  daily: number[];
};

export type AdminOverview = {
  pendingCampaigns: number;
  pendingChannels: number;
  pendingMiniApps: number;
  pendingWithdrawals: number;
  openAnomalies: number;
  activeCampaigns: number;
  activeChannels: number;
  advertisers: number;
  publishers: number;
  balanceOwedToPublishers: string;
  commissionToday: string;
};

export type Queue<T> = { items: T[]; total: number; counts: Record<string, number> };

export type Anomaly = {
  id: string;
  kind: string;
  subject: string;
  subjectId: string | null;
  reason: string;
  score: string;
  details: Record<string, unknown> | null;
  resolved: boolean;
  detectedAt: string | null;
};

export type AuditEntry = {
  id: string;
  actor: string;
  action: string;
  target: string | null;
  targetType: string | null;
  targetId: string | null;
  details: Record<string, unknown> | null;
  createdAt: string | null;
};

export type Finances = {
  period: string;
  periodStart: string;
  periodEnd: string;
  grossRevenue: string;
  commission: string;
  publisherShare: string;
  depositsTotal: string;
  withdrawalsPaid: string;
  withdrawalsPending: string;
  advertiserBalances: string;
  publisherLiabilities: string;
  netTreasury: string;
  impressions: number;
  clicks: number;
  activeCampaigns: number;
  activeChannels: number;
  series: { date: string; gross: string; commission: string; payouts: string }[];
  topAdvertisers: { id: string; label: string; amount: string; secondary: string | null }[];
  topPublishers: { id: string; label: string; amount: string; secondary: string | null }[];
};
