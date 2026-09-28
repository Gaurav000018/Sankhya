import { useCallback, useEffect, useMemo, useState } from "react";

import { ApiError, api } from "../api";
import { PageHeader } from "../components/Layout";
import { btnPrimary, btnSecondary, Card, Empty, ErrorNote, Note, Spinner } from "../components/ui";
import { usePageTitle } from "../hooks/usePageTitle";

/**
 * The role simulation.
 *
 * Every other assessment on this platform asks what an officer knows. This one
 * asks what they would do: a situation from their own work, a constraint that
 * removes the comfortable option, and no single right answer.
 *
 * Three rules this screen keeps.
 *
 * **The rubric is never on screen while the clock is running.** The server does
 * not send `expected_points` for an open attempt, so there is nothing here to
 * hide with CSS — the same rule the assessment keeps about its answer key. It
 * arrives with the result, which is when it becomes useful.
 *
 * **The draft survives a reload.** Fifteen minutes of typing lost to a stray
 * refresh is the kind of thing that stops someone using a tool once. The draft
 * is kept in `localStorage` against the attempt id and cleared on submit.
 *
 * **It shows which axes counted.** Two of the five became evidence; three are
 * feedback and stop there. An officer reading a score they disagree with is
 * entitled to know which numbers moved their record and which did not.
 */

interface Attempt {
  attempt_id: number;
  status: string;
  scenario_code: string;
  title: string;
  competency_name: string | null;
  situation: string;
  task: string;
  constraint: string | null;
  minutes: number;
  target_level: number;
  response: string | null;
}

interface Result {
  attempt_id: number;
  status: string;
  scenario_code: string;
  title: string;
  competency_name: string | null;
  situation: string;
  task: string;
  constraint: string | null;
  response: string | null;
  knowledge: number | null;
  reasoning: number | null;
  prioritisation: number | null;
  communication: number | null;
  decision_making: number | null;
  derived_level: number | null;
  confidence: number | null;
  covered_points: string[];
  missed_points: string[];
  traps_hit: string[];
  expected_points: string[];
  feedback: string | null;
  model_name: string | null;
  degraded: boolean;
  submitted_at: string | null;
}

/** The two axes that become competency evidence, and the three that do not. */
const EVIDENCE_AXES: { key: keyof Result; label: string; why: string }[] = [
  { key: "knowledge", label: "Knowledge", why: "Were the methods and obligations you invoked correct?" },
  { key: "reasoning", label: "Reasoning", why: "Does your justification actually support the decision?" },
];

const FEEDBACK_AXES: { key: keyof Result; label: string; why: string }[] = [
  { key: "prioritisation", label: "Prioritisation", why: "Did the scarce resource go to what mattered most?" },
  { key: "communication", label: "Communication", why: "Would the people who must act on this know what to do?" },
  { key: "decision_making", label: "Decision-making", why: "Did you decide and own the trade-off, or list options?" },
];

const MIN_WORDS = 40;

function draftKey(attemptId: number) {
  return `sankhya.simulation.draft.${attemptId}`;
}

function AxisRow({ label, why, score }: { label: string; why: string; score: number | null }) {
  const pct = score == null ? 0 : ((score - 1) / 4) * 100;
  return (
    <div className="py-2">
      <div className="flex items-baseline justify-between gap-3">
        <span className="text-[13.5px] font-semibold text-ink">{label}</span>
        <span className="tabular-nums text-[13.5px] font-semibold text-ink">
          {score == null ? "—" : score.toFixed(1)}
          <span className="font-normal text-ink-3"> / 5</span>
        </span>
      </div>
      <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-surface-2">
        <div
          className="h-full rounded-full bg-accent transition-[width] duration-700"
          style={{ width: `${pct}%` }}
        />
      </div>
      <p className="mt-1 text-[12px] leading-snug text-ink-3">{why}</p>
    </div>
  );
}

export function Simulation() {
  usePageTitle("title.simulation");

  const [attempt, setAttempt] = useState<Attempt | null>(null);
  const [result, setResult] = useState<Result | null>(null);
  const [history, setHistory] = useState<Result[]>([]);
  const [response, setResponse] = useState("");

  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [exhausted, setExhausted] = useState(false);

  const load = useCallback(async () => {
    setHistory(await api.get<Result[]>("/simulations/me"));
  }, []);

  useEffect(() => {
    load()
      .catch((e) => setError(e instanceof Error ? e.message : "Could not load your simulations."))
      .finally(() => setLoading(false));
  }, [load]);

  // Keep the draft against the attempt, not the page: an officer who reloads
  // mid-answer gets their work back rather than starting again.
  useEffect(() => {
    if (!attempt) return;
    try {
      window.localStorage.setItem(draftKey(attempt.attempt_id), response);
    } catch {
      // A browser with storage blocked still gets a working exercise; it just
      // does not get the safety net. Not worth an error message.
    }
  }, [attempt, response]);

  const words = useMemo(() => response.trim().split(/\s+/).filter(Boolean).length, [response]);
  const enough = words >= MIN_WORDS;

  async function start() {
    setBusy(true);
    setError(null);
    setResult(null);
    setExhausted(false);
    try {
      const created = await api.post<Attempt>("/simulations", {});
      setAttempt(created);
      let draft = created.response ?? "";
      try {
        draft = window.localStorage.getItem(draftKey(created.attempt_id)) ?? draft;
      } catch {
        /* storage blocked — fall back to whatever the server has */
      }
      setResponse(draft);
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) setExhausted(true);
      else setError(e instanceof ApiError ? e.message : "Could not start a simulation.");
    } finally {
      setBusy(false);
    }
  }

  async function submit() {
    if (!attempt || !enough) return;
    setBusy(true);
    setError(null);
    try {
      const scored = await api.post<Result>(`/simulations/${attempt.attempt_id}/submit`, {
        response,
      });
      try {
        window.localStorage.removeItem(draftKey(attempt.attempt_id));
      } catch {
        /* nothing to clean up if storage was never available */
      }
      setResult(scored);
      setAttempt(null);
      setResponse("");
      void load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not submit that response.");
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <Spinner label="Loading simulations" />;

  return (
    <>
      <PageHeader
        title="Role simulation"
        subtitle="A situation from the job, and the decision you would take"
      />

      {error && <ErrorNote message={error} />}

      {/* ----------------------------------------------------------------- */}
      {/* The result of the attempt just submitted                          */}
      {/* ----------------------------------------------------------------- */}
      {result && (
        <Card title={`Assessed — ${result.title}`}>
          {result.degraded ? (
            <Note tone="brass">
              Your response was saved, but it could not be scored: {result.feedback}. Nothing
              has been added to your competency record for it.
            </Note>
          ) : (
            <>
              <div className="mb-4 flex flex-wrap items-baseline gap-x-6 gap-y-1">
                <div>
                  <div className="text-[11px] uppercase tracking-[0.06em] text-ink-3">
                    Level this is evidence for
                  </div>
                  <div className="text-[28px] font-semibold tabular-nums text-ink">
                    {result.derived_level?.toFixed(2) ?? "—"}
                  </div>
                </div>
                <div>
                  <div className="text-[11px] uppercase tracking-[0.06em] text-ink-3">
                    Competency
                  </div>
                  <div className="text-[15px] font-semibold text-ink">
                    {result.competency_name ?? "—"}
                  </div>
                </div>
              </div>

              {result.feedback && (
                <p className="mb-4 text-[14px] leading-relaxed text-ink-2">{result.feedback}</p>
              )}

              <div className="grid gap-6 md:grid-cols-2">
                <div>
                  <h3 className="mb-1 text-[13px] font-semibold text-ink">
                    Counted towards your level
                  </h3>
                  <p className="mb-2 text-[12px] leading-snug text-ink-3">
                    Averaged and written to your evidence record at the simulation weight.
                  </p>
                  {EVIDENCE_AXES.map((a) => (
                    <AxisRow
                      key={a.key}
                      label={a.label}
                      why={a.why}
                      score={result[a.key] as number | null}
                    />
                  ))}
                </div>
                <div>
                  <h3 className="mb-1 text-[13px] font-semibold text-ink">
                    Feedback only
                  </h3>
                  <p className="mb-2 text-[12px] leading-snug text-ink-3">
                    Shown to you and nobody else. These describe how you worked, not what you
                    can do, so they never move your competency level.
                  </p>
                  {FEEDBACK_AXES.map((a) => (
                    <AxisRow
                      key={a.key}
                      label={a.label}
                      why={a.why}
                      score={result[a.key] as number | null}
                    />
                  ))}
                </div>
              </div>

              {result.covered_points.length > 0 && (
                <div className="mt-5">
                  <h3 className="mb-2 text-[13px] font-semibold text-ink">You covered</h3>
                  <ul className="space-y-1.5">
                    {result.covered_points.map((p) => (
                      <li key={p} className="flex gap-2 text-[13.5px] leading-snug text-ink-2">
                        <span aria-hidden="true" className="text-accent">✓</span>
                        <span>{p}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {result.missed_points.length > 0 && (
                <div className="mt-5">
                  <h3 className="mb-2 text-[13px] font-semibold text-ink">
                    A strong answer would also have covered
                  </h3>
                  <ul className="space-y-1.5">
                    {result.missed_points.map((p) => (
                      <li key={p} className="flex gap-2 text-[13.5px] leading-snug text-ink-2">
                        <span aria-hidden="true" className="text-ink-3">○</span>
                        <span>{p}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {result.traps_hit.length > 0 && (
                <div className="mt-5">
                  <h3 className="mb-2 text-[13px] font-semibold text-ink">
                    Where the answer went wrong
                  </h3>
                  <ul className="space-y-1.5">
                    {result.traps_hit.map((p) => (
                      <li key={p} className="flex gap-2 text-[13.5px] leading-snug text-ink-2">
                        <span aria-hidden="true" className="text-brass">!</span>
                        <span>{p}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Named on purpose. A keyword-scored attempt must never be read
                  as a judged one, and the officer is the person with the most
                  right to know which they got. */}
              <p className="mt-5 text-[12px] text-ink-3">
                Scored by {result.model_name ?? "unknown"}.
              </p>
            </>
          )}
          <div className="mt-5 flex gap-3">
            <button className={btnPrimary} onClick={() => setResult(null)}>
              Done
            </button>
            <button className={btnSecondary} disabled={busy} onClick={() => void start()}>
              Try another situation
            </button>
          </div>
        </Card>
      )}

      {/* ----------------------------------------------------------------- */}
      {/* The attempt in progress                                           */}
      {/* ----------------------------------------------------------------- */}
      {!result && attempt && (
        <Card title={attempt.title}>
          <div className="mb-3 flex flex-wrap gap-x-5 gap-y-1 text-[12px] text-ink-3">
            <span>{attempt.competency_name}</span>
            <span>About {attempt.minutes} minutes</span>
            <span>Written for level {attempt.target_level.toFixed(1)}</span>
          </div>

          <p className="text-[14.5px] leading-relaxed text-ink-2">{attempt.situation}</p>

          <div className="mt-4">
            <h3 className="text-[13px] font-semibold text-ink">What you are asked to do</h3>
            <p className="mt-1 text-[14px] leading-relaxed text-ink-2">{attempt.task}</p>
          </div>

          {attempt.constraint && (
            <Note tone="brass">
              <strong className="font-semibold">The constraint:</strong> {attempt.constraint}
            </Note>
          )}

          <label htmlFor="sim-response" className="mt-5 block text-[13px] font-semibold text-ink">
            Your decision, and why
          </label>
          <p className="mb-2 text-[12px] text-ink-3">
            There is no single right answer. A decision that differs from what the authors
            expected is not wrong — what is assessed is the judgement behind it.
          </p>
          <textarea
            id="sim-response"
            className="min-h-[260px] w-full rounded border border-line bg-surface p-3 text-[14px] leading-relaxed text-ink outline-none focus:border-accent"
            value={response}
            onChange={(e) => setResponse(e.target.value)}
            placeholder="Say what you would do, in what order, and the reasoning behind each decision."
          />
          <div className="mt-2 flex flex-wrap items-center justify-between gap-3">
            <span className={`text-[12px] ${enough ? "text-ink-3" : "text-brass"}`}>
              {words} word{words === 1 ? "" : "s"}
              {enough ? "" : ` — at least ${MIN_WORDS} before this can be assessed fairly`}
            </span>
            <button className={btnPrimary} disabled={busy || !enough} onClick={() => void submit()}>
              {busy ? "Assessing…" : "Submit for assessment"}
            </button>
          </div>
        </Card>
      )}

      {/* ----------------------------------------------------------------- */}
      {/* Nothing open — the invitation, or the exhausted library            */}
      {/* ----------------------------------------------------------------- */}
      {!result && !attempt && (
        <Card title="Start a simulation">
          {exhausted ? (
            <Note>
              You have worked through every situation in the library. New ones are added as
              they are authored and reviewed — a scenario is written by hand, because a
              rubric an officer can contest has to be one a person is prepared to defend.
            </Note>
          ) : (
            <>
              <p className="text-[14px] leading-relaxed text-ink-2">
                You will be given one real situation, the constraint that makes it hard, and
                fifteen minutes or so to say what you would do. The situation is chosen to sit
                on your widest gap against your role, at a level you can reach.
              </p>
              <p className="mt-3 text-[14px] leading-relaxed text-ink-2">
                This is the heaviest-weighted evidence on the platform. A quiz shows what you
                know; this shows what you would do with it.
              </p>
              <button className={`${btnPrimary} mt-4`} disabled={busy} onClick={() => void start()}>
                {busy ? "Choosing a situation…" : "Begin"}
              </button>
            </>
          )}
        </Card>
      )}

      {/* ----------------------------------------------------------------- */}
      {/* Everything previously attempted                                   */}
      {/* ----------------------------------------------------------------- */}
      <Card title="Your simulations">
        {history.length === 0 ? (
          <Empty>Nothing yet. Your first simulation will appear here once assessed.</Empty>
        ) : (
          <ul className="divide-y divide-line">
            {history.map((h) => (
              <li key={h.attempt_id} className="flex flex-wrap items-baseline gap-x-4 gap-y-1 py-2.5">
                <span className="flex-1 text-[14px] font-semibold text-ink">{h.title}</span>
                <span className="text-[12.5px] text-ink-3">{h.competency_name}</span>
                <span className="tabular-nums text-[14px] font-semibold text-ink">
                  {h.degraded ? "not scored" : `L${h.derived_level?.toFixed(2) ?? "—"}`}
                </span>
                <span className="text-[12px] text-ink-3">
                  {h.submitted_at ? new Date(h.submitted_at).toLocaleDateString() : ""}
                </span>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </>
  );
}
