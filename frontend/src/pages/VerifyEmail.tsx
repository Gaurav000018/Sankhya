import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { ApiError, api } from "../api";
import { useAuth } from "../auth";
import {
  AuthShell,
  DevLink,
  Field,
  FormError,
  FormNote,
  SubmitButton,
  inputClass,
} from "../components/AuthShell";
import { Spinner } from "../components/ui";
import { usePageTitle } from "../hooks/usePageTitle";

/**
 * Landing page for the confirmation link.
 *
 * Consuming the token signs the officer in: they have just proved control of
 * the mailbox, which is exactly what the email-OTP path proves. Bouncing them
 * to a login form to type a password they set ninety seconds ago adds a step
 * and no security.
 *
 * The token is burned on use, so this must fire **once**. React's StrictMode
 * runs effects twice in development, which without the guard below would send
 * the second request against an already-consumed token and show a failure on a
 * verification that actually succeeded.
 */
export function VerifyEmail() {
  usePageTitle("title.verify");
  const [params] = useSearchParams();
  const token = params.get("token") ?? "";
  const navigate = useNavigate();
  const { signIn } = useAuth();

  const [state, setState] = useState<"working" | "done" | "failed">(
    token ? "working" : "failed",
  );
  const [error, setError] = useState<string | null>(
    token ? null : "This link is missing its confirmation token.",
  );
  const attempted = useRef(false);

  useEffect(() => {
    if (!token || attempted.current) return;
    attempted.current = true;

    (async () => {
      try {
        const { access_token } = await api.verifyEmail(token);
        await signIn(access_token);
        setState("done");
        // Straight to the dashboard. A confirmed officer with no evidence yet
        // still sees their profile and the diagnostic that starts it off.
        navigate("/dashboard", { replace: true });
      } catch (e) {
        setError(
          e instanceof ApiError
            ? e.message
            : "Could not confirm this address. The link may have expired.",
        );
        setState("failed");
      }
    })();
  }, [token, signIn, navigate]);

  if (state === "working") {
    return (
      <AuthShell heading="Confirming your address" intro="One moment.">
        <Spinner label="Checking your confirmation link" />
      </AuthShell>
    );
  }

  if (state === "done") {
    return (
      <AuthShell heading="Address confirmed" intro="Taking you to your dashboard…">
        <Spinner label="Signing you in" />
      </AuthShell>
    );
  }

  return <ResendForm error={error} />;
}

/** Shown when a link has expired or been used. Offers a fresh one. */
function ResendForm({ error }: { error: string | null }) {
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState<{ message: string; devUrl: string | null } | null>(null);
  const [sendError, setSendError] = useState<string | null>(null);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setSendError(null);
    try {
      const result = await api.resendVerification(email.trim());
      setSent({ message: result.message, devUrl: result.dev_url });
    } catch (e) {
      setSendError(
        e instanceof ApiError ? e.message : "Could not send a new link. Try again.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthShell
      heading="This link is no longer valid"
      intro="Confirmation links expire after 24 hours and can only be used once. Enter your address and we will send a new one."
      footer={
        <>
          Already confirmed?{" "}
          <Link to="/login" className="text-accent underline underline-offset-2">
            Sign in
          </Link>
        </>
      }
    >
      <FormError message={error} />

      {sent ? (
        <>
          <FormNote>{sent.message}</FormNote>
          {sent.devUrl && <DevLink url={sent.devUrl} label="Open the new confirmation link" />}
        </>
      ) : (
        <form onSubmit={submit} className="mt-4" noValidate>
          <Field id="resend-email" label="Official email">
            <input
              id="resend-email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="username"
              className={inputClass}
            />
          </Field>
          <SubmitButton busy={busy}>
            {busy ? "Sending…" : "Send a new link"}
          </SubmitButton>
          <FormError message={sendError} />
        </form>
      )}
    </AuthShell>
  );
}
