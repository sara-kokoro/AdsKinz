import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { useNavigate } from "@tanstack/react-router";
import { useQueryClient } from "@tanstack/react-query";
import { apiFetch, tokenStore, type Role } from "./api";
import type { AdminPartialTokenResponse, AdminSessionResponse, TokenResponse, UserProfile } from "./types";

type AuthState = {
  ready: boolean;
  token: string | null;
  role: Role | null;
  user: UserProfile | null;
  login: (email: string, password: string) => Promise<Role>;
  register: (input: {
    email: string;
    password: string;
    role: Exclude<Role, "admin">;
    display_name?: string;
    telegram_username?: string;
  }) => Promise<Role>;
  adminLogin: (email: string, password: string) => Promise<AdminPartialTokenResponse>;
  adminTotp: (partialToken: string, code: string) => Promise<void>;
  logout: () => void;
  refresh: () => Promise<void>;
};

const AuthContext = createContext<AuthState | null>(null);

export const HOME_FOR_ROLE: Record<Role, string> = {
  advertiser: "/traffic",
  publisher: "/partner",
  admin: "/kingcey/overview",
};

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [role, setRole] = useState<Role | null>(null);
  const [user, setUser] = useState<UserProfile | null>(null);
  const [ready, setReady] = useState(false);
  const qc = useQueryClient();

  const loadProfile = useCallback(async () => {
    try {
      const me = await apiFetch<UserProfile>("/auth/me");
      setUser(me);
      setRole(me.role);
      tokenStore.set(tokenStore.get() ?? "", me.role);
    } catch {
      setUser(null);
    }
  }, []);

  useEffect(() => {
    const stored = tokenStore.get();
    const storedRole = tokenStore.role();
    setToken(stored);
    setRole(storedRole);
    if (stored && storedRole !== "admin") {
      void loadProfile().finally(() => setReady(true));
    } else {
      setReady(true);
    }
  }, [loadProfile]);

  const applySession = useCallback(
    (accessToken: string, nextRole: Role, profile: UserProfile | null) => {
      tokenStore.set(accessToken, nextRole);
      setToken(accessToken);
      setRole(nextRole);
      setUser(profile);
      qc.clear();
    },
    [qc],
  );

  const login = useCallback(
    async (email: string, password: string) => {
      const res = await apiFetch<TokenResponse>("/auth/login", {
        method: "POST",
        body: { email, password },
        auth: false,
      });
      applySession(res.access_token, res.role, res.user ?? null);
      return res.role;
    },
    [applySession],
  );

  const register = useCallback<AuthState["register"]>(
    async (input) => {
      const res = await apiFetch<TokenResponse>("/auth/register", {
        method: "POST",
        body: input,
        auth: false,
      });
      applySession(res.access_token, res.role, res.user ?? null);
      return res.role;
    },
    [applySession],
  );

  const adminLogin = useCallback(
    (email: string, password: string) =>
      apiFetch<AdminPartialTokenResponse>("/admin/auth/login", {
        method: "POST",
        body: { email, password },
        auth: false,
      }),
    [],
  );

  const adminTotp = useCallback(
    async (partialToken: string, code: string) => {
      const res = await apiFetch<AdminSessionResponse>("/admin/auth/totp", {
        method: "POST",
        body: { partial_token: partialToken, code },
        auth: false,
      });
      applySession(res.access_token, "admin", null);
    },
    [applySession],
  );

  const logout = useCallback(() => {
    tokenStore.clear();
    setToken(null);
    setRole(null);
    setUser(null);
    qc.clear();
  }, [qc]);

  const value = useMemo<AuthState>(
    () => ({
      ready,
      token,
      role,
      user,
      login,
      register,
      adminLogin,
      adminTotp,
      logout,
      refresh: loadProfile,
    }),
    [ready, token, role, user, login, register, adminLogin, adminTotp, logout, loadProfile],
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
