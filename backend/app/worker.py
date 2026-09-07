"""Speech analysis worker.

Runs on the HOST, next to the GPU:

    cd backend && python -m app.worker

Pulls answer ids from Redis, runs the speech pipeline, calls the judge, writes
the four axes back, and deletes the recording. The API never does any of this
inside a request — analysis takes roughly twenty seconds.

Ordering inside `process_answer` is deliberate: transcription runs on the GPU,
Whisper is then unloaded, and only afterwards is the judge invoked. Six
gigabytes of VRAM will not comfortably hold Whisper and a 7B Q4 model at once,
and the pipeline is sequential anyway.
"""

from __future__ import annotations

import logging
import signal
import sys
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.core import queue
from app.db import SessionLocal
from app.ml.judge import degraded_verdict, get_judge
from app.ml.speech import analyse_answer, availability, unload_whisper
from app.models_interview import AnswerStatus, InterviewAnswer
from app.services.interview import AnalysisInput, apply_calibration, score_answer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s %(name)s  %(message)s",
)
log = logging.getLogger("sankhya.worker")

_shutdown = False

REPO_AUDIO_DIR = Path(__file__).resolve().parents[2] / "data" / "audio"


def resolve_audio_dir() -> Path:
    """Where the recordings actually are.

    `settings.audio_dir` is the container path (/data/audio). On the host that
    resolves to somewhere meaningless, so fall back to the bind-mounted
    directory in the repo — the same files, seen from the other side of the
    mount. An explicit AUDIO_DIR environment variable still wins.
    """
    configured = Path(settings.audio_dir)
    if configured.exists() or configured.parent.exists():
        return configured
    return REPO_AUDIO_DIR


AUDIO_DIR = resolve_audio_dir()


def _handle_signal(signum, frame) -> None:
    global _shutdown
    log.info("Shutdown requested; finishing the current job first")
    _shutdown = True


def find_audio(answer_id: int) -> Path | None:
    if not AUDIO_DIR.exists():
        return None
    for candidate in sorted(AUDIO_DIR.glob(f"answer_{answer_id}.*")):
        return candidate
    return None


def process_answer(db: Session, answer_id: int) -> None:
    answer = db.get(InterviewAnswer, answer_id)
    if answer is None:
        log.warning("Answer %s no longer exists; dropping the job", answer_id)
        return

    question = answer.question
    audio = find_audio(answer_id)

    # A re-judge after a transcript correction arrives with no audio, which is
    # expected: the measured speech signal is already stored, so only the
    # Knowledge and Structure axes need recomputing.
    rejudge_only = audio is None and answer.transcript_raw and answer.metrics

    if audio is None and not rejudge_only:
        answer.status = AnswerStatus.FAILED
        answer.failure_reason = "Recording not found"
        queue.set_status(answer_id, "failed", "Recording not found")
        db.commit()
        return

    queue.set_status(answer_id, "analysing")
    answer.status = AnswerStatus.ANALYSING
    db.commit()

    try:
        if rejudge_only:
            metrics = answer.metrics
            from app.services.interview_scoring import SpeechSignal, count_hedges

            transcript = answer.transcript or ""
            data = AnalysisInput(
                transcript=transcript,
                signal=SpeechSignal(
                    words=len(transcript.split()),
                    wpm=metrics.wpm,
                    filler_count=metrics.filler_count,
                    filler_rate=metrics.filler_rate,
                    long_pause_count=metrics.long_pause_count,
                    latency_to_first_word=metrics.latency_to_first_word,
                    hedge_count=count_hedges(transcript),
                ),
                fillers=metrics.fillers or [],
                pauses={
                    "pause_count": metrics.pause_count,
                    "long_pause_count": metrics.long_pause_count,
                    "mean_pause_seconds": metrics.mean_pause_seconds,
                    "latency_to_first_word": metrics.latency_to_first_word,
                    "pause_spans": metrics.pause_spans,
                },
                prosody={
                    "pitch_mean": metrics.pitch_mean, "pitch_sd": metrics.pitch_sd,
                    "intensity_mean": metrics.intensity_mean, "jitter": metrics.jitter,
                },
                duration=answer.duration_seconds or 0.0,
                warnings=["Re-judged after transcript correction"],
            )
        else:
            log.info("Analysing answer %s (%s)", answer_id, audio.name)
            analysis = analyse_answer(audio, language=answer.interview.language)
            data = AnalysisInput(
                transcript=analysis.transcript,
                signal=analysis.signal,
                fillers=analysis.fillers,
                pauses=analysis.pauses,
                prosody=analysis.prosody,
                duration=analysis.duration,
                warnings=analysis.warnings,
            )
            answer.duration_seconds = analysis.duration
            for warning in analysis.warnings:
                log.warning("answer %s: %s", answer_id, warning)

        if question is not None and question.is_baseline:
            apply_calibration(db, answer, data)
            db.commit()
            queue.set_status(answer_id, "done", "Calibration baseline captured")
            log.info(
                "Baseline for interview %s: %s wpm, %s fillers/100w",
                answer.interview_id, answer.interview.baseline_wpm,
                answer.interview.baseline_filler_rate,
            )
            return

        # Free VRAM before the judge loads. 6 GB will not hold both.
        unload_whisper()

        if not (data.transcript or "").strip():
            verdict = degraded_verdict("No speech was detected in this answer")
        else:
            verdict = get_judge().score(
                question.prompt if question else "",
                list(question.expected_points or []) if question else [],
                data.transcript,
            )

        score_answer(db, answer, data, verdict)
        db.commit()

        queue.set_status(
            answer_id, "done",
            "Scored with a degraded verdict" if verdict.degraded else None,
        )
        log.info(
            "Answer %s scored — knowledge %s, structure %s, fluency %s, confidence %s",
            answer_id, verdict.knowledge, verdict.structure,
            answer.score.fluency, answer.score.confidence,
        )

    except Exception as exc:
        db.rollback()
        # The recording is deleted below whatever happens, so a failure means the
        # officer has to record again. Say that, rather than showing them a
        # stack-trace fragment they can do nothing with.
        detail = (
            "Analysis failed, so this answer could not be scored. "
            "Please record it again."
        )
        log.exception("Analysis failed for answer %s: %s", answer_id, exc)

        answer = db.get(InterviewAnswer, answer_id)
        if answer:
            answer.status = AnswerStatus.FAILED
            answer.failure_reason = detail
            db.commit()
        queue.set_status(answer_id, "failed", detail)

    finally:
        # No audio is retained, whatever happened above. That is the stronger
        # commitment: a failed job costs one re-recording, whereas keeping audio
        # around "just in case" quietly breaks the retention promise.
        if audio is not None:
            Path(audio).unlink(missing_ok=True)


MAX_CHUNKS_PER_RUN = 25


def process_generation(db: Session, payload: dict) -> None:
    """Generate questions from a material's passages.

    Every candidate goes through citation verification before it is stored, and
    everything that survives lands as DRAFT. Nothing here can publish anything.
    """
    from app.ml.generator import get_generator
    from app.models_content import Material, MaterialChunk
    from app.services import quizgen

    material_id = payload.get("material_id")
    count = int(payload.get("count", 2))
    bloom = str(payload.get("bloom", "apply"))

    material = db.get(Material, material_id)
    if material is None:
        log.warning("Material %s no longer exists; dropping the job", material_id)
        return

    chunks = db.scalars(
        select(MaterialChunk)
        .where(MaterialChunk.material_id == material.id)
        .order_by(MaterialChunk.ordinal)
        .limit(MAX_CHUNKS_PER_RUN)
    ).all()

    competency = material.competency.name if material.competency else None
    generator = get_generator()
    created = rejected = 0

    log.info(
        "Generating from material %s (%s): %d passages via %s",
        material.id, material.title, len(chunks), generator.model_name,
    )

    for chunk in chunks:
        if _shutdown:
            log.info("Stopping generation early at passage %s", chunk.ordinal)
            break
        try:
            candidates = generator.generate(
                chunk.text, competency=competency, count=count, bloom=bloom
            )
            result = quizgen.store_candidates(
                db, material=material, chunk=chunk,
                candidates=candidates, model_name=generator.model_name,
                actor_id=material.uploaded_by_id,
            )
            db.commit()
            created += len(result.created)
            rejected += len(result.rejected)
        except Exception:
            db.rollback()
            log.exception("Generation failed on passage %s", chunk.ordinal)

    log.info(
        "Material %s: %d questions queued for SME review, %d discarded for "
        "unverifiable citations",
        material.id, created, rejected,
    )


def report_capabilities() -> None:
    components = availability()
    log.info("Speech components: %s", ", ".join(
        f"{name}={'yes' if ok else 'NO'}" for name, ok in components.items()
    ))
    if not components["ffmpeg"]:
        log.error("ffmpeg is missing — audio cannot be decoded and every job will fail")
    if not components["vosk"]:
        log.warning(
            "Vosk model not configured: fillers cannot be counted. Whisper strips "
            "disfluencies, so fluency will be reported as unscoreable rather than zero."
        )


def main() -> int:
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    AUDIO_DIR.mkdir(parents=True, exist_ok=True)

    log.info("Speech worker starting")
    log.info("  queue      %s", settings.analysis_queue)
    log.info("  audio dir  %s", AUDIO_DIR.resolve())
    log.info("  database   %s", settings.database_url.split("@")[-1])
    report_capabilities()
    log.info("Waiting for work. Ctrl+C to stop.")

    consecutive_failures = 0

    while not _shutdown:
        try:
            queue.worker_heartbeat()
            job = queue.dequeue_job(timeout=5)
            consecutive_failures = 0
        except queue.TRANSIENT_ERRORS as exc:
            # A dropped connection while blocked on BRPOP is normal on Windows
            # over Docker's port forwarding. Reconnect rather than exiting — a
            # worker that dies on a blip is a worker that is down at the demo.
            consecutive_failures += 1
            if consecutive_failures >= 12:
                log.error("Redis unreachable after %d attempts: %s",
                          consecutive_failures, exc)
                return 1
            log.warning("Redis hiccup (%s); reconnecting", type(exc).__name__)
            continue

        if job is None:
            continue

        kind, payload = job
        db = SessionLocal()
        try:
            if kind == "analysis":
                process_answer(db, int(payload["answer_id"]))
            elif kind == "generation":
                process_generation(db, payload)
            else:
                log.warning("Unknown job kind %r; dropping it", kind)
        except Exception:
            # One bad job must never take the worker down. A database error
            # raised inside process_answer's own error handling used to escape
            # this loop and kill the process, which meant every queued answer
            # after it sat unanalysed with no indication why.
            log.exception("Job failed and was dropped: %s %r", kind, payload)
            try:
                db.rollback()
            except Exception:
                pass
        finally:
            db.close()

    log.info("Worker stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
