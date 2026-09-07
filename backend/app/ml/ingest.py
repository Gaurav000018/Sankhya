"""Turn an uploaded document into citable passages.

Text extraction is cheap and runs in the API container; generation and
embeddings need the model and run on the host worker.

Chunks are the unit a citation points at, so they carry a page number wherever
the format provides one. A citation an officer cannot follow back to a page is
not much of a citation.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger("sankhya.ingest")

TARGET_CHUNK_CHARS = 1200
CHUNK_OVERLAP_CHARS = 150
MIN_CHUNK_CHARS = 120

# A recorded lecture is learning material like any other. The audio pipeline
# already exists for interviews, so this is a transcription away rather than a
# new capability.
VIDEO_SUFFIXES = {".mp4", ".mkv", ".webm", ".mov", ".m4v", ".mp3", ".wav", ".m4a"}

SUPPORTED_SUFFIXES = {".pdf", ".docx", ".pptx", ".txt", ".md"} | VIDEO_SUFFIXES


@dataclass
class Page:
    number: int | None
    text: str


@dataclass
class Chunk:
    ordinal: int
    page: int | None
    text: str


class UnsupportedDocument(Exception):
    pass


def _clean(text: str) -> str:
    text = text.replace(" ", " ").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _extract_pdf(path: Path) -> list[Page]:
    try:
        from pypdf import PdfReader
    except ImportError:
        raise UnsupportedDocument("PDF support needs pypdf installed")
    reader = PdfReader(str(path))
    return [
        Page(number=i + 1, text=_clean(page.extract_text() or ""))
        for i, page in enumerate(reader.pages)
    ]


def _extract_docx(path: Path) -> list[Page]:
    try:
        import docx
    except ImportError:
        raise UnsupportedDocument("DOCX support needs python-docx installed")
    document = docx.Document(str(path))
    parts = [p.text for p in document.paragraphs if p.text.strip()]
    for table in document.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells if c.text.strip()]
            if cells:
                parts.append(" | ".join(cells))
    # Word has no page concept we can read without rendering, so page stays None
    # rather than being guessed. A wrong page number is worse than none.
    return [Page(number=None, text=_clean("\n".join(parts)))]


def _extract_pptx(path: Path) -> list[Page]:
    try:
        from pptx import Presentation
    except ImportError:
        raise UnsupportedDocument("PPTX support needs python-pptx installed")
    presentation = Presentation(str(path))
    pages = []
    for index, slide in enumerate(presentation.slides, start=1):
        parts = [
            shape.text for shape in slide.shapes
            if getattr(shape, "has_text_frame", False) and shape.text.strip()
        ]
        if slide.has_notes_slide and slide.notes_slide.notes_text_frame:
            notes = slide.notes_slide.notes_text_frame.text.strip()
            if notes:
                parts.append(f"[Speaker notes] {notes}")
        pages.append(Page(number=index, text=_clean("\n".join(parts))))
    return pages


def _extract_media(path: Path) -> list[Page]:
    """Transcribe a recording and treat the transcript as the document.

    Deliberately reuses the interview pipeline: ffmpeg to 16 kHz mono, then
    Whisper. A second transcription stack for training videos would be two
    things to keep working instead of one.

    Pages are minutes of runtime. A citation has to point somewhere a reviewer
    can go back to, and "minute 7" is the video equivalent of a page number.
    """
    from app.ml.speech import transcode_to_wav, transcribe

    wav = transcode_to_wav(path)
    if wav is None:
        raise UnsupportedDocument(
            "The audio track could not be decoded. Check that ffmpeg is installed."
        )

    try:
        transcription = transcribe(wav)
    finally:
        wav.unlink(missing_ok=True)

    if transcription is None:
        raise UnsupportedDocument(
            "Transcription is unavailable on this machine, so a recording cannot "
            "be turned into questions. Install faster-whisper on the worker host."
        )
    if not transcription.text.strip():
        raise UnsupportedDocument("No speech was found in that recording.")

    # Group words into minute-long pages so citations carry a timestamp.
    if not transcription.words:
        return [Page(number=None, text=_clean(transcription.text))]

    minutes: dict[int, list[str]] = {}
    for word in transcription.words:
        minute = int((word.get("start") or 0) // 60) + 1
        minutes.setdefault(minute, []).append(str(word.get("word", "")))

    return [
        Page(number=minute, text=_clean(" ".join(words)))
        for minute, words in sorted(minutes.items())
    ]


def _extract_text(path: Path) -> list[Page]:
    return [Page(number=None, text=_clean(path.read_text(encoding="utf-8", errors="replace")))]


EXTRACTORS = {
    ".pdf": _extract_pdf,
    ".docx": _extract_docx,
    ".pptx": _extract_pptx,
    ".txt": _extract_text,
    ".md": _extract_text,
    **{suffix: _extract_media for suffix in VIDEO_SUFFIXES},
}


def extract_pages(path: str | Path) -> list[Page]:
    path = Path(path)
    extractor = EXTRACTORS.get(path.suffix.lower())
    if extractor is None:
        raise UnsupportedDocument(
            f"Cannot read {path.suffix or 'this file'}. Supported: "
            f"{', '.join(sorted(SUPPORTED_SUFFIXES))}"
        )
    return [p for p in extractor(path) if p.text.strip()]


def chunk_pages(
    pages: list[Page],
    target_chars: int = TARGET_CHUNK_CHARS,
    overlap: int = CHUNK_OVERLAP_CHARS,
) -> list[Chunk]:
    """Split into passages, preferring paragraph boundaries.

    Chunks never span pages: a citation has to name one page, and a passage
    straddling two makes that impossible.
    """
    chunks: list[Chunk] = []
    ordinal = 0

    for page in pages:
        paragraphs = [p.strip() for p in page.text.split("\n\n") if p.strip()]
        buffer = ""

        for paragraph in paragraphs:
            if buffer and len(buffer) + len(paragraph) + 2 > target_chars:
                chunks.append(Chunk(ordinal, page.number, buffer.strip()))
                ordinal += 1
                tail = buffer[-overlap:] if overlap else ""
                buffer = f"{tail}\n\n{paragraph}" if tail else paragraph
            else:
                buffer = f"{buffer}\n\n{paragraph}" if buffer else paragraph

            # A single paragraph longer than the target is split on sentences.
            while len(buffer) > target_chars * 1.6:
                cut = buffer.rfind(". ", 0, target_chars)
                cut = cut + 1 if cut > MIN_CHUNK_CHARS else target_chars
                chunks.append(Chunk(ordinal, page.number, buffer[:cut].strip()))
                ordinal += 1
                buffer = buffer[max(cut - overlap, 0):].strip()

        if len(buffer.strip()) >= MIN_CHUNK_CHARS:
            chunks.append(Chunk(ordinal, page.number, buffer.strip()))
            ordinal += 1
        elif buffer.strip() and chunks:
            # Too small to stand alone: fold it into the previous chunk rather
            # than leaving a fragment nothing can be cited from.
            chunks[-1].text = f"{chunks[-1].text}\n\n{buffer.strip()}"

    return chunks


def ingest(path: str | Path) -> tuple[list[Chunk], int, int]:
    """Returns (chunks, page_count, char_count)."""
    pages = extract_pages(path)
    chunks = chunk_pages(pages)
    numbered = [p.number for p in pages if p.number is not None]
    return chunks, (max(numbered) if numbered else 0), sum(len(p.text) for p in pages)
