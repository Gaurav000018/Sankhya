import { useId, useState } from "react";
import type { ReactNode } from "react";

import { useT } from "../i18n";
import type { MessageKey } from "../i18n";
import type { GapStatus } from "../types";

/* Shared primitives. Borders carry structure; colour is reserved for meaning,
   so a panel never competes with a status. */

/** Button styles, shared so every action on every screen looks the same. */
export const btnPrimary =
  "inline-flex items-center justify-center gap-1.5 rounded bg-accent px-4 py-2 text-[13.5px] font-semibold text-white hover:bg-accent-strong disabled:cursor-not-allowed disabled:opacity-50";
export const btnSecondary =
  "inline-flex items-center justify-center gap-1.5 rounded border border-accent bg-surface px-4 py-2 text-[13.5px] font-semibold text-accent hover:bg-tint-accent disabled:cursor-not-allowed disabled:opacity-50";

/**
 * A titled panel. `collapsible` turns the header into a disclosure button, for
 * secondary sections that should not push the main content below the fold.
 */
export function Card({
  title,
  hint,
  children,
  className = "",
  action,
  collapsible = false,
  defaultOpen = true,
  flush = false,
}: {
  title?: string;
  hint?: string;
  children: ReactNode;
  className?: string;
  action?: ReactNode;
  collapsible?: boolean;
  defaultOpen?: boolean;
  /** Drop the body padding, for a table that runs edge to edge. */
  flush?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const bodyId = useId();
  const showBody = !collapsible || open;

  return (
    <section className={`rounded border border-rule bg-surface ${className}`}>
      {(title || action) && (
        <header
          className={`flex flex-wrap items-center justify-between gap-3 bg-surface-2 px-4 py-2.5 ${
            showBody ? "border-b border-rule" : ""
          }`}
        >
          {collapsible ? (
            <button
              type="button"
              aria-expanded={open}
              aria-controls={bodyId}
              onClick={() => setOpen(!open)}
              className="flex min-w-0 flex-1 items-center gap-2 text-left"
            >
              <svg
                width="14"
                height="14"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.2"
                aria-hidden="true"
                className={`shrink-0 text-accent ${open ? "rotate-90" : ""}`}
              >
                <path d="m9 6 6 6-6 6" />
              </svg>
              <span className="min-w-0">
                {title && <h2 className="text-[14.5px] font-semibold text-ink">{title}</h2>}
                {hint && <p className="text-[12px] text-ink-3">{hint}</p>}
              </span>
            </button>
          ) : (
            <div className="min-w-0">
              {title && <h2 className="text-[14.5px] font-semibold text-ink">{title}</h2>}
              {hint && <p className="text-[12px] text-ink-3">{hint}</p>}
            </div>
          )}
          {action && showBody && <div className="shrink-0">{action}</div>}
        </header>
      )}
      {showBody && (
        <div id={bodyId} className={flush ? "" : "p-4"}>
          {children}
        </div>
      )}
    </section>
  );
}

export function StatTile({
  label,
  value,
  unit,
  note,
  trend,
}: {
  label: string;
  value: string | number;
  unit?: string;
  note?: string;
  trend?: string;
}) {
  return (
    <div className="rounded border border-rule bg-surface px-4 py-3.5">
      <div className="text-[12.5px] font-medium text-ink-3">{label}</div>
      <div className="mt-1.5 flex items-baseline gap-2">
        <span className="tabular text-[24px] font-semibold leading-none text-ink">{value}</span>
        {unit && <span className="text-[13px] text-ink-3">{unit}</span>}
        {trend && <span className="ml-auto text-[12px] font-semibold text-good">{trend}</span>}
      </div>
      {note && <div className="mt-1.5 text-[12px] text-ink-2">{note}</div>}
    </div>
  );
}

const STATUS_STYLE: Record<GapStatus, { key: MessageKey; className: string }> = {
  critical: { key: "status.critical", className: "border-critical/40 bg-tint-critical text-critical" },
  at_risk: { key: "status.at_risk", className: "border-warn/40 bg-tint-brass text-warn" },
  near_target: { key: "status.near_target", className: "border-near/40 bg-[#fbf6e6] text-near" },
  met: { key: "status.met", className: "border-good/40 bg-tint-good text-good" },
};

export function StatusPill({ status }: { status: GapStatus }) {
  const t = useT();
  const style = STATUS_STYLE[status] ?? STATUS_STYLE.met;
  return (
    <span
      className={`inline-block whitespace-nowrap rounded-sm border px-1.5 py-0.5 text-[11.5px] font-semibold ${style.className}`}
    >
      {t(style.key)}
    </span>
  );
}

/** Current level against the required level, with the requirement marked.
 *  The number is always shown too — colour is never the only channel. */
export function LevelBar({
  current,
  required,
  status,
}: {
  current: number;
  required: number;
  status: GapStatus;
}) {
  const fill = Math.max(0, Math.min(100, (current / 5) * 100));
  const marker = Math.max(0, Math.min(100, (required / 5) * 100));
  const colour = {
    critical: "bg-critical",
    at_risk: "bg-warn",
    near_target: "bg-near",
    met: "bg-good",
  }[status];

  return (
    <div
      role="img"
      aria-label={`Assessed level ${current} of 5, required ${required}`}
      className="relative h-2 w-full rounded-sm bg-surface-3"
    >
      <div className={`absolute left-0 top-0 h-2 rounded-sm ${colour}`} style={{ width: `${fill}%` }} />
      <div
        className="absolute top-[-3px] h-3.5 w-0.5 bg-ink"
        style={{ left: `${marker}%` }}
        title={`Required: L${required}`}
      />
    </div>
  );
}

/** A plain percentage bar with its value printed beside it. */
export function ProgressBar({
  value,
  label,
  tone = "accent",
}: {
  value: number;
  label: string;
  tone?: "accent" | "good" | "warn";
}) {
  const pct = Math.max(0, Math.min(100, Math.round(value)));
  const colour = { accent: "bg-accent", good: "bg-good", warn: "bg-warn" }[tone];
  return (
    <div className="flex items-center gap-3">
      <div
        role="progressbar"
        aria-label={label}
        aria-valuenow={pct}
        aria-valuemin={0}
        aria-valuemax={100}
        className="h-2.5 flex-1 rounded-sm bg-surface-3"
      >
        <div className={`h-2.5 rounded-sm ${colour}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="tabular w-11 text-right text-[13px] font-semibold text-ink">{pct}%</span>
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return (
    <div className="rounded border border-dashed border-rule-strong bg-surface px-5 py-8 text-center text-[13.5px] text-ink-3">
      {children}
    </div>
  );
}

export function Spinner({ label = "Loading" }: { label?: string }) {
  return (
    // role="status" so a screen reader announces the wait instead of landing on
    // an apparently empty page.
    <div
      role="status"
      aria-live="polite"
      className="flex items-center gap-2 px-5 py-8 text-[13.5px] text-ink-3"
    >
      <span
        aria-hidden="true"
        className="inline-block h-3.5 w-3.5 animate-spin rounded-full border-2 border-rule border-t-accent"
      />
      {label}
    </div>
  );
}

export function ErrorNote({ message }: { message: string }) {
  return (
    // Failures are announced. A visually-styled error nobody hears is not an
    // error message.
    <div
      role="alert"
      className="rounded border border-critical/40 border-l-4 border-l-critical bg-tint-critical px-4 py-3 text-[13.5px] text-ink"
    >
      {message}
    </div>
  );
}

export function Note({ children, tone = "accent" }: { children: ReactNode; tone?: "accent" | "brass" }) {
  const style =
    tone === "brass"
      ? "border-brass/40 border-l-brass bg-tint-brass"
      : "border-accent/30 border-l-accent bg-tint-accent";
  return (
    <div className={`rounded border border-l-4 ${style} px-4 py-3 text-[13px] leading-relaxed text-ink-2`}>
      {children}
    </div>
  );
}

export function SourceTag({ source }: { source: string | null }) {
  if (!source) return <span className="text-ink-3">—</span>;
  return (
    <span className="rounded-sm border border-rule bg-surface-2 px-1.5 py-0.5 text-[11.5px] text-ink-2">
      {source.replace(/_/g, " ")}
    </span>
  );
}
