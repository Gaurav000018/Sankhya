import { Note } from "./ui";
import { liveTips } from "../lib/liveCoaching";
import type { LiveSpeech } from "../types";

/**
 * What the officer sees from live speech analysis.
 *
 * Two components, because the same numbers need saying very differently
 * depending on whether the officer is still speaking.
 */

const PACE_COPY: Record<string, string> = {
  slow: "unhurried",
  steady: "steady",
  fast: "quick",
  unknown: "listening",
};

/**
 * During the answer.
 *
 * Deliberately not a filler counter. A number climbing while someone explains
 * stratified sampling takes the working memory the explanation needs, and this
 * platform treats disfluency as cognitive load rather than competence — so a
 * live count would penalise exactly the hard thinking the question is for.
 *
 * What is shown instead: that speech is being picked up, and a one-word read on
 * pace. Enough to catch a dead microphone or a bolting delivery, not enough to
 * argue with.
 */
export function LiveIndicator({ live }: { live: LiveSpeech | null }) {
  if (!live) return null;

  const heard = live.words > 0;

  return (
    <div
      className="mt-3 flex items-center gap-2.5 border border-rule bg-surface-2 px-3 py-2"
      aria-live="off"
    >
      <span
        className={`inline-block h-1.5 w-1.5 shrink-0 rounded-full ${
          heard ? "animate-pulse bg-good" : "bg-rule-strong"
        }`}
      />
      <span className="text-[11.5px] text-ink-2">
        {heard
          ? `Hearing you — ${PACE_COPY[live.pace]}`
          : "Listening — say something to check the microphone"}
      </span>
    </div>
  );
}

const TONE_STYLE: Record<string, string> = {
  good: "border-good",
  neutral: "border-rule-strong",
  attention: "border-warn",
};

/**
 * The moment the answer ends.
 *
 * This is where the filler analysis actually goes, while the answer is still in
 * the officer's head. The server measures the recording again under better
 * conditions and that pass is what the report and the evidence are built from;
 * this one is here because it arrives in a second rather than twenty.
 */
export function LiveDebrief({ live }: { live: LiveSpeech | null }) {
  const tips = liveTips(live);
  if (!live || tips.length === 0) return null;

  return (
    <div className="mt-4 border border-rule bg-surface p-4">
      <div className="flex items-baseline justify-between gap-3">
        <h3 className="text-[12.5px] font-semibold">How that came out</h3>
        <span className="tabular font-mono text-[11px] text-ink-3">
          {live.words} words · {live.seconds.toFixed(0)}s
        </span>
      </div>

      <dl className="mt-3 grid grid-cols-3 gap-3">
        <div>
          <dt className="text-[10.5px] uppercase tracking-[0.06em] text-ink-3">Pace</dt>
          <dd className="tabular mt-0.5 font-mono text-[16px]">
            {live.wpm ?? "—"}
            <span className="ml-1 text-[10.5px] text-ink-3">wpm</span>
          </dd>
        </div>
        <div>
          <dt className="text-[10.5px] uppercase tracking-[0.06em] text-ink-3">Fillers</dt>
          <dd className="tabular mt-0.5 font-mono text-[16px]">
            {live.filler_count}
            {live.filler_rate !== null && (
              <span className="ml-1 text-[10.5px] text-ink-3">
                /{live.filler_rate} per 100w
              </span>
            )}
          </dd>
        </div>
        <div>
          <dt className="text-[10.5px] uppercase tracking-[0.06em] text-ink-3">
            Long pauses
          </dt>
          <dd className="tabular mt-0.5 font-mono text-[16px]">{live.long_pauses}</dd>
        </div>
      </dl>

      <ul className="mt-3.5 space-y-2.5">
        {tips.map((tip, index) => (
          <li
            key={index}
            className={`border-l-2 pl-3 ${TONE_STYLE[tip.tone] ?? "border-rule"}`}
          >
            <p className="text-[12.5px] font-medium">{tip.headline}</p>
            <p className="mt-0.5 text-[11.5px] leading-relaxed text-ink-2">{tip.detail}</p>
          </li>
        ))}
      </ul>

      <Note>
        Measured in your browser as you spoke, so it is here immediately. The
        recording is measured again on the server under better conditions, and
        that is the figure your report and your competency evidence are built
        from — expect small differences between the two.
      </Note>
    </div>
  );
}
