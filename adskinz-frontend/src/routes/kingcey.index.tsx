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
  const { adminRequestCode, adminVerifyCode, token, role, ready } = useAuth();
  const navigate = useNavigate();
  const [step, setStep] = useState<"ask" | "verify">("ask");
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sentNotice, setSentNotice] = useState(false);

  useEffect(() => {
    if (ready && token && role === "admin") void navigate({ to: "/kingcey/overview", replace: true });
  }, [ready, token, role, navigate]);

  async function askCode() {
    setBusy(true);
    setError(null);
    try {
      await adminRequestCode();
      setStep("verify");
      setSentNotice(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not send the code. Try again.");
    } finally {
      setBusy(false);
    }
  }

  async function submitVerify(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await adminVerifyCode(code.trim(), password);
      await navigate({ to: "/kingcey/overview", replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Invalid or expired code/password.");
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
          {step === "ask" ? (
            <div className="space-y-4">
              {error && <FieldError>{error}</FieldError>}
              <Btn className="w-full" onClick={() => void askCode()} disabled={busy}>
                {busy ? "Sending…" : "Ask code"}
              </Btn>
            </div>
          ) : (
            <form className="space-y-4" onSubmit={submitVerify}>
              {sentNotice && (
                <p className="rounded-xl border border-seam bg-panel-2 px-3 py-2 text-xs text-paper-dim">
                  A code was emailed. It expires in 10 minutes and can only be used once.
                </p>
              )}
              <Field label="8-digit code">
                <input
                  className={`${inputCls()} num tracking-[0.3em]`}
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  maxLength={8}
                  value={code}
                  onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
                  required
                />
              </Field>
              <Field label="Console password">
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
              <Btn className="w-full" disabled={busy || code.length < 8 || !password}>
                {busy ? "Verifying…" : "Open console"}
              </Btn>
              <button
                type="button"
                className="w-full text-xs font-semibold text-paper-dim hover:text-paper"
                onClick={() => void askCode()}
                disabled={busy}
              >
                Ask a new code
              </button>
            </form>
          )}
        </div>

        <div className="mt-5">
          <Quote>The code and the console password are both required — either alone opens nothing.</Quote>
        </div>
      </div>
    </main>
  );
}

