/** TanStack Query wiring for every AdsKinz API surface used by the dashboards. */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "./api";
import type {
  AdminOverview,
  AdvertiserStats,
  Anomaly,
  AuditEntry,
  Balance,
  BotStatus,
  Campaign,
  CampaignTranslations,
  Channel,
  Deposit,
  DepositAddress,
  DepositList,
  Finances,
  LedgerItem,
  MiniApp,
  MiniAppKey,
  Paged,
  PublisherStats,
  Queue,
  UserProfile,
  Withdrawal,
  WithdrawalList,
} from "./types";

const list = <T,>(v: Paged<T> | undefined): T[] => v?.items ?? [];

/* ---------------------------------- account --------------------------------- */

export function useMe(enabled = true) {
  return useQuery({
    queryKey: ["me"],
    queryFn: () => apiFetch<UserProfile>("/auth/me"),
    enabled,
    retry: false,
  });
}

export function useUpdateProfile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: {
      display_name?: string | undefined;
      telegram_username?: string | undefined;
      country?: string | undefined;
    }) => apiFetch<UserProfile>("/auth/me", { method: "PATCH", body }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["me"] }),
  });
}

export function useChangePassword() {
  return useMutation({
    mutationFn: (body: { current_password: string; new_password: string }) =>
      apiFetch<{ message: string }>("/auth/password", { method: "POST", body }),
  });
}

/* -------------------------------- advertiser -------------------------------- */

export function useAdvertiserStats() {
  return useQuery({
    queryKey: ["advertiser", "stats"],
    queryFn: () => apiFetch<AdvertiserStats>("/advertiser/stats"),
  });
}

export function useCampaigns(status?: string) {
  return useQuery({
    queryKey: ["advertiser", "campaigns", status ?? "all"],
    queryFn: () =>
      apiFetch<Paged<Campaign>>(
        "/advertiser/campaigns",
        status && status !== "all" ? { query: { status } } : {},
      ),
    select: list<Campaign>,
  });
}

export function useCampaign(id: string) {
  return useQuery({
    queryKey: ["advertiser", "campaign", id],
    queryFn: () => apiFetch<Campaign>(`/advertiser/campaigns/${id}`),
    enabled: Boolean(id),
  });
}

export function useCampaignTranslations(id: string, enabled = true) {
  return useQuery({
    queryKey: ["advertiser", "campaign", id, "translations"],
    queryFn: () => apiFetch<CampaignTranslations>(`/advertiser/campaigns/${id}/translations`),
    enabled: Boolean(id) && enabled,
  });
}

export type CampaignCreateBody = {
  name: string;
  format: string;
  copy: string;
  button_label: string;
  destinationUrl: string;
  language: string;
  budget: number;
  dailyBudget?: number | null | undefined;
  cpm: number;
  imageUrl?: string | null | undefined;
  ai_generated?: boolean | undefined;
};

export function useCreateCampaign() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: CampaignCreateBody) =>
      apiFetch<Campaign>("/advertiser/campaigns", { method: "POST", body }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["advertiser"] }),
  });
}

export function useUpdateCampaign(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      apiFetch<Campaign>(`/advertiser/campaigns/${id}`, { method: "PATCH", body }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["advertiser"] }),
  });
}

export function useGenerateCopy() {
  return useMutation({
    mutationFn: (body: { brief: string; language: string; tone: string }) =>
      apiFetch<{ copy: string; model: string }>("/advertiser/creatives/generate", {
        method: "POST",
        body,
      }),
  });
}

export function useAdLanguages() {
  return useQuery({
    queryKey: ["advertiser", "languages"],
    queryFn: () => apiFetch<unknown>("/advertiser/languages"),
    staleTime: 60 * 60 * 1000,
  });
}

/* ---------------------------------- billing --------------------------------- */

export function useBalance() {
  return useQuery({ queryKey: ["billing", "balance"], queryFn: () => apiFetch<Balance>("/billing/balance") });
}

export function useDeposits(page = 1, pageSize = 10) {
  return useQuery({
    queryKey: ["billing", "deposits", page, pageSize],
    queryFn: () =>
      apiFetch<DepositList>("/billing/deposits", { query: { page, page_size: pageSize } }),
    placeholderData: (prev) => prev,
  });
}

export function useDepositAddress(network: string, enabled = true) {
  return useQuery({
    queryKey: ["billing", "deposit-address", network],
    queryFn: () => apiFetch<DepositAddress>("/billing/deposit-address", { query: { network } }),
    enabled: Boolean(network) && enabled,
  });
}

export function useVerifyDeposit() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (network: string) =>
      apiFetch<{ transfers_seen: number; deposits_created: number; deposits_confirmed: number; deposits_credited: number }>(
        "/billing/deposit-address/verify",
        { method: "POST", query: { network } },
      ),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["billing", "deposits"] });
      void qc.invalidateQueries({ queryKey: ["billing", "balance"] });
    },
  });
}

export function useLedger() {
  return useQuery({
    queryKey: ["billing", "ledger"],
    queryFn: () => apiFetch<Paged<LedgerItem>>("/billing/ledger"),
    select: list<LedgerItem>,
  });
}

export type { Deposit };

/* --------------------------------- publisher -------------------------------- */

export function usePublisherStats() {
  return useQuery({ queryKey: ["publisher", "stats"], queryFn: () => apiFetch<PublisherStats>("/publisher/stats") });
}

export function useChannels() {
  return useQuery({
    queryKey: ["publisher", "channels"],
    queryFn: () => apiFetch<Paged<Channel>>("/publisher/channels"),
    select: list<Channel>,
  });
}

export function useBotStatus(enabled = true) {
  return useQuery({
    queryKey: ["publisher", "bot-status"],
    queryFn: () => apiFetch<BotStatus>("/publisher/channels/bot-status"),
    enabled,
  });
}

export type ChannelCreateBody = {
  name: string;
  publicLink: string;
  privateLink: string;
  adminUsername: string;
  language: string;
  subscribers: number;
  maxAdsPerDay: number;
  preferredHours?: number[] | null | undefined;
  description?: string | null | undefined;
};

export function useCreateChannel() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: ChannelCreateBody) =>
      apiFetch<Channel>("/publisher/channels", { method: "POST", body }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["publisher"] }),
  });
}

export function useStartChannel() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      apiFetch<Channel>(`/publisher/channels/${id}/start`, { method: "POST" }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["publisher"] }),
  });
}

export function useUpdateChannel() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...body }: { id: string } & Record<string, unknown>) =>
      apiFetch<Channel>(`/publisher/channels/${id}`, { method: "PATCH", body }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["publisher"] }),
  });
}

export function useMiniApps() {
  return useQuery({
    queryKey: ["publisher", "mini-apps"],
    queryFn: () => apiFetch<Paged<MiniApp>>("/publisher/mini-apps"),
    select: list<MiniApp>,
  });
}

export function useCreateMiniApp() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: {
      name: string;
      url: string;
      formats: string[];
      category?: string | null | undefined;
      description?: string | null | undefined;
    }) => apiFetch<MiniApp>("/publisher/mini-apps", { method: "POST", body }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["publisher"] }),
  });
}

export function useMiniAppKey(id: string | null) {
  return useQuery({
    queryKey: ["publisher", "mini-app-key", id],
    queryFn: () => apiFetch<MiniAppKey>(`/publisher/mini-apps/${id}/key`),
    enabled: Boolean(id),
  });
}

export function useWithdrawals() {
  return useQuery({
    queryKey: ["publisher", "withdrawals"],
    queryFn: () => apiFetch<WithdrawalList>("/publisher/withdrawals"),
  });
}

export function useCreateWithdrawal() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { amount: number; address: string; memo?: string | null }) =>
      apiFetch<Withdrawal>("/publisher/withdrawals", { method: "POST", body }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["publisher"] }),
  });
}

/* ----------------------------------- admin ---------------------------------- */

export function useAdminOverview() {
  return useQuery({ queryKey: ["admin", "overview"], queryFn: () => apiFetch<AdminOverview>("/admin/overview") });
}

export function useAdminQueue<T = Record<string, unknown>>(
  kind: "campaigns" | "channels" | "mini-apps" | "withdrawals",
) {
  return useQuery({
    queryKey: ["admin", "queue", kind],
    queryFn: () => apiFetch<Queue<T>>(`/admin/queue/${kind}`),
  });
}

export function useModerate(kind: "campaigns" | "channels" | "mini-apps" | "withdrawals") {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      action,
      note,
      reason,
      txHash,
    }: {
      id: string;
      action: "approve" | "reject" | "mark-paid";
      note?: string | undefined;
      reason?: string | undefined;
      txHash?: string | undefined;
    }) => {
      const body =
        action === "approve"
          ? { note: note ?? null }
          : action === "reject"
            ? { reason: reason ?? "" }
            : { txHash: txHash ?? null };
      return apiFetch<{ id: string; status: string; message: string }>(
        `/admin/queue/${kind}/${id}/${action}`,
        { method: "POST", body },
      );
    },
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["admin"] }),
  });
}

export function useAdminFinances(period = "30d") {
  return useQuery({
    queryKey: ["admin", "finances", period],
    queryFn: () => apiFetch<Finances>("/admin/finances", { query: { period } }),
  });
}

export function useAnomalies() {
  return useQuery({
    queryKey: ["admin", "anomalies"],
    queryFn: () => apiFetch<Paged<Anomaly>>("/admin/anomalies"),
    select: list<Anomaly>,
  });
}

export function useResolveAnomaly() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      apiFetch<{ message: string }>(`/admin/anomalies/${id}/resolve`, { method: "POST" }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["admin"] }),
  });
}

export function useAudit() {
  return useQuery({
    queryKey: ["admin", "audit"],
    queryFn: () => apiFetch<Paged<AuditEntry>>("/admin/audit"),
    select: list<AuditEntry>,
  });
}

export function useBlockAccount() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      role,
      id,
      blocked,
      reason,
    }: {
      role: "advertiser" | "publisher";
      id: string;
      blocked: boolean;
      reason: string;
    }) =>
      apiFetch<{ message: string }>(`/admin/accounts/${role}/${id}/block`, {
        method: "POST",
        body: { blocked, reason },
      }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["admin"] }),
  });
}
