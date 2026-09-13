import { useState } from "react";
import { Link } from "react-router-dom";

import { ApiError, api } from "../api";
import {
  AuthShell,
  DevLink,
  Field,
  FormError,
  FormNote,
  SubmitButton,
  inputClass,
} from "../components/AuthShell";
import { usePageTitle } from "../hooks/usePageTitle";

/**
 * Request a password reset link.
 *
 * The success screen is shown for *any* well-formed address, including ones
 * with no account. That is not a bug being papered over: if this page said
 * "no such account", anyone could use it to work out which officers are on the
 * platform, which is exactly the list you would want before a phishing run.
 */
export function ForgotPassword() {
  usePageTitle("title.forgotPassword");

  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sent, setSent] = useState<{ message: string; devUrl: string | null } | null>(null);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const result = await api.forgotPassword(email.trim());
      setSent({ message: result.message, devUrl: result.dev_url });
    } catch (e) {
      setError(
        e instanceof ApiError ? e.message : "Could not send a reset link. Try again.",
      );
    } finally {
      setBusy(false);
    }
  }

  if (sent) {
    return (
      <AuthShell
        heading="Check your inbox"
        intro="If that address has an account, a reset link is on its way."
        footer={
          <Link to="/login" className="text-accent underline underline-offset-2">
            ← Back to sign in
          </Link>
        }
      >
        <p className="text-[13.5px] leading-relaxed text-ink-2">{sent.message}</p>
        <p className="mt-3 text-[12.5px] leading-relaxed text-ink-3">
          The link is valid for 2 hours and can be used once. Requesting another
          one invalidates this one.
        </p>
        {sent.devUrl && <DevLink url={sent.devUrl} label="Open the reset link" />}
      </AuthShell>
    );
  }

  return (
    <AuthShell
      heading="Reset your password"
      intro="Enter the address on your account and we will send you a link to choose a new password."
      footer={
        <>
          Remembered it?{" "}
          <Link to="/login" className="text-accent underline underline-offset-2">
            Sign in
          </Link>
        </>
      }
    >
      <form onSubmit={submit} noValidate>
        <Field id="forgot-email" label="Official email">
          <input
            id="forgot-email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            autoComplete="username"
            className={inputClass}
          />
        </Field>
        <SubmitButton busy={busy}>{busy ? "Sending…" : "Send reset link"}</SubmitButton>
        <FormError message={error} />
        <FormNote>
          You can also sign in with a one-time email code from the sign-in page,
          which needs no password at all.
        </FormNote>
      </form>
    </AuthShell>
  );
}
