import { Card, Empty, Note } from "./ui";
import type { AttentionReport, Coaching, FollowThrough } from "../types";

/**
 * The five-axis report.
 *
 * There is no overall figure and no place to put one. Knowledge is the only
 * axis that becomes competency evidence; Structure, Communication, Delivery and
 * Confidence are coaching feedback — and the report says so rather than leaving
 * the reader to infer it.
 *
 * Camera notes appear only in the officer's own copy. The server strips them
 * for every other reader, so this component never has to decide.
 */

export interface Mistake {
  quote: string;
  problem: string;
  correction: string;
}

export interface TechnicalTerms {
  used: string[];
  expected: string[];
  missing: string[];
  /** Null when the question expected no glossary terms — not the same as 0. */
  coverage: number | null;
}

export interface Axis {
  label: string;
  score: number | null;
  answers_scored: number;
}

export interface AnswerReport {
  answer_id: number;
  sequence: number;
  status: string;
  question: string;
  competency: string | null;
  transcript: string | null;
  transcript_was_corrected: boolean;
  duration_seconds: number | null;
  scores: {
    knowledge: number | null;
    structure: number | null;
    communication: number | null;
    fluency: number | null;
    confidence: number | null;
  } | null;
  /** Why the interview asked this question, in the officer's own report. */
  asked_because?: string | null;
  /** Written by the model mid-session rather than drawn from the vetted bank. */
  is_generated?: boolean;
  /** Present only in the officer's own copy — the API strips it for others. */
  attention?: AttentionReport | null;
  covered_points: string[];
  missed_points: string[];
  /** Statements that contradict an approved expected point. The quote is the
   *  officer's own sentence and the correction is the approved fact. */
  mistakes?: Mistake[];
  technical_terms?: TechnicalTerms;
  rationale: Record<string, unknown> | null;
  timeline: {
    duration: number;
    fillers: { word: string; t: number }[];
    pauses: { start: number; end: number }[];
    latency_to_first_word: number | null;
  };
  metrics: {
    words: number;
    wpm: number | null;
    filler_count: number;
    filler_rate: number | null;
    long_pause_count: number;
    hedge_count: number;
  } | null;
}

const AXIS_ORDER = [
  "knowledge", "structure", "communication", "fluency", "confidence",
] as const;

const AXIS_LABEL: Record<(typeof AXIS_ORDER)[number], string> = {
  knowledge: "Knowledge",
  structure: "Structure",
  communication: "Communication",
  fluency: "Delivery",
  confidence: "Confidence",
};

// Only Knowledge is written through to the Skill Twin — see
// `services/competency.record_interview_evidence`, which accepts a knowledge
// level and nothing else. This map used to claim Structure was recorded too,
// which told officers their answers were being filed under something they were
// not.
const AXIS_MEANING: Record<string, string> = {
  knowledge: "The only axis recorded as competency evidence",
  structure: "Coaching feedback only — never competency evidence",
  communication: "Coaching feedback only — judged from your words, not your voice",
  fluency: "Coaching feedback only — measured against your own baseline",
  confidence: "Coaching feedback only — never competency evidence",
};

/**
 * A score on the 1-5 axis, said in words as well as a number.
 *
 * Bands, not grades. Each axis is rated separately and there is no overall
 * figure; this only makes a single axis readable at a glance.
 */
export function ratingBand(score: number): { label: string; tone: string } {
  if (score < 1.75) return { label: "Needs work", tone: "text-critical" };
  if (score < 2.5) return { label: "Developing", tone: "text-warn" };
  if (score < 3.25) return { label: "Competent", tone: "text-ink" };
  if (score < 4.25) return { label: "Strong", tone: "text-good" };
  return { label: "Excellent", tone: "text-good" };
}

/** Five dots, filled to the score. Rounded to the nearest half. */
export function RatingDots({ score, label }: { score: number; label: string }) {
  const halves = Math.round(score * 2) / 2;
  return (
    <span
      className="inline-flex items-center gap-1"
      role="img"
      aria-label={`${label}: ${score.toFixed(1)} out of 5`}
    >
      {[1, 2, 3, 4, 5].map((n) => {
        const fill = halves >= n ? "full" : halves >= n - 0.5 ? "half" : "empty";
        return (
          <span
            key={n}
            aria-hidden="true"
            className="relative inline-block h-2.5 w-2.5 overflow-hidden rounded-full border border-accent"
          >
            {fill !== "empty" && (
              <span
                className="absolute inset-y-0 left-0 bg-accent"
                style={{ width: fill === "full" ? "100%" : "50%" }}
              />
            )}
          </span>
        );
      })}
    </span>
  );
}

export function AxisScores({
  axes,
  fluencyEnabled,
}: {
  axes: Record<string, Axis>;
  fluencyEnabled: boolean;
}) {
  return (
    <div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {AXIS_ORDER.map((key) => {
          const axis = axes[key];
          if (!axis) return null;
          // Knowledge only. Colouring Structure the same way implied it was
          // recorded against the officer's competency profile, and it is not.
          const assessed = key === "knowledge";
          const band = axis.score !== null ? ratingBand(axis.score) : null;
          return (
            <div key={key} className="border border-rule bg-surface px-4 py-3.5">
              <div className="text-[11px] font-semibold uppercase tracking-[0.07em] text-ink-3">
                {axis.label}
              </div>
              <div className="mt-2 flex items-baseline gap-1.5">
                <span className="tabular font-mono text-[26px] font-medium leading-none">
                  {axis.score !== null ? axis.score.toFixed(1) : "—"}
                </span>
                {axis.score !== null && <span className="text-xs text-ink-3">/ 5</span>}
              </div>
              {axis.score !== null && band && (
                <div className="mt-1.5 flex items-center gap-2">
                  <RatingDots score={axis.score} label={axis.label} />
                  <span className={`text-[12px] font-semibold ${band.tone}`}>{band.label}</span>
                </div>
              )}
              <div className="mt-2.5 h-1.5 w-full bg-surface-2">
                {axis.score !== null && (
                  <div
                    className={`h-1.5 ${assessed ? "bg-accent" : "bg-rule-strong"}`}
                    style={{ width: `${(axis.score / 5) * 100}%` }}
                  />
                )}
              </div>
              <div className="mt-2 text-[11px] leading-snug text-ink-3">
                {axis.score === null && key === "fluency" && !fluencyEnabled
                  ? "Switched off for this officer"
                  : axis.score === null
                    ? "Not scored"
                    : AXIS_MEANING[key]}
              </div>
            </div>
          );
        })}
      </div>

      <div className="mt-3">
        <Note>
          <strong className="font-semibold text-ink">Five axes, reported separately.</strong>{" "}
          No overall score is produced. Only Knowledge becomes competency evidence.
          Communication is judged from the transcript — whether ideas were ordered and
          terms defined — never from how the answer sounded. Delivery is measured against
          this officer&rsquo;s own calibration baseline, never a population average, so
          accent and regional speech patterns are not penalised.
        </Note>
      </div>
    </div>
  );
}

/**
 * Where the hesitation happened, not just how much of it there was.
 *
 * Fillers are dots on the track, long pauses are bands, and the delay before
 * the first word is marked at the start.
 */
export function FumbleTimeline({ answer }: { answer: AnswerReport }) {
  const { timeline, metrics } = answer;
  const duration = Math.max(timeline.duration || answer.duration_seconds || 0, 1);
  const pct = (t: number) => `${Math.max(0, Math.min(100, (t / duration) * 100))}%`;

  return (
    <div>
      <div className="relative h-11 w-full border border-rule bg-surface-2">
        {timeline.pauses.map((pause, i) => (
          <div
            key={i}
            title={`Pause ${(pause.end - pause.start).toFixed(1)}s`}
            className={`absolute top-0 h-full ${
              pause.end - pause.start >= 2 ? "bg-warn/35" : "bg-rule-strong/40"
            }`}
            style={{ left: pct(pause.start), width: pct(pause.end - pause.start) }}
          />
        ))}

        {timeline.latency_to_first_word ? (
          <div
            title={`${timeline.latency_to_first_word.toFixed(1)}s before speaking`}
            className="absolute top-0 h-full border-r border-dashed border-ink-3 bg-surface-2"
            style={{ width: pct(timeline.latency_to_first_word) }}
          />
        ) : null}

        {timeline.fillers.map((filler, i) => (
          <div
            key={i}
            title={`"${filler.word}" at ${filler.t.toFixed(1)}s`}
            className="absolute top-1/2 h-2 w-2 -translate-x-1/2 -translate-y-1/2 rounded-full bg-critical"
            style={{ left: pct(filler.t) }}
          />
        ))}

        <div className="absolute inset-x-0 bottom-0 flex justify-between px-1 text-[9.5px] text-ink-3">
          <span>0s</span>
          <span>{duration.toFixed(0)}s</span>
        </div>
      </div>

      <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-ink-2">
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-2 w-2 rounded-full bg-critical" />
          Filler word
        </span>
        <span className="flex items-center gap-1.5">
          <span className="bg-warn/35 inline-block h-2.5 w-4" />
          Pause over 2s
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-2.5 w-0 border-r border-dashed border-ink-3" />
          Delay before first word
        </span>
      </div>

      {metrics && (
        <dl className="tabular mt-3 grid grid-cols-2 gap-x-6 gap-y-1 border-t border-rule pt-3 font-mono text-[11.5px] sm:grid-cols-4">
          <div className="flex justify-between gap-2">
            <dt className="text-ink-3">words</dt>
            <dd>{metrics.words}</dd>
          </div>
          <div className="flex justify-between gap-2">
            <dt className="text-ink-3">wpm</dt>
            <dd>{metrics.wpm?.toFixed(0) ?? "—"}</dd>
          </div>
          <div className="flex justify-between gap-2">
            <dt className="text-ink-3">fillers/100w</dt>
            <dd>{metrics.filler_rate?.toFixed(1) ?? "—"}</dd>
          </div>
          <div className="flex justify-between gap-2">
            <dt className="text-ink-3">long pauses</dt>
            <dd>{metrics.long_pause_count}</dd>
          </div>
        </dl>
      )}
    </div>
  );
}

export function AnswerBreakdown({ answers }: { answers: AnswerReport[] }) {
  const scored = answers.filter((a) => a.scores);
  if (scored.length === 0)
    return <Empty>No answers have been scored yet.</Empty>;

  return (
    <div className="grid gap-3.5">
      {scored.map((answer) => (
        <Card
          key={answer.answer_id}
          title={answer.competency ?? "Answer"}
          hint={`Question ${answer.sequence} · ${answer.duration_seconds?.toFixed(0) ?? "—"}s`}
        >
          <p className="text-[13.5px] leading-relaxed text-ink-2">{answer.question}</p>

          <div className="mt-3 grid gap-x-6 gap-y-1.5 sm:grid-cols-2">
            {AXIS_ORDER.map((key) => {
              const value = answer.scores?.[key];
              if (value === null || value === undefined) return null;
              const band = ratingBand(value);
              return (
                <div key={key} className="flex items-center justify-between gap-3 text-[12.5px]">
                  <span className="text-ink-2">{AXIS_LABEL[key]}</span>
                  <span className="flex items-center gap-2">
                    <RatingDots score={value} label={AXIS_LABEL[key]} />
                    <span className="tabular w-8 text-right font-mono text-[12px]">
                      {value.toFixed(1)}
                    </span>
                    <span className={`w-[76px] text-[11.5px] font-semibold ${band.tone}`}>
                      {band.label}
                    </span>
                  </span>
                </div>
              );
            })}
          </div>

          {answer.metrics && (
            <div className="tabular mt-3 flex flex-wrap gap-x-5 gap-y-1 border-t border-rule pt-3 font-mono text-[12px] text-ink-2">
              <span>
                <span className="text-ink-3">fillers </span>
                <span className="font-semibold text-ink">{answer.metrics.filler_count}</span>
                {answer.metrics.filler_rate !== null && (
                  <span className="text-ink-3"> ({answer.metrics.filler_rate}/100 words)</span>
                )}
              </span>
              <span>
                <span className="text-ink-3">pace </span>
                <span className="font-semibold text-ink">{answer.metrics.wpm ?? "—"}</span>
                <span className="text-ink-3"> wpm</span>
              </span>
              <span>
                <span className="text-ink-3">long pauses </span>
                <span className="font-semibold text-ink">{answer.metrics.long_pause_count}</span>
              </span>
            </div>
          )}

          {answer.mistakes && answer.mistakes.length > 0 && (
            <div className="mt-4">
              <div className="mb-1.5 text-[11px] font-semibold uppercase tracking-[0.07em] text-critical">
                Mistakes in this answer
              </div>
              <MistakeList mistakes={answer.mistakes} />
            </div>
          )}

          {answer.technical_terms && answer.technical_terms.expected.length + answer.technical_terms.used.length > 0 && (
            <div className="mt-4">
              <div className="mb-1.5 flex items-baseline justify-between gap-3">
                <span className="text-[11px] font-semibold uppercase tracking-[0.07em] text-ink-3">
                  Technical terms
                </span>
                {answer.technical_terms.coverage !== null && (
                  <span className="tabular font-mono text-[11.5px] text-ink-3">
                    {answer.technical_terms.expected.length - answer.technical_terms.missing.length}
                    {" of "}
                    {answer.technical_terms.expected.length} expected
                  </span>
                )}
              </div>
              <TermChips terms={answer.technical_terms} />
            </div>
          )}

          <div className="mt-4">
            <div className="mb-1.5 text-[11px] font-semibold uppercase tracking-[0.07em] text-ink-3">
              Where the hesitation was
            </div>
            <FumbleTimeline answer={answer} />
          </div>

          {(answer.covered_points.length > 0 || answer.missed_points.length > 0) && (
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              {answer.covered_points.length > 0 && (
                <div>
                  <div className="mb-1 text-[11px] font-semibold uppercase tracking-[0.07em] text-good">
                    Covered
                  </div>
                  <ul className="list-disc space-y-0.5 pl-4 text-[12.5px] text-ink-2">
                    {answer.covered_points.map((p) => (
                      <li key={p}>{p}</li>
                    ))}
                  </ul>
                </div>
              )}
              {answer.missed_points.length > 0 && (
                <div>
                  <div className="mb-1 text-[11px] font-semibold uppercase tracking-[0.07em] text-warn">
                    Not addressed
                  </div>
                  <ul className="list-disc space-y-0.5 pl-4 text-[12.5px] text-ink-2">
                    {answer.missed_points.map((p) => (
                      <li key={p}>{p}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}

          {Array.isArray(answer.rationale?.delivery_notes) &&
            (answer.rationale.delivery_notes as string[]).length > 0 && (
              <div className="mt-4 border-t border-rule pt-3">
                <div className="mb-1 text-[11px] font-semibold uppercase tracking-[0.07em] text-ink-3">
                  Delivery feedback
                </div>
                <ul className="space-y-1 text-[12.5px] text-ink-2">
                  {(answer.rationale.delivery_notes as string[]).map((note, i) => (
                    <li key={i}>{note}</li>
                  ))}
                </ul>
              </div>
            )}

          {answer.transcript && (
            <details className="mt-3">
              <summary className="cursor-pointer text-[12.5px] text-accent">
                {answer.transcript_was_corrected
                  ? "Show transcript (corrected by you)"
                  : "Show transcript"}
              </summary>
              <p className="mt-2 whitespace-pre-wrap border border-rule bg-surface-2 p-3 text-[12.5px] leading-relaxed text-ink-2">
                {answer.transcript}
              </p>
            </details>
          )}
        </Card>
      ))}
    </div>
  );
}


/**
 * Strengths, weaknesses and what to do next.
 *
 * Every line is computed from the numbers above it — see
 * `services/coaching.py`. Nothing here is written by a model, because a model
 * asked for "strengths and weaknesses" writes fluent encouragement whether the
 * evidence supports it or not, and one invented strength costs the officer's
 * trust in the whole report.
 */
export function CoachingPanel({ coaching }: { coaching: Coaching | null }) {
  if (!coaching) return null;

  const sections: { title: string; items: string[]; tone: string }[] = [
    { title: "What went well", items: coaching.strengths, tone: "text-good" },
    { title: "Where it fell short", items: coaching.weaknesses, tone: "text-warn" },
    { title: "What to try next time", items: coaching.suggestions, tone: "text-ink-2" },
    { title: "Worth practising", items: coaching.practice, tone: "text-ink-2" },
  ].filter((section) => section.items.length > 0);

  if (sections.length === 0) return null;

  return (
    <Card title="Your feedback" hint={coaching.note}>
      <div className="grid gap-5 sm:grid-cols-2">
        {sections.map((section) => (
          <div key={section.title}>
            <h3 className="text-[11px] font-semibold uppercase tracking-[0.07em] text-ink-3">
              {section.title}
            </h3>
            <ul className="mt-2 space-y-2">
              {section.items.map((item, index) => (
                <li
                  key={index}
                  className={`text-[12.5px] leading-relaxed ${section.tone}`}
                >
                  {item}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </Card>
  );
}

const QUALITY_NOTE: Record<string, string> = {
  good: "The camera tracked you for most of the answer.",
  partial:
    "The camera lost you for a good part of this answer, so read these loosely.",
  unusable:
    "Too little was tracked to say anything useful — lighting, framing or the camera itself.",
};

/**
 * Camera engagement, for the officer and nobody else.
 *
 * Presented as observations rather than scores, and with the reason it is not a
 * score stated on the panel rather than buried in a policy document. Anyone
 * reading this report who is not the officer never receives the data at all —
 * `apply_officer_only_redaction` removes it server-side.
 */
export function AttentionPanel({ attention }: { attention: AttentionReport | null }) {
  if (!attention) return null;

  const unusable = attention.quality === "unusable";
  const pct = (value: number | null) =>
    value === null ? "—" : `${Math.round(value * 100)}%`;

  return (
    <Card
      title="Camera notes (only you can see these)"
      hint={QUALITY_NOTE[attention.quality] ?? ""}
    >
      {unusable ? (
        <Empty>
          Not enough was tracked to report anything. This has no effect on any of
          your scores.
        </Empty>
      ) : (
        <>
          <dl className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <div>
              <dt className="text-[11px] uppercase tracking-[0.06em] text-ink-3">
                Looking at screen
              </dt>
              <dd className="tabular mt-1 font-mono text-[19px]">
                {pct(attention.screen_gaze_ratio)}
              </dd>
            </div>
            <div>
              <dt className="text-[11px] uppercase tracking-[0.06em] text-ink-3">
                Longest look away
              </dt>
              <dd className="tabular mt-1 font-mono text-[19px]">
                {attention.longest_look_away_seconds === null
                  ? "—"
                  : `${attention.longest_look_away_seconds}s`}
              </dd>
            </div>
            <div>
              <dt className="text-[11px] uppercase tracking-[0.06em] text-ink-3">
                Head steadiness
              </dt>
              <dd className="tabular mt-1 font-mono text-[19px]">
                {pct(attention.head_stability)}
              </dd>
            </div>
            <div>
              <dt className="text-[11px] uppercase tracking-[0.06em] text-ink-3">
                Frames tracked
              </dt>
              <dd className="tabular mt-1 font-mono text-[19px]">
                {pct(attention.face_present_ratio)}
              </dd>
            </div>
          </dl>

          {attention.hands_visible_ratio !== null && (
            <div className="mt-4 border-t border-rule pt-4">
              <h3 className="text-[11px] font-semibold uppercase tracking-[0.07em] text-ink-3">
                Gestures
              </h3>
              <dl className="mt-2 grid grid-cols-3 gap-4">
                <div>
                  <dt className="text-[11px] uppercase tracking-[0.06em] text-ink-3">
                    Hands in view
                  </dt>
                  <dd className="tabular mt-1 font-mono text-[19px]">
                    {pct(attention.hands_visible_ratio)}
                  </dd>
                </div>
                <div>
                  <dt className="text-[11px] uppercase tracking-[0.06em] text-ink-3">
                    Hand movement
                  </dt>
                  <dd className="mt-1 text-[15px] font-medium">
                    {gestureBand(attention.hand_movement)}
                  </dd>
                </div>
                <div>
                  <dt className="text-[11px] uppercase tracking-[0.06em] text-ink-3">
                    Touched face
                  </dt>
                  <dd className="tabular mt-1 font-mono text-[19px]">
                    {attention.face_touch_count ?? "—"}
                    {attention.face_touch_count !== null && (
                      <span className="ml-1 text-[11px] text-ink-3">times</span>
                    )}
                  </dd>
                </div>
              </dl>
              <p className="mt-2 text-[11.5px] leading-relaxed text-ink-2">
                {gestureNote(attention)}
              </p>
            </div>
          )}

          <div className="mt-4">
            <Note tone="brass">
              <strong className="font-semibold text-ink">
                These are notes, not scores.
              </strong>{" "}
              Where you look is not evidence of what you know. Eye-contact habits differ
              by culture and by person — in many settings looking away from a senior is
              courtesy, not disengagement — and they differ again for autistic officers
              and for anyone with a visual impairment. So nothing here touches a
              competency level, your promotion readiness, or anything your supervisor
              sees. It is here so you can watch your own recording and see what a
              listener would see.
            </Note>
          </div>
        </>
      )}
    </Card>
  );
}

const PRACTICE_LABEL: Record<string, string> = {
  recall: "Recall",
  explain: "Explain",
  drill: "Drill",
  mock: "Mock interview",
};

/**
 * What to do after the interview.
 *
 * Courses come from the same recommender the development plan uses — one
 * ranking, whose input the interview changed. Two rankings would leave an
 * officer with no way to know which to believe.
 *
 * The practice list is the part no course covers. Most of what an interview
 * exposes is not a knowledge gap: it is that the officer knows the material and
 * cannot yet explain it under time pressure, and booking three days of training
 * for that wastes three days.
 */
export function FollowThroughPanel({ data }: { data: FollowThrough | null }) {
  if (!data) return null;

  return (
    <Card title="What to do next" hint="Drawn from what this interview found">
      {data.competencies.length > 0 && (
        <div className="space-y-5">
          {data.competencies.map((block) => (
            <div key={block.competency_id}>
              <h3 className="text-[13px] font-semibold">
                {block.competency_name}
                {block.current_level !== null && block.required_level !== null && (
                  <span className="ml-2 font-normal text-[11.5px] text-ink-3">
                    L{block.current_level.toFixed(1)} against L
                    {block.required_level.toFixed(1)}
                  </span>
                )}
              </h3>

              {block.courses.length > 0 ? (
                <ul className="mt-2 space-y-2">
                  {block.courses.map((course) => (
                    <li key={course.course_id} className="border-l-2 border-rule pl-3">
                      <div className="flex items-baseline justify-between gap-3">
                        <span className="text-[12.5px] font-medium">{course.title}</span>
                        <span className="tabular shrink-0 font-mono text-[11px] text-ink-3">
                          {course.duration_hours}h
                        </span>
                      </div>
                      <p className="mt-0.5 text-[11.5px] leading-relaxed text-ink-2">
                        {course.reason}
                      </p>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="mt-1.5 text-[11.5px] leading-relaxed text-warn">
                  {block.note}
                </p>
              )}
            </div>
          ))}
        </div>
      )}

      {data.practice.length > 0 && (
        <div className="mt-6 border-t border-rule pt-5">
          <h3 className="text-[11px] font-semibold uppercase tracking-[0.07em] text-ink-3">
            Practice — no booking needed
          </h3>
          <ul className="mt-2.5 space-y-3">
            {data.practice.map((item, index) => (
              <li key={index}>
                <div className="flex items-baseline gap-2">
                  <span className="shrink-0 border border-rule px-1.5 py-0.5 text-[10px] uppercase tracking-[0.05em] text-ink-3">
                    {PRACTICE_LABEL[item.kind] ?? item.kind}
                  </span>
                  <span className="text-[12.5px] font-medium">{item.title}</span>
                </div>
                <p className="mt-1 text-[11.5px] leading-relaxed text-ink-2">
                  {item.detail}
                </p>
              </li>
            ))}
          </ul>
        </div>
      )}

      <Note tone="brass">{data.caveat}</Note>
    </Card>
  );
}


/**
 * Statements that were wrong, each with the approved fact that shows it.
 *
 * The quote is the officer's own sentence, split out before any model saw it,
 * so it cannot be misquoted. The correction is the expert-approved expected
 * point the statement contradicted — not an explanation a model wrote.
 */
export function MistakeList({ mistakes }: { mistakes: Mistake[] }) {
  return (
    <ul className="space-y-2.5">
      {mistakes.map((mistake, index) => (
        <li key={index} className="border-l-2 border-critical bg-surface-2 px-3 py-2.5">
          <p className="text-[12.5px] leading-relaxed text-ink">
            <span className="font-semibold">You said: </span>
            <span className="italic">&ldquo;{mistake.quote}&rdquo;</span>
          </p>
          <p className="mt-1 text-[12px] leading-relaxed text-ink-2">{mistake.problem}</p>
          <p className="mt-1.5 text-[12.5px] leading-relaxed text-ink">
            <span className="font-semibold text-good">Correct: </span>
            {mistake.correction}
          </p>
        </li>
      ))}
    </ul>
  );
}

/** Used terms, and the ones this question expected that the answer did not use. */
export function TermChips({ terms }: { terms: TechnicalTerms }) {
  const missing = new Set(terms.missing);
  const expectedUsed = terms.expected.filter((t) => !missing.has(t));
  const extra = terms.used.filter((t) => !terms.expected.includes(t));

  return (
    <div className="flex flex-wrap gap-1.5">
      {expectedUsed.map((term) => (
        <span
          key={`u-${term}`}
          className="border border-good px-2 py-0.5 text-[11.5px] text-good"
          title="Expected, and you used it"
        >
          ✓ {term}
        </span>
      ))}
      {terms.missing.map((term) => (
        <span
          key={`m-${term}`}
          className="border border-dashed border-warn px-2 py-0.5 text-[11.5px] text-warn"
          title="A complete answer would have used this"
        >
          missing: {term}
        </span>
      ))}
      {extra.map((term) => (
        <span
          key={`e-${term}`}
          className="border border-rule px-2 py-0.5 text-[11.5px] text-ink-2"
          title="Relevant term you used that this question did not require"
        >
          {term}
        </span>
      ))}
    </div>
  );
}

/**
 * Every mistake across the interview, collected at the top of the report.
 *
 * Shown before the per-answer detail because a wrong statement is the thing
 * most worth fixing first: an omission loses marks, a confident error is what a
 * colleague remembers.
 */
export function MistakesPanel({ answers }: { answers: AnswerReport[] }) {
  const all = answers.flatMap((answer) =>
    (answer.mistakes ?? []).map((mistake) => ({ ...mistake, competency: answer.competency })),
  );

  return (
    <Card
      title={all.length ? `Your mistakes (${all.length})` : "Your mistakes"}
      hint="Statements checked against the approved answer for each question"
    >
      {all.length === 0 ? (
        <Empty>
          Nothing you said contradicted the approved answers. That checks for wrong
          statements, not for completeness — see what each answer did not address below.
        </Empty>
      ) : (
        <>
          <MistakeList mistakes={all} />
          <p className="mt-3 text-[11.5px] leading-relaxed text-ink-3">
            Each quote is your own sentence and each correction is the approved
            answer it contradicts. The check is made by an AI reviewer, so if you
            are sure a flagged statement was right, raise it — it is worth an expert
            second look.
          </p>
        </>
      )}
    </Card>
  );
}

/** Hand movement in words. Null means hands were never tracked, not "still". */
function gestureBand(movement: number | null): string {
  if (movement === null) return "—";
  if (movement < 0.15) return "Very still";
  if (movement < 0.45) return "Moderate";
  if (movement < 0.8) return "Animated";
  return "Very animated";
}

/**
 * One observation about gestures, said as what a camera saw.
 *
 * Plenty of good explainers talk with their hands and plenty keep them still,
 * and both are fine. The one pattern worth raising on its own is touching the
 * face, because speakers rarely notice they do it.
 */
function gestureNote(attention: AttentionReport): string {
  const touches = attention.face_touch_count ?? 0;
  if (touches >= 4) {
    return `Your hand came up to your face ${touches} times. Most people do not notice this while speaking; watch your recording to see whether it clusters around the harder parts of the question.`;
  }
  if (attention.hands_visible_ratio !== null && attention.hands_visible_ratio < 0.1) {
    return "Your hands were mostly out of frame, so there is little to say about gestures. That is not a problem — it only means this camera angle does not show them.";
  }
  if (attention.hand_movement !== null && attention.hand_movement >= 0.8) {
    return "You gestured a lot. That often helps an explanation land; it is only worth a look if it pulled attention away from what you were saying.";
  }
  return "Nothing about your gestures stood out. These are observations, not a score.";
}
