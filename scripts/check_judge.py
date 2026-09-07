"""Prove the rubric judge can actually score an answer.

    python scripts/check_judge.py

Why this exists: the judge degrades rather than crashing, which is right for an
officer sitting an interview and wrong for the person running the machine. A
degraded verdict is quiet — it scores nobody, changes no competency level, and
looks from the outside like a model that answered badly. This script is the
thing that says out loud whether the judge works, and if not, which layer broke.

Three layers, checked in order, because a failure in one makes the next
meaningless:

  1. Is Ollama reachable?
  2. Is the configured model installed?
  3. Does it return output the schema accepts?

Found in the field: Ollama's CUDA runner is built against a newer toolkit than
an older NVIDIA driver can load. The model loads onto the GPU, then the runner
dies with "device kernel image is invalid", every call 500s, and the judge
reports a degraded verdict. Nothing about that points at the driver, which is
why the HTTP body is printed verbatim here.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.config import settings  # noqa: E402
from app.ml.judge import OllamaJudge, get_judge  # noqa: E402

QUESTION = "How would you use geo-spatial data to improve a sampling frame for a rural survey?"
EXPECTED_POINTS = [
    "Satellite or settlement layers to update village boundaries",
    "Detecting new settlements missing from the census frame",
    "Coordinate accuracy and projection consistency",
    "Field verification of what the imagery suggests",
]
ANSWER = (
    "I would pull recent satellite imagery and settlement layers to refresh the "
    "village boundaries, because the census frame is several years old and new "
    "habitations will be missing from it. Then I would send enumerators to "
    "verify a sample of what the imagery suggests, since built-up area is not "
    "the same as an occupied dwelling."
)

DRIVER_HINT = """
  The CUDA runner could not load. This is almost always the NVIDIA driver being
  older than the toolkit Ollama was built with.

    Check yours:   nvidia-smi --query-gpu=driver_version --format=csv
    Fix, either:
      a) Update the NVIDIA driver (restores GPU speed), or
      b) Run the judge on CPU, which works on any driver:
           setx OLLAMA_LLM_LIBRARY cpu
         then restart Ollama. A 3B model answers in roughly 20-40s on CPU,
         which is fine for scoring an answer after it is recorded.
"""


def reachable() -> bool:
    try:
        with urllib.request.urlopen(f"{settings.ollama_base_url}/api/tags", timeout=10) as r:
            return r.status == 200
    except Exception:
        return False


def installed_models() -> list[str]:
    with urllib.request.urlopen(f"{settings.ollama_base_url}/api/tags", timeout=15) as r:
        return [m["name"] for m in json.loads(r.read()).get("models", [])]


def main() -> int:
    print("\nRubric judge, end to end\n" + "-" * 58)
    print(f"  endpoint          {settings.ollama_base_url}")
    print(f"  configured model  {settings.judge_model}")

    if not reachable():
        print("\n  FAIL  Ollama is not reachable.")
        print("        Start it, then re-run. Until then the judge degrades every")
        print("        answer: interviews still record, but Knowledge is not scored.")
        return 1
    print("  OK    Ollama is reachable")

    models = installed_models()
    if settings.judge_model not in models:
        print(f"\n  FAIL  '{settings.judge_model}' is not installed.")
        print(f"        Installed: {', '.join(models) or '(none)'}")
        print(f"        Pull it:   ollama pull {settings.judge_model}")
        return 1
    print(f"  OK    model is installed ({len(models)} total)")

    judge = get_judge()
    if judge.__class__.__name__ == "StubJudge":
        print("\n  WARN  The stub judge is in use, so this proves nothing about the")
        print("        real model. Interviews will score, but from a keyword match.")
        return 0

    print("\n  Scoring a known-good answer...")
    started = time.time()
    verdict = OllamaJudge().score(QUESTION, EXPECTED_POINTS, ANSWER)
    elapsed = time.time() - started

    if verdict.degraded:
        print(f"\n  FAIL  degraded after {elapsed:.1f}s")
        print(f"        {verdict.reasons.get('error')}")
        if "kernel image" in str(verdict.reasons.get("error", "")).lower():
            print(DRIVER_HINT)
        return 1

    print(f"  knowledge         {verdict.knowledge} (confidence {verdict.knowledge_confidence})")
    print(f"  structure         {verdict.structure}")
    print(f"  covered           {len(verdict.covered_points)} of {len(EXPECTED_POINTS)}")
    for point in verdict.covered_points:
        print(f"    + {point}")
    for point in verdict.missed_points:
        print(f"    - {point}")
    print(f"  took              {elapsed:.1f}s")

    print("\n" + "-" * 58)
    failures = []

    # Every reported point must be one of the rubric's own, in its own wording.
    # The model echoes bullets and paraphrases; a report an officer can contest
    # cannot contain a point nobody asked about.
    for point in verdict.covered_points + verdict.missed_points:
        if point not in EXPECTED_POINTS:
            failures.append(f"reported a point that is not in the rubric: {point!r}")
    if set(verdict.covered_points) & set(verdict.missed_points):
        failures.append("a point is listed as both covered and missed")
    if len(set(verdict.covered_points + verdict.missed_points)) != len(EXPECTED_POINTS):
        failures.append("covered and missed do not account for every expected point")

    # This answer states two of the points almost verbatim. A judge that finds
    # none of them is not scoring content, whatever number it returned.
    if len(verdict.covered_points) < 2:
        failures.append(
            f"only {len(verdict.covered_points)} point(s) credited on an answer that "
            "states at least two of them plainly"
        )
    if verdict.knowledge_confidence <= 0:
        failures.append("zero confidence on a scorable verdict")

    for failure in failures:
        print(f"  FAIL  {failure}")
    if failures:
        return 1

    print("  PASS  the judge scored a real answer and its coverage reconciles")
    if elapsed > 60:
        print(f"  NOTE  {elapsed:.0f}s is slow. That is the CPU runner. Fine for")
        print("        scoring after a recording, too slow to do live.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
