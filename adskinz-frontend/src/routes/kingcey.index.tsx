import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { Logo } from "@/components/dashboard-shell";
import { Btn, Field, FieldError, Quote, inputCls } from "@/components/kit";
import { useAuth } from "@/lib/auth";
import { ApiError } from "@/lib/api";

export const Route = createFileRoute("/kingcey/")({
  head: () => ({
    meta: [
      { title: "Admin sign in — AdsKinz kingcey" },
      { name: "description", content: "Internal AdsKinz moderation and finance console." },
      { property: "og:title", content: "Admin sign in — AdsKinz kingcey" },
      { property: "og:description", content: "Internal console for moderation, payouts and anomalies." },
      { name: "robots", content: "noindex" },
    ],
  }),
  component: AdminSignIn,
});

function AdminSignIn() {
  const { adminLogin, adminTotp, token, role, ready } = useAuth();
  const navigate = useNavigate();
  const [step, setStep] = useState<"credentials" | "totp">("credentials");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [partialToken, setPartialToken] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (ready && token && role === "admin") void navigate({ to: "/kingcey/overview", replace: true });
  }, [ready, token, role, navigate]);

  async function submitCredentials(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await adminLogin(email.trim(), password);
      setPartialToken(res.partial_token);
      setStep("totp");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Sign in failed. Check your credentials.");
    } finally {
      setBusy(false);
    }
  }

  async function submitTotp(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await adminTotp(partialToken, code.trim());
      await navigate({ to: "/kingcey/overview", replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Invalid authentication code.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-ink px-4 py-14">
      <div className="w-full max-w-sm">
        <div className="flex items-center justify-center">
          <Logo />
        </div>
        <h1 className="mt-6 text-center font-display text-2xl font-extrabold tracking-tight">Internal console</h1>
        <p className="mt-1.5 text-center text-sm text-paper-dim">
          Staff access only. Every action is written to the audit trail.
        </p>

        <div className="mt-6 rounded-2xl border border-seam bg-panel p-5">
          {step === "credentials" ? (
            <form className="space-y-4" onSubmit={submitCredentials}>
              <Field label="Work email">
                <input
                  className={inputCls()}
                  type="email"
                  autoComplete="username"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                />
              </Field>
              <Field label="Password">
                <input
                  className={inputCls()}
                  type="password"
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                />
              </Field>
              {error && <FieldError>{error}</FieldError>}
              <Btn className="w-full" disabled={busy}>
                {busy ? "Checking…" : "Continue"}
              </Btn>
            </form>
          ) : (
            <form className="space-y-4" onSubmit={submitTotp}>
              <Field label="6-digit authenticator code">
                <input
                  className={`${inputCls()} num tracking-[0.4em]`}
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  maxLength={6}
                  value={code}
                  onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
                  required
                />
              </Field>
              {error && <FieldError>{error}</FieldError>}
              <Btn className="w-full" disabled={busy || code.length < 6}>
                {busy ? "Verifying…" : "Open console"}
              </Btn>
              <button
                type="button"
                className="w-full text-xs font-semibold text-paper-dim hover:text-paper"
                onClick={() => {
                  setStep("credentials");
                  setCode("");
                  setError(null);
                }}
              >
                Back to credentials
              </button>
            </form>
          )}
        </div>

        <div className="mt-5">
          <Quote>Two-factor authentication is mandatory for every admin session.</Quote>
        </div>
      </div>
    </main>
  );
}
