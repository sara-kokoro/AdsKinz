import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { Logo } from "@/components/dashboard-shell";
import { Btn, Field, FieldError, Quote, inputCls } from "@/components/kit";
import { LanguageSelect, ThemeToggle } from "@/components/controls";
import { useAuth, HOME_FOR_ROLE } from "@/lib/auth";
import { ApiError } from "@/lib/api";

export const Route = createFileRoute("/login")({
  head: () => ({
    meta: [
      { title: "Sign in — AdsKinz" },
      {
        name: "description",
        content:
          "Sign in to AdsKinz to launch Telegram campaigns as an advertiser or monetize channels and Mini Apps as a publisher.",
      },
      { property: "og:title", content: "Sign in — AdsKinz" },
      { property: "og:description", content: "Advertiser and publisher access to the AdsKinz workspaces." },
    ],
  }),
  component: LoginPage,
});

type Mode = "login" | "register";

type Step = "login" | "register" | "verify";

function LoginPage() {
  const { login, register, verifyEmail, resendVerification, token, role, ready } = useAuth();
  const navigate = useNavigate();
  const [mode, setMode] = useState<Mode>("login");
  const [step, setStep] = useState<Step>("login");
  const [accountRole, setAccountRole] = useState<"advertiser" | "publisher">("advertiser");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [passwordConfirm, setPasswordConfirm] = useState("");
  const [code, setCode] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [telegram, setTelegram] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [passwordConfirmError, setPasswordConfirmError] = useState<string | null>(null);
  const [countdown, setCountdown] = useState(0);

  useEffect(() => {
    if (ready && token && role) void navigate({ to: HOME_FOR_ROLE[role], replace: true });
  }, [ready, token, role, navigate]);

  useEffect(() => {
    if (countdown <= 0) return;
    const t = window.setInterval(() => setCountdown((c) => Math.max(0, c - 1)), 1000);
    return () => window.clearInterval(t);
  }, [countdown]);

  const startCountdown = () => setCountdown(60);

  const submitLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const nextRole = await login(email.trim(), password, accountRole);
      await navigate({ to: HOME_FOR_ROLE[nextRole], replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Please try again.");
    } finally {
      setBusy(false);
    }
  };

  const submitRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setPasswordConfirmError(null);
    if (password !== passwordConfirm) {
      setPasswordConfirmError("Passwords do not match.");
      return;
    }
    setBusy(true);
    try {
      await register({
        email: email.trim(),
        password,
        password_confirm: passwordConfirm,
        role: accountRole,
        ...(displayName.trim() ? { display_name: displayName.trim() } : {}),
        ...(telegram.trim() ? { telegram_username: telegram.trim() } : {}),
      });
      setStep("verify");
      startCountdown();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Please try again.");
    } finally {
      setBusy(false);
    }
  };

  const submitVerify = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const nextRole = await verifyEmail(email.trim(), code.trim());
      await navigate({ to: HOME_FOR_ROLE[nextRole], replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Invalid or expired code. Please try again.");
    } finally {
      setBusy(false);
    }
  };

  const onResend = async () => {
    if (countdown > 0) return;
    setBusy(true);
    setError(null);
    try {
      await resendVerification(email.trim());
      startCountdown();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not resend code.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen bg-ink">
      <header className="border-b border-seam">
        <div className="mx-auto flex min-h-16 max-w-6xl items-center gap-4 px-4">
          <Logo />
          <div className="ml-auto flex items-center gap-2">
            <LanguageSelect compact />
            <ThemeToggle />
          </div>
        </div>
      </header>

      <main className="mx-auto grid max-w-6xl gap-10 px-4 py-12 lg:grid-cols-2 lg:py-20">
        <div className="max-w-md">
          <h1 className="font-display text-3xl font-extrabold tracking-tight sm:text-4xl">
            {mode === "login" ? "Welcome back" : "Create your AdsKinz account"}
          </h1>
          <p className="mt-3 text-sm leading-relaxed text-paper-dim">
            One account, two workspaces: run native Telegram campaigns, or monetize your channels and Mini Apps and get
            paid in USDT.
          </p>
          <Quote tone="signal" label="No fiat, ever" className="mt-6">
            Deposits and payouts are USDT only — TON, TRC20 and BNB networks. Nothing else touches your balance.
          </Quote>
          <p className="mt-6 text-sm text-paper-dim">
            Building a Mini App?{" "}
            <Link to="/docs" className="font-semibold text-signal hover:underline">
              Read the Kinz-ID docs
            </Link>
          </p>
        </div>

        <div className="surface p-6 sm:p-8">
          {step !== "verify" && (
            <div className="mb-6 flex rounded-xl border border-seam p-1">
              {(["login", "register"] as Mode[]).map((m) => (
                <button
                  key={m}
                  type="button"
                  onClick={() => {
                    setMode(m);
                    setStep(m);
                    setError(null);
                  }}
                  className={`min-h-10 flex-1 rounded-lg text-sm font-bold transition-colors ${
                    mode === m ? "bg-panel-2 text-signal" : "text-paper-dim hover:text-paper"
                  }`}
                >
                  {m === "login" ? "Sign in" : "Sign up"}
                </button>
              ))}
            </div>
          )}

          {step === "verify" ? (
            <form onSubmit={submitVerify} className="space-y-4">
              <h2 className="font-display text-xl font-bold">Verify your email</h2>
              <p className="text-sm text-paper-dim">
                We sent a 6-digit code to <span className="font-semibold text-paper">{email}</span>. Enter it below to activate your account.
              </p>
              <Field label="Verification code">
                <input
                  type="text"
                  inputMode="numeric"
                  required
                  minLength={6}
                  maxLength={6}
                  pattern="\d{6}"
                  autoComplete="one-time-code"
                  value={code}
                  onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
                  className={inputCls()}
                  placeholder="000000"
                />
              </Field>
              {error && <FieldError>{error}</FieldError>}
              <Btn type="submit" disabled={busy || code.length !== 6} className="w-full">
                {busy ? "Please wait…" : "Verify and sign in"}
              </Btn>
              <button
                type="button"
                onClick={onResend}
                disabled={countdown > 0 || busy}
                className="w-full text-xs font-semibold text-paper-dim hover:text-paper disabled:opacity-50"
              >
                {countdown > 0 ? `Resend code in ${countdown}s` : "Resend code"}
              </button>
            </form>
          ) : (
            <form onSubmit={mode === "login" ? submitLogin : submitRegister} className="space-y-4">
              <div>
                <p className="mb-2 text-xs font-bold tracking-wide text-paper-dim uppercase">I am an</p>
                <div className="grid grid-cols-2 gap-2">
                  {(["advertiser", "publisher"] as const).map((r) => (
                    <button
                      key={r}
                      type="button"
                      onClick={() => setAccountRole(r)}
                      className={`min-h-11 rounded-xl border text-sm font-bold capitalize transition-colors ${
                        accountRole === r
                          ? "border-signal bg-signal-soft text-signal"
                          : "border-seam text-paper-dim hover:text-paper"
                      }`}
                    >
                      {r}
                    </button>
                  ))}
                </div>
              </div>

              <Field label="Email">
                <input
                  type="email"
                  required
                  autoComplete="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className={inputCls()}
                  placeholder="you@company.com"
                />
              </Field>

              <Field label="Password" hint={mode === "register" ? "At least 8 characters." : undefined}>
                <input
                  type="password"
                  required
                  minLength={8}
                  autoComplete={mode === "login" ? "current-password" : "new-password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className={inputCls()}
                  placeholder="••••••••"
                />
              </Field>

              {mode === "register" && (
                <Field label="Confirm password">
                  <input
                    type="password"
                    required
                    minLength={8}
                    autoComplete="new-password"
                    value={passwordConfirm}
                    onChange={(e) => {
                      setPasswordConfirm(e.target.value);
                      setPasswordConfirmError(null);
                    }}
                    className={inputCls()}
                    placeholder="••••••••"
                  />
                  <FieldError>{passwordConfirmError}</FieldError>
                </Field>
              )}

              {mode === "register" && (
                <>
                  <Field label="Display name" hint="Shown on your account and in moderation reviews.">
                    <input
                      value={displayName}
                      onChange={(e) => setDisplayName(e.target.value)}
                      className={inputCls()}
                      placeholder="Northline Labs"
                    />
                  </Field>
                  <Field label="Telegram username" hint="Used to reach you about moderation decisions.">
                    <input
                      value={telegram}
                      onChange={(e) => setTelegram(e.target.value)}
                      className={inputCls()}
                      placeholder="@yourhandle"
                    />
                  </Field>
                </>
              )}

              {error && <FieldError>{error}</FieldError>}

              <Btn type="submit" disabled={busy} className="w-full">
                {busy ? "Please wait…" : mode === "login" ? "Sign in" : "Create account"}
              </Btn>
            </form>
          )}

          <p className="mt-6 text-center text-xs text-paper-dim">
            Admin? <Link to="/kingcey" className="font-semibold text-signal hover:underline">Internal console</Link>
          </p>
        </div>
      </main>
    </div>
  );
}
