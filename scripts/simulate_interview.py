"""Drive an interview through scoring without a microphone.

    python scripts/simulate_interview.py

Feeds synthetic speech measurements straight into the real scoring service, so
`apply_calibration`, `score_answer`, the evidence writeback and the report
assembly all run exactly as they do for a recorded answer. Only the audio
pipeline is skipped.

Useful for two things: checking the report renders before ffmpeg and the models
are installed, and demonstrating that fluency really is scored relative to the
officer's own baseline — the second answer here fumbles noticeably more than the
first, on the same baseline.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

# The Windows console defaults to cp1252, which cannot encode the arrows and
# dashes used below. Without this the script dies inside `print` rather than in
# anything it is testing.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from sqlalchemy import select  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.ml.judge import StubJudge  # noqa: E402
from app.models import User  # noqa: E402
from app.models_interview import AnswerStatus, Interview, InterviewStatus  # noqa: E402
from app.services.interview import (  # noqa: E402
    AnalysisInput,
    apply_calibration,
    build_report,
    score_answer,
)
from app.services.interview_scoring import SpeechSignal, count_hedges  # noqa: E402

LEARNER = "venkatesan@sankhya.gov.in"

# The read-aloud baseline: how this officer speaks with no knowledge load.
BASELINE = dict(words=96, wpm=138.0, filler_count=2, filler_rate=2.1,
                long_pause_count=0, latency_to_first_word=0.6)

# Two answers on the same baseline. The first is fluent; the second fumbles.
ANSWERS = [
    {
        "label": "confident answer",
        "transcript": (
            "I would stratify by district and by rural and urban sector, then select "
            "villages as first stage units with probability proportional to size. "
            "Allocation across strata should reflect the variance within each stratum "
            "rather than being equal, because equal allocation wastes sample in "
            "homogeneous strata. For very small districts I would either collapse them "
            "with a neighbour or accept a larger relative standard error and say so."
        ),
        "signal": dict(words=86, wpm=142.0, filler_count=2, filler_rate=2.3,
                       long_pause_count=0, latency_to_first_word=0.9),
    },
    {
        "label": "hesitant answer on a weak competency",
        "transcript": (
            "So, um, for the spatial part I think maybe you would use the satellite "
            "imagery, uh, to see where the settlements are. Basically the frame might "
            "be, um, out of date and, matlab, you would want to check it. I am not "
            "completely sure about the projection side of it, uh, possibly that matters "
            "for the coordinates."
        ),
        "signal": dict(words=61, wpm=104.0, filler_count=8, filler_rate=13.1,
                       long_pause_count=4, latency_to_first_word=4.2),
    },
]


def main() -> int:
    db = SessionLocal()
    try:
        learner = db.scalar(select(User).where(User.email == LEARNER))
        if learner is None:
            print(f"No such officer: {LEARNER}. Run the seed first.")
            return 1

        interview = db.scalar(
            select(Interview)
            .where(Interview.user_id == learner.id)
            .order_by(Interview.id.desc())
            .limit(1)
        )
        if interview is None:
            print("No interview found. Start one in the UI first.")
            return 1

        answers = sorted(interview.answers, key=lambda a: a.sequence)
        judge = StubJudge()
        print(f"Interview {interview.id} for {learner.full_name}\n")

        # --- calibration -------------------------------------------------- #
        baseline_answer = next((a for a in answers if a.question.is_baseline), None)
        if baseline_answer:
            apply_calibration(db, baseline_answer, AnalysisInput(
                transcript="The National Statistical Office publishes a range of official statistics.",
                signal=SpeechSignal(**BASELINE),
                fillers=[], pauses={}, prosody={}, duration=42.0, warnings=[],
            ))
            db.commit()
            print(f"Baseline captured: {interview.baseline_wpm} wpm, "
                  f"{interview.baseline_filler_rate} fillers/100w\n")

        # --- answers ------------------------------------------------------ #
        scorable = [a for a in answers if not a.question.is_baseline]
        for spec, answer in zip(ANSWERS, scorable):
            signal = SpeechSignal(
                **spec["signal"], hedge_count=count_hedges(spec["transcript"])
            )
            fillers = [
                {"word": "um", "t": round(2.5 + i * 4.1, 1)}
                for i in range(signal.filler_count)
            ]
            pauses = {
                "pause_count": signal.long_pause_count + 1,
                "long_pause_count": signal.long_pause_count,
                "mean_pause_seconds": 1.8,
                "latency_to_first_word": signal.latency_to_first_word,
                "pause_spans": [
                    {"start": round(5.0 + i * 7.5, 1), "end": round(7.4 + i * 7.5, 1)}
                    for i in range(signal.long_pause_count)
                ],
            }
            data = AnalysisInput(
                transcript=spec["transcript"], signal=signal, fillers=fillers,
                pauses=pauses,
                prosody={"pitch_mean": 132.0, "pitch_sd": 21.5, "jitter": 0.014},
                duration=38.0, warnings=[],
            )
            answer.duration_seconds = 38.0
            verdict = judge.score(
                answer.question.prompt,
                list(answer.question.expected_points or []),
                spec["transcript"],
            )
            score = score_answer(db, answer, data, verdict)
            db.commit()

            print(f"{spec['label']}:")
            print(f"  knowledge {score.knowledge}   structure {score.structure}   "
                  f"fluency {score.fluency}   confidence {score.confidence}")
            for note in (score.rationale or {}).get("delivery_notes", []):
                print(f"    - {note}")
            print()

        for answer in scorable[len(ANSWERS):]:
            answer.status = AnswerStatus.SCORED
        interview.status = InterviewStatus.COMPLETED
        db.commit()

        report = build_report(db, interview)
        print("Report axes:")
        for key, axis in report["axes"].items():
            print(f"  {axis['label']:<24} {axis['score']}")

        # Assertions, not decoration. Assigning a score by foreign key instead of
        # through the relationship once left `answer.score` stale for the rest of
        # the session, and the report quietly came back with every axis null.
        failures = []
        for key in ("knowledge", "structure", "fluency", "confidence"):
            if report["axes"][key]["score"] is None:
                failures.append(f"axis '{key}' is null after scoring")
        if {"overall", "composite", "total_score"} & set(report):
            failures.append("a composite score field appeared in the report")

        fluent, hesitant = (a["scores"]["fluency"] for a in report["answers"][:2])
        if fluent is not None and hesitant is not None and hesitant >= fluent:
            failures.append(
                f"fluency did not separate the two answers ({fluent} vs {hesitant})"
            )

        print()
        if failures:
            for f in failures:
                print(f"  FAIL  {f}")
            return 1

        print(f"  PASS  four axes populated, no composite field")
        print(f"  PASS  fluency separated the answers on one baseline "
              f"({fluent} fluent vs {hesitant} hesitant)")
        print("\nOpen http://localhost:3000/interview to see the report.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
