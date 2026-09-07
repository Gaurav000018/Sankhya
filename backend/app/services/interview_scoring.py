"""Delivery scoring for the AI interview.

Knowledge and Structure come from the rubric judge (see `ml/judge.py`). This
module computes the two *delivery* axes from measured speech signal — and the
rules it encodes are the reason the feature is defensible:

* Fluency is a deviation from the officer's **own** read-aloud baseline, never a
  population mean. A naturally fast speaker, a regional speech pattern or an
  accent shifts the baseline too, so it cancels out. What remains is "did this
  person fumble more than they normally do", which is the only version of the
  question worth asking.
* No baseline means **no fluency score**. Returning a number computed against a
  population average would be exactly the bias the baseline exists to remove.
* Confidence is computed from hedging language, response latency and long
  pauses — linguistic and temporal signal. It deliberately does **not** use
  pitch, affect or facial expression: inferring emotional state from voice
  quality is weak science and is not something to attach to an officer's record.
* Neither axis becomes competency evidence.
"""

from __future__ import annotations

from dataclasses import dataclass

# Grace band: speaking within 20% of your own usual rate costs nothing.
RATE_GRACE = 0.20
LONG_PAUSE_PENALTY = 0.30
MAX_PAUSE_PENALTY = 1.50
MAX_FILLER_PENALTY = 2.00
MAX_RATE_PENALTY = 1.00

# A pause under this is thinking, not fumbling.
LONG_PAUSE_SECONDS = 2.0
LATENCY_GRACE_SECONDS = 2.0

# Words that mark uncertainty rather than content. Counted on the transcript.
HEDGE_MARKERS = {
    "maybe", "perhaps", "possibly", "probably", "somewhat", "sort", "kind",
    "guess", "suppose", "unsure", "roughly", "approximately", "might",
    "shayad", "lagta",
}

FILLER_WORDS = {
    "um", "uh", "erm", "hmm", "ah", "eh", "mm",
    "matlab", "yaani", "actually", "basically", "like", "so",
}


def _clamp(value: float, low: float = 1.0, high: float = 5.0) -> float:
    return round(max(low, min(high, value)), 2)


def _capped(value: float, cap: float) -> float:
    return max(0.0, min(cap, value))


@dataclass
class SpeechSignal:
    """Measured facts about one answer. No judgement in here."""

    words: int = 0
    wpm: float | None = None
    filler_count: int = 0
    filler_rate: float | None = None      # per 100 words
    long_pause_count: int = 0
    latency_to_first_word: float | None = None
    hedge_count: int = 0


@dataclass
class Baseline:
    wpm: float | None = None
    filler_rate: float | None = None

    @property
    def is_usable(self) -> bool:
        return bool(self.wpm and self.wpm > 0 and self.filler_rate is not None)


@dataclass
class DeliveryScores:
    fluency: float | None
    confidence: float | None
    # Plain-language reasons, shown to the officer alongside the numbers.
    notes: list[str]


def compute_baseline(signal: SpeechSignal) -> Baseline:
    """Derive a baseline from the read-aloud calibration task.

    Reading neutral text carries no knowledge load, so what it measures is how
    this person speaks when they are not searching for an answer.
    """
    if signal.words < 20:
        # Too short to characterise anyone. Better to have no baseline — and so
        # no fluency score — than a baseline built on ten words.
        return Baseline()
    return Baseline(wpm=signal.wpm, filler_rate=signal.filler_rate or 0.0)


def score_fluency(
    signal: SpeechSignal, baseline: Baseline, *, enabled: bool = True
) -> tuple[float | None, list[str]]:
    notes: list[str] = []

    if not enabled:
        return None, ["Fluency scoring is switched off for this officer. "
                      "Knowledge and Structure are unaffected."]
    if signal.words == 0:
        return None, ["No speech detected in this answer."]
    if not baseline.is_usable:
        return None, ["No calibration baseline for this session, so fluency is "
                      "not scored. Scoring it against a population average would "
                      "penalise accent and regional speech patterns."]

    penalty = 0.0

    if signal.filler_rate is not None:
        # Compare against the person's own habit, with a floor so someone with a
        # near-zero baseline is not punished for a single "um".
        reference = max(baseline.filler_rate or 0.0, 1.0)
        ratio = signal.filler_rate / reference
        filler_penalty = _capped((ratio - 1.0) * 1.0, MAX_FILLER_PENALTY)
        penalty += filler_penalty
        if filler_penalty > 0.4:
            notes.append(
                f"Filler words ran at {signal.filler_rate:.1f} per 100 words "
                f"against your usual {reference:.1f}."
            )

    if signal.wpm and baseline.wpm:
        deviation = abs(signal.wpm - baseline.wpm) / baseline.wpm
        rate_penalty = _capped((deviation - RATE_GRACE) * 5.0, MAX_RATE_PENALTY)
        penalty += rate_penalty
        if rate_penalty > 0.3:
            direction = "faster" if signal.wpm > baseline.wpm else "slower"
            notes.append(
                f"You spoke noticeably {direction} than your baseline "
                f"({signal.wpm:.0f} vs {baseline.wpm:.0f} wpm)."
            )

    pause_penalty = _capped(signal.long_pause_count * LONG_PAUSE_PENALTY, MAX_PAUSE_PENALTY)
    penalty += pause_penalty
    if signal.long_pause_count >= 2:
        notes.append(f"{signal.long_pause_count} pauses over {LONG_PAUSE_SECONDS:.0f}s.")

    if signal.latency_to_first_word:
        penalty += _capped((signal.latency_to_first_word - LATENCY_GRACE_SECONDS) * 0.3, 0.5)

    return _clamp(5.0 - penalty), notes


def score_confidence(signal: SpeechSignal) -> tuple[float | None, list[str]]:
    """Assertiveness of delivery, from language and timing only."""
    notes: list[str] = []
    if signal.words == 0:
        return None, []

    penalty = 0.0

    hedge_rate = 100.0 * signal.hedge_count / max(signal.words, 1)
    hedge_penalty = _capped(hedge_rate * 0.35, 1.5)
    penalty += hedge_penalty
    if hedge_penalty > 0.4:
        notes.append(
            f"{signal.hedge_count} hedging phrases (\"maybe\", \"I think\") — "
            "stating the answer directly reads as more assured."
        )

    if signal.latency_to_first_word:
        latency_penalty = _capped(
            (signal.latency_to_first_word - LATENCY_GRACE_SECONDS) * 0.4, 1.0
        )
        penalty += latency_penalty
        if latency_penalty > 0.3:
            notes.append(
                f"You took {signal.latency_to_first_word:.1f}s to begin answering."
            )

    penalty += _capped(signal.long_pause_count * 0.2, 1.0)

    return _clamp(5.0 - penalty), notes


def score_delivery(
    signal: SpeechSignal, baseline: Baseline, *, fluency_enabled: bool = True
) -> DeliveryScores:
    fluency, fluency_notes = score_fluency(signal, baseline, enabled=fluency_enabled)
    confidence, confidence_notes = score_confidence(signal)
    return DeliveryScores(
        fluency=fluency,
        confidence=confidence,
        notes=fluency_notes + confidence_notes,
    )


def count_hedges(transcript: str) -> int:
    words = [w.strip(".,!?;:").lower() for w in (transcript or "").split()]
    return sum(1 for w in words if w in HEDGE_MARKERS)


def count_fillers(tokens: list[str]) -> int:
    """Count disfluency tokens.

    Fed from the Vosk pass, not Whisper: Whisper is trained to produce clean
    readable text and removes "um" / "uh", which would report every officer as
    perfectly fluent.
    """
    return sum(1 for t in tokens if t.strip(".,!?;:").lower() in FILLER_WORDS)
