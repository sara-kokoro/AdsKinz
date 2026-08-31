import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { useNavigate } from "@tanstack/react-router";
import { useQueryClient } from "@tanstack/react-query";
import { apiFetch, tokenStore, type Role } from "./api";
import type { AdminRequestCodeResponse, AdminSessionResponse, RegisterResponse, TokenRefreshResponse, TokenResponse, UserProfile } from "./types";

type AuthState = {
  ready: boolean;
  token: string | null;
  role: Role | null;
  user: UserProfile | null;
  login: (email: string, password: string, role: Exclude<Role, "admin">) => Promise<Role>;
  register: (input: {
    email: string;
    password: string;
    password_confirm: string;
    role: Exclude<Role, "admin">;
    display_name?: string;
    telegram_username?: string;
  }) => Promise<RegisterResponse>;
  verifyEmail: (email: string, code: string) => Promise<Role>;
  resendVerification: (email: string) => Promise<RegisterResponse>;
  adminRequestCode: () => Promise<AdminRequestCodeResponse>;
  adminVerifyCode: (code: string, password: string) => Promise<void>;
  logout: () => void;
  refresh: () => Promise<void>;
};

const AuthContext = createContext<AuthState | null>(null);

export const HOME_FOR_ROLE: Record<Role, string> = {
  advertiser: "/traffic",
  publisher: "/partner",
  admin: "/kingcey/overview",
};

function parseJwt(token: string): { exp?: number; role?: Role; sub?: string } | null {
  try {
    const payload = token.split(".")[1];
    if (!payload) return null;
    const json = atob(payload.replace(/-/g, "+").replace(/_/g, "/"));
    return JSON.parse(json) as { exp?: number; role?: Role; sub?: string };
  } catch {
    return null;
  }
}

function isTokenExpired(token: string, bufferSeconds = 60): boolean {
  const claims = parseJwt(token);
  if (!claims?.exp) return true;
  return Date.now() >= (claims.exp - bufferSeconds) * 1000;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [role, setRole] = useState<Role | null>(null);
  const [user, setUser] = useState<UserProfile | null>(null);
  const [ready, setReady] = useState(false);
  const qc = useQueryClient();

  const clearSession = useCallback(() => {
    tokenStore.clear();
    setToken(null);
    setRole(null);
    setUser(null);
    qc.clear();
  }, [qc]);

  const loadProfile = useCallback(async () => {
    try {
      const me = await apiFetch<UserProfile>("/auth/me");
      setUser(me);
      setRole(me.role);
      tokenStore.set(tokenStore.get() ?? "", tokenStore.getRefresh() ?? "", me.role);
    } catch {
      setUser(null);
    }
  }, []);

  const restoreSession = useCallback(async () => {
    const stored = tokenStore.get();
    const storedRole = tokenStore.role();
    const storedRefresh = tokenStore.getRefresh();

    if (!stored || !storedRefresh) {
      clearSession();
      setReady(true);
      return;
    }

    if (isTokenExpired(stored)) {
      try {
        const res = await apiFetch<TokenRefreshResponse>("/auth/refresh", {
          method: "POST",
          body: { refresh_token: storedRefresh },
          auth: false,
        });
        tokenStore.set(res.access_token, res.refresh_token, res.role);
        setToken(res.access_token);
        setRole(res.role);
        if (res.role !== "admin") {
          await apiFetch<UserProfile>("/auth/me").then(setUser).catch(() => setUser(null));
        }
        setReady(true);
        return;
      } catch {
        clearSession();
        setReady(true);
        return;
      }
    }

    setToken(stored);
    setRole(storedRole);
    if (storedRole && storedRole !== "admin") {
      await apiFetch<UserProfile>("/auth/me")
        .then((me) => {
          setUser(me);
          setRole(me.role);
        })
        .catch(() => setUser(null));
    }
    setReady(true);
  }, [clearSession]);

  useEffect(() => {
    void restoreSession();
  }, [restoreSession]);

  // ------------------------------------------------------------------------ #
  // Inactivity timeout: force logout after 20 minutes without user input.
  // The timer resets on keyboard, pointer and touch events, so an active user
  // is never kicked out. A 1-minute grace window is left before the access
  // token itself expires so the refresh interceptor can still run.
  // ------------------------------------------------------------------------ #
  useEffect(() => {
    if (typeof window === "undefined" || !token) return;

    const INACTIVE_MS = 20 * 60 * 1000; // 20 minutes
    let timer: number | undefined;

    const reset = () => {
      window.clearTimeout(timer);
      timer = window.setTimeout(() => {
        clearSession();
      }, INACTIVE_MS);
    };

    reset();
    const events = ["mousedown", "keydown", "touchstart", "scroll", "mousemove"];
    events.forEach((event) => window.addEventListener(event, reset, { passive: true }));

    return () => {
      window.clearTimeout(timer);
      events.forEach((event) => window.removeEventListener(event, reset));
    };
  }, [token, clearSession]);

  const applySession = useCallback(
    (accessToken: string, refreshToken: string, nextRole: Role, profile: UserProfile | null) => {
      tokenStore.set(accessToken, refreshToken, nextRole);
      setToken(accessToken);
      setRole(nextRole);
      setUser(profile);
      qc.clear();
    },
    [qc],
  );

  const login = useCallback(
    async (email: string, password: string, nextRole: Exclude<Role, "admin">) => {
      const res = await apiFetch<TokenResponse>("/auth/login", {
        method: "POST",
        body: { email, password, role: nextRole },
        auth: false,
      });
      applySession(res.access_token, res.refresh_token, res.role, res.user ?? null);
      return res.role;
    },
    [applySession],
  );

  const register = useCallback<AuthState["register"]>(
    async (input) => {
      return apiFetch<RegisterResponse>("/auth/register", {
        method: "POST",
        body: input,
        auth: false,
      });
    },
    [],
  );

  const verifyEmail = useCallback(
    async (email: string, code: string) => {
      const res = await apiFetch<TokenResponse>("/auth/verify-email", {
        method: "POST",
        body: { email, code },
        auth: false,
      });
      applySession(res.access_token, res.refresh_token, res.role, res.user ?? null);
      return res.role;
    },
    [applySession],
  );

  const resendVerification = useCallback(async (email: string) => {
    return apiFetch<RegisterResponse>("/auth/resend-verification", {
      method: "POST",
      body: { email },
      auth: false,
    });
  }, []);

  const adminRequestCode = useCallback(
    () =>
      apiFetch<AdminRequestCodeResponse>("/admin/auth/request-code", {
        method: "POST",
        auth: false,
      }),
    [],
  );

  const adminVerifyCode = useCallback(
    async (code: string, password: string) => {
      const res = await apiFetch<AdminSessionResponse>("/admin/auth/verify-code", {
        method: "POST",
        body: { code, password },
        auth: false,
      });
      applySession(res.access_token, res.refresh_token, "admin", null);
    },
    [applySession],
  );

  const logout = useCallback(() => {
    clearSession();
  }, [clearSession]);

  const refresh = useCallback(async () => {
    const storedRefresh = tokenStore.getRefresh();
    if (!storedRefresh) {
      clearSession();
      throw new Error("No refresh token.");
    }
    const res = await apiFetch<TokenRefreshResponse>("/auth/refresh", {
      method: "POST",
      body: { refresh_token: storedRefresh },
      auth: false,
    });
    applySession(res.access_token, res.refresh_token, res.role, user);
  }, [applySession, clearSession, user]);

  const value = useMemo<AuthState>(
    () => ({
      ready,
      token,
      role,
      user,
      login,
      register,
      verifyEmail,
      resendVerification,
      adminRequestCode,
      adminVerifyCode,
      logout,
      refresh,
    }),
    [ready, token, role, user, login, register, verifyEmail, resendVerification, adminRequestCode, adminVerifyCode, logout, refresh],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}

/**
 * Client-side guard for a workspace. Redirects to the matching sign-in screen
 * when no session is present. Returns false while the check is pending.
 */
export function useAuthGuard(expected: Role): boolean {
  const { ready, token, role } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (!ready) return;
    if (!token) {
      void navigate({ to: expected === "admin" ? "/kingcey" : "/login", replace: true });
      return;
    }
    if (role && role !== expected) {
      void navigate({ to: HOME_FOR_ROLE[role], replace: true });
    }
  }, [ready, token, role, expected, navigate]);

  return ready && Boolean(token) && (!role || role === expected);
}
