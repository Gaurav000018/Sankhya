"""Report translation coverage and catch broken keys.

    python scripts/check_i18n.py

Two different jobs:

* **Errors** — a key used in a component that does not exist in the English
  catalogue, or a key defined and never used. Both are bugs.
* **Coverage** — how much of each non-English locale is actually translated.
  This is reported, not enforced. A partial translation that falls back to
  English is honest; one that silently ships machine-translated government
  terminology is not.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SRC = Path(__file__).resolve().parents[1] / "frontend" / "src"
LOCALES_FILE = SRC / "i18n" / "locales.ts"

# Coverage below this is fine, but it should be a deliberate choice.
EXPECTED_MINIMUM = 0.90


def extract_block(source: str, start_marker: str) -> str:
    """Grab a locale object literal by brace matching."""
    index = source.index(start_marker)
    open_brace = source.index("{", index)
    depth = 0
    for position in range(open_brace, len(source)):
        if source[position] == "{":
            depth += 1
        elif source[position] == "}":
            depth -= 1
            if depth == 0:
                return source[open_brace : position + 1]
    raise ValueError(f"Unbalanced braces after {start_marker}")


def keys_in(block: str) -> set[str]:
    return set(re.findall(r'"([a-zA-Z0-9_.]+)"\s*:', block))


def main() -> int:
    if not LOCALES_FILE.exists():
        print(f"Not found: {LOCALES_FILE}")
        return 1

    source = LOCALES_FILE.read_text(encoding="utf-8")
    english = keys_in(extract_block(source, "const en = {"))
    hindi = keys_in(extract_block(source, "const hi:"))

    # Keys referenced from components.
    used: dict[str, set[str]] = {}
    for path in sorted(SRC.rglob("*.tsx")):
        if path.name == "locales.ts":
            continue
        text = path.read_text(encoding="utf-8")
        for key in re.findall(r't\(\s*"([a-zA-Z0-9_.]+)"', text):
            used.setdefault(key, set()).add(str(path.relative_to(SRC)))
        # Keys held in a lookup table and passed to t() indirectly.
        for key in re.findall(r'"((?:nav|role|status|source|common|login|dashboard)\.[a-zA-Z0-9_.]+)"', text):
            used.setdefault(key, set()).add(str(path.relative_to(SRC)))

    errors: list[str] = []

    for key, files in sorted(used.items()):
        if key not in english:
            errors.append(
                f"key \"{key}\" used in {', '.join(sorted(files))} but not defined in English"
            )

    unused = sorted(english - set(used))

    print(f"\nTranslation catalogue — {len(english)} keys\n")

    if errors:
        for error in errors:
            print(f"  FAIL  {error}")
        print()

    missing = sorted(english - hindi)
    coverage = len(hindi & english) / len(english) if english else 0.0
    print(f"  hi    {len(hindi & english)}/{len(english)} translated  ({coverage:.0%})")
    if missing:
        print(f"        {len(missing)} falling back to English:")
        for key in missing[:8]:
            print(f"          {key}")
        if len(missing) > 8:
            print(f"          ... and {len(missing) - 8} more")

    stray = sorted(hindi - english)
    if stray:
        for key in stray:
            errors.append(f'Hindi defines "{key}", which is not an English key')
            print(f"  FAIL  Hindi defines \"{key}\", not present in English")

    if unused:
        print(f"\n  {len(unused)} key(s) defined but never used:")
        for key in unused[:8]:
            print(f"    {key}")
        if len(unused) > 8:
            print(f"    ... and {len(unused) - 8} more")

    print()
    if errors:
        print(f"  {len(errors)} error(s). Broken keys render as English fallback at best.")
        return 1

    if coverage < EXPECTED_MINIMUM:
        print(
            f"  No broken keys. Hindi coverage is {coverage:.0%} — the remainder "
            f"falls back to English by design."
        )
    else:
        print(f"  No broken keys. Hindi coverage {coverage:.0%}.")
    print(
        "  Every Hindi string still needs review by a Hindi-speaking officer "
        "before deployment."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
