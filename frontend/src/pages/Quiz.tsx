import { useCallback, useEffect, useState } from "react";

import { ApiError, api } from "../api";
import { PageHeader } from "../components/Layout";
import { AbilityScale, AbilityTrace } from "../components/AbilityScale";
import type { Ability, TraceStep } from "../components/AbilityScale";
import { btnPrimary, btnSecondary, Card, Empty, ErrorNote, Note, Spinner, StatTile } from "../components/ui";
import { usePageTitle } from "../hooks/usePageTitle";
import type { Competency, Gap } from "../types";

/**
 * The adaptive assessment.
 *
 * One question at a time, and the officer is shown *why* each one was chosen.
 * That transparency is not decoration: an assessment that silently changes
 * difficulty feels like it is reacting to something it will not say, and the
 * whole point of the Skill Twin is that an officer can argue with it.
 *
 * Three rules this screen keeps:
 *
 * **It never holds the answer key for an open question.** The key arrives in
 * the response to the answer, for that question only. There is nothing to hide
 * with CSS because there is nothing here to hide.
 *
 * **It never decides what to ask.** The server picks; this renders. A client
 * that could choose its own next item could choose easy ones.
 *
 * **It shows the interval, never the point alone.** Twelve four-option items
 * support roughly ±0.65 of a FRAC level, and the band narrowing question by
 * question is the clearest evidence the test is doing anything at all.
 */

interface AdaptiveItem {
  sequence: number;
  question_id: number;
  stem: string;
  options: string[];
  bloom_level: string;
  difficulty_level: number;
  is_calibrated: boolean;
  information: number;
  asked_because: string | null;
}

interface GradedItem {
  question_id: number;
  stem: string;
  options: string[];
  selected_index: number | null;
  correct_index: number;
  is_correct: boolean;
  skipped: boolean;
  difficulty_level: number;
  explanation: string | null;
  distractor_rationale: string[] | null;
  citation: { page: number | null; quote: string | null } | null;
}

interface Attempt {
  id: number;
  competency_id: number | null;
  competency_name: string | null;
  status: string;
  asked: number;
  correct: number;
  min_items: number;
  max_items: number;
  target_se: number;
  ability: Ability;
  current_item: AdaptiveItem | null;
  finished: boolean;
  stop_reason: string | null;
  stop_explanation: string | null;
}

interface Result {
  attempt_id: number;
  competency_id: number | null;
  competency_name: string | null;
  asked: number;
  correct: number;
  accuracy: number;
  ability: Ability;
  derived_level: number;
  confidence: number;
  stop_reason: string | null;
  stop_explanation: string | null;
  mean_item_level: number | null;
  trace: TraceStep[];
  review: GradedItem[];
  note: string;
}

interface AnswerOut {
  graded: GradedItem;
  ability: Ability;
  next_item: AdaptiveItem | null;
  attempt: Attempt;
  result: Result | null;
}

interface History {
  attempts: {
    id: number;
    competency_name: string | null;
    correct: number;
    items: number;
    accuracy: number;
    derived_level: number | null;
    level_low: number | null;
    level_high: number | null;
    adaptive: boolean;
    stop_reason: string | null;
    submitted_at: string;
  }[];
  item_health: {
    approved_items: number;
    with_statistics: number;
    min_attempts: number;
    irt_calibrated: number;
    min_responses_to_calibrate: number;
  };
  settings: { min_items: number; max_items: number; target_se: number };
}

/**
 * The rationale for one option, out of a list that has no slot for the key.
 *
 * `distractor_rationale` holds one entry per *distractor*, in option order —
 * three for a four-option item. Indexing it by option position is off by one
 * for every option after the key, and silently so: it returns a real sentence
 * about a different option rather than erroring.
 */
function rationaleFor(
  rationales: string[] | null,
  optionIndex: number,
  correctIndex: number,
): string | null {
  if (!rationales || optionIndex === correctIndex) return null;
  const position = optionIndex > correctIndex ? optionIndex - 1 : optionIndex;
  return rationales[position] ?? null;
}

const STOP_LABEL: Record<string, string> = {
  precision: "Stopped early — enough precision",
  max_items: "Stopped at the item ceiling",
  exhausted: "Stopped — bank exhausted",
  no_informative_items: "Stopped — nothing left worth asking",
};

export function Quiz() {
  usePageTitle("title.quiz");

  const [history, setHistory] = useState<History | null>(null);
  const [gaps, setGaps] = useState<Gap[]>([]);
  const [, setCompetencies] = useState<Competency[]>([]);

  const [attempt, setAttempt] = useState<Attempt | null>(null);
  const [item, setItem] = useState<AdaptiveItem | null>(null);
  const [ability, setAbility] = useState<Ability | null>(null);
  const [choice, setChoice] = useState<number | null>(null);
  const [graded, setGraded] = useState<GradedItem | null>(null);
  const [result, setResult] = useState<Result | null>(null);

  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [askedAt, setAskedAt] = useState<number>(Date.now());

  const load = useCallback(async () => {
    const [h, g, c] = await Promise.all([
      api.get<History>("/quizzes"),
      api.get<Gap[]>("/gaps/me"),
      api.get<Competency[]>("/frac/competencies"),
    ]);
    setHistory(h);
    setGaps(g);
    setCompetencies(c);
  }, []);

  useEffect(() => {
    load()
      .catch((e) => setError(e instanceof Error ? e.message : "Could not load assessments."))
      .finally(() => setLoading(false));
  }, [load]);

  const requiredLevel =
    attempt?.competency_id != null
      ? (gaps.find((g) => g.competency_id === attempt.competency_id)?.required_level ?? null)
      : null;

  async function start(competencyId?: number) {
    setBusy(true);
    setError(null);
    setResult(null);
    setGraded(null);
    setChoice(null);
    try {
      const created = await api.post<Attempt>("/quizzes", {
        competency_id: competencyId ?? null,
      });
      setAttempt(created);
      setItem(created.current_item);
      setAbility(created.ability);
      setAskedAt(Date.now());
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not start an assessment.");
    } finally {
      setBusy(false);
    }
  }

  async function submitAnswer() {
    if (!attempt || !item) return;
    setBusy(true);
    setError(null);
    try {
      const out = await api.post<AnswerOut>(`/quizzes/${attempt.id}/answer`, {
        question_id: item.question_id,
        selected_index: choice,
        seconds_taken: Math.round((Date.now() - askedAt) / 100) / 10,
      });
      setGraded(out.graded);
      setAbility(out.ability);
      setAttempt(out.attempt);
      // The next question is held back until the officer has read the feedback
      // on this one. Advancing straight past the explanation would make this a
      // measurement instrument and nothing else.
      setItem(out.next_item);
      if (out.result) setResult(out.result);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not submit that answer.");
    } finally {
      setBusy(false);
    }
  }

  /** Dismiss the feedback on the question just answered and move on. */
  function advance() {
    setGraded(null);
    setChoice(null);
    setAskedAt(Date.now());
    if (result) {
      // The attempt is over; clearing these drops us onto the result screen.
      setAttempt(null);
      setItem(null);
      void load();
    }
  }

  /** Leave the result screen and go back to the start.
   *
   * Separate from `advance` because it is the only place `result` is cleared,
   * and sharing one handler meant "Done" re-rendered the same result screen —
   * the button looked live and did nothing.
   */
  function finish() {
    setResult(null);
    setGraded(null);
    setChoice(null);
    setAttempt(null);
    setItem(null);
    setAbility(null);
    void load();
  }

  async function abandon() {
    if (!attempt) return;
    try {
      await api.post(`/quizzes/${attempt.id}/abandon`, {});
    } catch {
      /* Leaving is the intent either way. */
    }
    setAttempt(null);
    setItem(null);
    setGraded(null);
    setResult(null);
    void load();
  }

  if (loading) return <Spinner label="Loading" />;

  // ------------------------------------------------------------- result --
  if (result && !graded) {
    return <ResultView result={result} requiredLevel={requiredLevel} onDone={finish} />;
  }

  // -------------------------------------------------------- taking one --
  if (attempt && !attempt.finished) {
    return (
      <TakingView
        attempt={attempt}
        item={item}
        ability={ability ?? attempt.ability}
        graded={graded}
        choice={choice}
        busy={busy}
        error={error}
        requiredLevel={requiredLevel}
        onChoose={setChoice}
        onSubmit={submitAnswer}
        onAdvance={advance}
        onAbandon={abandon}
      />
    );
  }

  // Feedback on the final question, before the result screen.
  if (graded && attempt) {
    return (
      <TakingView
        attempt={attempt}
        item={null}
        ability={ability ?? attempt.ability}
        graded={graded}
        choice={choice}
        busy={busy}
        error={error}
        requiredLevel={requiredLevel}
        onChoose={setChoice}
        onSubmit={submitAnswer}
        onAdvance={advance}
        onAbandon={abandon}
      />
    );
  }

  // -------------------------------------------------------------- start --
  const openGaps = gaps.filter((g) => g.gap > 0.1);
  return (
    <>
      <PageHeader
        title="Adaptive assessment"
        subtitle="Each question is chosen from how you answered the last one"
        meta={
          history
            ? `${history.settings.min_items}–${history.settings.max_items} questions · stops when the estimate is precise enough`
            : undefined
        }
      />

      {error && (
        <div className="mb-4">
          <ErrorNote message={error} />
        </div>
      )}

      <div className="grid gap-3.5 lg:grid-cols-[minmax(0,1fr)_360px]">
        <Card
          title="Start an assessment"
          hint="Pick a competency, or let it choose your widest gap"
        >
          <button
            disabled={busy}
            onClick={() => start()}
            className={`${btnPrimary} w-full`}
          >
            {busy ? "Preparing…" : "Assess my widest gap"}
          </button>

          {openGaps.length > 0 && (
            <div className="mt-4 border-t border-rule pt-3">
              <div className="mb-2 text-[11px] font-semibold uppercase tracking-[0.07em] text-ink-3">
                Or choose a competency
              </div>
              <div className="flex flex-wrap gap-2">
                {openGaps.map((gap) => (
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
          )}

          <div className="mt-4">
            <Note>
              <strong className="font-semibold text-ink">
                This is not a fixed paper.
              </strong>{" "}
              Every question has a difficulty on the same L1–L5 scale your
              competency is measured on, and the next one is always picked to sit
              near where you are currently estimated — which is where an answer
              tells us the most. Answer well and it gets harder; miss and it
              steps back. It stops when the estimate is precise enough, which is
              usually before the ceiling.
            </Note>
          </div>
        </Card>

        <Card title="Item bank" hint="What the assessment has to draw on">
          {history && (
            <dl className="space-y-2 text-[13px]">
              <div className="flex justify-between gap-3">
                <dt className="text-ink-2">Approved questions</dt>
                <dd className="tabular font-mono font-semibold">
                  {history.item_health.approved_items}
                </dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-ink-2">Difficulty calibrated from responses</dt>
                <dd className="tabular font-mono font-semibold">
                  {history.item_health.irt_calibrated}
                </dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-ink-2">With classical item statistics</dt>
                <dd className="tabular font-mono font-semibold">
                  {history.item_health.with_statistics}
                </dd>
              </div>
              <p className="border-t border-rule pt-2.5 text-[11.5px] leading-relaxed text-ink-3">
                An item needs {history.item_health.min_responses_to_calibrate} responses
                before its difficulty can be estimated from data rather than from
                the author's judgement. Until then it is used, and labelled as
                authored rather than measured.
              </p>
            </dl>
          )}
        </Card>
      </div>

      {history && history.attempts.length > 0 && (
        <div className="mt-4">
          <Card
            title="Previous attempts"
            hint="Compare the intervals, not the points — two overlapping estimates are not a measured change"
          >
            <div className="divide-y divide-rule">
              {history.attempts.map((a) => (
                <div
                  key={a.id}
                  className="grid grid-cols-[minmax(0,1fr)_100px_130px_auto] items-center gap-3 py-2.5 first:pt-0"
                >
                  <span className="truncate text-[13.5px]">{a.competency_name}</span>
                  <span className="tabular font-mono text-[12px] text-ink-3">
                    {a.correct} / {a.items}
                  </span>
                  <span className="tabular font-mono text-[12.5px]">
                    <span className="font-semibold">L{a.derived_level}</span>
                    {a.level_low != null && a.level_high != null && (
                      <span className="ml-1.5 text-[11px] text-ink-3">
                        ({a.level_low}–{a.level_high})
                      </span>
                    )}
                  </span>
                  <span className="text-right text-[11px] text-ink-3">
                    {a.adaptive ? (STOP_LABEL[a.stop_reason ?? ""] ?? "Adaptive") : "Fixed form"}
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

// --------------------------------------------------------------------------- //
// Taking one
// --------------------------------------------------------------------------- //

function TakingView({
  attempt,
  item,
  ability,
  graded,
  choice,
  busy,
  error,
  requiredLevel,
  onChoose,
  onSubmit,
  onAdvance,
  onAbandon,
}: {
  attempt: Attempt;
  item: AdaptiveItem | null;
  ability: Ability;
  graded: GradedItem | null;
  choice: number | null;
  busy: boolean;
  error: string | null;
  requiredLevel: number | null;
  onChoose: (index: number) => void;
  onSubmit: () => void;
  onAdvance: () => void;
  onAbandon: () => void;
}) {
  const showing = graded ?? item;
  if (!showing) return <Empty>No question is open on this attempt.</Empty>;

  const number = attempt.asked + (graded ? 0 : 1);

  return (
    <>
      <PageHeader
        title={attempt.competency_name ?? "Assessment"}
        subtitle={`Question ${number} — the test decides its own length`}
        meta={`${attempt.correct} of ${attempt.asked} correct so far · ceiling ${attempt.max_items}`}
        action={
          <button
            onClick={onAbandon}
            className={btnSecondary}
          >
            Leave
          </button>
        }
      />

      {error && (
        <div className="mb-4">
          <ErrorNote message={error} />
        </div>
      )}

      <div className="mb-4 grid gap-3.5 lg:grid-cols-[minmax(0,1fr)_300px]">
        <Card>
          <AbilityScale
            ability={ability}
            itemLevel={graded ? graded.difficulty_level : item?.difficulty_level}
            requiredLevel={requiredLevel}
            label={graded ? "Where the estimate moved to" : "This question, against your estimate"}
          />
        </Card>

        <div className="grid grid-cols-2 gap-3.5 lg:grid-cols-1">
          <StatTile
            label="Precision"
            value={`±${(1.96 * ability.se * (2 / 3)).toFixed(2)}`}
            note={`Stops at ±${(1.96 * attempt.target_se * (2 / 3)).toFixed(2)} of a level`}
          />
          <StatTile
            label="Progress"
            value={`${attempt.asked} / ${attempt.max_items}`}
            note={`At least ${attempt.min_items} before it can stop early`}
          />
        </div>
      </div>

      {/* Why this question. Shown before the question, not after, because it is
          context for reading it rather than a justification afterwards. */}
      {!graded && item?.asked_because && (
        <div className="mb-3.5">
          <Note tone="brass">
            <span className="font-semibold text-ink">Why this question: </span>
            {item.asked_because}{" "}
            <span className="text-ink-3">
              Difficulty L{item.difficulty_level.toFixed(1)} ·{" "}
              {item.is_calibrated
                ? "calibrated from real responses"
                : "difficulty set by the author, not yet calibrated"}
              .
            </span>
          </Note>
        </div>
      )}

      <Card
        title={`Question ${number}`}
        hint={graded ? undefined : item?.bloom_level}
        action={
          graded ? (
            <span
              className={`text-[11px] font-semibold uppercase tracking-[0.05em] ${
                graded.skipped
                  ? "text-ink-3"
                  : graded.is_correct
                    ? "text-good"
                    : "text-critical"
              }`}
            >
              {graded.skipped ? "Skipped" : graded.is_correct ? "Correct" : "Incorrect"}
            </span>
          ) : undefined
        }
      >
        <fieldset disabled={!!graded || busy}>
          <legend className="text-[15px] leading-relaxed">{showing.stem}</legend>
          <div className="mt-4 space-y-1.5">
            {showing.options.map((option, index) => {
              const isKey = graded != null && index === graded.correct_index;
              const isYours = graded
                ? index === graded.selected_index
                : index === choice;

              const tone = graded
                ? isKey
                  ? "border-good bg-tint-good"
                  : isYours
                    ? "border-critical bg-tint-critical"
                    : "border-rule"
                : isYours
                  ? "border-accent bg-tint-accent"
                  : "border-rule hover:border-rule-strong";

              return (
                <label
                  key={index}
                  htmlFor={`o${index}`}
                  className={`flex items-start gap-3 border px-3 py-2 text-[13.5px] transition-colors ${tone} ${
                    graded ? "" : "cursor-pointer"
                  }`}
                >
                  <input
                    type="radio"
                    id={`o${index}`}
                    name="answer"
                    checked={isYours}
                    onChange={() => onChoose(index)}
                    className="mt-0.5"
                  />
                  <span className="font-mono text-[11.5px] text-ink-3">
                    {String.fromCharCode(65 + index)}
                  </span>
                  <span className="flex-1">{option}</span>
                  {isKey && (
                    <span className="text-[10.5px] font-semibold uppercase tracking-[0.05em] text-good">
                      Correct
                    </span>
                  )}
                  {graded && isYours && !isKey && (
                    <span className="text-[10.5px] font-semibold uppercase tracking-[0.05em] text-critical">
                      Your answer
                    </span>
                  )}
                </label>
              );
            })}
          </div>
        </fieldset>

        {graded && (
          <div className="mt-4 border-t border-rule pt-3.5">
            {graded.explanation && (
              <p className="text-[13.5px] leading-relaxed text-ink-2">
                {graded.explanation}
              </p>
            )}

            {/* Why the option they picked was wrong — the part that makes this a
                learning tool rather than a scoreboard. Only their own is shown:
                four rationales at once is a wall nobody reads. */}
            {!graded.is_correct &&
              !graded.skipped &&
              graded.selected_index != null &&
              rationaleFor(
                graded.distractor_rationale,
                graded.selected_index,
                graded.correct_index,
              ) && (
                <p className="mt-3 border-l-2 border-critical pl-3 text-[13px] leading-relaxed text-ink-2">
                  <span className="font-semibold text-ink">
                    Why {String.fromCharCode(65 + graded.selected_index)} is wrong:{" "}
                  </span>
                  {rationaleFor(
                    graded.distractor_rationale,
                    graded.selected_index,
                    graded.correct_index,
                  )}
                </p>
              )}

            {graded.citation?.quote && (
              <blockquote className="mt-3 border-l-2 border-brass bg-tint-brass px-3 py-2 text-[12.5px] italic leading-relaxed text-ink-2">
                &ldquo;{graded.citation.quote}&rdquo;
              </blockquote>
            )}
          </div>
        )}
      </Card>

      <div className="mt-4 flex items-center justify-between gap-4">
        <p className="text-[11.5px] leading-relaxed text-ink-3">
          {graded
            ? "This question will not be asked again, so the explanation is safe to read now."
            : "Leaving a question unanswered counts as incorrect — declining a question pitched at your own level is a result, not an absence."}
        </p>
        {graded ? (
          <button
            onClick={onAdvance}
            className={`${btnPrimary} shrink-0`}
          >
            {attempt.finished ? "See the result" : "Next question"}
          </button>
        ) : (
          <div className="flex shrink-0 gap-2">
            <button
              disabled={busy}
              onClick={onSubmit}
              className={btnSecondary}
            >
              Skip
            </button>
            <button
              disabled={busy || choice === null}
              onClick={onSubmit}
              className={btnPrimary}
            >
              {busy ? "Scoring…" : "Answer"}
            </button>
          </div>
        )}
      </div>
    </>
  );
}

// --------------------------------------------------------------------------- //
// The result
// --------------------------------------------------------------------------- //

function ResultView({
  result,
  requiredLevel,
  onDone,
}: {
  result: Result;
  requiredLevel: number | null;
  onDone: () => void;
}) {
  return (
    <>
      <PageHeader
        title="Assessment result"
        subtitle={result.competency_name ?? ""}
        meta={STOP_LABEL[result.stop_reason ?? ""] ?? undefined}
        action={
          <button
            onClick={onDone}
            className={btnSecondary}
          >
            Done
          </button>
        }
      />

      <div className="mb-4 grid gap-3.5 sm:grid-cols-2 lg:grid-cols-4">
        <StatTile
          label="Assessed level"
          value={`L${result.derived_level}`}
          note={`95% interval L${result.ability.level_low}–L${result.ability.level_high}`}
        />
        <StatTile
          label="Questions asked"
          value={result.asked}
          note={`${result.correct} correct (${result.accuracy}%)`}
        />
        <StatTile
          label="Evidence weight"
          value={result.confidence.toFixed(2)}
          note="Marginal reliability — how much of the range this resolved"
        />
        <StatTile
          label="Mean question level"
          value={result.mean_item_level ? `L${result.mean_item_level}` : "—"}
          note="A well-adapted test lands near your own level"
        />
      </div>

      <div className="mb-4 grid gap-3.5 lg:grid-cols-[minmax(0,1fr)_340px]">
        <Card
          title="How the estimate got there"
          hint="Question difficulty chasing your ability, and the interval closing"
        >
          <AbilityTrace steps={result.trace} />
        </Card>

        <div className="grid gap-3.5">
          <Card title="Final estimate">
            <AbilityScale
              ability={result.ability}
              requiredLevel={requiredLevel}
              label="Recorded as evidence"
            />
            <p className="mt-4 text-[12.5px] leading-relaxed text-ink-2">{result.note}</p>
          </Card>

          {result.stop_explanation && (
            <Note>
              <span className="font-semibold text-ink">Why it stopped here: </span>
              {result.stop_explanation}
            </Note>
          )}
        </div>
      </div>

      <Card title="Every question, with the answer key" hint="Now that the attempt is closed">
        <div className="divide-y divide-rule">
          {result.review.map((q, index) => (
            <div key={q.question_id} className="py-4 first:pt-0 last:pb-0">
              <div className="mb-2 flex items-baseline justify-between gap-3">
                <span className="text-[11px] font-semibold uppercase tracking-[0.06em] text-ink-3">
                  Question {index + 1} · difficulty L{q.difficulty_level.toFixed(1)}
                </span>
                <span
                  className={`text-[10.5px] font-semibold uppercase tracking-[0.05em] ${
                    q.skipped ? "text-ink-3" : q.is_correct ? "text-good" : "text-critical"
                  }`}
                >
                  {q.skipped ? "Skipped" : q.is_correct ? "Correct" : "Incorrect"}
                </span>
              </div>
              <p className="text-[13.5px] leading-relaxed">{q.stem}</p>
              <ul className="mt-2.5 space-y-1">
                {q.options.map((option, optionIndex) => {
                  const isKey = optionIndex === q.correct_index;
                  const isYours = optionIndex === q.selected_index;
                  if (!isKey && !isYours) return null;
                  return (
                    <li
                      key={optionIndex}
                      className={`flex items-start gap-2.5 border px-3 py-1.5 text-[13px] ${
                        isKey ? "border-good bg-tint-good" : "border-critical bg-tint-critical"
                      }`}
                    >
                      <span className="font-mono text-[11px] text-ink-3">
                        {String.fromCharCode(65 + optionIndex)}
                      </span>
                      <span className="flex-1">{option}</span>
                      <span
                        className={`text-[10px] font-semibold uppercase tracking-[0.05em] ${
                          isKey ? "text-good" : "text-critical"
                        }`}
                      >
                        {isKey ? "Correct" : "Yours"}
                      </span>
                    </li>
                  );
                })}
              </ul>
              {q.explanation && (
                <p className="mt-2.5 text-[12.5px] leading-relaxed text-ink-2">
                  {q.explanation}
                </p>
              )}
            </div>
          ))}
        </div>
      </Card>
    </>
  );
}
