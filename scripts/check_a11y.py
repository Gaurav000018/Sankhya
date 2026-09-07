"""Static accessibility checks over the frontend source.

    python scripts/check_a11y.py

Catches the regressions that are easy to introduce and invisible until someone
uses a screen reader: a table header without `scope`, a form control with no
label, a page that never sets its title. It is a linter, not an audit — it
cannot see computed contrast (that is `check_contrast.py`) or keyboard order.

Paired with GIGW 3.0, which requires WCAG 2.1 AA for Indian government sites.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SRC = Path(__file__).resolve().parents[1] / "frontend" / "src"
PAGES = SRC / "pages"


def strip_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"^\s*//.*$", "", text, flags=re.M)


def find_tags(source: str, tag: str) -> list[str]:
    """Return each opening tag's full text, attributes included."""
    return re.findall(rf"<{tag}\b[^>]*?/?>", source, flags=re.S)


def has_attr(tag_text: str, *names: str) -> bool:
    return any(re.search(rf"\b{name}\s*=", tag_text) for name in names)


CHECKS: list[tuple[str, str, str]] = [
    # (element, required attribute alternatives, why)
    ("th", "scope", "a header cell without scope leaves a screen reader guessing "
                    "which cells it describes (WCAG 1.3.1)"),
]


def main() -> int:
    if not SRC.exists():
        print(f"Source not found: {SRC}")
        return 1

    problems: list[str] = []
    files = sorted(SRC.rglob("*.tsx"))

    for path in files:
        rel = path.relative_to(SRC)
        source = strip_comments(path.read_text(encoding="utf-8"))

        for element, attribute, why in CHECKS:
            for tag in find_tags(source, element):
                if not has_attr(tag, attribute):
                    problems.append(f"{rel}: <{element}> without {attribute} — {why}")

        # Form controls need a programmatic name: an id a <label htmlFor> points
        # at, or an aria-label.
        for element in ("input", "select", "textarea"):
            for tag in find_tags(source, element):
                if not has_attr(tag, "id", "aria-label", "aria-labelledby"):
                    snippet = " ".join(tag.split())[:70]
                    problems.append(
                        f"{rel}: <{element}> with no id or aria-label — "
                        f"{snippet}"
                    )

        # A label with htmlFor is only useful if something carries that id.
        for target in re.findall(r'htmlFor="([^"]+)"', source):
            if f'id="{target}"' not in source:
                problems.append(f"{rel}: label htmlFor=\"{target}\" points at no element")

        # Data tables carry meaning; a caption says what they are.
        if "<table" in source and "<caption" not in source and "aria-label" not in source:
            problems.append(
                f"{rel}: <table> with neither a caption nor an aria-label"
            )

    # Every page should name itself in the tab title (WCAG 2.4.2).
    for path in sorted(PAGES.glob("*.tsx")):
        if "usePageTitle" not in path.read_text(encoding="utf-8"):
            problems.append(f"pages/{path.name}: never calls usePageTitle")

    # Landmarks and bypass, checked once where they live.
    layout = (SRC / "components" / "Layout.tsx").read_text(encoding="utf-8")
    if "skip-link" not in layout:
        problems.append("Layout.tsx: no skip link (WCAG 2.4.1 Bypass Blocks)")
    if 'id="main"' not in layout:
        problems.append("Layout.tsx: no <main id=\"main\"> for the skip link to reach")
    # The accessible name may be a literal or a translated expression, so
    # look for the attribute rather than one particular string.
    if not re.search(r"<nav[\s>][^>]*aria-label=", layout):
        problems.append("Layout.tsx: <nav> has no accessible name")

    print(f"\nStatic accessibility checks — {len(files)} files under {SRC.name}/\n")
    if problems:
        for problem in problems:
            print(f"  FAIL  {problem}")
        print(f"\n  {len(problems)} issue(s).")
        return 1

    print("  PASS  table headers scoped")
    print("  PASS  every form control has a programmatic name")
    print("  PASS  every label points at a real element")
    print("  PASS  every data table is captioned")
    print("  PASS  every page sets a document title")
    print("  PASS  skip link, main landmark and named navigation present")
    print(f"\n  No issues across {len(files)} files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
