"""AI interview endpoints.

Audio is written to a directory shared with the speech worker and deleted as
soon as analysis finishes. It is never stored in the database and never served
back — the derived measurements are all that survives an answer.
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.core import queue
from app.core.deps import can_view_officer, get_current_user, write_audit
from app.db import get_db
from app.models import User
from app.models_interview import (
    AnswerStatus,
    AttentionMetrics,
    Interview,
    InterviewAnswer,
    InterviewStatus,
)
from app.schemas import (
    AttentionIn,
    InterviewOut,
    InterviewStartIn,
    NextQuestionOut,
    InterviewSummaryOut,
    TranscriptCorrectionIn,
    UploadAcceptedOut,
)
from app.services.interview import (
    InterviewError,
    advance,
    build_report,
    complete_interview,
    start_interview,
)

log = logging.getLogger("sankhya.api.interview")
router = APIRouter(prefix="/interviews", tags=["interview"])

ALLOWED_AUDIO_SUFFIXES = {".webm", ".ogg", ".wav", ".m4a", ".mp4", ".mp3"}


def _audio_path(answer_id: int, suffix: str) -> Path:
    return Path(settings.audio_dir) / f"answer_{answer_id}{suffix}"


def _load_interview(db: Session, interview_id: int, viewer: User) -> Interview:
    interview = db.get(Interview, interview_id)
    if interview is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Interview not found")
    if not can_view_officer(viewer, interview.user):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "You do not have access to this interview"
        )
    return interview


def _load_answer(db: Session, interview: Interview, answer_id: int) -> InterviewAnswer:
    answer = db.get(InterviewAnswer, answer_id)
    if answer is None or answer.interview_id != interview.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Answer not found in this interview")
    return answer


@router.post("", response_model=InterviewOut, status_code=status.HTTP_201_CREATED)
def create_interview(
    payload: InterviewStartIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Open a session.

    Questions are weighted toward this officer's widest gaps, with the read-aloud
    calibration task first — fluency is scored against their own baseline, so
    there is no fair way to score delivery until that has been captured.
    """
    try:
        interview = start_interview(db, user=user, target_role_id=payload.target_role_id)
    except InterviewError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc))

    db.commit()
    db.refresh(interview)
    return _serialise(db, interview, user)


@router.get("/me", response_model=list[InterviewSummaryOut])
def my_interviews(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    interviews = db.scalars(
        select(Interview)
        .where(Interview.user_id == user.id)
        .order_by(Interview.started_at.desc())
        .limit(50)
    ).all()
    return [
        InterviewSummaryOut(
            id=i.id,
            status=i.status.value,
            started_at=i.started_at,
            completed_at=i.completed_at,
            answers=len(i.answers),
            scored=sum(1 for a in i.answers if a.status == AnswerStatus.SCORED),
        )
        for i in interviews
    ]


@router.get("/{interview_id}", response_model=InterviewOut)
def get_interview(
    interview_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return _serialise(db, _load_interview(db, interview_id, user), user)


@router.post(
    "/{interview_id}/answers/{answer_id}/audio",
    response_model=UploadAcceptedOut,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_answer_audio(
    interview_id: int,
    answer_id: int,
    request: Request,
    audio: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Accept a recording and queue it for analysis.

    Returns immediately: transcription, disfluency counting, pause analysis and
    the rubric judge take roughly twenty seconds and cannot run inside a request.
    """
    interview = _load_interview(db, interview_id, user)
    if interview.user_id != user.id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Only the officer being interviewed can submit audio"
        )
    if interview.status in (InterviewStatus.COMPLETED, InterviewStatus.ABANDONED):
        raise HTTPException(status.HTTP_409_CONFLICT, "This interview is already closed")

    answer = _load_answer(db, interview, answer_id)

    suffix = Path(audio.filename or "").suffix.lower() or ".webm"
    if suffix not in ALLOWED_AUDIO_SUFFIXES:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            f"Unsupported audio format. Expected one of: "
            f"{', '.join(sorted(ALLOWED_AUDIO_SUFFIXES))}",
        )

    payload = await audio.read()
    if not payload:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "The recording was empty")
    if len(payload) > settings.max_upload_bytes:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"Recording is too large. Answers are capped at "
            f"{settings.max_answer_seconds} seconds.",
        )

    target = _audio_path(answer.id, suffix)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)

    answer.status = AnswerStatus.RECORDED
    answer.failure_reason = None
    write_audit(
        db,
        action="interview.audio_received",
        actor_user_id=user.id,
        entity_type="interview_answer",
        entity_id=str(answer.id),
        meta={"bytes": len(payload), "format": suffix},
        request=request,
    )
    db.commit()

    queue.enqueue_analysis(answer.id)

    return UploadAcceptedOut(
        answer_id=answer.id,
        status="queued",
        worker_online=queue.worker_is_alive(),
        queue_depth=queue.queue_depth(),
        message=(
            "Analysing your answer."
            if queue.worker_is_alive()
            else "Queued, but no speech worker is running. Start it with "
                 "`python -m app.worker` on the host."
        ),
    )


@router.get("/{interview_id}/answers/{answer_id}/status")
def answer_status(
    interview_id: int,
    answer_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Poll while analysis runs."""
    interview = _load_interview(db, interview_id, user)
    answer = _load_answer(db, interview, answer_id)
    job = queue.get_status(answer.id)
    return {
        "answer_id": answer.id,
        "status": answer.status.value,
        "job": job.get("status"),
        "detail": job.get("detail") or answer.failure_reason,
        "worker_online": queue.worker_is_alive(),
        "transcript": answer.transcript,
        "scored": answer.status == AnswerStatus.SCORED,
    }


@router.patch("/{interview_id}/answers/{answer_id}/transcript")
def correct_transcript(
    interview_id: int,
    answer_id: int,
    payload: TranscriptCorrectionIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Let the officer fix the transcript before it is judged.

    Speech recognition error rates are higher on Indian English and on
    Hindi-English code-switching, which would bias the Knowledge score against
    exactly the officers this platform serves. The original is kept alongside the
    correction — the difference between them measures how well ASR served this
    speaker.
    """
    interview = _load_interview(db, interview_id, user)
    if interview.user_id != user.id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Only the officer can correct their own transcript"
        )

    answer = _load_answer(db, interview, answer_id)
    if not answer.transcript_raw:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "This answer has not been transcribed yet"
        )

    answer.transcript_confirmed = payload.transcript.strip()
    answer.status = AnswerStatus.TRANSCRIBED

    write_audit(
        db,
        action="interview.transcript_corrected",
        actor_user_id=user.id,
        entity_type="interview_answer",
        entity_id=str(answer.id),
        meta={
            "raw_chars": len(answer.transcript_raw or ""),
            "corrected_chars": len(answer.transcript_confirmed or ""),
        },
        request=request,
    )
    db.commit()

    if payload.rejudge:
        queue.enqueue_analysis(answer.id)

    return {
        "answer_id": answer.id,
        "transcript": answer.transcript,
        "rejudging": payload.rejudge,
    }


@router.post("/{interview_id}/complete", response_model=InterviewOut)
def finish_interview(
    interview_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    interview = _load_interview(db, interview_id, user)
    if interview.user_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This is not your interview")

    complete_interview(db, interview)
    write_audit(
        db,
        action="interview.completed",
        actor_user_id=user.id,
        entity_type="interview",
        entity_id=str(interview.id),
        request=request,
    )
    db.commit()
    db.refresh(interview)
    return _serialise(db, interview, user)


def _serialise(
    db: Session, interview: Interview, viewer: User | None = None
) -> InterviewOut:
    # The viewer decides whether the camera block is included at all.
    report = build_report(db, interview, viewer_id=viewer.id if viewer else None)
    pending = [
        {
            "answer_id": a.id,
            "sequence": a.sequence,
            "question": a.question.prompt if a.question else None,
            "is_baseline": bool(a.question and a.question.is_baseline),
            "status": a.status.value,
            # Why the interview chose this, and whether a person vetted it.
            # Both are shown to the officer rather than kept in the audit log.
            "asked_because": a.asked_because,
            "is_generated": bool(a.question and a.question.is_generated),
            "competency_name": (
                a.question.competency.name
                if a.question and a.question.competency else None
            ),
        }
        for a in sorted(interview.answers, key=lambda x: x.sequence)
    ]
    return InterviewOut(
        **report,
        questions=pending,
        worker_online=queue.worker_is_alive(),
        max_answer_seconds=settings.max_answer_seconds,
    )


@router.post("/{interview_id}/next-question", response_model=NextQuestionOut)
def next_question(
    interview_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Ask the interview what comes next.

    Called after each answer is scored. The question returned depends on that
    answer — covered it well and the next one pushes further, missed something
    and it comes back to that, struggled and it steps down to the foundation.

    `done: true` is a normal ending, not an error: the question budget is spent
    or the bank has nothing left that fits.
    """
    interview = _load_interview(db, interview_id, user)
    if interview.user_id != user.id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Only the officer being interviewed can continue the session",
        )
    if interview.status == InterviewStatus.COMPLETED:
        raise HTTPException(status.HTTP_409_CONFLICT, "This interview is already finished")

    asked = sum(
        1 for a in interview.answers
        if a.question is not None and not a.question.is_baseline
    )

    answer = advance(db, interview)
    if answer is None:
        db.commit()
        return NextQuestionOut(
            done=True, asked=asked, max_questions=interview.max_questions
        )

    db.commit()
    db.refresh(answer)

    question = answer.question
    competency = question.competency if question else None
    return NextQuestionOut(
        done=False,
        answer_id=answer.id,
        sequence=answer.sequence,
        question=question.prompt if question else None,
        competency_name=competency.name if competency else None,
        asked_because=answer.asked_because,
        is_generated=bool(question and question.is_generated),
        asked=asked,
        max_questions=interview.max_questions,
    )


@router.post("/{interview_id}/answers/{answer_id}/attention", status_code=status.HTTP_202_ACCEPTED)
def submit_attention(
    interview_id: int,
    answer_id: int,
    payload: AttentionIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Accept camera engagement aggregates computed in the officer's browser.

    What arrives here is a handful of numbers. No frame, image or face landmark
    is accepted — see `AttentionIn`, which has nowhere to put one.

    These figures are coaching feedback for the officer alone. They are not an
    axis, they write no evidence, they do not reach promotion readiness, and
    `officer_report` refuses to include them for any reader but the officer
    themselves.
    """
    interview = _load_interview(db, interview_id, user)
    if interview.user_id != user.id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Only the officer being interviewed can submit their own camera metrics",
        )

    answer = db.get(InterviewAnswer, answer_id)
    if answer is None or answer.interview_id != interview.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Answer not found")

    metrics = answer.attention
    if metrics is None:
        metrics = AttentionMetrics()
        answer.attention = metrics

    for field, value in payload.model_dump().items():
        setattr(metrics, field, value)
    metrics.quality = _attention_quality(payload.face_present_ratio, payload.frames_analysed)

    write_audit(
        db, actor=user, action="interview.attention_received",
        entity_type="interview_answer", entity_id=str(answer.id),
        request=request,
        meta={
            "quality": metrics.quality,
            "frames_analysed": payload.frames_analysed,
            # Recorded so it is demonstrable after the fact that nothing else
            # was sent.
            "payload_fields": sorted(payload.model_dump().keys()),
        },
    )
    db.commit()
    return {
        "status": "recorded",
        "quality": metrics.quality,
        "note": (
            "Camera engagement is coaching feedback for you alone. It is not "
            "scored, does not appear in your competency profile, and is not "
            "visible to your supervisor."
        ),
    }


def _attention_quality(face_present_ratio: float | None, frames: int) -> str:
    """How much of the answer the camera actually tracked.

    A gaze figure derived from a fifth of the frames should not sit next to one
    derived from nearly all of them looking equally authoritative.
    """
    if not frames or face_present_ratio is None or frames < 30:
        return "unusable"
    if face_present_ratio >= 0.7:
        return "good"
    if face_present_ratio >= 0.35:
        return "partial"
    return "unusable"
