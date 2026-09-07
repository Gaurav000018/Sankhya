"""Report what the speech pipeline can do on this machine.

    python -m app.ml.check

Run it on the host, not in the container. A component reported as missing
produces partial results, not an error — so this is how you find out that
fluency is silently unscoreable before a demo rather than during one.
"""

from __future__ import annotations

from app.ml.judge import OllamaJudge
from app.ml.speech import availability

NOTES = {
    "ffmpeg": "Required. Browser audio is WebM/Opus; Whisper and Vosk need 16kHz mono PCM.",
    "faster_whisper": "Transcript. Without it there is nothing for the judge to read.",
    "vosk": "Filler counting. Whisper deletes 'um'/'uh', so fluency needs this second pass.",
    "silero_vad": "Pauses and response latency.",
    "parselmouth": "Pitch and voice quality (reported, not scored).",
}


def main() -> int:
    print("\nSANKHYA speech pipeline\n" + "-" * 58)

    components = availability()
    for name, ok in components.items():
        print(f"  {'OK  ' if ok else 'MISS'}  {name:<16} {NOTES.get(name, '')}")

    judge = OllamaJudge()
    judge_ok = judge.is_available()
    print(f"  {'OK  ' if judge_ok else 'MISS'}  {'judge':<16} "
          f"{judge.model} at {judge.base_url}"
          f"{'' if judge_ok else '  -> falling back to the stub scorer'}")

    print("-" * 58)
    if not components["ffmpeg"]:
        print("  ffmpeg is missing. Nothing else can run without it.")
    if not components["vosk"]:
        print("  Set VOSK_MODEL_PATH to an unpacked Vosk model directory to")
        print("  enable filler detection. Until then fluency cannot be scored,")
        print("  and the report will say so rather than showing a zero.")
    if all(components.values()) and judge_ok:
        print("  Everything is available. The pipeline runs fully local.")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
