"""Verify the palette against WCAG 2.1 AA contrast ratios.

    python scripts/check_contrast.py

Reads the tokens straight out of the stylesheet, so this checks what the app
actually ships rather than a copy of it. "WCAG 2.1 AA" is a claim a government
platform will be held to — this makes it a thing that fails a build rather than
a sentence in a pitch deck.

Thresholds (WCAG 2.1):
  1.4.3 Contrast (Minimum)      4.5:1 body text, 3:1 large text (>=18.66px bold
                                or >=24px regular)
  1.4.11 Non-text Contrast      3:1 for UI component boundaries and meaningful
                                graphics — which includes every bar and heatmap
                                cell that carries information
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CSS = Path(__file__).resolve().parents[1] / "frontend" / "src" / "index.css"

AA_BODY = 4.5
AA_LARGE = 3.0
AA_NON_TEXT = 3.0


def parse_tokens(css: str) -> dict[str, str]:
    return {
        name: value
        for name, value in re.findall(r"--color-([a-z0-9-]+):\s*(#[0-9a-fA-F]{6})", css)
    }


def relative_luminance(hex_colour: str) -> float:
    r, g, b = (int(hex_colour[i : i + 2], 16) / 255 for i in (1, 3, 5))

    def channel(c: float) -> float:
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def contrast(a: str, b: str) -> float:
    la, lb = relative_luminance(a), relative_luminance(b)
    lighter, darker = max(la, lb), min(la, lb)
    return (lighter + 0.05) / (darker + 0.05)


# (foreground, background, minimum, where it is used)
PAIRS = [
    ("ink", "ground", AA_BODY, "body text on the page"),
    ("ink", "surface", AA_BODY, "body text on cards"),
    ("ink-2", "surface", AA_BODY, "secondary copy"),
    ("ink-2", "ground", AA_BODY, "secondary copy on the page"),
    ("ink-3", "surface", AA_BODY, "labels, hints, table meta"),
    ("ink-3", "ground", AA_BODY, "page-level meta"),
    ("ink-3", "surface-2", AA_BODY, "muted text on inset panels"),
    ("accent", "surface", AA_BODY, "links and interactive text"),
    ("brass", "surface", AA_BODY, "eyebrow labels"),
    ("critical", "surface", AA_BODY, "critical gap status"),
    ("warn", "surface", AA_BODY, "at-risk status"),
    ("near", "surface", AA_BODY, "near-target status"),
    ("good", "surface", AA_BODY, "met status"),
    # Filled cells and buttons: white text on a solid semantic ground.
    ("surface", "critical", AA_BODY, "white on critical fill (heatmap, buttons)"),
    ("surface", "warn", AA_BODY, "white on at-risk fill"),
    ("surface", "near", AA_BODY, "white on near-target fill"),
    ("surface", "good", AA_BODY, "white on met fill"),
    ("surface", "accent", AA_BODY, "primary button label"),
    ("surface", "navy", AA_BODY, "header text"),
    # Non-text: bars, rules and cell fills carry meaning on their own.
    ("accent", "surface-2", AA_NON_TEXT, "progress and signal bars"),
    ("rule-strong", "surface", AA_NON_TEXT, "input borders"),
    ("critical", "surface-2", AA_NON_TEXT, "gap bar against its track"),
]


def main() -> int:
    if not CSS.exists():
        print(f"Stylesheet not found: {CSS}")
        return 1

    tokens = parse_tokens(CSS.read_text(encoding="utf-8"))
    missing = {
        name for pair in PAIRS for name in pair[:2] if name not in tokens
    }
    if missing:
        print(f"Tokens missing from the stylesheet: {', '.join(sorted(missing))}")
        return 1

    print(f"\nWCAG 2.1 AA contrast — {len(PAIRS)} pairs from {CSS.name}\n")
    failures = []

    for fg, bg, minimum, where in PAIRS:
        ratio = contrast(tokens[fg], tokens[bg])
        ok = ratio >= minimum
        if not ok:
            failures.append((fg, bg, ratio, minimum, where))
        print(
            f"  {'PASS' if ok else 'FAIL'}  {ratio:5.2f}:1  "
            f"(min {minimum})  {fg} on {bg:<10} {where}"
        )

    print()
    if failures:
        print(f"  {len(failures)} pair(s) below the AA threshold:\n")
        for fg, bg, ratio, minimum, where in failures:
            shortfall = minimum - ratio
            print(
                f"    {fg} on {bg}: {ratio:.2f}:1, needs {minimum}:1 "
                f"(short by {shortfall:.2f}) — {where}"
            )
        print("\n  Darken the foreground token or lighten the background.")
        return 1

    print(f"  All {len(PAIRS)} pairs meet WCAG 2.1 AA.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
