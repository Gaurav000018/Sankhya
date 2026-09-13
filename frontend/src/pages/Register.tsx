import { useState } from "react";
import { Link } from "react-router-dom";

import { ApiError, api } from "../api";
import {
  AuthShell,
  DevLink,
  Field,
  FormError,
  FormNote,
  PasswordMeter,
  SubmitButton,
  inputClass,
} from "../components/AuthShell";
import { usePageTitle } from "../hooks/usePageTitle";

/**
 * Self-registration for an officer of the statistical system.
 *
 * Division and FRAC role are not asked for. Every competency figure on the
 * platform is computed against the requirements of a role in a division, so
 * letting an applicant declare their own grade would put a self-assertion at
 * the root of a system whose entire premise is that competency is never
 * self-declared. An administrator assigns them after the address is confirmed,
 * and the page says so rather than leaving it a surprise.
 */

const PASSWORD_MIN = 10;

export function Register() {
  usePageTitle("title.register");

  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");
  const [serviceYears, setServiceYears] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState<{ message: string; devUrl: string | null } | null>(null);

  const tooShort = password.length > 0 && password.length < PASSWORD_MIN;

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const result = await api.register({
        email: email.trim(),
        full_name: fullName.trim(),
        password,
        service_years: Number(serviceYears) || 0,
      });
      setSent({ message: result.message, devUrl: result.dev_verify_url });
    } catch (e) {
      setError(
        e instanceof ApiError ? e.message : "Could not create the account. Try again.",
      );
    } finally {
      setBusy(false);
    }
  }

  // The confirmation screen never says whether the address was already taken —
  // the API does not tell us, on purpose.
  if (sent) {
    return (
      <AuthShell
        heading="Check your inbox"
        intro="Confirm your address to activate the account."
        footer={
          <>
            Wrong address?{" "}
            <button
              onClick={() => setSent(null)}
              className="text-accent underline underline-offset-2"
            >
              Go back and change it
            </button>
          </>
        }
      >
        <p className="text-[13.5px] leading-relaxed text-ink-2">{sent.message}</p>
        <p className="mt-3 text-[12.5px] leading-relaxed text-ink-3">
          The link is valid for 24 hours. If it does not arrive, check your spam
          folder — or{" "}
          <Link to="/login" className="text-accent underline underline-offset-2">
            request a new one from the sign-in page
          </Link>
          .
        </p>
        {sent.devUrl && <DevLink url={sent.devUrl} label="Open the confirmation link" />}
      </AuthShell>
    );
  }

  return (
    <AuthShell
      heading="Create your account"
      intro="For officers of India's Official Statistical System. Registration is limited to official government addresses."
      footer={
        <>
          Already registered?{" "}
          <Link to="/login" className="text-accent underline underline-offset-2">
            Sign in
          </Link>
        </>
      }
    >
      <form onSubmit={submit} noValidate>
        <Field id="reg-name" label="Full name">
          <input
            id="reg-name"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            required
            minLength={2}
            autoComplete="name"
            className={inputClass}
          />
        </Field>

        <div className="mt-4">
          <Field
            id="reg-email"
            label="Official email"
            hint="A gov.in or nic.in address. This is where your confirmation link goes."
          >
            <input
              id="reg-email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="username"
              placeholder="name@mospi.gov.in"
              className={inputClass}
            />
          </Field>
        </div>

        <div className="mt-4">
          <Field id="reg-password" label="Password">
            <input
              id="reg-password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={PASSWORD_MIN}
              autoComplete="new-password"
              aria-describedby="reg-password-meter"
              className={inputClass}
            />
          </Field>
          <div id="reg-password-meter">
            <PasswordMeter value={password} minLength={PASSWORD_MIN} />
          </div>
        </div>

        <div className="mt-4">
          <Field
            id="reg-years"
            label="Years of service"
            hint="Optional. Used for promotion eligibility, and your administrator can correct it."
          >
            <input
              id="reg-years"
              type="number"
              min={0}
              max={60}
              step={0.5}
              value={serviceYears}
              onChange={(e) => setServiceYears(e.target.value)}
              className={`tabular ${inputClass}`}
            />
          </Field>
        </div>

        <SubmitButton busy={busy} disabled={tooShort}>
          {busy ? "Creating your account…" : "Create account"}
        </SubmitButton>

        <FormError message={error} />

        <FormNote>
          Your division and FRAC role are assigned by an administrator after you
          confirm. Competency on this platform is derived from evidence, so the
          role your gaps are measured against is never self-declared.
        </FormNote>
      </form>
    </AuthShell>
  );
}
