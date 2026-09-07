"""Check that the recommender's relevance floor still separates related from
unrelated courses.

    python scripts/check_relevance_floor.py

Why this exists: `relevance()` scores a course against a competency it does not
belong to by cosine similarity, and admits it above a floor. That floor is an
empirical property of whichever embedder is configured, not a universal
constant. When the embedder changed from lexical hashing to a trained model,
the old floor of 0.20 silently admitted *every* pair in the catalogue — a QGIS
course was recommended against a team-leadership gap, and nothing failed.

So this measures the two distributions on the real catalogue and reports where
the floor sits between them. It fails when the floor stops discriminating,
which is the condition that was previously invisible.
"""

from __future__ import annotations

import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.db import SessionLocal  # noqa: E402
from app.ml.embeddings import cosine, get_embedder  # noqa: E402
from app.models import Competency  # noqa: E402
from app.models_learning import Course  # noqa: E402

# A floor that admits almost everything is not a filter, and one that admits
# almost nothing turns off cross-competency recommendation altogether.
MAX_ADMITTED_SHARE = 0.40
MIN_ADMITTED_SHARE = 0.02


def main() -> int:
    db = SessionLocal()
    embedder = get_embedder()
    floor = embedder.relevance_floor

    print("\nRecommender relevance floor\n" + "-" * 58)
    print(f"  embedder    {embedder.name}")
    print(f"  floor       {floor:.2f}")

    competencies = db.scalars(select_all(Competency)).all()
    courses = [c for c in db.scalars(select_all(Course)).all() if c.embedding]

    if not courses:
        print("\n  No embedded courses. Seed the database first.")
        return 1

    competency_vectors = {
        c.id: embedder.embed(f"{c.name}. {c.description or ''}") for c in competencies
    }

    same: list[float] = []
    cross: list[tuple[float, str, str]] = []
    for course in courses:
        for competency in competencies:
            score = cosine(course.embedding, competency_vectors[competency.id])
            if course.competency_id == competency.id:
                same.append(score)
            else:
                cross.append((score, course.title, competency.name))

    if not same or not cross:
        print("\n  Not enough data to compare.")
        return 1

    cross_scores = [s for s, _, _ in cross]
    admitted = [c for c in cross if c[0] >= floor]
    share = len(admitted) / len(cross)

    print(f"\n  same-competency   n={len(same):<4} "
          f"min={min(same):.3f} median={statistics.median(same):.3f} max={max(same):.3f}")
    print(f"  cross-competency  n={len(cross):<4} "
          f"min={min(cross_scores):.3f} median={statistics.median(cross_scores):.3f} "
          f"max={max(cross_scores):.3f}")
    print(f"\n  admitted across competencies: {len(admitted)} of {len(cross)} "
          f"({share:.0%})")

    for score, title, competency in sorted(admitted, reverse=True)[:8]:
        print(f"    {score:.3f}  {title[:40]:<42} -> {competency}")

    print("\n" + "-" * 58)
    failures = []
    if share > MAX_ADMITTED_SHARE:
        failures.append(
            f"the floor admits {share:.0%} of unrelated pairs — it is not filtering. "
            f"Raise Embedder.relevance_floor for {embedder.name}."
        )
    if share < MIN_ADMITTED_SHARE:
        failures.append(
            f"the floor admits only {share:.0%} — cross-competency recommendation "
            "is effectively off. Lower it, or drop the feature deliberately."
        )
    if floor <= statistics.median(cross_scores):
        failures.append(
            f"the floor ({floor:.2f}) is at or below the median unrelated score "
            f"({statistics.median(cross_scores):.3f}), so more unrelated pairs pass "
            "than fail."
        )

    for failure in failures:
        print(f"  FAIL  {failure}")
    if failures:
        return 1

    print(f"  PASS  the floor sits above the unrelated median and admits {share:.0%}")
    print("\n  The two bands overlap by nature — a genuinely adjacent course can")
    print("  outscore a poorly-worded one in its own competency. This checks that")
    print("  the floor discriminates, not that it is perfect.")
    return 0


def select_all(model):
    from sqlalchemy import select

    return select(model)


if __name__ == "__main__":
    raise SystemExit(main())
