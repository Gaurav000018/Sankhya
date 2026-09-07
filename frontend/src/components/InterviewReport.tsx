import { Card, Empty, Note } from "./ui";
import type { AttentionReport, Coaching } from "../types";

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
          const assessed = key === "knowledge" || key === "structure";
          return (
            <div key={key} className="border border-rule bg-surface px-4 py-3.5">
              <div className="text-[11px] font-semibold uppercase tracking-[0.07em] text-ink-3">
                {axis.label}
              </div>
              <div className="mt-2 flex items-baseline gap-1.5">
                <span className="tabular font-mono text-[26px] font-medium leading-none">
                  {axis.score ?? "—"}
                </span>
                {axis.score !== null && <span className="text-xs text-ink-3">/ 5</span>}
              </div>
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

          <div className="tabular mt-3 flex flex-wrap gap-x-6 gap-y-1 font-mono text-[12px]">
            {AXIS_ORDER.map((key) => (
              <span key={key} className="flex gap-2">
                <span className="text-ink-3">{key}</span>
                <span className="font-semibold">{answer.scores?.[key] ?? "—"}</span>
              </span>
            ))}
          </div>

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
