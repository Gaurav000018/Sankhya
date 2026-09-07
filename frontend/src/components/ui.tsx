import type { ReactNode } from "react";

import { useT } from "../i18n";
import type { MessageKey } from "../i18n";
import type { GapStatus } from "../types";

/* Shared primitives. Border and background carry structure; colour is reserved
   for meaning, so a card never competes with a status. */

export function Card({
  title,
  hint,
  children,
  className = "",
  action,
}: {
  title?: string;
  hint?: string;
  children: ReactNode;
  className?: string;
  action?: ReactNode;
}) {
  return (
    <section className={`border border-rule bg-surface ${className}`}>
      {(title || action) && (
        <header className="flex items-baseline justify-between gap-4 border-b border-rule px-5 py-3">
          <div>
            {title && <h2 className="text-sm font-semibold">{title}</h2>}
            {hint && <p className="mt-0.5 text-xs text-ink-3">{hint}</p>}
          </div>
          {action}
        </header>
      )}
      <div className="p-5">{children}</div>
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
    <div className="border border-rule bg-surface px-5 py-4">
      <div className="text-[11px] font-semibold uppercase tracking-[0.07em] text-ink-3">
        {label}
      </div>
      <div className="mt-2 flex items-baseline gap-2">
        <span className="tabular font-mono text-[28px] font-medium leading-none">{value}</span>
        {unit && <span className="text-sm text-ink-3">{unit}</span>}
        {trend && <span className="ml-auto text-xs font-medium text-good">{trend}</span>}
      </div>
      {note && <div className="mt-2 text-xs text-ink-2">{note}</div>}
    </div>
  );
}

const STATUS_STYLE: Record<GapStatus, { key: MessageKey; className: string }> = {
  critical: { key: "status.critical", className: "text-critical" },
  at_risk: { key: "status.at_risk", className: "text-warn" },
  near_target: { key: "status.near_target", className: "text-near" },
  met: { key: "status.met", className: "text-good" },
};

export function StatusPill({ status }: { status: GapStatus }) {
  const t = useT();
  const style = STATUS_STYLE[status] ?? STATUS_STYLE.met;
  return (
    <span
      className={`text-[10.5px] font-semibold uppercase tracking-[0.05em] ${style.className}`}
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
      className="relative h-1.5 w-full bg-surface-2"
    >
      <div className={`absolute left-0 top-0 h-1.5 ${colour}`} style={{ width: `${fill}%` }} />
      <div
        className="absolute top-[-3px] h-3 w-0.5 bg-brass"
        style={{ left: `${marker}%` }}
        title={`Required: L${required}`}
      />
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return (
    <div className="border border-dashed border-rule-strong px-5 py-8 text-center text-sm text-ink-3">
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
      className="flex items-center gap-2 px-5 py-8 text-sm text-ink-3"
    >
      <span
        aria-hidden="true"
        className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-rule-strong border-t-accent"
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
      className="border-l-2 border-critical bg-surface px-4 py-3 text-sm text-ink-2"
    >
      {message}
    </div>
  );
}

export function Note({ children, tone = "accent" }: { children: ReactNode; tone?: "accent" | "brass" }) {
  const border = tone === "brass" ? "border-brass" : "border-accent";
  const bg = tone === "brass" ? "bg-[#f6f4ee]" : "bg-[#f3f5f9]";
  return (
    <div className={`border-l-2 ${border} ${bg} px-4 py-3 text-[13px] leading-relaxed text-ink-2`}>
      {children}
    </div>
  );
}

export function SourceTag({ source }: { source: string | null }) {
  if (!source) return <span className="text-ink-3">—</span>;
  return (
    <span className="bg-surface-2 px-1.5 py-0.5 font-mono text-[10.5px] text-ink-2">
      {source.replace(/_/g, " ")}
    </span>
  );
}
