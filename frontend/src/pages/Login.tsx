import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { ApiError, api } from "../api";
import { AuthDivider, GoogleSignIn } from "../components/GoogleSignIn";
import { PublicShell } from "../components/portal";
import { useAuth } from "../auth";
import { usePageTitle } from "../hooks/usePageTitle";
import { useT } from "../i18n";
import type { MessageKey } from "../i18n";

type Method = "password" | "otp" | "totp";

const METHODS: { id: Method; label: MessageKey; note: MessageKey | null }[] = [
  { id: "password", label: "login.method.password", note: null },
  { id: "otp", label: "login.method.otp", note: "login.methodNote.otp" },
  { id: "totp", label: "login.method.totp", note: "login.methodNote.totp" },
];

export function Login() {
  const t = useT();
  usePageTitle("title.signIn");

  const { signIn } = useAuth();
  const navigate = useNavigate();

  const [method, setMethod] = useState<Method>("password");
  const [email, setEmail] = useState("venkatesan@sankhya.gov.in");
  const [password, setPassword] = useState("Sankhya@2026");
  const [code, setCode] = useState("");
  const [devCode, setDevCode] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  // Asked at runtime so enabling Google is a server restart, not a rebuild.
  // Null while unknown, so the button never flashes in and out.
  const [googleClientId, setGoogleClientId] = useState<string | null>(null);

  useEffect(() => {
    api
      .authConfig()
      .then((config) => setGoogleClientId(config.google_client_id))
      .catch(() => setGoogleClientId(null));
  }, []);

  async function run(fn: () => Promise<{ access_token: string }>) {
    setBusy(true);
    setError(null);
    try {
      const { access_token } = await fn();
      await signIn(access_token);
      navigate("/dashboard");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not sign in. Try again.");
    } finally {
      setBusy(false);
    }
  }

  async function sendCode() {
    setBusy(true);
    setError(null);
    try {
      const result = await api.requestOtp(email);
      setDevCode(result.dev_code);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not send a code.");
    } finally {
      setBusy(false);
    }
  }

  const DEMO_ACCOUNTS = [
    ["Officer", "venkatesan@sankhya.gov.in"],
    ["Supervisor", "director.esd@sankhya.gov.in"],
    ["Subject expert", "sme@sankhya.gov.in"],
    ["Administrator", "admin@sankhya.gov.in"],
  ] as const;

  return (
    <PublicShell>
      <div className="mx-auto grid max-w-[980px] gap-6 px-4 py-10 sm:px-6 md:grid-cols-[minmax(0,1fr)_320px]">
      <div className="w-full">
        <nav aria-label="Breadcrumb" className="mb-2 text-[12.5px] text-ink-3">
          <Link to="/" className="text-accent hover:underline">Home</Link>
          <span className="mx-1.5">›</span>
          <span className="text-ink-2">{t("login.heading")}</span>
        </nav>
        <h1 className="text-[22px] font-semibold leading-tight text-ink">
          {t("login.heading")}
        </h1>
        <p className="mt-1 max-w-[56ch] text-[13.5px] leading-relaxed text-ink-2">
{t("login.intro")}
        </p>

        <div className="mt-5 rounded border border-rule bg-surface">
          {googleClientId && (
            <div className="border-b border-rule p-5 pb-0">
              <GoogleSignIn
                clientId={googleClientId}
                disabled={busy}
                onCredential={(credential) =>
                  run(() => api.signInWithGoogle(credential))
                }
              />
              <AuthDivider />
            </div>
          )}
          <div role="tablist" aria-label="Sign-in method" className="flex border-b border-rule">
            {METHODS.map((m) => (
              <button
                key={m.id}
                role="tab"
                aria-selected={method === m.id}
                onClick={() => {
                  setMethod(m.id);
                  setError(null);
                  setCode("");
                  setDevCode(null);
                }}
                className={`flex-1 px-3 py-2.5 text-[12.5px] transition-colors ${
                  method === m.id
                    ? "border-b-2 border-accent font-medium text-ink"
                    : "text-ink-3 hover:text-ink-2"
                }`}
              >
                {t(m.label)}
              </button>
            ))}
          </div>

          <div className="p-5">
            <label
              htmlFor="login-email"
              className="block text-[13px] font-semibold text-ink"
            >
              {t("login.email")}
            </label>
            <input
              id="login-email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="username"
              className="mt-1.5 w-full rounded border border-rule-strong bg-surface px-3 py-2 text-sm outline-none focus:border-accent"
            />

            {method === "password" && (
              <>
                <label
                  htmlFor="login-password"
                  className="mt-4 block text-[13px] font-semibold text-ink"
                >
                  {t("login.password")}
                </label>
                <input
                  id="login-password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoComplete="current-password"
                  onKeyDown={(e) =>
                    e.key === "Enter" && run(() => api.loginWithPassword(email, password))
                  }
                  className="mt-1.5 w-full rounded border border-rule-strong bg-surface px-3 py-2 text-sm outline-none focus:border-accent"
                />
                <button
                  disabled={busy}
                  onClick={() => run(() => api.loginWithPassword(email, password))}
                  className="mt-5 w-full rounded bg-accent px-4 py-2.5 text-sm font-semibold text-white hover:bg-accent-strong disabled:opacity-50"
                >
                  {busy ? t("login.submitting") : t("login.submit")}
                </button>
                <div className="mt-3 text-center">
                  <Link
                    to="/forgot-password"
                    className="text-[12.5px] text-ink-3 transition-colors hover:text-accent"
                  >
                    Forgotten your password?
                  </Link>
                </div>
              </>
            )}

            {method === "otp" && (
              <>
                <button
                  disabled={busy}
                  onClick={sendCode}
                  className="mt-4 w-full rounded border border-rule-strong px-4 py-2 text-sm text-ink-2 transition-colors hover:border-accent hover:text-accent disabled:opacity-50"
                >
                  {busy ? t("login.sending") : t("login.sendCode")}
                </button>

                {devCode && (
                  <div className="mt-3 border-l-2 border-brass bg-tint-brass px-3 py-2 text-[12.5px] text-ink-2">
                    <strong className="font-semibold text-ink">Development mode.</strong>{" "}
                    Your code is <span className="font-mono font-semibold">{devCode}</span>.
                    Email sending is off, so a demo never waits on a message arriving.
                  </div>
                )}

                <label
                  htmlFor="login-otp"
                  className="mt-4 block text-[13px] font-semibold text-ink"
                >
                  {t("login.code")}
                </label>
                <input
                  id="login-otp"
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  maxLength={6}
                  value={code}
                  onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
                  onKeyDown={(e) =>
                    e.key === "Enter" && run(() => api.verifyOtp(email, code))
                  }
                  className="tabular mt-1.5 w-full rounded border border-rule-strong bg-surface px-3 py-2 font-mono text-lg tracking-[0.3em] outline-none focus:border-accent"
                />
                <button
                  disabled={busy || code.length !== 6}
                  onClick={() => run(() => api.verifyOtp(email, code))}
                  className="mt-5 w-full rounded bg-accent px-4 py-2.5 text-sm font-semibold text-white hover:bg-accent-strong disabled:opacity-50"
                >
                  {t("login.verify")}
                </button>
              </>
            )}

            {method === "totp" && (
              <>
                <label
                  htmlFor="login-totp"
                  className="mt-4 block text-[13px] font-semibold text-ink"
                >
                  {t("login.codeFromApp")}
                </label>
                <input
                  id="login-totp"
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  maxLength={6}
                  value={code}
                  onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
                  onKeyDown={(e) =>
                    e.key === "Enter" && run(() => api.loginWithTotp(email, code))
                  }
                  className="tabular mt-1.5 w-full rounded border border-rule-strong bg-surface px-3 py-2 font-mono text-lg tracking-[0.3em] outline-none focus:border-accent"
                />
                <button
                  disabled={busy || code.length !== 6}
                  onClick={() => run(() => api.loginWithTotp(email, code))}
                  className="mt-5 w-full rounded bg-accent px-4 py-2.5 text-sm font-semibold text-white hover:bg-accent-strong disabled:opacity-50"
                >
                  Sign in
                </button>
              </>
            )}

            {(() => {
              const note = METHODS.find((m) => m.id === method)?.note;
              return note ? (
                <p className="mt-3 text-[12px] leading-relaxed text-ink-3">{t(note)}</p>
              ) : null;
            })()}

            {error && (
              <div role="alert" className="mt-4 rounded border border-critical/40 border-l-4 border-l-critical bg-tint-critical px-3 py-2 text-[13px] text-ink">
                {error}
              </div>
            )}
          </div>
        </div>

        <p className="mt-5 text-[13px] text-ink-2">
          New to SANKHYA?{" "}
          <Link to="/register" className="text-accent underline underline-offset-2">
            Create an account
          </Link>
        </p>

        <p className="mt-4 text-[12px] leading-relaxed text-ink-3">
{t("login.parichay")}
        </p>
      </div>

      <aside className="space-y-4">
        <section className="rounded border border-rule bg-surface">
          <h2 className="border-b border-rule bg-surface-2 px-4 py-2.5 text-[14px] font-semibold text-ink">
            Demonstration accounts
          </h2>
          <div className="p-4 text-[13px]">
            <p className="text-ink-2">
              Select an account to fill in its email. The password for all of them is{" "}
              <span className="font-semibold text-ink">Sankhya@2026</span>.
            </p>
            <ul className="mt-3 divide-y divide-rule rounded border border-rule">
              {DEMO_ACCOUNTS.map(([role, address]) => (
                <li key={address}>
                  <button
                    type="button"
                    onClick={() => {
                      setEmail(address);
                      setPassword("Sankhya@2026");
                      setMethod("password");
                      setError(null);
                    }}
                    className={`block w-full px-3 py-2 text-left hover:bg-tint-accent ${
                      email === address ? "bg-tint-accent" : ""
                    }`}
                  >
                    <span className="block font-semibold text-ink">{role}</span>
                    <span className="block truncate text-[12.5px] text-ink-3">{address}</span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        </section>
        <section className="rounded border border-rule bg-surface p-4 text-[12.5px] leading-relaxed text-ink-2">
          <h2 className="mb-1 text-[14px] font-semibold text-ink">Important</h2>
          <ul className="list-disc space-y-1 pl-4">
            <li>Never share your password or one-time code with anyone.</li>
            <li>Sign out after use on a shared computer.</li>
            <li>All records in this prototype are synthetic.</li>
          </ul>
        </section>
      </aside>
      </div>
    </PublicShell>
  );
}
