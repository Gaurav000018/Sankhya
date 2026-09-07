"""Exercise the whole audio path without a microphone.

    python scripts/check_speech_pipeline.py

Synthesises a spoken answer with the Windows speech engine, writes it as WebM
(the format a browser actually produces), and runs it through the real pipeline:
ffmpeg transcode, Whisper transcription, the Vosk disfluency pass, Silero pause
detection, Praat prosody, and the rubric judge.

Why this exists: the audio path is the one thing that cannot be proved by unit
tests, and "never demo it live for the first time on stage" is on this project's
own risk list. A synthetic voice is not a human one — it has no natural
hesitation, so the script *scripts* the fillers into the text and checks they are
counted. What it proves is that every stage runs, hands its output to the next,
and produces a scored answer. What it cannot prove is how the numbers behave on
real human speech.

Anything missing degrades to a warning rather than a failure, so this reports an
honest picture of the machine it runs on.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.ml.judge import get_judge  # noqa: E402
from app.ml.speech import analyse_answer, availability  # noqa: E402

# Deliberately full of hesitation. A synthetic voice will not hesitate on its
# own, so the disfluencies are written in — that is what the Vosk pass is meant
# to count, and a test that only spoke fluently would never exercise it.
SPOKEN_ANSWER = (
    "So, um, for the spatial part I think maybe you would use the satellite "
    "imagery, uh, to see where the settlements are. Basically the frame might "
    "be, um, out of date and you would want to check it. I am not completely "
    "sure about the projection side of it, uh, possibly that matters for the "
    "coordinates as well."
)

QUESTION = "How would you use geo-spatial data to improve a sampling frame for a rural survey?"
EXPECTED_POINTS = [
    "Satellite or settlement layers to update village boundaries",
    "Detecting new settlements missing from the census frame",
    "Coordinate accuracy and projection consistency",
    "Field verification of what the imagery suggests",
]

PS_SYNTHESISE = """
Add-Type -AssemblyName System.Speech
$speaker = New-Object System.Speech.Synthesis.SpeechSynthesizer
$speaker.Rate = -1
$speaker.SetOutputToWaveFile("{wav}")
$speaker.Speak(@'
{text}
'@)
$speaker.Dispose()
"""


def synthesise(text: str, wav_path: Path) -> bool:
    """Speak the text to a WAV using the Windows speech engine."""
    script = PS_SYNTHESISE.format(wav=str(wav_path).replace("\\", "\\\\"), text=text)
    result = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"  Speech synthesis failed: {result.stderr.strip()[:200]}")
        return False
    return wav_path.exists() and wav_path.stat().st_size > 1000


def to_webm(wav_path: Path, webm_path: Path) -> bool:
    """Re-encode as WebM/Opus, which is what MediaRecorder hands the API.

    Testing on the WAV directly would skip the transcode stage, which is exactly
    the stage that broke first when real audio arrived.
    """
    result = subprocess.run(
        ["ffmpeg", "-y", "-i", str(wav_path), "-c:a", "libopus", "-b:a", "24k",
         str(webm_path)],
        capture_output=True,
    )
    return result.returncode == 0 and webm_path.exists()


def main() -> int:
    print("\nSpeech pipeline, end to end\n" + "-" * 58)

    components = availability()
    for name, ok in components.items():
        print(f"  {'OK  ' if ok else 'MISS'}  {name}")
    if not components["ffmpeg"]:
        print("\n  ffmpeg is missing; nothing downstream can run.")
        return 1

    tmp = Path(tempfile.mkdtemp(prefix="sankhya-speech-"))
    wav, webm = tmp / "spoken.wav", tmp / "spoken.webm"

    print("\n  Synthesising a spoken answer...")
    if not synthesise(SPOKEN_ANSWER, wav):
        print("  Could not synthesise speech on this machine.")
        return 1
    print(f"  wrote {wav.stat().st_size:,} bytes of WAV")

    if not to_webm(wav, webm):
        print("  Could not encode WebM.")
        return 1
    print(f"  encoded {webm.stat().st_size:,} bytes of WebM/Opus "
          f"(the format a browser produces)")

    print("\n  Running the pipeline...")
    analysis = analyse_answer(webm, language="en")

    for warning in analysis.warnings:
        print(f"  WARN  {warning}")

    signal = analysis.signal
    print(f"\n  duration          {analysis.duration:.1f}s")
    print(f"  transcript        {len(analysis.transcript)} chars, {signal.words} words")
    print(f"  words per minute  {signal.wpm}")
    print(f"  fillers           {signal.filler_count}"
          f"{f' ({signal.filler_rate}/100w)' if signal.filler_rate is not None else ''}")
    print(f"  long pauses       {signal.long_pause_count}")
    print(f"  latency           {signal.latency_to_first_word}")
    print(f"  hedges            {signal.hedge_count}")
    print(f"  pitch mean / sd   {analysis.prosody.get('pitch_mean')} / "
          f"{analysis.prosody.get('pitch_sd')}")

    if analysis.transcript:
        print(f'\n  heard: "{analysis.transcript[:150]}"')

    print("\n  Judging...")
    judge = get_judge()
    verdict = judge.score(QUESTION, EXPECTED_POINTS, analysis.transcript)
    print(f"  judge             {verdict.model_name}")
    print(f"  knowledge         {verdict.knowledge} (confidence {verdict.knowledge_confidence})")
    print(f"  structure         {verdict.structure}")
    print(f"  covered           {len(verdict.covered_points)} of {len(EXPECTED_POINTS)} points")
    if verdict.degraded:
        print(f"  DEGRADED          {verdict.reasons.get('error')}")

    print("\n" + "-" * 58)
    failures = []
    if not analysis.transcript.strip():
        failures.append("no transcript — transcription did not run")
    if signal.words == 0:
        failures.append("no words counted")
    if components["vosk"] and signal.filler_rate is None:
        failures.append("Vosk is configured but produced no filler measurement")
    if components["silero_vad"] and signal.latency_to_first_word is None:
        failures.append("Silero is installed but produced no pause measurement")
    if components["parselmouth"] and analysis.prosody.get("pitch_mean") is None:
        failures.append("parselmouth is installed but produced no pitch measurement")

    for failure in failures:
        print(f"  FAIL  {failure}")

    if failures:
        print(f"\n  {len(failures)} stage(s) did not produce output.")
        return 1

    print("  PASS  every installed stage produced output, end to end")
    if not components["vosk"]:
        print("  NOTE  Vosk is not configured, so fluency would be reported as")
        print("        unscoreable rather than as a misleading zero.")
    if verdict.model_name == "stub":
        print("  NOTE  No judge model pulled; the stub scorer was used.")
    print("\n  A synthetic voice is not a human one. This proves the stages")
    print("  connect, not how the numbers behave on real speech.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
