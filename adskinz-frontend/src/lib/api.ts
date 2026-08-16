/**
 * AdsKinz API client — production wiring against the FastAPI backend.
 * No mock data: every screen reads from these endpoints.
 */
export const API_BASE = (
  import.meta.env["VITE_API_BASE"] ??
  "https://competent-rebekkah-davelam-58380a6b.koyeb.app"
).replace(/\/$/, "");

const TOKEN_KEY = "adskinz.token";
const ROLE_KEY = "adskinz.role";

export type Role = "advertiser" | "publisher" | "admin";

export const tokenStore = {
  get(): string | null {
    if (typeof window === "undefined") return null;
    try {
      return window.localStorage.getItem(TOKEN_KEY);
    } catch {
      return null;
    }
  },
  role(): Role | null {
    if (typeof window === "undefined") return null;
    try {
      return window.localStorage.getItem(ROLE_KEY) as Role | null;
    } catch {
      return null;
    }
  },
  set(token: string, role: Role) {
    try {
      window.localStorage.setItem(TOKEN_KEY, token);
      window.localStorage.setItem(ROLE_KEY, role);
    } catch {
      /* storage unavailable */
    }
  },
  clear() {
    try {
      window.localStorage.removeItem(TOKEN_KEY);
      window.localStorage.removeItem(ROLE_KEY);
    } catch {
      /* storage unavailable */
    }
  },
};

export class ApiError extends Error {
  status: number;
  code?: string;
  constructor(message: string, status: number, code?: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    if (code) this.code = code;
  }
}

function messageFromBody(body: unknown, status: number): string {
  if (typeof body === "string" && body) return body;
  if (body && typeof body === "object") {
    const b = body as Record<string, unknown>;
    const detail = b["detail"] ?? b["message"] ?? b["error"];
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      const first = detail[0] as Record<string, unknown> | undefined;
      if (first && typeof first["msg"] === "string") return String(first["msg"]);
    }
  }
  if (status === 401) return "Your session expired. Please sign in again.";
  if (status === 403) return "You don't have access to this resource.";
  if (status === 404) return "Not found.";
  return `Request failed (${status}).`;
}

export type RequestOptions = {
  method?: "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
  body?: unknown;
  query?: Record<string, string | number | boolean | undefined | null>;
  token?: string | null;
  auth?: boolean;
  signal?: AbortSignal;
};

export async function apiFetch<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, query, auth = true, signal } = opts;

  const url = new URL(`${API_BASE}${path.startsWith("/") ? path : `/${path}`}`);
  if (query) {
    for (const [k, v] of Object.entries(query)) {
      if (v !== undefined && v !== null && v !== "") url.searchParams.set(k, String(v));
    }
  }

  const headers: Record<string, string> = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  const token = opts.token ?? (auth ? tokenStore.get() : null);
  if (token) headers["Authorization"] = `Bearer ${token}`;

  let res: Response;
  try {
    res = await fetch(url.toString(), {
      method,
      headers,
      ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
      ...(signal ? { signal } : {}),
    });
  } catch {
    throw new ApiError("Network error — the AdsKinz API is unreachable.", 0, "NETWORK_ERROR");
  }

  const text = await res.text();
  let parsed: unknown = null;
  if (text) {
    try {
      parsed = JSON.parse(text);
    } catch {
      parsed = text;
    }
  }

  if (!res.ok) {
    if (res.status === 401 && auth && typeof window !== "undefined" && tokenStore.get()) {
      tokenStore.clear();
    }
    const code =
      parsed && typeof parsed === "object"
        ? (((parsed as Record<string, unknown>)["code"] as string) ?? undefined)
        : undefined;
    throw new ApiError(messageFromBody(parsed, res.status), res.status, code);
  }

  return parsed as T;
}

/** Numeric fields come back as decimal strings from the API. */
export const num = (v: string | number | null | undefined, fallback = 0): number => {
  if (v === null || v === undefined || v === "") return fallback;
  const n = typeof v === "number" ? v : Number(v);
  return Number.isFinite(n) ? n : fallback;
};

/** Public click-tracking URL for a campaign tracking id. */
export const trackingUrl = (id: string) => `${API_BASE}/t/${id}`;

/** Kinz-ID Mini App SDK script URL served by the API. */
export const SDK_SCRIPT_URL = `${API_BASE}/sdk/kinz.js`;
