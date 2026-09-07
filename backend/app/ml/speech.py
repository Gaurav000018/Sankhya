"""Speech analysis: audio in, measured signal out.

Runs on the **host**, not in the API container — Docker on Windows cannot reach
the RTX 4050 cleanly, and this is the ML runtime drawn outside the containers in
the architecture.

Every heavy dependency is imported lazily and every stage degrades to None rather
than raising, so the pipeline still produces a partial result on a machine with
no models pulled. `availability()` reports exactly what is installed, so a
missing component is visible rather than silently zero.

Two stages exist that look redundant and are not:

* **ffmpeg transcode.** The browser's MediaRecorder produces WebM/Opus; Whisper
  and Vosk want 16 kHz mono PCM. Skipping this yields garbage transcripts.
* **A second ASR pass with Vosk.** Whisper is trained to produce clean readable
  text and deletes "um" and "uh" outright. Counting fillers from Whisper output
  reports every officer as perfectly fluent — the single most expensive bug
  available in this pipeline. Vosk is a raw acoustic recogniser and keeps them.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
import tempfile
import wave
from dataclasses import dataclass, field
from pathlib import Path

from app.services.interview_scoring import SpeechSignal, count_fillers, count_hedges

log = logging.getLogger("sankhya.speech")

TARGET_SAMPLE_RATE = 16000
LONG_PAUSE_SECONDS = 2.0
VOSK_MODEL_ENV = "VOSK_MODEL_PATH"


@dataclass
class Transcription:
    text: str = ""
    words: list[dict] = field(default_factory=list)   # [{word, start, end}]
    language: str = "en"
    duration: float = 0.0


# --------------------------------------------------------------------------- #
# Audio
# --------------------------------------------------------------------------- #

def has_ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None


def transcode_to_wav(source: str | Path) -> Path | None:
    """WebM/Opus (or anything ffmpeg reads) to 16 kHz mono PCM."""
    if not has_ffmpeg():
        log.error("ffmpeg not found on PATH — audio cannot be decoded")
        return None

    out = Path(tempfile.mkstemp(suffix=".wav")[1])
    result = subprocess.run(
        ["ffmpeg", "-y", "-i", str(source), "-ac", "1",
         "-ar", str(TARGET_SAMPLE_RATE), "-f", "wav", str(out)],
        capture_output=True,
    )
    if result.returncode != 0:
        log.error("ffmpeg failed: %s", result.stderr.decode(errors="replace")[-400:])
        out.unlink(missing_ok=True)
        return None
    return out


def wav_duration(path: str | Path) -> float:
    try:
        with wave.open(str(path), "rb") as w:
            return w.getnframes() / float(w.getframerate())
    except Exception:
        return 0.0


# --------------------------------------------------------------------------- #
# Transcription
# --------------------------------------------------------------------------- #

_whisper_model = None
_cuda_dlls_registered = False


def _register_cuda_dlls() -> None:
    """Put the pip-installed NVIDIA DLLs on the Windows search path.

    `nvidia-cublas-cu12` and `nvidia-cudnn-cu12` drop their DLLs under
    site-packages/nvidia/*/bin, which Windows does not search. Without this,
    CTranslate2 loads, reports CUDA available, and then fails at the first
    inference with "Library cublas64_12.dll is not found" — after the model has
    already spent thirty seconds loading. Not a hypothetical: it is what
    happened on the first real recording.
    """
    global _cuda_dlls_registered
    if _cuda_dlls_registered or os.name != "nt":
        return
    _cuda_dlls_registered = True

    for base in {*sys.path, *(getattr(__import__("site"), "getsitepackages", list)() or [])}:
        nvidia = Path(base) / "nvidia"
        if not nvidia.is_dir():
            continue
        for bin_dir in sorted(nvidia.glob("*/bin")):
            try:
                os.add_dll_directory(str(bin_dir))
                log.debug("Registered CUDA DLL directory %s", bin_dir)
            except (OSError, AttributeError):
                pass


def _load_whisper(model_size: str = "small"):
    """Loaded once and reused. Held at module level so the ~20-40s first load
    happens at worker startup rather than mid-demo."""
    global _whisper_model
    if _whisper_model is not None:
        return _whisper_model
    # Before the import, not after: CTranslate2 resolves its CUDA libraries when
    # the extension module loads, so registering the directories afterwards has
    # no effect and the GPU path fails at the first inference.
    _register_cuda_dlls()
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        return None

    try:
        _whisper_model = WhisperModel(model_size, device="cuda", compute_type="float16")
        log.info("Whisper %s loaded on CUDA", model_size)
    except Exception as exc:
        log.warning("CUDA unavailable for Whisper (%s); falling back to CPU", exc)
        try:
            _whisper_model = WhisperModel(model_size, device="cpu", compute_type="int8")
        except Exception:
            log.exception("Could not load Whisper at all")
            return None
    return _whisper_model


def unload_whisper() -> None:
    """Free VRAM before invoking the judge.

    6 GB does not comfortably hold Whisper and a 7B Q4 model at once, and the
    pipeline is sequential anyway — transcription finishes before judging starts.
    """
    global _whisper_model
    _whisper_model = None


def _fall_back_to_cpu(model_size: str = "small"):
    """Reload on CPU after a CUDA failure.

    Loading succeeds on CUDA and inference fails separately, so the fallback
    cannot live only in the loader.
    """
    global _whisper_model
    try:
        from faster_whisper import WhisperModel

        _whisper_model = WhisperModel(model_size, device="cpu", compute_type="int8")
        log.warning("CUDA inference failed; Whisper reloaded on CPU")
        return _whisper_model
    except Exception:
        log.exception("Could not fall back to CPU")
        return None


def transcribe(
    wav_path: str | Path, language: str | None = None, *, allow_retry: bool = True
) -> Transcription | None:
    model = _load_whisper()
    if model is None:
        return None
    try:
        segments, info = model.transcribe(
            str(wav_path), language=language, word_timestamps=True,
            vad_filter=False,   # our own VAD measures the pauses; do not remove them
        )
        words, parts = [], []
        for seg in segments:
            parts.append(seg.text)
            for w in (seg.words or []):
                words.append({"word": w.word.strip(), "start": w.start, "end": w.end})
        return Transcription(
            text="".join(parts).strip(),
            words=words,
            language=getattr(info, "language", language or "en"),
            duration=getattr(info, "duration", 0.0) or wav_duration(wav_path),
        )
    except RuntimeError as exc:
        # A missing CUDA library surfaces here, not at load time.
        cuda_related = any(
            token in str(exc).lower() for token in ("cuda", "cublas", "cudnn")
        )
        # `allow_retry` stops this recursing if the CPU model somehow raises the
        # same class of error.
        if cuda_related and allow_retry and _fall_back_to_cpu() is not None:
            return transcribe(wav_path, language=language, allow_retry=False)
        log.exception("Transcription failed")
        return None
    except Exception:
        log.exception("Transcription failed")
        return None


# --------------------------------------------------------------------------- #
# Disfluency (second pass)
# --------------------------------------------------------------------------- #

_vosk_model = None


def _vosk_model_path() -> str:
    """Where the Vosk model lives.

    The environment wins so a worker launcher can point at a different model,
    but .env is the documented place and has to work on its own. Reading only
    os.environ meant a correctly-configured .env silently lost filler detection,
    and the symptom — fluency reported as unscoreable — looks like a policy
    decision rather than a missing model.
    """
    import os

    from app.config import settings

    return os.environ.get(VOSK_MODEL_ENV) or settings.vosk_model_path or ""


def _load_vosk():
    global _vosk_model
    if _vosk_model is not None:
        return _vosk_model

    path = _vosk_model_path()
    if not path or not Path(path).exists():
        return None
    try:
        from vosk import Model
        _vosk_model = Model(path)
        return _vosk_model
    except ImportError:
        return None
    except Exception:
        log.exception("Could not load the Vosk model")
        return None


def extract_fillers(wav_path: str | Path) -> tuple[int, list[dict]] | None:
    """Count disfluency tokens from a raw acoustic pass."""
    model = _load_vosk()
    if model is None:
        return None
    try:
        import json as _json

        from vosk import KaldiRecognizer

        with wave.open(str(wav_path), "rb") as wf:
            rec = KaldiRecognizer(model, wf.getframerate())
            rec.SetWords(True)
            tokens: list[dict] = []
            while True:
                data = wf.readframes(4000)
                if not data:
                    break
                if rec.AcceptWaveform(data):
                    tokens += _json.loads(rec.Result()).get("result", [])
            tokens += _json.loads(rec.FinalResult()).get("result", [])

        found = [
            {"word": t["word"], "t": round(t.get("start", 0.0), 2)}
            for t in tokens
            if count_fillers([t["word"]])
        ]
        return len(found), found
    except Exception:
        log.exception("Filler extraction failed")
        return None


# --------------------------------------------------------------------------- #
# Pauses and prosody
# --------------------------------------------------------------------------- #

def _read_wav_samples(path: str | Path):
    """16-bit mono PCM to a normalised float32 array.

    Deliberately not `silero_vad.read_audio`: that pulls in torchaudio and, on
    recent versions, torchcodec — neither of which we install, and both of which
    fail at runtime rather than at import. The file is already 16 kHz mono PCM
    because ffmpeg made it that way, so the stdlib `wave` module is enough.
    """
    import numpy as np

    with wave.open(str(path), "rb") as wf:
        if wf.getsampwidth() != 2:
            raise ValueError(f"expected 16-bit PCM, got {wf.getsampwidth() * 8}-bit")
        frames = wf.readframes(wf.getnframes())
        samples = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
        if wf.getnchannels() > 1:
            samples = samples.reshape(-1, wf.getnchannels()).mean(axis=1)
    return samples


def analyse_pauses(wav_path: str | Path) -> dict | None:
    """Silence structure via Silero VAD."""
    try:
        from silero_vad import get_speech_timestamps, load_silero_vad
    except ImportError:
        return None
    try:
        model = load_silero_vad(onnx=True)
        samples = _read_wav_samples(wav_path)
        try:
            import torch

            audio = torch.from_numpy(samples)
        except ImportError:
            audio = samples
        stamps = get_speech_timestamps(
            audio, model, sampling_rate=TARGET_SAMPLE_RATE, return_seconds=True
        )
        if not stamps:
            return {"pause_count": 0, "long_pause_count": 0,
                    "mean_pause_seconds": 0.0, "latency_to_first_word": None,
                    "speech_seconds": 0.0}

        spans = [
            {"start": round(stamps[i]["end"], 2), "end": round(stamps[i + 1]["start"], 2)}
            for i in range(len(stamps) - 1)
            if stamps[i + 1]["start"] - stamps[i]["end"] > 0.25
        ]
        gaps = [s["end"] - s["start"] for s in spans]
        speech = sum(s["end"] - s["start"] for s in stamps)
        return {
            "pause_count": len(gaps),
            "long_pause_count": sum(1 for g in gaps if g >= LONG_PAUSE_SECONDS),
            "mean_pause_seconds": round(sum(gaps) / len(gaps), 2) if gaps else 0.0,
            "latency_to_first_word": round(stamps[0]["start"], 2),
            "speech_seconds": round(speech, 2),
            "pause_spans": spans,
        }
    except Exception:
        log.exception("Pause analysis failed")
        return None


def analyse_prosody(wav_path: str | Path) -> dict | None:
    """Pitch and voice-quality measures via Praat.

    Reported to the officer as delivery feedback and stored as measurement.
    Deliberately NOT used to compute the Confidence axis — see
    `services/interview_scoring`.
    """
    try:
        import parselmouth
    except ImportError:
        return None
    try:
        sound = parselmouth.Sound(str(wav_path))
        pitch = sound.to_pitch()
        values = [v for v in pitch.selected_array["frequency"] if v > 0]
        intensity = sound.to_intensity()

        result = {
            "pitch_mean": round(sum(values) / len(values), 1) if values else None,
            "pitch_sd": None,
            "intensity_mean": round(float(intensity.values.mean()), 1),
            "jitter": None,
        }
        if len(values) > 1:
            mean = sum(values) / len(values)
            var = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
            result["pitch_sd"] = round(var ** 0.5, 1)
        try:
            point_process = parselmouth.praat.call(
                sound, "To PointProcess (periodic, cc)", 75, 500
            )
            result["jitter"] = round(
                parselmouth.praat.call(
                    point_process, "Get jitter (local)", 0, 0, 0.0001, 0.02, 1.3
                ), 5,
            )
        except Exception:
            pass
        return result
    except Exception:
        log.exception("Prosody analysis failed")
        return None


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #

def _discard(path: Path) -> None:
    """Delete the decoded audio, and never let that failure lose the analysis.

    On Windows a reader (Vosk, or Praat) can still hold the handle when we get
    here, and `unlink` raises PermissionError. Letting that propagate would throw
    away a completed analysis and — in the worker, whose handler catches
    everything — mark a perfectly good answer as FAILED.

    A leftover file in the system temp directory is the lesser problem: the
    officer's actual recording is deleted separately by the worker, so the
    retention promise does not depend on this line succeeding.
    """
    import gc

    for attempt in range(2):
        try:
            path.unlink(missing_ok=True)
            return
        except OSError:
            # Drop any lingering reference the audio libraries left behind.
            gc.collect()
    log.warning("Could not delete the decoded audio at %s; it will be cleaned "
                "up with the system temp directory", path)


@dataclass
class AnswerAnalysis:
    transcript: str = ""
    words: list[dict] = field(default_factory=list)
    signal: SpeechSignal = field(default_factory=SpeechSignal)
    fillers: list[dict] = field(default_factory=list)
    prosody: dict = field(default_factory=dict)
    pauses: dict = field(default_factory=dict)
    duration: float = 0.0
    warnings: list[str] = field(default_factory=list)


def analyse_answer(audio_path: str | Path, language: str | None = None) -> AnswerAnalysis:
    """Full pipeline for one recorded answer.

    Missing components produce warnings and partial results rather than an
    exception — a laptop without Vosk should still transcribe and judge.
    """
    analysis = AnswerAnalysis()
    wav = transcode_to_wav(audio_path)
    if wav is None:
        analysis.warnings.append("Audio could not be decoded (is ffmpeg installed?)")
        return analysis

    try:
        analysis.duration = wav_duration(wav)

        transcription = transcribe(wav, language=language)
        if transcription is None:
            analysis.warnings.append("Transcription unavailable (faster-whisper not installed)")
        else:
            analysis.transcript = transcription.text
            analysis.words = transcription.words
            analysis.duration = transcription.duration or analysis.duration

        pauses = analyse_pauses(wav)
        if pauses is None:
            analysis.warnings.append("Pause analysis unavailable (silero-vad not installed)")
        else:
            analysis.pauses = pauses

        prosody = analyse_prosody(wav)
        if prosody is None:
            analysis.warnings.append("Prosody unavailable (parselmouth not installed)")
        else:
            analysis.prosody = prosody

        word_count = len(analysis.transcript.split())

        fillers = extract_fillers(wav)
        if fillers is None:
            analysis.warnings.append(
                "Filler detection unavailable — Vosk model not configured. "
                "Whisper strips disfluencies, so fluency cannot be scored from it."
            )
            filler_count, filler_rate = 0, None
        else:
            filler_count, analysis.fillers = fillers
            filler_rate = round(100.0 * filler_count / word_count, 2) if word_count else None

        # Words per minute over speaking time where we have it, wall clock otherwise.
        speaking = analysis.pauses.get("speech_seconds") or analysis.duration
        wpm = round(60.0 * word_count / speaking, 1) if speaking and word_count else None

        analysis.signal = SpeechSignal(
            words=word_count,
            wpm=wpm,
            filler_count=filler_count,
            filler_rate=filler_rate,
            long_pause_count=analysis.pauses.get("long_pause_count", 0),
            latency_to_first_word=analysis.pauses.get("latency_to_first_word"),
            hedge_count=count_hedges(analysis.transcript),
        )
        return analysis
    finally:
        _discard(wav)


def availability() -> dict[str, bool]:
    """What this machine can actually do. Surfaced at worker startup so a
    missing component is visible rather than silently producing zeros."""
    import importlib.util

    def installed(name: str) -> bool:
        return importlib.util.find_spec(name) is not None

    vosk_path = _vosk_model_path()
    return {
        "ffmpeg": has_ffmpeg(),
        "faster_whisper": installed("faster_whisper"),
        "vosk": installed("vosk") and bool(vosk_path) and Path(vosk_path or "").exists(),
        "silero_vad": installed("silero_vad"),
        "parselmouth": installed("parselmouth"),
    }
