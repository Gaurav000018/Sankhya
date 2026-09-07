import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { ApiError, api } from "../api";
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

  async function run(fn: () => Promise<{ access_token: string }>) {
    setBusy(true);
    setError(null);
    try {
      const { access_token } = await fn();
      await signIn(access_token);
      navigate("/");
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

  return (
    <div className="flex min-h-full items-center justify-center px-6 py-12">
      <div className="w-full max-w-[420px]">
        <div className="mb-7 flex items-center gap-2.5">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#8a6614" strokeWidth="1.8" strokeLinecap="round">
            <path d="M4 20V13" /><path d="M9.3 20V8" /><path d="M14.7 20V15" /><path d="M20 20V4" />
          </svg>
          <span className="font-serif text-[21px] font-semibold tracking-[0.08em]">SANKHYA</span>
        </div>

        <h1 className="font-serif text-[24px] font-semibold leading-tight">
          {t("login.heading")}
        </h1>
        <p className="mt-2 max-w-[46ch] text-[13.5px] leading-relaxed text-ink-2">
{t("login.intro")}
        </p>

        <div className="mt-7 border border-rule bg-surface">
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
              className="block text-[11px] font-semibold uppercase tracking-[0.07em] text-ink-3"
            >
              {t("login.email")}
            </label>
            <input
              id="login-email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="username"
              className="mt-1.5 w-full border border-rule-strong bg-surface px-3 py-2 text-sm outline-none focus:border-accent"
            />

            {method === "password" && (
              <>
                <label
                  htmlFor="login-password"
                  className="mt-4 block text-[11px] font-semibold uppercase tracking-[0.07em] text-ink-3"
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
                  className="mt-1.5 w-full border border-rule-strong bg-surface px-3 py-2 text-sm outline-none focus:border-accent"
                />
                <button
                  disabled={busy}
                  onClick={() => run(() => api.loginWithPassword(email, password))}
                  className="mt-5 w-full bg-accent px-4 py-2.5 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
                >
                  {busy ? t("login.submitting") : t("login.submit")}
                </button>
              </>
            )}

            {method === "otp" && (
              <>
                <button
                  disabled={busy}
                  onClick={sendCode}
                  className="mt-4 w-full border border-rule-strong px-4 py-2 text-sm text-ink-2 transition-colors hover:border-accent hover:text-ink disabled:opacity-50"
                >
                  {busy ? t("login.sending") : t("login.sendCode")}
                </button>

                {devCode && (
                  <div className="mt-3 border-l-2 border-brass bg-[#f6f4ee] px-3 py-2 text-[12.5px] text-ink-2">
                    <strong className="font-semibold text-ink">Development mode.</strong>{" "}
                    Your code is <span className="font-mono font-semibold">{devCode}</span>.
                    Email sending is off, so a demo never waits on a message arriving.
                  </div>
                )}

                <label
                  htmlFor="login-otp"
                  className="mt-4 block text-[11px] font-semibold uppercase tracking-[0.07em] text-ink-3"
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
                  className="tabular mt-1.5 w-full border border-rule-strong bg-surface px-3 py-2 font-mono text-lg tracking-[0.3em] outline-none focus:border-accent"
                />
                <button
                  disabled={busy || code.length !== 6}
                  onClick={() => run(() => api.verifyOtp(email, code))}
                  className="mt-5 w-full bg-accent px-4 py-2.5 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
                >
                  {t("login.verify")}
                </button>
              </>
            )}

            {method === "totp" && (
              <>
                <label
                  htmlFor="login-totp"
                  className="mt-4 block text-[11px] font-semibold uppercase tracking-[0.07em] text-ink-3"
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
                  className="tabular mt-1.5 w-full border border-rule-strong bg-surface px-3 py-2 font-mono text-lg tracking-[0.3em] outline-none focus:border-accent"
                />
                <button
                  disabled={busy || code.length !== 6}
                  onClick={() => run(() => api.loginWithTotp(email, code))}
                  className="mt-5 w-full bg-accent px-4 py-2.5 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
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
              <div className="mt-4 border-l-2 border-critical bg-surface px-3 py-2 text-[13px] text-ink-2">
                {error}
              </div>
            )}
          </div>
        </div>

        <p className="mt-5 text-[12px] leading-relaxed text-ink-3">
{t("login.parichay")}
        </p>
      </div>
    </div>
  );
}
