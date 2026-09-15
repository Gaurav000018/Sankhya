import { Link } from "react-router-dom";

import type { JourneyOut } from "../../types";
import { StepShell } from "./steps";

/**
 * The payoff screen: what each method found, where they disagree, and the
 * ordered roadmap to the next role.
 *
 * Every figure here comes from the journey endpoint, which composes evidence
 * rather than generating anything. The narrative is assembled server-side from
 * measured values for the same reason — a paragraph describing someone's
 * competence has to say the same thing on a second reading.
 */

function levelBar(level: number, required?: number) {
  const fill = Math.max(0, Math.min(100, (level / 5) * 100));
  const mark = required ? Math.max(0, Math.min(100, (required / 5) * 100)) : null;
  return (
    <div className="relative h-1.5 w-full rounded-full bg-surface-2">
      <div className="absolute left-0 top-0 h-1.5 rounded-full bg-accent" style={{ width: `${fill}%` }} />
      {mark !== null && (
        <div
          className="absolute top-[-3px] h-3 w-0.5 rounded bg-brass"
          style={{ left: `${mark}%` }}
          title={`Required: L${required}`}
        />
      )}
    </div>
  );
}

function SignalTable({
  title,
  hint,
  rows,
}: {
  title: string;
  hint: string;
  rows: JourneyOut["assessment"];
}) {
  return (
    <div className="rounded border border-rule bg-surface-2 p-4">
      <div className="text-[13px] font-semibold">{title}</div>
      <p className="mt-0.5 text-[11.5px] text-ink-3">{hint}</p>
      {rows.length === 0 ? (
        <p className="mt-4 text-[12.5px] text-ink-3">Nothing measured yet.</p>
      ) : (
        <ul className="mt-3.5 space-y-3">
          {rows.map((row) => (
            <li key={row.competency_id}>
              <div className="flex items-baseline justify-between gap-3">
                <span className="truncate text-[12.5px]">{row.competency_name}</span>
                <span className="tabular shrink-0 font-mono text-[12px] font-medium">
                  L{row.level?.toFixed(2)}
                </span>
              </div>
              <div className="mt-1.5">{levelBar(row.level ?? 0)}</div>
              <div className="mt-1 font-mono text-[10px] text-ink-3">
                {row.records} record{row.records === 1 ? "" : "s"}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function AnalysisStep({ journey }: { journey: JourneyOut }) {
  return (
    <div className="space-y-4">
      <StepShell
        eyebrow="Step 5 of 5"
        title="What the evidence shows"
        lede="Assembled from what you actually did. No part of this is self-reported, and nothing here was written by a language model."
      >
        <div className="space-y-3.5">
          {journey.narrative.map((line, i) => (
            <p key={i} className="text-[14px] leading-relaxed text-ink-2">
              {line}
            </p>
          ))}
        </div>

        <div className="mt-7 grid gap-3.5 sm:grid-cols-2">
          <SignalTable
            title="What the assessment found"
            hint="Written items, scored against difficulty"
            rows={journey.assessment}
          />
          <SignalTable
            title="What the interview found"
            hint="Open answers, knowledge axis only"
            rows={journey.interview}
          />
        </div>

        {journey.divergences.length > 0 && (
          <div className="mt-4 space-y-3">
            <div className="font-mono text-[10.5px] uppercase tracking-[0.12em] text-brass">
              Where the two methods disagree
            </div>
            {journey.divergences.map((d) => (
              <div
                key={d.competency_name}
                className="rounded border-l-2 border-brass bg-tint-brass p-4"
              >
                <div className="flex flex-wrap items-baseline justify-between gap-3">
                  <span className="text-[14px] font-medium">{d.competency_name}</span>
                  <span className="tabular font-mono text-[12.5px] text-ink-2">
                    written L{d.assessment_level} · spoken L{d.interview_level}
                  </span>
                </div>
                <p className="mt-2 text-[13px] leading-relaxed text-ink-2">{d.reading}</p>
              </div>
            ))}
            <p className="text-[11.5px] leading-relaxed text-ink-3">
              These are reported rather than averaged. A mean of the two would erase
              exactly the thing worth knowing.
            </p>
          </div>
        )}

        {journey.unmeasured.length > 0 && (
          <div className="mt-4 rounded border border-dashed border-rule-strong p-4">
            <div className="font-mono text-[10.5px] uppercase tracking-[0.12em] text-ink-3">
              Not yet measured
            </div>
            <p className="mt-2 text-[13px] leading-relaxed text-ink-2">
              {journey.unmeasured.join(", ")} — required for the role but with no
              assessment or interview evidence. Their gap is assumed from the role
              requirement, not observed.
            </p>
          </div>
        )}
      </StepShell>

      {journey.needs_role ? (
        <section className="rounded border border-brass/40 bg-tint-brass p-6 sm:p-8">
          <div className="font-mono text-[11px] uppercase tracking-[0.18em] text-brass">
            Roadmap unavailable
          </div>
          <h2 className="mt-3 font-serif text-[22px] font-medium leading-tight">
            Your role has not been assigned yet
          </h2>
          <p className="mt-3 max-w-[64ch] text-[13.5px] leading-relaxed text-ink-2">
            Every competency requirement on this platform comes from a FRAC role in a
            division, so without one there is no target to measure a gap against. An
            administrator assigns it — deliberately not something you can set yourself,
            because the whole point is that the bar you are measured against is
            authoritative rather than self-declared.
          </p>
          <p className="mt-3 max-w-[64ch] text-[13.5px] leading-relaxed text-ink-2">
            The assessment and interview evidence above is real and has been kept. Once
            your role is set, this page builds the roadmap from it with nothing to redo.
          </p>
        </section>
      ) : (
      <section className="rounded border border-rule bg-surface p-6 sm:p-8">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <div className="font-mono text-[11px] uppercase tracking-[0.18em] text-accent">
              Your roadmap
            </div>
            <h2 className="mt-3 font-serif text-[24px] font-medium leading-tight">
              {journey.target_role
                ? `Getting to ${journey.target_role}`
                : "Closing your widest gaps"}
            </h2>
          </div>
          {journey.target_role && (
            <div className="text-right">
              <div className="tabular font-mono text-[30px] font-medium leading-none">
                {journey.readiness_now}
                <span className="text-[16px] text-ink-3">%</span>
              </div>
              <div className="mt-1 text-[11px] uppercase tracking-[0.08em] text-ink-3">
                ready now
              </div>
            </div>
          )}
        </div>

        <ol className="mt-7 space-y-3.5">
          {journey.roadmap.map((step) => (
            <li
              key={step.order}
              className="rounded border border-rule bg-surface-2 p-5"
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="flex min-w-0 gap-3.5">
                  <span className="tabular mt-[1px] shrink-0 font-mono text-[13px] text-accent">
                    {String(step.order).padStart(2, "0")}
                  </span>
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-[15px] font-medium">{step.competency_name}</span>
                      {step.criticality === "critical" && (
                        <span className="rounded bg-critical/15 px-2 py-0.5 font-mono text-[9.5px] uppercase tracking-[0.08em] text-critical">
                          critical
                        </span>
                      )}
                    </div>
                    <p className="mt-1.5 text-[12.5px] leading-relaxed text-ink-2">
                      {step.why}
                    </p>
                  </div>
                </div>
                <span className="tabular shrink-0 font-mono text-[12.5px]">
                  L{step.current_level} <span className="text-rule-strong">→</span>{" "}
                  L{step.required_level}
                </span>
              </div>

              <div className="ml-[30px] mt-3">{levelBar(step.current_level, step.required_level)}</div>

              {step.course_title && (
                <div className="ml-[30px] mt-4 rounded-md border border-accent/25 bg-tint-accent p-3.5">
                  <div className="font-mono text-[9.5px] uppercase tracking-[0.1em] text-accent">
                    Recommended course
                  </div>
                  <div className="mt-1.5 text-[13.5px] font-medium">
                    {step.course_title}
                  </div>
                  <div className="mt-0.5 font-mono text-[11px] text-ink-3">
                    {step.course_provider}
                    {step.course_hours ? ` · ${step.course_hours}h` : ""}
                  </div>
                  {step.course_reason && (
                    <p className="mt-2 text-[12px] leading-relaxed text-ink-2">
                      {step.course_reason}
                    </p>
                  )}
                </div>
              )}
            </li>
          ))}
        </ol>

        {journey.projected_date && (
          <p className="mt-6 border-t border-rule pt-4 text-[13px] leading-relaxed text-ink-2">
            At your current rate of movement the binding gap closes around{" "}
            <span className="text-brass">{journey.projected_date}</span>. Working the
            critical steps first moves that date; the projection assumes you carry on
            exactly as you have been.
          </p>
        )}
        {journey.caveat && (
          <p className="mt-3 text-[11.5px] leading-relaxed text-ink-3">{journey.caveat}</p>
        )}

        <div className="mt-7 flex flex-wrap gap-3">
          <Link
            to="/learning"
            className="rounded bg-accent px-5 py-2.5 text-[14px] font-medium text-white hover:bg-accent-strong"
          >
            Build a learning path
          </Link>
          <Link
            to="/dashboard"
            className="rounded border border-rule-strong px-5 py-2.5 text-[14px] text-ink-2 transition-colors hover:border-accent hover:text-accent"
          >
            Back to your dashboard
          </Link>
        </div>
      </section>
      )}
    </div>
  );
}
