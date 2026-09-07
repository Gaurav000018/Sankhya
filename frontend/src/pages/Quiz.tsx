import { useCallback, useEffect, useState } from "react";

import { ApiError, api } from "../api";
import { PageHeader } from "../components/Layout";
import { Card, Empty, ErrorNote, Note, Spinner, StatTile } from "../components/ui";
import { usePageTitle } from "../hooks/usePageTitle";
import type { Competency, Gap } from "../types";

/**
 * Taking a quiz.
 *
 * Everything served here has been approved by a subject expert, and the answer
 * key never reaches the browser until the attempt is submitted — it is withheld
 * server-side, not hidden with CSS.
 */

interface QuizItem {
  sequence: number;
  question_id: number;
  stem: string;
  options: string[];
  bloom_level: string;
  selected_index: number | null;
  correct_index: number | null;
  is_correct: boolean | null;
  explanation: string | null;
  citation: { page: number | null; quote: string | null } | null;
}

interface Attempt {
  id: number;
  competency_id: number | null;
  competency_name: string | null;
  status: string;
  item_count: number;
  mean_difficulty: number | null;
  items: QuizItem[];
}

interface Result {
  attempt: Attempt;
  correct: number;
  total: number;
  accuracy: number;
  derived_level: number;
  confidence: number;
  note: string;
}

interface History {
  attempts: {
    id: number;
    competency_name: string | null;
    correct: number;
    items: number;
    accuracy: number;
    derived_level: number | null;
    submitted_at: string;
  }[];
  item_health: { approved_items: number; with_statistics: number; min_attempts: number };
}

export function Quiz() {
  usePageTitle("title.quiz");

  const [history, setHistory] = useState<History | null>(null);
  const [gaps, setGaps] = useState<Gap[]>([]);
  const [competencies, setCompetencies] = useState<Competency[]>([]);
  const [attempt, setAttempt] = useState<Attempt | null>(null);
  const [answers, setAnswers] = useState<Record<number, number>>({});
  const [result, setResult] = useState<Result | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    const [h, g, c] = await Promise.all([
      api.get<History>("/quizzes"),
      api.get<Gap[]>("/gaps/me"),
      api.get<Competency[]>("/frac/competencies"),
    ]);
    setHistory(h);
    setGaps(g.filter((x) => x.gap > 0.1));
    setCompetencies(c);
  }, []);

  useEffect(() => {
    load()
      .catch((e) => setError(e instanceof Error ? e.message : "Could not load quizzes."))
      .finally(() => setLoading(false));
  }, [load]);

  async function start(competencyId?: number) {
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const created = await api.post<Attempt>("/quizzes", {
        competency_id: competencyId ?? null,
        item_count: 6,
      });
      setAttempt(created);
      setAnswers({});
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not start a quiz.");
    } finally {
      setBusy(false);
    }
  }

  async function submit() {
    if (!attempt) return;
    setBusy(true);
    try {
      const submitted = await api.post<Result>(`/quizzes/${attempt.id}/submit`, {
        answers: Object.entries(answers).map(([question_id, selected_index]) => ({
          question_id: Number(question_id),
          selected_index,
        })),
      });
      setResult(submitted);
      setAttempt(null);
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not submit the quiz.");
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <Spinner label="Loading" />;

  const answered = attempt ? Object.keys(answers).length : 0;
  const competencyName = (id: number | null) =>
    competencies.find((c) => c.id === id)?.name ?? "";

  // ----------------------------------------------------------- taking one --
  if (attempt) {
    return (
      <>
        <PageHeader
          title={attempt.competency_name ?? "Quiz"}
          subtitle={`${attempt.item_count} questions, all reviewed by a subject expert`}
          meta={`Mean difficulty ${attempt.mean_difficulty} of 5 · ${answered} of ${attempt.item_count} answered`}
          action={
            <button
              disabled={busy || answered === 0}
              onClick={submit}
              className="bg-accent px-4 py-2 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
            >
              {busy ? "Submitting…" : "Submit"}
            </button>
          }
        />

        {error && (
          <div className="mb-4">
            <ErrorNote message={error} />
          </div>
        )}

        <div className="grid gap-3.5">
          {attempt.items.map((item, index) => (
            <Card key={item.question_id} title={`Question ${index + 1}`} hint={item.bloom_level}>
              <fieldset>
                <legend className="text-[15px] leading-relaxed">{item.stem}</legend>
                <div className="mt-4 space-y-1.5">
                  {item.options.map((option, optionIndex) => {
                    const id = `q${item.question_id}-o${optionIndex}`;
                    const chosen = answers[item.question_id] === optionIndex;
                    return (
                      <label
                        key={optionIndex}
                        htmlFor={id}
                        className={`flex cursor-pointer items-start gap-3 border px-3 py-2 text-[13.5px] transition-colors ${
                          chosen ? "border-accent bg-[#f3f5f9]" : "border-rule hover:border-rule-strong"
                        }`}
                      >
                        <input
                          type="radio"
                          id={id}
                          name={`question-${item.question_id}`}
                          checked={chosen}
                          onChange={() =>
                            setAnswers((prev) => ({ ...prev, [item.question_id]: optionIndex }))
                          }
                          className="mt-0.5"
                        />
                        <span className="font-mono text-[11.5px] text-ink-3">
                          {String.fromCharCode(65 + optionIndex)}
                        </span>
                        <span className="flex-1">{option}</span>
                      </label>
                    );
                  })}
                </div>
              </fieldset>
            </Card>
          ))}
        </div>

        <div className="mt-4">
          <Note>
            Unanswered questions count as incorrect — leaving one blank is a result,
            not an absence. Your score becomes competency evidence weighted by how
            many questions you answered and how hard they were.
          </Note>
        </div>
      </>
    );
  }

  // -------------------------------------------------------------- result --
  if (result) {
    return (
      <>
        <PageHeader
          title="Quiz result"
          subtitle={result.attempt.competency_name ?? ""}
          action={
            <button
              onClick={() => setResult(null)}
              className="border border-rule-strong px-4 py-2 text-sm text-ink-2 transition-colors hover:border-accent hover:text-ink"
            >
              Done
            </button>
          }
        />

        <div className="mb-4 grid gap-3.5 sm:grid-cols-4">
          <StatTile label="Correct" value={`${result.correct} / ${result.total}`} />
          <StatTile label="Accuracy" value={result.accuracy} unit="%" />
          <StatTile
            label="Assessed level"
            value={`L${result.derived_level}`}
            note="Adjusted for how hard the paper was"
          />
          <StatTile
            label="Evidence weight"
            value={result.confidence}
            note="Reflects how many questions you answered"
          />
        </div>

        <div className="mb-4">
          <Note>{result.note}</Note>
        </div>

        <div className="grid gap-3.5">
          {result.attempt.items.map((item, index) => (
            <Card
              key={item.question_id}
              title={`Question ${index + 1}`}
              hint={item.is_correct ? "Correct" : "Incorrect"}
            >
              <p className="text-[14px] leading-relaxed">{item.stem}</p>
              <ul className="mt-3 space-y-1.5">
                {item.options.map((option, optionIndex) => {
                  const isKey = optionIndex === item.correct_index;
                  const isYours = optionIndex === item.selected_index;
                  return (
                    <li
                      key={optionIndex}
                      className={`flex items-start gap-3 border px-3 py-2 text-[13.5px] ${
                        isKey
                          ? "border-good bg-[#f2f7f4]"
                          : isYours
                            ? "border-critical bg-[#faf3f2]"
                            : "border-rule"
                      }`}
                    >
                      <span className="font-mono text-[11.5px] text-ink-3">
                        {String.fromCharCode(65 + optionIndex)}
                      </span>
                      <span className="flex-1">{option}</span>
                      {isKey && (
                        <span className="text-[10.5px] font-semibold uppercase tracking-[0.05em] text-good">
                          Correct
                        </span>
                      )}
                      {isYours && !isKey && (
                        <span className="text-[10.5px] font-semibold uppercase tracking-[0.05em] text-critical">
                          Your answer
                        </span>
                      )}
                    </li>
                  );
                })}
              </ul>

              {item.explanation && (
                <p className="mt-3 text-[13px] leading-relaxed text-ink-2">{item.explanation}</p>
              )}

              {item.citation?.quote && (
                <blockquote className="mt-3 border-l-2 border-brass bg-[#f6f4ee] px-3 py-2 text-[12.5px] italic leading-relaxed text-ink-2">
                  &ldquo;{item.citation.quote}&rdquo;
                  {item.citation.page && (
                    <span className="ml-2 font-mono not-italic text-[11px] text-ink-3">
                      page {item.citation.page}
                    </span>
                  )}
                </blockquote>
              )}
            </Card>
          ))}
        </div>
      </>
    );
  }

  // --------------------------------------------------------------- start --
  return (
    <>
      <PageHeader
        title="Assessment"
        subtitle="Quizzes drawn from your competency gaps"
        meta="Every question has been reviewed by a subject expert before being used"
      />

      {error && (
        <div className="mb-4">
          <ErrorNote message={error} />
        </div>
      )}

      <div className="grid gap-3.5 lg:grid-cols-[minmax(0,1fr)_360px]">
        <Card title="Start a quiz" hint="Pick a competency, or let it choose your widest gap">
          {gaps.length === 0 ? (
            <Empty>Every competency meets its requirement — nothing to assess.</Empty>
          ) : (
            <>
              <button
                disabled={busy}
                onClick={() => start()}
                className="w-full bg-accent px-4 py-2.5 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
              >
                {busy ? "Preparing…" : "Assess my widest gap"}
              </button>

              <div className="mt-4 border-t border-rule pt-3">
                <div className="mb-2 text-[11px] font-semibold uppercase tracking-[0.07em] text-ink-3">
                  Or choose a competency
                </div>
                <div className="flex flex-wrap gap-2">
                  {gaps.map((gap) => (
                    <button
                      key={gap.competency_id}
                      disabled={busy}
                      onClick={() => start(gap.competency_id)}
                      className="border border-rule-strong px-3 py-1.5 text-[12.5px] text-ink-2 transition-colors hover:border-accent hover:text-ink disabled:opacity-50"
                    >
                      {gap.competency_name}
                      <span className="tabular ml-2 font-mono text-[11px] text-ink-3">
                        L{gap.current_level}
                      </span>
                    </button>
                  ))}
                </div>
              </div>
            </>
          )}
        </Card>

        <Card title="Question bank" hint="How much of it has enough data to be trusted">
          {history && (
            <dl className="space-y-2 text-[13px]">
              <div className="flex justify-between gap-3">
                <dt className="text-ink-2">Approved questions</dt>
                <dd className="tabular font-mono font-semibold">
                  {history.item_health.approved_items}
                </dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-ink-2">With item statistics</dt>
                <dd className="tabular font-mono font-semibold">
                  {history.item_health.with_statistics}
                </dd>
              </div>
              <p className="border-t border-rule pt-2.5 text-[11.5px] leading-relaxed text-ink-3">
                An item needs {history.item_health.min_attempts} attempts before its
                difficulty and discrimination mean anything. Until then it is used
                but not judged.
              </p>
            </dl>
          )}
        </Card>
      </div>

      {history && history.attempts.length > 0 && (
        <div className="mt-4">
          <Card title="Previous attempts">
            <div className="divide-y divide-rule">
              {history.attempts.map((a) => (
                <div
                  key={a.id}
                  className="grid grid-cols-[minmax(0,1fr)_110px_90px_90px] items-center gap-3 py-2.5 first:pt-0"
                >
                  <span className="truncate text-[13.5px]">
                    {a.competency_name ?? competencyName(null)}
                  </span>
                  <span className="tabular font-mono text-[12px] text-ink-3">
                    {a.correct} / {a.items} correct
                  </span>
                  <span className="tabular text-right font-mono text-[13px] font-semibold">
                    {a.accuracy}%
                  </span>
                  <span className="tabular text-right font-mono text-[12px] text-ink-2">
                    L{a.derived_level}
                  </span>
                </div>
              ))}
            </div>
          </Card>
        </div>
      )}
    </>
  );
}
