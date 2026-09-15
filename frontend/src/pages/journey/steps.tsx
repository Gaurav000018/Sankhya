import { useEffect, useRef, useState } from "react";

import { ApiError, api } from "../../api";
import { AbilityScale, AbilityTrace } from "../../components/AbilityScale";
import type { TraceStep } from "../../components/AbilityScale";
import { Empty, ErrorNote, Spinner } from "../../components/ui";
import type { Gap, JourneyOut, WrittenAnswerOut } from "../../types";

/* The individual steps of the guided journey. Each one is self-contained: it
   fetches what it needs, reports completion upward, and can be re-entered
   without losing anything, because all progress lives in the evidence record
   rather than in component state. */

export const inputClass =
  "mt-1.5 w-full rounded-md border border-rule-strong bg-surface-2 px-3 py-2 text-sm outline-none transition-colors focus:border-accent";

export function StepShell({
  eyebrow,
  title,
  lede,
  children,
}: {
  eyebrow: string;
  title: string;
  lede?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded border border-rule bg-surface p-6 sm:p-8">
      <div className="font-mono text-[11px] uppercase tracking-[0.18em] text-accent">
        {eyebrow}
      </div>
      <h2 className="mt-3 font-serif text-[24px] font-medium leading-tight">{title}</h2>
      {lede && (
        <p className="mt-2.5 max-w-[62ch] text-[13.5px] leading-relaxed text-ink-2">{lede}</p>
      )}
      <div className="mt-6">{children}</div>
    </section>
  );
}

export function PrimaryButton({
  onClick,
  disabled,
  busy,
  children,
}: {
  onClick: () => void;
  disabled?: boolean;
  busy?: boolean;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled || busy}
      className="rounded bg-accent px-5 py-2.5 text-[14px] font-medium text-white hover:bg-accent-strong disabled:opacity-40"
    >
      {busy ? "Working…" : children}
    </button>
  );
}

/* ------------------------------------------------------------- 1. context -- */

export function ContextStep({ onNext }: { onNext: () => void }) {
  return (
    <StepShell
      eyebrow="Step 1 of 5"
      title="What this is measuring, and why"
      lede="Two minutes of reading before you start, so the numbers at the end mean something to you."
    >
      <div className="space-y-5 text-[14px] leading-relaxed text-ink-2">
        <p>
          iGOT Karmayogi records which courses you completed. That is attendance.
          It cannot tell your division whether you can design a sampling frame, and
          it cannot tell you which of your competencies is actually holding back
          your next posting.
        </p>
        <p>
          SANKHYA measures the second thing. Everything it reports about you is
          derived from evidence — an assessment you sat, an interview you gave, work
          a supervisor signed off — and every level traces back to the record that
          produced it. <span className="text-ink">Nothing here is self-declared.</span>
        </p>

        <div className="rounded border border-rule bg-surface-2 p-5">
          <div className="font-mono text-[10.5px] uppercase tracking-[0.12em] text-ink-3">
            What happens next
          </div>
          <ol className="mt-3 space-y-2.5 text-[13.5px]">
            {[
              ["Self-rating", "You rate yourself. This is recorded, but carries the lowest weight of any signal — it exists so the platform can show you where your self-assessment and the evidence disagree."],
              ["Assessment", "Multiple-choice items drawn from your widest measured gap. Scored against item difficulty, not raw percentage."],
              ["Interview", "Open questions on the same competencies. Judged on knowledge and structure — how you express it never becomes a competency level."],
              ["Analysis", "What each method found, where they disagree, and what that disagreement usually means."],
            ].map(([name, text], i) => (
              <li key={name} className="flex gap-3">
                <span className="tabular mt-[1px] shrink-0 font-mono text-[11px] text-accent">
                  {i + 1}
                </span>
                <span>
                  <span className="font-medium text-ink">{name}.</span>{" "}
                  <span className="text-ink-2">{text}</span>
                </span>
              </li>
            ))}
          </ol>
        </div>

        <p className="text-[13px] text-ink-3">
          You can stop at any point and come back. Progress is held in your evidence
          record, not in this browser tab.
        </p>
      </div>

      <div className="mt-7">
        <PrimaryButton onClick={onNext}>Start</PrimaryButton>
      </div>
    </StepShell>
  );
}

/* ----------------------------------------------------------- 2. diagnostic -- */

interface DiagnosticItem {
  competency_id: number;
  competency_name: string;
  anchors?: Record<string, string>;
}

export function DiagnosticStep({ onNext }: { onNext: () => void }) {
  const [items, setItems] = useState<DiagnosticItem[]>([]);
  const [ratings, setRatings] = useState<Record<number, number>>({});
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<{ competencies: DiagnosticItem[] } | DiagnosticItem[]>("/diagnostic")
      .then((data) => {
        const list = Array.isArray(data) ? data : data.competencies;
        setItems(list ?? []);
      })
      .catch((e) => setError(e instanceof ApiError ? e.message : "Could not load."))
      .finally(() => setLoading(false));
  }, []);

  const answered = Object.keys(ratings).length;

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      await api.post("/diagnostic", {
        ratings: Object.entries(ratings).map(([id, level]) => ({
          competency_id: Number(id),
          self_rated_level: level,
        })),
      });
      onNext();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not save your ratings.");
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <Spinner label="Loading the framework" />;

  return (
    <StepShell
      eyebrow="Step 2 of 5"
      title="Rate yourself"
      lede="Against the competencies your role requires. This carries the least weight of any signal on the platform — its purpose is to surface where your own view and the evidence part company."
    >
      {error && <ErrorNote message={error} />}
      {items.length === 0 ? (
        <Empty>No competencies are assigned to your role yet.</Empty>
      ) : (
        <>
          <ul className="divide-y divide-rule">
            {items.map((item) => (
              <li
                key={item.competency_id}
                className="flex flex-wrap items-center justify-between gap-4 py-3.5"
              >
                <span className="text-[14px]">{item.competency_name}</span>
                <div className="flex gap-1.5" role="group" aria-label={item.competency_name}>
                  {[1, 2, 3, 4, 5].map((level) => {
                    const active = ratings[item.competency_id] === level;
                    return (
                      <button
                        key={level}
                        aria-pressed={active}
                        onClick={() =>
                          setRatings((r) => ({ ...r, [item.competency_id]: level }))
                        }
                        className={`tabular h-9 w-9 rounded-md border font-mono text-[13px] transition-colors ${
                          active
                            ? "border-accent bg-accent text-white"
                            : "border-rule-strong text-ink-2 hover:border-accent hover:text-accent"
                        }`}
                      >
                        {level}
                      </button>
                    );
                  })}
                </div>
              </li>
            ))}
          </ul>
          <div className="mt-6 flex flex-wrap items-center gap-4">
            <PrimaryButton
              onClick={submit}
              busy={busy}
              disabled={answered < items.length}
            >
              Save and continue
            </PrimaryButton>
            <span className="tabular font-mono text-[12px] text-ink-3">
              {answered} of {items.length} rated
            </span>
          </div>
        </>
      )}
    </StepShell>
  );
}

/* ----------------------------------------------------------- 3. assessment -- */

interface AdaptiveItem {
  question_id: number;
  stem: string;
  options: string[];
  difficulty_level: number;
  asked_because: string | null;
}

interface JourneyAbility {
  theta: number;
  se: number;
  level: number;
  level_low: number;
  level_high: number;
  reliability: number;
}

interface JourneyAttempt {
  id: number;
  competency_name: string;
  asked: number;
  correct: number;
  min_items: number;
  max_items: number;
  ability: JourneyAbility;
  current_item: AdaptiveItem | null;
  finished: boolean;
}

interface JourneyGraded {
  question_id: number;
  correct_index: number;
  selected_index: number | null;
  is_correct: boolean;
  explanation: string | null;
}

interface JourneyResult {
  asked: number;
  correct: number;
  accuracy: number;
  ability: JourneyAbility;
  derived_level: number;
  confidence: number;
  stop_explanation: string | null;
  trace: TraceStep[];
}

interface JourneyAnswerOut {
  graded: JourneyGraded;
  ability: JourneyAbility;
  next_item: AdaptiveItem | null;
  attempt: JourneyAttempt;
  result: JourneyResult | null;
}

/**
 * The assessment step, one question at a time.
 *
 * The journey used to show a fixed page of six questions. It is adaptive now,
 * which changes the shape of this step rather than just its contents: there is
 * no list to render, so it advances question by question, and the ability band
 * is drawn throughout because watching it narrow is the clearest explanation of
 * what is happening that the product contains.
 */
export function AssessmentStep({ onNext }: { onNext: () => void }) {
  const [attempt, setAttempt] = useState<JourneyAttempt | null>(null);
  const [item, setItem] = useState<AdaptiveItem | null>(null);
  const [ability, setAbility] = useState<JourneyAbility | null>(null);
  const [chosen, setChosen] = useState<number | null>(null);
  const [graded, setGraded] = useState<JourneyGraded | null>(null);
  const [result, setResult] = useState<JourneyResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .post<JourneyAttempt>("/quizzes", {})
      .then((a) => {
        setAttempt(a);
        setItem(a.current_item);
        setAbility(a.ability);
      })
      .catch((e) => setError(e instanceof ApiError ? e.message : "Could not start."))
      .finally(() => setLoading(false));
  }, []);

  async function answer(selected: number | null) {
    if (!attempt || !item) return;
    setBusy(true);
    setError(null);
    try {
      const out = await api.post<JourneyAnswerOut>(`/quizzes/${attempt.id}/answer`, {
        question_id: item.question_id,
        selected_index: selected,
      });
      setGraded(out.graded);
      setAbility(out.ability);
      setAttempt(out.attempt);
      setItem(out.next_item);
      if (out.result) setResult(out.result);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not submit.");
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <Spinner label="Choosing a first question for your widest gap" />;
  if (error && !attempt) return <ErrorNote message={error} />;
  if (!attempt) return <Empty>No assessment could be started.</Empty>;

  if (result && !graded) {
    return (
      <StepShell
        eyebrow="Step 3 of 5"
        title="Assessment complete"
        lede={`${attempt.competency_name} — ${result.correct} of ${result.asked} correct, over questions chosen from how you answered.`}
      >
        <div className="grid gap-3 sm:grid-cols-3">
          {[
            [
              "Assessed level",
              `L${result.derived_level}`,
              `95% interval L${result.ability.level_low}–L${result.ability.level_high}`,
            ],
            ["Questions", `${result.asked}`, `${Math.round(result.accuracy)}% correct`],
            [
              "Evidence weight",
              result.confidence.toFixed(2),
              "how much of the range this resolved",
            ],
          ].map(([label, value, note]) => (
            <div key={label} className="rounded border border-rule bg-surface-2 px-4 py-3.5">
              <div className="text-[10.5px] font-semibold uppercase tracking-[0.09em] text-ink-3">
                {label}
              </div>
              <div className="tabular mt-2 font-mono text-[22px] font-medium">{value}</div>
              <div className="mt-1 text-[11.5px] text-ink-3">{note}</div>
            </div>
          ))}
        </div>

        <div className="mt-5 rounded-lg border border-rule bg-surface-2 px-4 py-4">
          <AbilityTrace steps={result.trace} />
        </div>

        {result.stop_explanation && (
          <p className="mt-5 border-l-2 border-accent bg-tint-accent px-4 py-3 text-[13px] leading-relaxed text-ink-2">
            {result.stop_explanation}
          </p>
        )}

        <div className="mt-6">
          <PrimaryButton onClick={onNext}>Continue to the interview</PrimaryButton>
        </div>
      </StepShell>
    );
  }

  const showing = graded ? null : item;

  return (
    <StepShell
      eyebrow="Step 3 of 5"
      title={`Assessment — ${attempt.competency_name}`}
      lede="Chosen because this is your widest measured gap. Each question is picked to sit near where you are currently estimated, which is where an answer tells us the most."
    >
      {error && <ErrorNote message={error} />}

      {ability && (
        <div className="mb-6 rounded-lg border border-rule bg-surface-2 px-4 py-3.5">
          <AbilityScale
            ability={ability}
            itemLevel={showing?.difficulty_level ?? null}
            label={`Question ${attempt.asked + (graded ? 0 : 1)} of at most ${attempt.max_items}`}
          />
        </div>
      )}

      {showing && showing.asked_because && (
        <p className="mb-4 border-l-2 border-brass px-4 py-2 text-[12.5px] leading-relaxed text-ink-3">
          {showing.asked_because}
        </p>
      )}

      {showing && (
        <>
          <p className="text-[14.5px] leading-relaxed">{showing.stem}</p>
          <div className="mt-4 space-y-2">
            {showing.options.map((option, oi) => {
              const active = chosen === oi;
              return (
                <button
                  key={oi}
                  onClick={() => setChosen(oi)}
                  aria-pressed={active}
                  className={`flex w-full gap-3 rounded-md border px-3.5 py-2.5 text-left text-[13.5px] transition-colors ${
                    active
                      ? "border-accent bg-tint-accent text-ink"
                      : "border-rule text-ink-2 hover:border-rule-strong"
                  }`}
                >
                  <span className="font-mono text-[11px] text-ink-3">
                    {String.fromCharCode(65 + oi)}
                  </span>
                  {option}
                </button>
              );
            })}
          </div>
          <div className="mt-7">
            <PrimaryButton
              onClick={() => answer(chosen)}
              busy={busy}
              disabled={chosen === null}
            >
              Answer
            </PrimaryButton>
          </div>
        </>
      )}

      {graded && (
        <div className="rounded-lg border border-rule bg-surface-2 px-4 py-4">
          <div
            className={`text-[11px] font-semibold uppercase tracking-[0.07em] ${
              graded.is_correct ? "text-good" : "text-critical"
            }`}
          >
            {graded.is_correct ? "Correct" : "Incorrect"}
          </div>
          {graded.explanation && (
            <p className="mt-2.5 text-[13px] leading-relaxed text-ink-2">
              {graded.explanation}
            </p>
          )}
          <div className="mt-5">
            <PrimaryButton
              onClick={() => {
                setGraded(null);
                setChosen(null);
              }}
            >
              {attempt.finished ? "See the result" : "Next question"}
            </PrimaryButton>
          </div>
        </div>
      )}
    </StepShell>
  );
}

/* ------------------------------------------------------------ 4. interview -- */

interface NextQuestion {
  done: boolean;
  answer_id: number | null;
  sequence: number | null;
  question: string | null;
  competency_name: string | null;
  asked_because: string | null;
  asked: number;
  max_questions: number;
}

export function InterviewStep({ onNext }: { onNext: () => void }) {
  const [interviewId, setInterviewId] = useState<number | null>(null);
  const [question, setQuestion] = useState<NextQuestion | null>(null);
  const [text, setText] = useState("");
  const [last, setLast] = useState<WrittenAnswerOut | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const started = useRef(false);

  useEffect(() => {
    // StrictMode runs effects twice in development; a second POST would open a
    // second interview and orphan the first.
    if (started.current) return;
    started.current = true;
    (async () => {
      try {
        const iv = await api.post<{ interview_id: number }>("/interviews", {});
        setInterviewId(iv.interview_id);
        setQuestion(
          await api.post<NextQuestion>(`/interviews/${iv.interview_id}/next-question`, {}),
        );
      } catch (e) {
        setError(e instanceof ApiError ? e.message : "Could not start the interview.");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  async function submitAnswer() {
    if (!interviewId || !question?.answer_id) return;
    setBusy(true);
    setError(null);
    try {
      const scored = await api.submitWrittenAnswer(interviewId, question.answer_id, text);
      setLast(scored);
      setText("");
      const next = await api.post<NextQuestion>(
        `/interviews/${interviewId}/next-question`,
        {},
      );
      setQuestion(next);
      if (next.done) await api.post(`/interviews/${interviewId}/complete`, {});
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not submit your answer.");
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <Spinner label="Opening an interview session" />;
  if (error && !question) return <ErrorNote message={error} />;

  const isCalibration = question?.sequence === 0;

  if (question?.done) {
    return (
      <StepShell
        eyebrow="Step 4 of 5"
        title="Interview complete"
        lede="Your answers have been scored and written to your evidence record."
      >
        {last && <ScoreCard result={last} />}
        <div className="mt-6">
          <PrimaryButton onClick={onNext}>See your analysis</PrimaryButton>
        </div>
      </StepShell>
    );
  }

  const tooShort = text.trim().length > 0 && text.trim().length < 20;

  return (
    <StepShell
      eyebrow="Step 4 of 5"
      // The calibration passage occupies sequence 0 and is not one of the
      // scored questions, so numbering it "question 2 of 5" both miscounts and
      // implies it is being marked.
      title={
        isCalibration
          ? "Interview — calibration"
          : `Interview — question ${Math.max(1, question?.asked ?? 1)} of ${
              (question?.max_questions ?? 5) - 1
            }`
      }
      lede={
        isCalibration
          ? "A short calibration passage first. Type it out as written — it establishes a baseline the later answers are compared against."
          : "Answer in your own words. You are scored on whether the content is right and whether the reasoning is clear."
      }
    >
      {error && <ErrorNote message={error} />}

      {question?.competency_name && (
        <div className="mb-4 flex flex-wrap items-center gap-2">
          <span className="rounded border border-rule-strong px-2.5 py-1 font-mono text-[10.5px] text-ink-3">
            {question.competency_name}
          </span>
          {question.asked_because && (
            <span className="text-[12px] text-ink-3">{question.asked_because}</span>
          )}
        </div>
      )}

      <p className="rounded border-l-2 border-accent bg-surface-2 px-4 py-3.5 text-[14.5px] leading-relaxed">
        {question?.question}
      </p>

      <label htmlFor="answer" className="mt-5 block text-[11px] font-semibold uppercase tracking-[0.07em] text-ink-3">
        Your answer
      </label>
      <textarea
        id="answer"
        rows={8}
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Explain your reasoning as you would to a colleague…"
        className={`${inputClass} resize-y leading-relaxed`}
      />
      <div className="mt-1.5 flex justify-between text-[11.5px] text-ink-3">
        <span>
          {tooShort ? "A little more — at least 20 characters." : " "}
        </span>
        <span className="tabular font-mono">{text.trim().split(/\s+/).filter(Boolean).length} words</span>
      </div>

      <div className="mt-5">
        <PrimaryButton onClick={submitAnswer} busy={busy} disabled={text.trim().length < 20}>
          Submit answer
        </PrimaryButton>
      </div>

      {last && (
        <div className="mt-7 border-t border-rule pt-5">
          <div className="font-mono text-[10.5px] uppercase tracking-[0.12em] text-ink-3">
            Previous answer
          </div>
          <div className="mt-3">
            <ScoreCard result={last} />
          </div>
        </div>
      )}
    </StepShell>
  );
}

function ScoreCard({ result }: { result: WrittenAnswerOut }) {
  const axes: [string, number | null][] = [
    ["Knowledge", result.scored.knowledge],
    ["Structure", result.scored.structure],
    ["Communication", result.scored.communication],
    ["Fluency", result.scored.fluency],
    ["Confidence", result.scored.confidence],
  ];
  return (
    <div className="rounded border border-rule bg-surface-2 p-4">
      <div className="grid grid-cols-2 gap-x-6 gap-y-2 sm:grid-cols-5">
        {axes.map(([label, value]) => (
          <div key={label}>
            <div className="text-[10px] font-semibold uppercase tracking-[0.08em] text-ink-3">
              {label}
            </div>
            <div
              className={`tabular mt-1 font-mono text-[17px] ${
                value === null ? "text-ink-3" : "font-medium"
              }`}
            >
              {value === null ? "—" : value.toFixed(2)}
            </div>
          </div>
        ))}
      </div>
      {result.covered_points.length + result.missed_points.length > 0 && (
        <div className="mt-3.5 border-t border-rule pt-3 text-[12px] leading-relaxed">
          {result.covered_points.length > 0 && (
            <p className="text-ink-2">
              <span className="text-good">Covered:</span>{" "}
              {result.covered_points.join("; ")}
            </p>
          )}
          {result.missed_points.length > 0 && (
            <p className="mt-1 text-ink-2">
              <span className="text-warn">Missed:</span> {result.missed_points.join("; ")}
            </p>
          )}
        </div>
      )}
      <p className="mt-3 text-[11.5px] leading-relaxed text-ink-3">
        {result.note}
        {result.degraded && " The scoring model was unavailable, so this is a degraded verdict."}
      </p>
    </div>
  );
}

export type { Gap, JourneyOut };
