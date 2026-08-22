/**
 * AdsKinz API client — production wiring against the FastAPI backend.
 * No mock data: every screen reads from these endpoints.
 */
export const API_BASE = (
  import.meta.env["VITE_API_URL"] ??
  import.meta.env["VITE_API_BASE"] ??
  "https://competent-rebekkah-davelam-58380a6b.koyeb.app"
).replace(/\/$/, "");

const TOKEN_KEY = "adskinz.token";
const REFRESH_KEY = "adskinz.refresh";
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
  getRefresh(): string | null {
    if (typeof window === "undefined") return null;
    try {
      return window.localStorage.getItem(REFRESH_KEY);
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
  set(token: string, refreshToken: string, role: Role) {
    try {
      window.localStorage.setItem(TOKEN_KEY, token);
      window.localStorage.setItem(REFRESH_KEY, refreshToken);
      window.localStorage.setItem(ROLE_KEY, role);
    } catch {
      /* storage unavailable */
    }
  },
  clear() {
    try {
      window.localStorage.removeItem(TOKEN_KEY);
      window.localStorage.removeItem(REFRESH_KEY);
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

    // FastAPI / Pydantic standard 422: { "detail": [{ "msg": "..." }] }
    if (Array.isArray(detail)) {
      const first = detail[0] as Record<string, unknown> | undefined;
      const msg = first?.["msg"] ?? first?.["message"];
      if (typeof msg === "string") return String(msg);
    }

    // Custom backend shape: { "detail": { "message": "...", "fields": [...] } }
    if (detail && typeof detail === "object") {
      const d = detail as Record<string, unknown>;
      const fields = d["fields"];
      if (Array.isArray(fields) && fields.length > 0) {
        const firstField = fields[0] as Record<string, unknown> | undefined;
        const fieldName = firstField?.["field"];
        const fieldMsg = firstField?.["message"];
        if (typeof fieldMsg === "string") {
          return typeof fieldName === "string" && fieldName
            ? `${fieldName}: ${fieldMsg}`
            : fieldMsg;
        }
      }
      if (typeof d["message"] === "string") return d["message"];
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

let isRefreshing = false;
let refreshPromise: Promise<string> | null = null;
const refreshQueue: Array<(token: string | null) => void> = [];

async function doRefresh(): Promise<string> {
  const refresh = tokenStore.getRefresh();
  if (!refresh) {
    throw new ApiError("No refresh token available.", 401, "NO_REFRESH_TOKEN");
  }

  const res = await fetch(`${API_BASE}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify({ refresh_token: refresh }),
  });

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
    throw new ApiError(messageFromBody(parsed, res.status), res.status);
  }

  const data = parsed as Record<string, unknown>;
  const accessToken = String(data["access_token"] ?? "");
  const newRefresh = String(data["refresh_token"] ?? "");
  const role = String(data["role"] ?? tokenStore.role() ?? "advertiser") as Role;
  if (!accessToken || !newRefresh) {
    throw new ApiError("Invalid refresh response.", 401, "INVALID_REFRESH_RESPONSE");
  }
  tokenStore.set(accessToken, newRefresh, role);
  return accessToken;
}

async function refreshToken(): Promise<string> {
  if (isRefreshing && refreshPromise) {
    return refreshPromise;
  }
  isRefreshing = true;
  refreshPromise = doRefresh()
    .then((token) => {
      refreshQueue.forEach((resolve) => resolve(token));
      refreshQueue.length = 0;
      return token;
    })
    .catch((err) => {
      refreshQueue.forEach((resolve) => resolve(null));
      refreshQueue.length = 0;
      tokenStore.clear();
      throw err;
    })
    .finally(() => {
      isRefreshing = false;
      refreshPromise = null;
    });
  return refreshPromise;
}

function enqueueRefresh(): Promise<string | null> {
  return new Promise((resolve) => refreshQueue.push(resolve));
}

export async function uploadCreativeImage(file: File): Promise<{ url: string; name: string }> {
  const { upload_url, public_url } = await apiFetch<{ upload_url: string; public_url: string }>(
    "/advertiser/creatives/upload-url",
    { method: "POST", body: { contentType: file.type } },
  );
  const put = await fetch(upload_url, {
    method: "PUT",
    headers: { "Content-Type": file.type },
    body: file,
  });
  if (!put.ok) {
    throw new ApiError("Image upload failed — please try again.", put.status, "UPLOAD_FAILED");
  }
  return { url: public_url, name: file.name };
}

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

  if (res.status === 401 && auth && typeof window !== "undefined" && tokenStore.get()) {
    let newToken: string | null;
    if (isRefreshing) {
      newToken = await enqueueRefresh();
    } else {
      try {
        newToken = await refreshToken();
      } catch {
        newToken = null;
      }
    }
    if (newToken) {
      return apiFetch(path, { ...opts, token: newToken });
    }
    tokenStore.clear();
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
    let code: string | undefined;
    if (parsed && typeof parsed === "object") {
      const root = parsed as Record<string, unknown>;
      const detail = root["detail"];
      if (detail && typeof detail === "object") {
        code = ((detail as Record<string, unknown>)["code"] as string) ?? undefined;
      } else {
        code = (root["code"] as string) ?? undefined;
      }
    }
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
