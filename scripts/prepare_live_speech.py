"""Package the Vosk model so the browser can run it.

    python scripts/prepare_live_speech.py

Live filler detection runs a recogniser in the officer's browser, which needs
the model as a single .tar.gz it can fetch. This builds that from the model the
worker already uses, so both ends of the system hear with the same ears — and
so the repository does not carry forty megabytes of the same model twice.

The Indian English model is deliberate rather than incidental: the officers
being assessed speak Indian English, and a US model mistakes ordinary Indian
pronunciation for hesitation, which is exactly the error this platform must not
make.

If this has not been run, live analysis is simply off. The interview records,
transcribes and scores exactly as it does now — nothing degrades except the
live display.
"""

from __future__ import annotations

import os
import sys
import tarfile
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "models" / "vosk-model-small-en-in-0.4"
TARGET = ROOT / "frontend" / "public" / "vosk" / "model.tar.gz"


def main() -> int:
    source = Path(os.environ.get("VOSK_MODEL_PATH") or DEFAULT_SOURCE)

    print("\nPackaging the live-speech model\n" + "-" * 58)
    print(f"  source  {source}")
    print(f"  target  {TARGET}")

    if not source.is_dir():
        print("\n  The Vosk model is not on this machine.")
        print("  Download the Indian English model and unpack it to:")
        print(f"    {DEFAULT_SOURCE}")
        print("  from https://alphacephei.com/vosk/models")
        print("\n  Until then live analysis stays off and the interview works")
        print("  exactly as it does without it.")
        return 1

    if TARGET.exists():
        print(f"\n  Already built ({TARGET.stat().st_size / 1e6:.0f} MB). Delete it to rebuild.")
        return 0

    TARGET.parent.mkdir(parents=True, exist_ok=True)

    # vosk-browser expects the model directory at the archive root, named
    # exactly as it will be referenced.
    print("\n  Building...")
    with tarfile.open(TARGET, "w:gz") as archive:
        archive.add(source, arcname="model")

    size = TARGET.stat().st_size / 1e6
    print(f"  wrote {size:.0f} MB")
    print("\n  Live filler analysis is now available in the interview. It runs")
    print("  entirely in the browser: no audio is streamed anywhere for it, and")
    print("  the recorded answer is still measured server-side, which is what")
    print("  the report and the evidence are built from.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
