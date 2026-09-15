import { useCallback, useEffect, useState } from "react";

import { ApiError, api } from "../api";
import { ErrorNote, Spinner } from "../components/ui";
import { usePageTitle } from "../hooks/usePageTitle";
import type { JourneyOut } from "../types";
import { AnalysisStep } from "./journey/Analysis";
import {
  AssessmentStep,
  ContextStep,
  DiagnosticStep,
  InterviewStep,
} from "./journey/steps";

/**
 * The guided journey, end to end: context → self-rating → assessment →
 * interview → analysis and roadmap.
 *
 * Progress is **derived from the evidence record**, not stored in this
 * component or in localStorage. An officer who closes the tab halfway through
 * and signs in on another machine resumes where they left off, because "have
 * they done the assessment" is answered by whether quiz evidence exists — which
 * is the same fact the dashboard reads.
 *
 * The step can still be moved manually, so someone who wants to retake an
 * assessment is not blocked by having already taken one.
 */

const STEPS = ["Context", "Self-rating", "Assessment", "Interview", "Analysis"] as const;

export function Journey() {
  usePageTitle("title.journey");

  const [step, setStep] = useState(0);
  const [journey, setJourney] = useState<JourneyOut | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const data = await api.journey();
      setJourney(data);
      return data;
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not load your progress.");
      return null;
    }
  }, []);

  // Resume where the evidence says they got to, on first load only. After that
  // the officer drives, so finishing a step never yanks them somewhere else.
  useEffect(() => {
    (async () => {
      const data = await load();
      if (data) {
        if (data.interview.length > 0) setStep(4);
        else if (data.assessment.length > 0) setStep(3);
      }
      setLoading(false);
    })();
  }, [load]);

  const advance = useCallback(
    async (to: number) => {
      await load();
      setStep(to);
      window.scrollTo({ top: 0, behavior: "smooth" });
    },
    [load],
  );

  if (loading) return <Spinner label="Checking what you have completed" />;

  return (
    <>
      <div className="mb-6">
        <h1
          tabIndex={-1}
          ref={(node) => {
            if (node && node.dataset.focused !== "1") {
              node.dataset.focused = "1";
              node.focus({ preventScroll: true });
            }
          }}
          className="font-serif text-[26px] font-medium leading-tight"
        >
          Measure where you stand
        </h1>
        <p className="mt-1.5 text-[13.5px] text-ink-2">
          An assessment, an interview, and a roadmap built from what they find.
        </p>
      </div>

      {/* Progress rail. Completed steps are clickable so anything can be redone. */}
      <nav aria-label="Journey progress" className="mb-6">
        <ol className="flex flex-wrap gap-x-1 gap-y-2">
          {STEPS.map((label, index) => {
            const done = index < step;
            const current = index === step;
            return (
              <li key={label} className="flex items-center">
                <button
                  onClick={() => index <= step && advance(index)}
                  disabled={index > step}
                  aria-current={current ? "step" : undefined}
                  className={`rounded px-3.5 py-1.5 text-[12.5px] transition-colors ${
                    current
                      ? "bg-tint-accent font-medium text-accent"
                      : done
                        ? "text-ink-2 hover:text-accent"
                        : "text-ink-3"
                  }`}
                >
                  <span className="tabular mr-1.5 font-mono text-[10.5px]">
                    {done ? "✓" : index + 1}
                  </span>
                  {label}
                </button>
                {index < STEPS.length - 1 && (
                  <span aria-hidden="true" className="h-px w-4 bg-rule" />
                )}
              </li>
            );
          })}
        </ol>
      </nav>

      {error && (
        <div className="mb-4">
          <ErrorNote message={error} />
        </div>
      )}

      {step === 0 && <ContextStep onNext={() => advance(1)} />}
      {step === 1 && <DiagnosticStep onNext={() => advance(2)} />}
      {step === 2 && <AssessmentStep onNext={() => advance(3)} />}
      {step === 3 && <InterviewStep onNext={() => advance(4)} />}
      {step === 4 &&
        (journey ? (
          <AnalysisStep journey={journey} />
        ) : (
          <Spinner label="Assembling your analysis" />
        ))}
    </>
  );
}
