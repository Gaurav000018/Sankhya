import { Link } from "react-router-dom";

import type { SkillTwin } from "../types";

/**
 * What a newly confirmed officer sees instead of a dashboard of zeros.
 *
 * The dashboard is built to interpret evidence, and a new account has none: it
 * renders 0% readiness, "0 of 0 competencies", an empty radar, and — worst —
 * a "strongest area" picked from competencies nobody has measured. That reads
 * as a broken product rather than an empty one.
 *
 * Two of the three steps below are not things the officer can do themselves.
 * Saying so is the point: "waiting on your administrator" is a state, and an
 * interface that hides it leaves someone clicking around looking for the part
 * they have done wrong.
 */

function Step({
  index,
  title,
  body,
  state,
  waitingOn,
  action,
}: {
  index: number;
  title: string;
  body: string;
  state: "done" | "now" | "waiting";
  /** What the step is blocked on. Named, because "waiting" with no subject
   *  leaves someone hunting for the thing they have done wrong. */
  waitingOn?: string;
  action?: { to: string; label: string };
}) {
  const mark = {
    done: { ring: "border-good bg-good text-ground", label: "✓" },
    now: { ring: "border-accent bg-accent text-ground", label: String(index) },
    waiting: { ring: "border-rule-strong text-ink-3", label: String(index) },
  }[state];

  return (
    <li className="relative flex gap-4 pb-6 last:pb-0">
      {/* Spine between the markers, stopping at the last one. */}
      <span
        aria-hidden="true"
        className="absolute bottom-0 left-[13px] top-7 w-px bg-rule last:hidden"
      />
      <span
        className={`relative z-10 flex h-7 w-7 shrink-0 items-center justify-center rounded-full border text-[12px] font-semibold ${mark.ring}`}
      >
        {mark.label}
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className={`text-[14px] font-semibold ${state === "waiting" ? "text-ink-2" : ""}`}>
            {title}
          </h3>
          {state === "done" && (
            <span className="rounded-full bg-tint-good px-2 py-0.5 font-mono text-[10px] uppercase tracking-[0.08em] text-good">
              done
            </span>
          )}
          {state === "waiting" && waitingOn && (
            <span className="rounded-full bg-surface-2 px-2 py-0.5 font-mono text-[10px] uppercase tracking-[0.08em] text-ink-3">
              {waitingOn}
            </span>
          )}
        </div>
        <p className="mt-1.5 text-[13px] leading-relaxed text-ink-2">{body}</p>
        {action && state === "now" && (
          <Link
            to={action.to}
            className="mt-3 inline-flex items-center gap-2 rounded-full bg-accent px-4 py-2 text-[13px] font-medium text-ground transition-[filter] hover:brightness-110"
          >
            {action.label}
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" className="h-3.5 w-3.5" aria-hidden="true">
              <path d="M5 12h13M13 6l6 6-6 6" />
            </svg>
          </Link>
        )}
      </div>
    </li>
  );
}

export function GettingStarted({ twin }: { twin: SkillTwin }) {
  const hasRole = Boolean(twin.role_name);
  const evidenceCount = twin.competencies.reduce((n, c) => n + c.evidence_count, 0);
  const hasSelfRating = evidenceCount > 0;

  return (
    <section className="relative overflow-hidden rounded-xl border border-rule bg-surface">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute right-[-8rem] top-[-10rem] -z-10 h-72 w-72 rounded-full bg-accent opacity-[0.07] blur-[90px]"
      />
      <div className="border-b border-rule px-6 py-5">
        <h1
          tabIndex={-1}
          ref={(node) => {
            if (node && node.dataset.focused !== "1") {
              node.dataset.focused = "1";
              node.focus({ preventScroll: true });
            }
          }}
          className="font-serif text-[26px] font-medium leading-tight tracking-[-0.015em]"
        >
          Welcome, {twin.user.full_name}
        </h1>
        <p className="mt-2 max-w-[62ch] text-[13.5px] leading-relaxed text-ink-2">
          Your Digital Skill Twin is empty. It fills from evidence — assessments,
          interviews, demonstrated work — so there is nothing to show yet, and
          nothing is wrong. Here is what happens next.
        </p>
      </div>

      <div className="grid gap-8 p-6 lg:grid-cols-[minmax(0,1fr)_300px]">
        <ol>
          <Step
            index={1}
            title="Your email address is confirmed"
            body="You can sign in with your password, a one-time email code, or an authenticator app."
            state="done"
          />
          <Step
            index={2}
            title={hasRole ? `Your role is set: ${twin.role_name}` : "An administrator assigns your role"}
            body={
              hasRole
                ? "Your gaps are measured against what this role requires, competency by competency."
                : "Until your division and FRAC role are set, there is no requirement to measure you against — so readiness and gaps stay empty. Your division administrator does this; you do not need to chase it."
            }
            state={hasRole ? "done" : "waiting"}
            waitingOn="waiting on your administrator"
          />
          <Step
            index={3}
            title="Start with the diagnostic"
            body="A short self-rating across the twelve competencies. It carries the lowest weight in the model and any real assessment overrides it — but it gives the platform a starting point, and it is what the confidence–competence check later compares against."
            state={hasSelfRating ? "done" : "now"}
            action={{ to: "/settings", label: "Take the diagnostic" }}
          />
          <Step
            index={4}
            title="Then demonstrate it"
            body="An adaptive assessment locates your level in about eight questions. An AI interview scores knowledge, structure, communication and fluency separately. Both write evidence, and your profile moves."
            state={hasSelfRating ? "now" : "waiting"}
            waitingOn="after the diagnostic"
            action={{ to: "/quiz", label: "Take an assessment" }}
          />
        </ol>

        <aside className="rounded-lg border border-rule bg-surface-2 p-5">
          <h2 className="font-mono text-[10.5px] uppercase tracking-[0.12em] text-accent">
            How your level is decided
          </h2>
          <dl className="mt-4 space-y-3 text-[12.5px]">
            {[
              ["Demonstrated work", "0.95", "text-ink"],
              ["Adaptive quiz", "0.90", "text-ink"],
              ["AI interview", "0.80", "text-ink"],
              ["Supervisor rating", "0.70", "text-ink"],
              ["Your self-rating", "0.30", "text-ink-3"],
            ].map(([label, weight, tone]) => (
              <div key={label} className="flex items-center justify-between gap-3">
                <dt className={tone}>{label}</dt>
                <dd className="tabular font-mono text-[11px] text-ink-3">×{weight}</dd>
              </div>
            ))}
          </dl>
          <p className="mt-4 border-t border-rule pt-3 text-[11.5px] leading-relaxed text-ink-3">
            Nothing writes a score directly. Every level you see is derived from
            these records, and a correction is a new record rather than an edit —
            which is what lets a level be defended six months later.
          </p>
        </aside>
      </div>
    </section>
  );
}
