import type { LiveSpeech, LiveTip } from "../types";

/**
 * Turn one answer's live measurements into something worth saying.
 *
 * Shown the moment the officer stops speaking, while the answer is still in
 * their head — which is the only time this kind of feedback is actionable.
 * Waiting twenty seconds for the server pass means telling someone about a
 * habit they have already stopped thinking about.
 *
 * Two rules the wording follows.
 *
 * **Fillers are not a fault.** They mark where the answer was still being
 * planned. This platform's own model treats disfluency as cognitive load, not
 * as competence, and an expert on a hard question produces more of it than
 * someone reciting. So every tip says what the pattern means before it says
 * what to do, and none of them tell the officer they did badly.
 *
 * **Say nothing rather than pad.** An answer with no notable pattern gets one
 * line confirming that. Manufacturing three suggestions for a clean answer is
 * how a coaching tool teaches people to ignore it.
 */

const HIGH_FILLER_RATE = 8;      // per 100 words
const VERY_HIGH_FILLER_RATE = 14;
const SHORT_ANSWER_WORDS = 25;

// Pace thresholds deliberately live in `useLiveSpeech`, which is what decides
// `live.pace`. Keeping a second copy here would let the wording and the
// classification drift apart — the tip would say "quick" off one threshold
// while the indicator said "steady" off another.

/** Fillers bunched in the opening seconds mean a different thing to fillers spread out. */
const OPENING_WINDOW_SECONDS = 8;
const CLUSTER_SHARE = 0.5;

export function liveTips(live: LiveSpeech | null): LiveTip[] {
  if (!live) return [];

  const tips: LiveTip[] = [];

  if (live.words < SHORT_ANSWER_WORDS) {
    return [{
      tone: "neutral",
      headline: "That was a short answer",
      detail:
        live.words === 0
          ? "Nothing was picked up. Check your microphone is the one the browser "
            + "is using, then try again — the recording itself may still be fine."
          : "Too little was said to read anything into the delivery. If you had "
            + "more to say, the recorder gives you the full ninety seconds.",
    }];
  }

  const rate = live.filler_rate;

  if (rate !== null && rate >= HIGH_FILLER_RATE) {
    const opening = live.filler_times.filter((t) => t <= OPENING_WINDOW_SECONDS).length;
    const clustered =
      live.filler_count > 0 && opening / live.filler_count >= CLUSTER_SHARE;

    tips.push({
      tone: rate >= VERY_HIGH_FILLER_RATE ? "attention" : "neutral",
      headline: `${live.filler_count} filler${live.filler_count === 1 ? "" : "s"} — ${rate} per 100 words`,
      detail: clustered
        ? "Most of them were in the first few seconds, which usually means you "
          + "started talking before you had decided where the answer was going. "
          + "Take two seconds of silence first and pick your opening sentence. "
          + "Silence at the start reads as composure; filler does not."
        : "They were spread through the answer, which is what happens when you "
          + "are assembling the reasoning as you speak. That is not a fault — it "
          + "is what thinking sounds like — but if you want fewer, deciding your "
          + "three points before you start is what changes it.",
    });
  }

  if (live.pace === "fast" && live.wpm !== null) {
    tips.push({
      tone: "neutral",
      headline: `${live.wpm} words a minute is quick`,
      detail:
        "Nothing is scored on pace. It matters because a listener who is also "
        + "taking notes falls behind, and in a briefing that costs you the point "
        + "you were making.",
    });
  } else if (live.pace === "slow" && live.wpm !== null) {
    tips.push({
      tone: "neutral",
      headline: `${live.wpm} words a minute is unhurried`,
      detail:
        "Fine in itself, and often a sign of care. Only worth noting if you ran "
        + "out of time before you finished the answer.",
    });
  }

  if (live.long_pauses >= 3) {
    tips.push({
      tone: "neutral",
      headline: `${live.long_pauses} long pauses`,
      detail:
        "A pause while you think is worth more than filler covering the same "
        + "gap. This is only worth attention if you felt stuck rather than "
        + "considering — and you are the only one who can tell which it was.",
    });
  }

  if (tips.length === 0) {
    tips.push({
      tone: "good",
      headline: "Nothing stood out in the delivery",
      detail:
        `${live.words} words at ${live.wpm ?? "a steady"} words a minute, with `
        + `${live.filler_count} filler${live.filler_count === 1 ? "" : "s"}. `
        + "Whether the answer was right is a separate question, and the scoring "
        + "that follows is what speaks to that.",
    });
  }

  return tips;
}
