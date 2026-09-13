import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { ApiError, api } from "../api";
import { useAuth } from "../auth";
import {
  AuthShell,
  Field,
  FormError,
  FormNote,
  PasswordMeter,
  SubmitButton,
  inputClass,
} from "../components/AuthShell";
import { usePageTitle } from "../hooks/usePageTitle";

/**
 * Choose a new password from a reset link.
 *
 * Succeeding signs the officer straight in — they have just proved control of
 * the mailbox and set the credential, so a login form immediately afterwards
 * asks them to retype what they typed two seconds ago.
 *
 * The confirmation field is checked here rather than server-side on purpose:
 * it guards against a typo, not against an attacker, and the API has no use for
 * a second copy of the password.
 */

const PASSWORD_MIN = 10;

export function ResetPassword() {
  usePageTitle("title.resetPassword");
  const [params] = useSearchParams();
  const token = params.get("token") ?? "";
  const navigate = useNavigate();
  const { signIn } = useAuth();

  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const mismatch = confirm.length > 0 && confirm !== password;
  const tooShort = password.length > 0 && password.length < PASSWORD_MIN;

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (password !== confirm) {
      setError("The two passwords do not match.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const { access_token } = await api.resetPassword(token, password);
      await signIn(access_token);
      navigate("/dashboard", { replace: true });
    } catch (e) {
      setError(
        e instanceof ApiError
          ? e.message
          : "Could not reset your password. The link may have expired.",
      );
    } finally {
      setBusy(false);
    }
  }

  if (!token) {
    return (
      <AuthShell
        heading="This link is incomplete"
        intro="The address is missing its reset token. Open the link from your email exactly as it was sent, or request a new one."
        footer={
          <Link to="/forgot-password" className="text-accent underline underline-offset-2">
            Request a new reset link
          </Link>
        }
      >
        <FormError message="No reset token found in this address." />
      </AuthShell>
    );
  }

  return (
    <AuthShell
      heading="Choose a new password"
      intro="This link can be used once. After you set a password, you will be signed in."
      footer={
        <Link to="/login" className="text-accent underline underline-offset-2">
          ← Back to sign in
        </Link>
      }
    >
      <form onSubmit={submit} noValidate>
        <Field id="reset-password" label="New password">
          <input
            id="reset-password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={PASSWORD_MIN}
            autoComplete="new-password"
            aria-describedby="reset-meter"
            className={inputClass}
          />
        </Field>
        <div id="reset-meter">
          <PasswordMeter value={password} minLength={PASSWORD_MIN} />
        </div>

        <div className="mt-4">
          <Field id="reset-confirm" label="Confirm new password">
            <input
              id="reset-confirm"
              type="password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              required
              autoComplete="new-password"
              aria-invalid={mismatch}
              className={`${inputClass} ${mismatch ? "border-critical" : ""}`}
            />
          </Field>
          {mismatch && (
            <p role="alert" className="mt-1.5 text-[11.5px] text-critical">
              These do not match.
            </p>
          )}
        </div>

        <SubmitButton busy={busy} disabled={tooShort || mismatch || !confirm}>
          {busy ? "Saving…" : "Set password and sign in"}
        </SubmitButton>

        <FormError message={error} />

        <FormNote>
          We will email you to confirm the change. If that message arrives and it
          was not you, contact your division administrator immediately.
        </FormNote>
      </form>
    </AuthShell>
  );
}
