import type { ReactNode } from "react";
import { Link } from "react-router-dom";

/**
 * Shared chrome for every page you can reach while signed out: sign in,
 * register, confirm, forgot, reset.
 *
 * They are one flow and people move between them mid-task, so a shared shell is
 * what stops the mark, the bloom and the card edge shifting a few pixels on
 * each navigation.
 */

export function AuthShell({
  heading,
  intro,
  children,
  footer,
}: {
  heading: string;
  intro?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
}) {
  return (
    <div className="relative flex min-h-full items-center justify-center overflow-hidden px-6 py-12">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute left-1/2 top-[-6rem] -z-10 h-[26rem] w-[36rem] -translate-x-1/2 animate-drift rounded-full bg-accent opacity-[0.10] blur-[110px]"
      />
      <div className="w-full max-w-[440px]">
        <Link to="/" className="mb-7 inline-flex items-center gap-2.5">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="var(--color-accent)" strokeWidth="1.8" strokeLinecap="round" aria-hidden="true">
            <path d="M4 20V13" /><path d="M9.3 20V8" /><path d="M14.7 20V15" /><path d="M20 20V4" />
          </svg>
          <span className="font-serif text-[21px] font-semibold tracking-[0.08em]">SANKHYA</span>
        </Link>

        <h1
          tabIndex={-1}
          ref={(node) => {
            // Focus lands on the heading so a screen reader announces the new
            // page; a client-side route change is otherwise silent.
            if (node && node.dataset.focused !== "1") {
              node.dataset.focused = "1";
              node.focus({ preventScroll: true });
            }
          }}
          className="font-serif text-[24px] font-semibold leading-tight"
        >
          {heading}
        </h1>
        {intro && (
          <p className="mt-2 max-w-[46ch] text-[13.5px] leading-relaxed text-ink-2">{intro}</p>
        )}

        <div className="mt-7 rounded-xl border border-rule bg-surface p-5">{children}</div>

        {footer && <div className="mt-5 text-[13px] text-ink-2">{footer}</div>}
      </div>
    </div>
  );
}

export function Field({
  id,
  label,
  hint,
  children,
}: {
  id: string;
  label: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <div>
      <label
        htmlFor={id}
        className="block text-[11px] font-semibold uppercase tracking-[0.07em] text-ink-3"
      >
        {label}
      </label>
      {children}
      {hint && <p className="mt-1.5 text-[11.5px] leading-relaxed text-ink-3">{hint}</p>}
    </div>
  );
}

export const inputClass =
  "mt-1.5 w-full rounded-md border border-rule-strong bg-surface-2 px-3 py-2 text-sm outline-none transition-colors focus:border-accent";

export function SubmitButton({
  busy,
  children,
  disabled,
}: {
  busy?: boolean;
  children: ReactNode;
  disabled?: boolean;
}) {
  return (
    <button
      type="submit"
      disabled={busy || disabled}
      className="mt-5 w-full rounded-full bg-accent px-4 py-2.5 text-sm font-medium text-ground transition-[filter] hover:brightness-110 disabled:opacity-50"
    >
      {children}
    </button>
  );
}

/** Failures are announced, not just coloured. */
export function FormError({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <div
      role="alert"
      className="mt-4 rounded-md border-l-2 border-critical bg-tint-critical px-3 py-2 text-[13px] leading-relaxed text-ink-2"
    >
      {message}
    </div>
  );
}

export function FormNote({ children }: { children: ReactNode }) {
  return (
    <div
      role="status"
      className="mt-4 rounded-md border-l-2 border-accent bg-tint-accent px-3 py-2 text-[13px] leading-relaxed text-ink-2"
    >
      {children}
    </div>
  );
}

/**
 * The link the API hands back in dev mode so a demo never waits on an email.
 * Labelled as development output rather than dressed up as a normal part of the
 * flow — it is exactly what must never appear in production.
 */
export function DevLink({ url, label }: { url: string; label: string }) {
  return (
    <div className="mt-4 rounded-md border-l-2 border-brass bg-tint-brass px-3 py-2.5 text-[12.5px] leading-relaxed text-ink-2">
      <strong className="font-semibold text-ink">Development mode.</strong> Email sending
      is off, so the link is shown here instead of being delivered.
      <Link
        to={url.replace(/^https?:\/\/[^/]+/, "")}
        className="mt-2 block break-all font-mono text-[11.5px] text-accent underline underline-offset-2"
      >
        {label}
      </Link>
    </div>
  );
}

/** Live strength feedback. The rule shown is the one the API enforces. */
export function PasswordMeter({ value, minLength }: { value: string; minLength: number }) {
  const checks = [
    { label: `${minLength}+ characters`, ok: value.length >= minLength },
    { label: "a letter", ok: /[a-zA-Z]/.test(value) },
    { label: "a digit or symbol", ok: /[^a-zA-Z]/.test(value) },
  ];
  const met = checks.filter((c) => c.ok).length;
  const tone = met === 3 ? "bg-good" : met === 2 ? "bg-warn" : "bg-critical";

  return (
    <div className="mt-2">
      <div className="flex gap-1" aria-hidden="true">
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className={`h-1 flex-1 rounded-full transition-colors ${
              i < met ? tone : "bg-surface-2"
            }`}
          />
        ))}
      </div>
      <p className="mt-1.5 text-[11.5px] text-ink-3">
        {checks.map((c, i) => (
          <span key={c.label} className={c.ok ? "text-ink-2" : ""}>
            {c.ok ? "✓" : "·"} {c.label}
            {i < checks.length - 1 ? " · " : ""}
          </span>
        ))}
      </p>
    </div>
  );
}
