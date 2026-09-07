"""Learning material, question generation, and the SME review queue.

Only an SME or admin can upload material or move a question to APPROVED, and
only APPROVED questions are served to officers. There is no endpoint that
publishes a draft.
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.core import queue
from app.core.deps import get_current_user, require_roles, write_audit
from app.db import get_db
from app.ml.ingest import (
    SUPPORTED_SUFFIXES,
    VIDEO_SUFFIXES,
    UnsupportedDocument,
    ingest,
)
from app.models import Competency, User, UserRole
from app.models_content import (
    GeneratedQuestion,
    Material,
    MaterialChunk,
    MaterialStatus,
    QuestionStatus,
)
from app.schemas import (
    GenerateRequest,
    MaterialOut,
    QuestionEditIn,
    QuestionOut,
    ReviewDecisionIn,
)
from app.services import quizgen

log = logging.getLogger("sankhya.api.content")
router = APIRouter(tags=["content"])

MATERIAL_DIR = Path(settings.audio_dir).parent / "materials"


def _question_out(q: GeneratedQuestion) -> QuestionOut:
    return QuestionOut(
        id=q.id,
        material_id=q.material_id,
        competency_id=q.competency_id,
        kind=q.kind.value,
        stem=q.stem,
        options=q.options,
        # Withheld from learners by the caller; SMEs and admins see everything.
        correct_index=q.correct_index,
        explanation=q.explanation,
        distractor_rationale=q.distractor_rationale or [],
        bloom_level=q.bloom_level,
        citation={
            "chunk_id": q.citation_chunk_id,
            "page": q.citation_page,
            "quote": q.citation_quote,
        },
        status=q.status.value,
        quality_flags=q.quality_flags or [],
        review_note=q.review_note,
        generated_by_model=q.generated_by_model,
        times_attempted=q.times_attempted,
        difficulty_p=q.difficulty_p,
        discrimination=q.discrimination,
        created_at=q.created_at,
    )


# --------------------------------------------------------------------------- #
# Material
# --------------------------------------------------------------------------- #

@router.post("/materials", response_model=MaterialOut, status_code=status.HTTP_201_CREATED)
async def upload_material(
    request: Request,
    file: UploadFile = File(...),
    title: str = Form(...),
    # Required: questions generated from a material inherit its competency,
    # and a question with no competency can never become evidence.
    competency_id: int = Form(...),
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(UserRole.SME, UserRole.ADMIN)),
):
    """Upload a document and split it into citable passages.

    Extraction happens here because it is cheap. Question generation needs the
    model and is queued for the host worker.
    """
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            f"Cannot read {suffix or 'that file type'}. Supported: "
            f"{', '.join(sorted(SUPPORTED_SUFFIXES))}",
        )

    if suffix in VIDEO_SUFFIXES:
        # Transcription needs Whisper and a GPU, which live on the worker host,
        # not in this container. Better to say that than to fail obscurely.
        from app.ml.speech import availability

        if not availability().get("faster_whisper"):
            raise HTTPException(
                status.HTTP_501_NOT_IMPLEMENTED,
                "Recordings are transcribed by the speech worker, which is not "
                "available to this service. Upload a document, or run ingestion "
                "on the host with the worker installed.",
            )

    payload = await file.read()
    if not payload:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "The file was empty")

    if db.get(Competency, competency_id) is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "That competency does not exist. Questions generated from this "
            "material would not be attributable to anything.",
        )

    material = Material(
        title=title.strip(),
        filename=file.filename or f"upload{suffix}",
        content_type=file.content_type,
        competency_id=competency_id,
        uploaded_by_id=actor.id,
        status=MaterialStatus.EXTRACTING,
    )
    db.add(material)
    db.flush()

    MATERIAL_DIR.mkdir(parents=True, exist_ok=True)
    stored = MATERIAL_DIR / f"material_{material.id}{suffix}"
    stored.write_bytes(payload)

    try:
        chunks, page_count, char_count = ingest(stored)
    except UnsupportedDocument as exc:
        material.status = MaterialStatus.FAILED
        material.failure_reason = str(exc)
        db.commit()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))
    except Exception as exc:
        material.status = MaterialStatus.FAILED
        material.failure_reason = str(exc)[:250]
        db.commit()
        log.exception("Extraction failed for material %s", material.id)
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "The document could not be read. It may be scanned images rather "
            "than text, which needs OCR.",
        )

    if not chunks:
        material.status = MaterialStatus.FAILED
        material.failure_reason = "No extractable text"
        db.commit()
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "No text could be extracted. If this is a scanned document it needs "
            "OCR before it can be used.",
        )

    for chunk in chunks:
        db.add(MaterialChunk(
            material_id=material.id, ordinal=chunk.ordinal,
            page=chunk.page, text=chunk.text,
        ))

    material.status = MaterialStatus.READY
    material.page_count = page_count or None
    material.char_count = char_count

    write_audit(
        db, action="material.uploaded", actor_user_id=actor.id,
        entity_type="material", entity_id=str(material.id),
        meta={"chunks": len(chunks), "chars": char_count, "format": suffix},
        request=request,
    )
    db.commit()
    db.refresh(material)

    return MaterialOut(
        id=material.id, title=material.title, filename=material.filename,
        status=material.status.value, competency_id=material.competency_id,
        page_count=material.page_count, char_count=material.char_count,
        chunk_count=len(chunks), created_at=material.created_at,
        questions_generated=0,
    )


@router.get("/materials", response_model=list[MaterialOut])
def list_materials(
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(UserRole.SME, UserRole.ADMIN)),
):
    materials = db.scalars(select(Material).order_by(Material.created_at.desc())).all()
    counts = dict(
        db.execute(
            select(MaterialChunk.material_id, func.count(MaterialChunk.id))
            .group_by(MaterialChunk.material_id)
        ).all()
    )
    questions = dict(
        db.execute(
            select(GeneratedQuestion.material_id, func.count(GeneratedQuestion.id))
            .group_by(GeneratedQuestion.material_id)
        ).all()
    )
    return [
        MaterialOut(
            id=m.id, title=m.title, filename=m.filename, status=m.status.value,
            competency_id=m.competency_id, page_count=m.page_count,
            char_count=m.char_count, chunk_count=counts.get(m.id, 0),
            questions_generated=questions.get(m.id, 0), created_at=m.created_at,
        )
        for m in materials
    ]


@router.post("/materials/{material_id}/generate", status_code=status.HTTP_202_ACCEPTED)
def generate_questions(
    material_id: int,
    payload: GenerateRequest,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(UserRole.SME, UserRole.ADMIN)),
):
    """Queue question generation.

    Everything produced lands as DRAFT and waits for review. Questions whose
    citation cannot be verified against the source passage are discarded by the
    worker and never enter the queue.
    """
    material = db.get(Material, material_id)
    if material is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Material not found")
    if material.status != MaterialStatus.READY:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"This material is {material.status.value}, not ready for generation",
        )

    queue.enqueue_generation(material.id, count=payload.per_chunk, bloom=payload.bloom_level)
    write_audit(
        db, action="quizgen.requested", actor_user_id=actor.id,
        entity_type="material", entity_id=str(material.id),
        meta={"per_chunk": payload.per_chunk, "bloom": payload.bloom_level},
        request=request,
    )
    db.commit()

    return {
        "material_id": material.id,
        "status": "queued",
        "worker_online": queue.worker_is_alive(),
        "queue_depth": queue.generation_depth(),
        "message": (
            "Generating questions. Everything produced needs SME approval before "
            "any officer sees it."
            if queue.worker_is_alive()
            else "Queued, but no worker is running. Start it with "
                 "`python -m app.worker` on the host."
        ),
    }


# --------------------------------------------------------------------------- #
# SME review queue
# --------------------------------------------------------------------------- #

@router.get("/questions/review-queue", response_model=list[QuestionOut])
def get_review_queue(
    competency_id: int | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(UserRole.SME, UserRole.ADMIN)),
):
    """Drafts awaiting review, automatically flagged items first."""
    return [
        _question_out(q)
        for q in quizgen.review_queue(db, competency_id=competency_id, limit=limit)
    ]


@router.get("/questions/approved", response_model=list[QuestionOut])
def get_approved_questions(
    competency_id: int | None = None,
    limit: int = 20,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """What an officer may be shown. Approved only — there is no way to ask this
    endpoint for drafts."""
    questions = quizgen.publishable_questions(
        db, competency_id=competency_id, limit=limit
    )
    out = [_question_out(q) for q in questions]
    if user.role == UserRole.LEARNER:
        # Do not hand the answer key to the person being assessed.
        for item in out:
            item.correct_index = None
            item.explanation = None
            item.distractor_rationale = []
    return out


@router.get("/questions/{question_id}", response_model=QuestionOut)
def get_question(
    question_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(UserRole.SME, UserRole.ADMIN)),
):
    question = db.get(GeneratedQuestion, question_id)
    if question is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Question not found")
    return _question_out(question)


@router.get("/questions/{question_id}/source")
def get_question_source(
    question_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(UserRole.SME, UserRole.ADMIN)),
):
    """The passage the question was drawn from, so a reviewer can check the
    citation without opening the original document."""
    question = db.get(GeneratedQuestion, question_id)
    if question is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Question not found")

    chunk = question.citation_chunk
    if chunk is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "The cited passage is no longer available"
        )

    check = quizgen.verify_citation(chunk.text, question.citation_quote or "")
    return {
        "question_id": question.id,
        "material_id": question.material_id,
        "material_title": question.material.title if question.material else None,
        "page": question.citation_page,
        "quote": question.citation_quote,
        "passage": chunk.text,
        # Re-checked live rather than trusted from generation time.
        "citation_verified": bool(check),
        "verification_detail": check.reason,
    }


@router.post("/questions/{question_id}/approve", response_model=QuestionOut)
def approve_question(
    question_id: int,
    payload: ReviewDecisionIn,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(UserRole.SME, UserRole.ADMIN)),
):
    """Clear an item for use. The only route to APPROVED."""
    question = db.get(GeneratedQuestion, question_id)
    if question is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Question not found")

    chunk = question.citation_chunk
    check = quizgen.verify_citation(chunk.text if chunk else "", question.citation_quote or "")
    if not check:
        # Belt and braces: generation already filtered these out, but an item
        # cannot become approved with a citation that does not hold.
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"This question cannot be approved — its citation does not verify: {check.reason}",
        )

    quizgen.approve(db, question, actor, payload.note)
    db.commit()
    db.refresh(question)
    return _question_out(question)


@router.post("/questions/{question_id}/reject", response_model=QuestionOut)
def reject_question(
    question_id: int,
    payload: ReviewDecisionIn,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(UserRole.SME, UserRole.ADMIN)),
):
    question = db.get(GeneratedQuestion, question_id)
    if question is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Question not found")
    quizgen.reject(db, question, actor, payload.note)
    db.commit()
    db.refresh(question)
    return _question_out(question)


@router.patch("/questions/{question_id}", response_model=QuestionOut)
def edit_question(
    question_id: int,
    payload: QuestionEditIn,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(UserRole.SME, UserRole.ADMIN)),
):
    """Fix an item rather than discard it.

    The citation is not editable — the quote and the passage it points at stay
    as generated, so an edit cannot quietly detach a question from its source.
    """
    question = db.get(GeneratedQuestion, question_id)
    if question is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Question not found")

    try:
        quizgen.apply_edit(db, question, actor, payload.model_dump(exclude_none=True))
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))

    db.commit()
    db.refresh(question)
    return _question_out(question)


@router.get("/questions", response_model=dict)
def question_stats(
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(UserRole.SME, UserRole.ADMIN)),
):
    counts = dict(
        db.execute(
            select(GeneratedQuestion.status, func.count(GeneratedQuestion.id))
            .group_by(GeneratedQuestion.status)
        ).all()
    )
    return {
        "by_status": {s.value: counts.get(s, 0) for s in QuestionStatus},
        "awaiting_review": counts.get(QuestionStatus.DRAFT, 0),
    }
