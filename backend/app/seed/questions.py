"""Interview question bank.

Pre-generated and reviewed rather than produced live. That removes a model call
from the demo path and, more importantly, means a human has seen every question
before an officer does — the same gate that generated quiz items pass through.

`expected_points` is what the judge scores coverage against, so the assessment
is anchored to a rubric rather than to the model's own opinion of a good answer.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Competency
from app.models_interview import InterviewQuestion

# Neutral text, no domain knowledge required. Reading this measures how the
# officer speaks when they are not searching for an answer — which is the
# baseline every later fluency score is compared against.
BASELINE_PROMPT = (
    "Before we begin, please read the following aloud at your normal speaking pace.\n\n"
    "\"The National Statistical Office publishes a range of official statistics "
    "covering prices, industrial production, national income and household "
    "consumption. These releases follow a published calendar so that users know "
    "in advance when each figure will become available. Wherever revisions are "
    "made, the reason for the revision is documented alongside the updated "
    "series so that users can trace what changed and why.\""
)

# competency code -> [(prompt, expected_points, bloom_level)]
QUESTIONS: dict[str, list[tuple[str, list[str], str]]] = {
    "STAT-SAMP": [
        (
            "You are designing a household survey to estimate district-level "
            "unemployment. Walk me through how you would construct the sampling "
            "frame and allocate the sample across districts.",
            [
                "Stratification by district and by rural/urban sector",
                "Two-stage design with villages or urban blocks as first-stage units",
                "Allocation approach and why equal allocation harms precision",
                "Handling districts with very small populations",
            ],
            "analyse",
        ),
        (
            "A colleague proposes increasing the sample size to fix a high "
            "non-response rate. How would you respond?",
            [
                "Non-response is bias, not variance, so more sample does not fix it",
                "Non-response follow-up and weighting adjustment",
                "Understanding who is missing rather than how many",
            ],
            "evaluate",
        ),
    ],
    "STAT-EST": [
        (
            "Explain how design weights are constructed in a multi-stage survey, "
            "and what goes wrong if they are ignored.",
            [
                "Inverse of the selection probability at each stage",
                "Non-response and post-stratification adjustments",
                "Biased estimates and wrong standard errors if unweighted",
            ],
            "apply",
        ),
    ],
    "STAT-NAS": [
        (
            "A state reports a sharp rise in Gross State Value Added for a quarter. "
            "How would you check whether the figure is credible before publication?",
            [
                "Cross-checking against related indicators and physical output",
                "Comparing with prior quarters and seasonal patterns",
                "Verifying deflators and the price base used",
                "Consulting the source agency before publishing",
            ],
            "evaluate",
        ),
    ],
    "STAT-INDEX": [
        (
            "Explain the difference between the Laspeyres and Paasche approaches "
            "to index construction, and why base year revision matters.",
            [
                "Base-period versus current-period weights",
                "Substitution bias in a fixed-base index",
                "Why the basket drifts from consumption patterns over time",
            ],
            "understand",
        ),
    ],
    "TECH-ANL": [
        (
            "You are asked to use a machine learning model to impute missing "
            "values in an official statistical release. What concerns would you "
            "raise, and what would you insist on?",
            [
                "Reproducibility and documentation of the method",
                "Imputation uncertainty must be reflected in published error",
                "Explainability to users and to auditors",
                "Whether a simpler documented method would serve better",
            ],
            "evaluate",
        ),
    ],
    "TECH-GIS": [
        (
            "How would you use geo-spatial data to improve a sampling frame for "
            "a rural survey?",
            [
                "Satellite or settlement layers to update village boundaries",
                "Detecting new settlements missing from the census frame",
                "Coordinate accuracy and projection consistency",
                "Field verification of what the imagery suggests",
            ],
            "apply",
        ),
        (
            "What is the difference between a raster and a vector layer, and when "
            "would you use each in statistical work?",
            [
                "Continuous surfaces versus discrete features",
                "Raster for land use or population density surfaces",
                "Vector for administrative boundaries and points",
            ],
            "understand",
        ),
    ],
    "TECH-BIG": [
        (
            "Your division needs to process a survey dataset that no longer fits "
            "in memory on a single machine. How would you approach it?",
            [
                "Chunked or columnar processing before reaching for a cluster",
                "Whether the volume genuinely warrants distributed compute",
                "Data residency constraints on where processing may run",
            ],
            "apply",
        ),
    ],
    "TECH-VIZ": [
        (
            "You must present a revised series to users who will notice the "
            "revision. How would you design that release?",
            [
                "Showing old and revised series together",
                "Documenting the reason for revision alongside the figures",
                "Avoiding a truncated axis that exaggerates the change",
                "Writing for a non-technical reader",
            ],
            "create",
        ),
    ],
    "DG-QUAL": [
        (
            "A quarterly return arrives from a state office with 30% of records "
            "failing validation, two days before the publication deadline. Walk "
            "me through what you do.",
            [
                "Characterising the failures before acting",
                "Contacting the source office rather than silently correcting",
                "Deciding between delay, partial publication or a flagged release",
                "Documenting the decision for the audit trail",
                "Escalating within the published revision policy",
            ],
            "evaluate",
        ),
    ],
    "DG-PRIV": [
        (
            "A researcher requests unit-level records from a household survey. "
            "How do you handle the request?",
            [
                "Statutory confidentiality obligations on unit records",
                "Anonymisation and disclosure control before any release",
                "Re-identification risk from combining datasets",
                "Offering a safe access route rather than a flat refusal",
            ],
            "evaluate",
        ),
    ],
    "BEH-COMM": [
        (
            "A journalist has misread one of your division's releases and "
            "published an incorrect figure. How do you handle it?",
            [
                "Correcting the record promptly and factually",
                "Identifying whether the release itself was unclear",
                "Coordinating through the proper channel rather than acting alone",
            ],
            "apply",
        ),
    ],
    "BEH-LEAD": [
        (
            "Two officers in your team disagree about a methodology change, and "
            "the disagreement is delaying the release. How do you resolve it?",
            [
                "Separating the technical question from the interpersonal one",
                "Seeking evidence or precedent rather than deciding by seniority",
                "Setting a decision point so the release is not held indefinitely",
                "Documenting the rationale for whichever way it goes",
            ],
            "evaluate",
        ),
        (
            "How would you plan your division's capacity building for the coming "
            "year given a limited training budget?",
            [
                "Prioritising by measured competency gap, not by demand",
                "Targeting critical competencies for the roles held",
                "Measuring whether the training actually changed capability",
            ],
            "create",
        ),
    ],
}


def seed_questions(db: Session, competencies: dict[str, Competency]) -> int:
    """Load the bank. Returns how many questions were created."""
    db.add(InterviewQuestion(
        prompt=BASELINE_PROMPT,
        expected_points=[],
        bloom_level="remember",
        is_baseline=True,
        difficulty=1.0,
    ))
    created = 0

    for code, entries in QUESTIONS.items():
        competency = competencies.get(code)
        if competency is None:
            continue
        for prompt, expected_points, bloom in entries:
            db.add(InterviewQuestion(
                competency_id=competency.id,
                prompt=prompt,
                expected_points=expected_points,
                bloom_level=bloom,
                difficulty=3.5,
            ))
            created += 1

    db.flush()
    return created
