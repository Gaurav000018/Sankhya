import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError, api } from "../api";
import { useAuth } from "../auth";
import { PageHeader } from "../components/Layout";
import {
  AnswerBreakdown,
  AttentionPanel,
  AxisScores,
  CoachingPanel,
  type AnswerReport,
  type Axis,
} from "../components/InterviewReport";
import { Card, Empty, ErrorNote, Note, Spinner } from "../components/ui";
import { useFaceMesh } from "../hooks/useFaceMesh";
import { useRecorder } from "../hooks/useRecorder";
import type { Coaching, FracRole, NextQuestion } from "../types";
import { usePageTitle } from "../hooks/usePageTitle";

interface QuestionSlot {
  answer_id: number;
  sequence: number;
  question: string | null;
  is_baseline: boolean;
  status: string;
  /** Why the interview asked this, in a sentence the officer can read. */
  asked_because: string | null;
  /** Written by the model mid-session rather than drawn from the vetted bank. */
  is_generated: boolean;
  competency_name: string | null;
}

interface Interview {
  interview_id: number;
  status: string;
  baseline: { wpm: number | null; filler_rate: number | null; captured: boolean };
  fluency_scoring_enabled: boolean;
  axes: Record<string, Axis>;
  answers: AnswerReport[];
  disclosure: { note: string };
  coaching?: Coaching | null;
  questions: QuestionSlot[];
  worker_online: boolean;
  max_answer_seconds: number;
}

interface AnswerStatus {
  answer_id: number;
  status: string;
  job: string;
  detail: string | null;
  worker_online: boolean;
  transcript: string | null;
  scored: boolean;
}

function seconds(value: number) {
  const m = Math.floor(value / 60);
  const s = Math.floor(value % 60);
  return `${m}:${String(s).padStart(2, "0")}`;
}

/**
 * What the officer agrees to before the camera turns on. Stored with every
 * attention record: consent you cannot produce afterwards is not consent, and
 * changing the wording below means changing this string.
 */
const ATTENTION_CONSENT_VERSION = "camera-coaching-v1";

export function Interview() {
  usePageTitle("title.interview");

  const { user } = useAuth();
  const [interview, setInterview] = useState<Interview | null>(null);
  const [roles, setRoles] = useState<FracRole[]>([]);
  const [targetRoleId, setTargetRoleId] = useState<number | null>(null);
  const [activeId, setActiveId] = useState<number | null>(null);
  const [progress, setProgress] = useState<string | null>(null);
  const [transcriptDraft, setTranscriptDraft] = useState("");
  const [answerStatus, setAnswerStatus] = useState<AnswerStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const pollRef = useRef<number | null>(null);

  // Camera is opt-in and off until the officer reads what it does and turns it
  // on. Defaulting it on would make "coaching only" a claim rather than a
  // choice, and the interview is complete without it.
  const [cameraWanted, setCameraWanted] = useState(false);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const faceMesh = useFaceMesh();
  const [attentionNote, setAttentionNote] = useState<string | null>(null);
  const [nextInfo, setNextInfo] = useState<NextQuestion | null>(null);

  useEffect(() => {
    api
      .get<FracRole[]>("/frac/roles")
      .then(setRoles)
      .catch(() => setRoles([]))
      .finally(() => setLoading(false));
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  const refresh = useCallback(async (id: number) => {
    const data = await api.get<Interview>(`/interviews/${id}`);
    setInterview(data);
    return data;
  }, []);

  /** Ask the interview what to ask next. The answer depends on the last one. */
  const requestNext = useCallback(
    async (interviewId: number) => {
      try {
        const next = await api.post<NextQuestion>(
          `/interviews/${interviewId}/next-question`,
        );
        setNextInfo(next);
        if (!next.done && next.answer_id !== null) {
          setActiveId(next.answer_id);
          await refresh(interviewId);
        } else {
          setActiveId(null);
        }
        return next;
      } catch {
        // A failure here leaves the officer on the report rather than stuck:
        // they can still finish the interview from what has been answered.
        setActiveId(null);
        return null;
      }
    },
    [refresh],
  );

  /**
   * Send the camera aggregates for one answer.
   *
   * Called after the audio upload so a camera failure can never cost the
   * officer their recording. What is sent is the eight numbers `summary()`
   * returns — no frame, image or landmark exists outside the browser to send.
   */
  const submitAttention = useCallback(
    async (interviewId: number, answerId: number, seconds: number) => {
      const summary = faceMesh.summary(seconds);
      if (!summary) return;
      try {
        await api.post(`/interviews/${interviewId}/answers/${answerId}/attention`, {
          ...summary,
          consent_version: ATTENTION_CONSENT_VERSION,
        });
      } catch {
        /* coaching feedback; never worth surfacing an error over */
      }
    },
    [faceMesh],
  );

  /** Poll while the worker transcribes and scores. Analysis is around twenty
   *  seconds, so this cannot be a synchronous request. */
  const watchAnswer = useCallback(
    (interviewId: number, answerId: number) => {
      if (pollRef.current) clearInterval(pollRef.current);
      let attempts = 0;

      pollRef.current = window.setInterval(async () => {
        attempts += 1;
        try {
          const status = await api.get<AnswerStatus>(
            `/interviews/${interviewId}/answers/${answerId}/status`,
          );
          setAnswerStatus(status);

          if (status.scored || status.status === "failed" || attempts > 90) {
            if (pollRef.current) clearInterval(pollRef.current);
            pollRef.current = null;
            setProgress(null);
            const data = await refresh(interviewId);
            const slot = data.questions.find((q) => q.answer_id === answerId);
            if (status.transcript && !slot?.is_baseline) {
              setTranscriptDraft(status.transcript);
            } else {
              // The calibration read-aloud is not reviewed, so the interview
              // moves straight on to the first real question.
              await requestNext(interviewId);
            }
          } else {
            setProgress(
              status.job === "analysing"
                ? "Transcribing and scoring your answer…"
                : status.worker_online
                  ? "Queued for analysis…"
                  : "Queued, but no analysis worker is running.",
            );
          }
        } catch {
          /* transient — keep polling */
        }
      }, 1500);
    },
    [refresh, requestNext],
  );

  const handleRecorded = useCallback(
    async (blob: Blob, seconds: number) => {
      if (!interview || activeId === null) return;
      setBusy(true);
      setError(null);
      setProgress("Uploading…");
      faceMesh.stop();
      try {
        const result = await api.uploadAnswerAudio(interview.interview_id, activeId, blob);
        void submitAttention(interview.interview_id, activeId, seconds);
        if (!result.worker_online) {
          setProgress(null);
          setError(
            "Recording received, but no analysis worker is running. Start it with " +
              "`python -m app.worker` on the host, then re-record.",
          );
          return;
        }
        setProgress("Queued for analysis…");
        watchAnswer(interview.interview_id, activeId);
      } catch (e) {
        setProgress(null);
        setError(e instanceof ApiError ? e.message : "Could not upload the recording.");
      } finally {
        setBusy(false);
      }
    },
    [activeId, interview, watchAnswer, faceMesh, submitAttention],
  );

  const onStream = useCallback(
    (stream: MediaStream) => {
      const element = videoRef.current;
      if (!element || stream.getVideoTracks().length === 0) return;
      element.srcObject = stream;
      void element.play().catch(() => {});
      faceMesh.start(element);
    },
    [faceMesh],
  );

  const recorder = useRecorder({
    maxSeconds: interview?.max_answer_seconds ?? 90,
    onComplete: handleRecorded,
    video: cameraWanted && faceMesh.supported !== false,
    onStream,
  });

  async function begin() {
    setBusy(true);
    setError(null);
    try {
      if (cameraWanted) await faceMesh.load();
      const created = await api.post<Interview>("/interviews", {
        target_role_id: targetRoleId,
      });
      setInterview(created);
      setActiveId(created.questions[0]?.answer_id ?? null);
      setAttentionNote(
        cameraWanted
          ? "Your camera is on. The video stays in this browser — only a few "
            + "engagement numbers are sent, and they are not scored."
          : null,
      );
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not start an interview.");
    } finally {
      setBusy(false);
    }
  }

  async function saveTranscript(rejudge: boolean) {
    if (!interview || activeId === null) return;
    setBusy(true);
    try {
      await api.patch(
        `/interviews/${interview.interview_id}/answers/${activeId}/transcript`,
        { transcript: transcriptDraft, rejudge },
      );
      setTranscriptDraft("");
      if (rejudge) {
        setProgress("Re-scoring with your corrections…");
        watchAnswer(interview.interview_id, activeId);
      } else {
        await refresh(interview.interview_id);
        await requestNext(interview.interview_id);
      }
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not save the transcript.");
    } finally {
      setBusy(false);
    }
  }

  async function finish() {
    if (!interview) return;
    setBusy(true);
    try {
      setInterview(await api.post<Interview>(`/interviews/${interview.interview_id}/complete`));
      setActiveId(null);
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <Spinner />;

  // ---------------------------------------------------------------- intro --
  if (!interview) {
    return (
      <>
        <PageHeader
          title="AI interview"
          subtitle="Assesses the behavioural and managerial competencies that multiple-choice questions cannot reach"
        />
        <div className="grid gap-3.5 lg:grid-cols-[minmax(0,1fr)_380px]">
          <Card title="How this works">
            <ol className="space-y-3 text-[13.5px] leading-relaxed text-ink-2">
              <li>
                <strong className="text-ink">First, a short reading aloud.</strong> Neutral
                text, no knowledge required. It measures how you speak when you are not
                searching for an answer, and everything afterwards is compared against that
                baseline rather than against other people.
              </li>
              <li>
                <strong className="text-ink">Then a conversation, not a form.</strong>{" "}
                It opens on the competency where your evidence is thinnest, and each
                question after that follows from your last answer — further in when you
                cover something well, back to the foundation when you do not. Up to{" "}
                {90} seconds each. Answer as you would to a colleague. Every question
                tells you why it was asked.
              </li>
              <li>
                <strong className="text-ink">You can correct the transcript.</strong> Speech
                recognition is less accurate on Indian English and on mixed
                Hindi-English speech, so you get the last word on what was said before it
                is re-scored.
              </li>
              <li>
                <strong className="text-ink">Five separate scores.</strong> Knowledge,
                Structure, Communication, Delivery and Confidence. No overall mark, and
                only Knowledge is recorded against your competency profile. Communication
                is judged from what you said, never from how you sounded.
              </li>
            </ol>

            <div className="mt-5">
              <Note tone="brass">
                This is a coaching tool, not a gate. Nothing here decides a posting or a
                promotion on its own, no audio is kept once it has been analysed, and you
                can switch delivery scoring off entirely without affecting the Knowledge
                score.
                {user && !user.fluency_scoring_enabled && (
                  <>
                    {" "}
                    <strong className="font-semibold text-ink">
                      Delivery scoring is currently switched off for your account.
                    </strong>
                  </>
                )}
              </Note>
            </div>
          </Card>

          <Card title="Start a session">
            <label
              htmlFor="interview-target-role"
              className="block text-[11px] font-semibold uppercase tracking-[0.07em] text-ink-3"
            >
              Interview against
            </label>
            <select
              id="interview-target-role"
              value={targetRoleId ?? ""}
              onChange={(e) => setTargetRoleId(Number(e.target.value) || null)}
              className="mt-1.5 w-full border border-rule-strong bg-surface px-3 py-2 text-sm outline-none focus:border-accent"
            >
              <option value="">My current role</option>
              {roles.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.name}
                </option>
              ))}
            </select>
            <p className="mt-2 text-[12px] leading-relaxed text-ink-3">
              Choosing a senior role asks harder questions against that role&rsquo;s
              requirements.
            </p>

            <div className="mt-5 border border-rule bg-surface-2 p-3.5">
              <label
                htmlFor="camera-consent"
                className="flex cursor-pointer items-start gap-2.5"
              >
                <input
                  id="camera-consent"
                  type="checkbox"
                  checked={cameraWanted}
                  onChange={(e) => setCameraWanted(e.target.checked)}
                  className="mt-0.5"
                />
                <span className="text-[12.5px] leading-relaxed text-ink-2">
                  <strong className="font-semibold text-ink">
                    Use my camera for practice feedback
                  </strong>
                  <br />
                  Optional. Your video is analysed inside this browser and{" "}
                  <strong className="font-semibold text-ink">never uploaded</strong> — only
                  a few engagement numbers are sent, so you can see what a listener would
                  see. They are <strong className="font-semibold text-ink">not scored</strong>,
                  do not appear in your competency profile, and your supervisor cannot see
                  them. No face recognition, no emotion detection.
                </span>
              </label>
            </div>

            <button
              disabled={busy}
              onClick={begin}
              className="mt-3 w-full bg-accent px-4 py-2.5 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
            >
              {busy ? "Preparing…" : "Begin interview"}
            </button>
            {error && (
              <div className="mt-3">
                <ErrorNote message={error} />
              </div>
            )}
          </Card>
        </div>
      </>
    );
  }

  const slot = interview.questions.find((q) => q.answer_id === activeId) ?? null;
  const remaining = interview.questions.filter((q) => q.status !== "scored");
  const done = remaining.length === 0;

  // --------------------------------------------------------------- report --
  if (!activeId && !transcriptDraft) {
    return (
      <>
        <PageHeader
          title="Interview report"
          subtitle={interview.status === "completed" ? "Completed" : "In progress"}
          meta={
            interview.baseline.captured
              ? `Your baseline: ${interview.baseline.wpm?.toFixed(0)} wpm, ${interview.baseline.filler_rate?.toFixed(1)} fillers per 100 words`
              : "Baseline not captured"
          }
          action={
            <div className="flex gap-2">
              {!done && (
                <button
                  onClick={() => setActiveId(remaining[0].answer_id)}
                  className="bg-accent px-4 py-2 text-sm font-medium text-white transition-opacity hover:opacity-90"
                >
                  Continue ({remaining.length} left)
                </button>
              )}
              {interview.status !== "completed" && (
                <button
                  disabled={busy}
                  onClick={finish}
                  className="border border-rule-strong px-4 py-2 text-sm text-ink-2 transition-colors hover:border-accent hover:text-ink"
                >
                  Finish
                </button>
              )}
              <button
                onClick={() => {
                  setInterview(null);
                  setActiveId(null);
                }}
                className="border border-rule-strong px-4 py-2 text-sm text-ink-2 transition-colors hover:border-accent hover:text-ink"
              >
                New interview
              </button>
            </div>
          }
        />

        <div className="mb-4">
          <AxisScores axes={interview.axes} fluencyEnabled={interview.fluency_scoring_enabled} />
        </div>

        <div className="mb-4">
          <CoachingPanel coaching={interview.coaching ?? null} />
        </div>

        {/* Camera notes for whichever answer actually produced usable tracking.
            Absent entirely when the officer did not use a camera, and stripped
            by the server for anyone reading someone else's interview. */}
        {(() => {
          const withCamera = interview.answers.find(
            (a) => a.attention && a.attention.quality !== "unusable",
          );
          return withCamera ? (
            <div className="mb-4">
              <AttentionPanel attention={withCamera.attention ?? null} />
            </div>
          ) : null;
        })()}

        {recorder.localVideoUrl && (
          <div className="mb-4">
            <Card
              title="Your recording"
              hint="Held in this browser only — never uploaded, and gone when you leave this page"
            >
              <video
                src={recorder.localVideoUrl}
                controls
                className="block max-h-[320px] w-full bg-navy"
              />
              <p className="mt-2 text-[11.5px] leading-relaxed text-ink-3">
                Watching yourself back is the part of this that actually teaches you
                something. Nothing about this recording was sent anywhere.
              </p>
            </Card>
          </div>
        )}

        <AnswerBreakdown answers={interview.answers} />
      </>
    );
  }

  // ------------------------------------------------------- transcript edit --
  if (transcriptDraft) {
    return (
      <>
        <PageHeader
          title="Check the transcript"
          subtitle="Correct anything speech recognition got wrong before it is re-scored"
        />
        <div className="grid gap-3.5 lg:grid-cols-[minmax(0,1fr)_340px]">
          <Card title="What we heard">
            <label htmlFor="transcript-correction" className="sr-only">
              Correct the transcript of your answer
            </label>
            <textarea
              id="transcript-correction"
              value={transcriptDraft}
              onChange={(e) => setTranscriptDraft(e.target.value)}
              rows={10}
              className="w-full border border-rule-strong bg-surface p-3 text-[13.5px] leading-relaxed outline-none focus:border-accent"
            />
            <div className="mt-3 flex flex-wrap gap-2.5">
              <button
                disabled={busy}
                onClick={() => saveTranscript(true)}
                className="bg-accent px-4 py-2 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
              >
                Save and re-score
              </button>
              <button
                disabled={busy}
                onClick={() => saveTranscript(false)}
                className="border border-rule-strong px-4 py-2 text-sm text-ink-2 transition-colors hover:border-accent hover:text-ink disabled:opacity-50"
              >
                Accept as is
              </button>
            </div>
          </Card>

          <Card title="Why you are being asked">
            <p className="text-[13px] leading-relaxed text-ink-2">
              Speech recognition has a higher error rate on Indian English and on mixed
              Hindi-English speech. If the transcript is wrong, the Knowledge score would
              be measuring the recogniser rather than you.
            </p>
            <p className="mt-3 text-[13px] leading-relaxed text-ink-2">
              Both versions are kept. The difference between them is itself a record of how
              well the system served you.
            </p>
          </Card>
        </div>
      </>
    );
  }

  // ------------------------------------------------------------ recording --
  const isBaseline = slot?.is_baseline ?? false;
  const cap = interview.max_answer_seconds;
  const answered = interview.questions.filter((q) => q.status === "scored").length;

  return (
    <>
      <PageHeader
        title={isBaseline ? "Calibration" : "Question"}
        subtitle={
          isBaseline
            ? "Read this aloud at your normal pace"
            : slot?.competency_name
              ? `On ${slot.competency_name}`
              : "Answer in your own words"
        }
        // An adaptive session has no fixed length: the next question is chosen
        // from the last answer, so "question 3 of 4" would be a promise it
        // cannot keep. Report what has happened and the ceiling instead.
        meta={
          nextInfo
            ? `${answered} answered · up to ${nextInfo.max_questions} questions`
            : `${answered} answered`
        }
      />

      {attentionNote && (
        <div className="mb-3.5">
          <Note>{attentionNote}</Note>
        </div>
      )}

      <div className="grid gap-3.5 lg:grid-cols-[minmax(0,1fr)_340px]">
        <Card title={isBaseline ? "Reading passage" : "Your question"}>
          <p className="whitespace-pre-wrap text-[15px] leading-relaxed">{slot?.question}</p>

          {!isBaseline && slot?.asked_because && (
            <div className="mt-3.5 border-l-2 border-accent pl-3">
              <p className="text-[12px] leading-relaxed text-ink-2">
                <span className="font-semibold text-ink">Why this question: </span>
                {slot.asked_because}
              </p>
              {slot.is_generated && (
                <p className="mt-1 text-[11px] text-ink-3">
                  Written for you during this session in response to your last answer, so
                  it has not been through subject-matter review. It counts for less towards
                  your competency profile than a reviewed question does.
                </p>
              )}
            </div>
          )}

          {isBaseline && (
            <div className="mt-4">
              <Note>
                This carries no knowledge load. It is measuring your natural speaking rate
                and how often you hesitate, so that later answers are compared against{" "}
                <strong className="font-semibold text-ink">you</strong> rather than an
                average.
              </Note>
            </div>
          )}
        </Card>

        <Card title="Recorder">
          {cameraWanted && faceMesh.supported !== false && (
            <div className="mb-3.5">
              <div className="relative overflow-hidden border border-rule bg-navy">
                {/* Mirrored, because a preview that is not mirrored reads as
                    someone else's face rather than your own. */}
                <video
                  ref={videoRef}
                  muted
                  playsInline
                  aria-label="Your camera preview. Nothing here is uploaded."
                  className="block h-[150px] w-full scale-x-[-1] object-cover"
                />
                {recorder.state === "recording" && faceMesh.livePresent === false && (
                  <p className="absolute inset-x-0 bottom-0 bg-navy/85 px-2 py-1 text-[11px] text-[#eceae4]">
                    Camera cannot see you — move into frame, or carry on, it does not
                    affect your score.
                  </p>
                )}
              </div>
              <p className="mt-1.5 text-[10.5px] leading-relaxed text-ink-3">
                Stays in this browser. Never uploaded, never scored.
              </p>
            </div>
          )}

          {faceMesh.error && (
            <p className="mb-3 text-[11.5px] leading-relaxed text-ink-2">{faceMesh.error}</p>
          )}

          {recorder.state === "recording" ? (
            <>
              <div className="flex items-baseline gap-3">
                <span className="inline-block h-2.5 w-2.5 animate-pulse rounded-full bg-critical" />
                <span className="tabular font-mono text-[28px] font-medium leading-none">
                  {seconds(recorder.seconds)}
                </span>
                <span className="text-xs text-ink-3">of {seconds(cap)}</span>
              </div>

              <div className="mt-3 h-1.5 w-full bg-surface-2">
                <div
                  className="h-1.5 bg-critical transition-[width] duration-100"
                  style={{ width: `${(recorder.seconds / cap) * 100}%` }}
                />
              </div>

              <div className="mt-4 flex h-10 items-end gap-1" aria-hidden>
                {Array.from({ length: 24 }).map((_, i) => (
                  <div
                    key={i}
                    className="flex-1 bg-accent/70"
                    style={{
                      height: `${Math.max(
                        6,
                        recorder.level * 100 * (0.55 + 0.45 * Math.sin(i * 0.9 + Date.now() / 180)),
                      )}%`,
                    }}
                  />
                ))}
              </div>

              <button
                onClick={recorder.stop}
                className="mt-5 w-full bg-navy px-4 py-2.5 text-sm font-medium text-white transition-opacity hover:opacity-90"
              >
                Stop and submit
              </button>
            </>
          ) : progress ? (
            <>
              <Spinner label={progress} />
              {answerStatus?.detail && (
                <p className="text-[12px] text-ink-3">{answerStatus.detail}</p>
              )}
            </>
          ) : (
            <>
              <p className="text-[13px] leading-relaxed text-ink-2">
                {isBaseline
                  ? "Read the passage aloud once. Around thirty seconds is enough."
                  : `Answer in your own words. Up to ${cap} seconds.`}
              </p>
              <button
                disabled={busy || recorder.state === "requesting"}
                onClick={recorder.start}
                className="mt-4 w-full bg-accent px-4 py-2.5 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
              >
                {recorder.state === "requesting" ? "Requesting microphone…" : "Start recording"}
              </button>

              {!interview.worker_online && (
                <p className="mt-3 text-[12px] leading-relaxed text-warn">
                  No analysis worker is running, so recordings cannot be scored yet.
                </p>
              )}
            </>
          )}

          {(recorder.error || error) && (
            <div className="mt-3">
              <ErrorNote message={recorder.error ?? error ?? ""} />
            </div>
          )}

          <p className="mt-4 border-t border-rule pt-3 text-[11.5px] leading-relaxed text-ink-3">
            Your recording is deleted as soon as it has been analysed. Only the derived
            measurements are kept.
          </p>
        </Card>
      </div>

      {interview.questions.length > 0 && (
        <div className="mt-4">
          <Card title="Session">
            <div className="flex flex-wrap gap-2">
              {interview.questions.map((q) => (
                <button
                  key={q.answer_id}
                  onClick={() => q.status !== "scored" && setActiveId(q.answer_id)}
                  disabled={q.status === "scored"}
                  className={`px-3 py-1.5 text-[12px] ${
                    q.answer_id === activeId
                      ? "bg-accent text-white"
                      : q.status === "scored"
                        ? "border border-rule bg-surface-2 text-ink-3"
                        : "border border-rule-strong text-ink-2 hover:border-accent"
                  }`}
                >
                  {q.is_baseline ? "Calibration" : `Q${q.sequence}`}
                  {q.status === "scored" && " ✓"}
                </button>
              ))}
            </div>
          </Card>
        </div>
      )}

      {interview.answers.some((a) => a.scores) && (
        <div className="mt-4">
          <button
            onClick={() => setActiveId(null)}
            className="text-[13px] text-accent hover:underline"
          >
            View the report so far →
          </button>
        </div>
      )}
    </>
  );
}

export function InterviewEmptyState() {
  return <Empty>Interviews are available to officers only.</Empty>;
}
