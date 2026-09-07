"""iGOT Karmayogi adapter.

The public iGOT APIs are not open to an unsanctioned client, so this is written
as an adapter with a catalogue-import fallback rather than a direct dependency.
The demo never waits on an external service, and moving to the live API is
implementing `fetch_catalogue` on a second class — nothing above this layer
changes.

The bundled catalogue is representative of iGOT's statistical-system offerings
and is clearly marked as such. It is not scraped from iGOT.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Competency
from app.models_learning import Course, CoursePrerequisite, CourseSource

log = logging.getLogger("sankhya.igot")


@dataclass
class CatalogueEntry:
    external_id: str
    title: str
    description: str
    competency_code: str
    level_from: float
    level_to: float
    duration_hours: float
    provider: str = "iGOT Karmayogi"
    source: CourseSource = CourseSource.IGOT
    requires: list[str] = field(default_factory=list)


class CatalogueProvider(Protocol):
    name: str

    def fetch_catalogue(self) -> list[CatalogueEntry]: ...


# Deliberately includes a three-step GIS chain with real prerequisites: it is
# the sequence the demo narrative walks, and it exercises the topological sort.
BUNDLED_CATALOGUE: list[CatalogueEntry] = [
    CatalogueEntry("IGOT-GIS-101", "Foundations of GIS for Official Statistics",
                   "Coordinate systems, projections and the vocabulary of spatial data, "
                   "framed for statistical officers with no prior GIS exposure.",
                   "TECH-GIS", 1.0, 2.5, 6.0),
    CatalogueEntry("IGOT-GIS-201", "Spatial Data Handling with QGIS",
                   "Working with vector and raster layers, joins between spatial and "
                   "survey data, and preparing maps for publication.",
                   "TECH-GIS", 2.5, 3.8, 8.0, requires=["IGOT-GIS-101"]),
    CatalogueEntry("IGOT-GIS-301", "Geo-spatial Sampling Frames",
                   "Using settlement layers and imagery to update and validate rural "
                   "sampling frames, including field verification.",
                   "TECH-GIS", 3.5, 4.6, 4.0, requires=["IGOT-GIS-201"]),

    CatalogueEntry("IGOT-SAMP-101", "Principles of Survey Sampling",
                   "Probability sampling, stratification and multi-stage designs as used "
                   "across NSS rounds.",
                   "STAT-SAMP", 1.0, 3.0, 8.0),
    CatalogueEntry("IGOT-SAMP-201", "Complex Survey Design in Practice",
                   "Designing multi-stage samples for district-level estimates, including "
                   "allocation and frame construction.",
                   "STAT-SAMP", 3.0, 4.5, 10.0, requires=["IGOT-SAMP-101"]),

    CatalogueEntry("IGOT-EST-101", "Weighting and Estimation",
                   "Design weights, non-response adjustment and post-stratification, with "
                   "worked examples on survey microdata.",
                   "STAT-EST", 1.5, 3.5, 6.0),
    CatalogueEntry("IGOT-EST-201", "Variance Estimation for Complex Designs",
                   "Standard errors under clustering and stratification, replication "
                   "methods and design effects.",
                   "STAT-EST", 3.5, 4.8, 6.0, requires=["IGOT-EST-101"]),

    CatalogueEntry("IGOT-NAS-101", "National Accounts: Concepts and Compilation",
                   "The production, income and expenditure approaches, and how GVA is "
                   "compiled from source statistics.",
                   "STAT-NAS", 1.0, 3.2, 12.0),
    CatalogueEntry("IGOT-NAS-201", "Deflators, Base Revision and Quality Review",
                   "Price deflation, base-year revision and the credibility checks applied "
                   "before a release.",
                   "STAT-NAS", 3.0, 4.5, 8.0, requires=["IGOT-NAS-101"]),

    CatalogueEntry("IGOT-IDX-101", "Index Numbers in Official Statistics",
                   "Laspeyres and Paasche approaches, basket construction and substitution "
                   "bias in CPI and WPI.",
                   "STAT-INDEX", 1.0, 3.5, 6.0),

    CatalogueEntry("IGOT-ANL-101", "Data Analytics for Statistical Officers",
                   "Exploratory analysis, regression and the limits of prediction in an "
                   "official statistics setting.",
                   "TECH-ANL", 1.0, 3.0, 10.0),
    CatalogueEntry("IGOT-ANL-201", "Machine Learning with Official Data",
                   "Where models help and where they must be documented, including "
                   "imputation and its effect on published uncertainty.",
                   "TECH-ANL", 3.0, 4.5, 12.0, requires=["IGOT-ANL-101"]),

    CatalogueEntry("IGOT-BIG-101", "Big Data Platforms for Statistics",
                   "Columnar and chunked processing, when distributed compute is warranted, "
                   "and data residency constraints.",
                   "TECH-BIG", 1.0, 3.4, 8.0),

    CatalogueEntry("IGOT-VIZ-101", "Communicating Statistics Visually",
                   "Chart selection, axis integrity and presenting revised series so users "
                   "can see what changed.",
                   "TECH-VIZ", 1.0, 3.6, 5.0),

    CatalogueEntry("IGOT-QUAL-101", "Data Quality Assurance Framework",
                   "Validation rules, editing and imputation, and documenting decisions "
                   "for the audit trail.",
                   "DG-QUAL", 1.0, 3.2, 6.0),
    CatalogueEntry("IGOT-QUAL-201", "Managing Quality Under Deadline",
                   "Handling failing returns close to a publication date, revision policy "
                   "and escalation.",
                   "DG-QUAL", 3.0, 4.6, 4.0, requires=["IGOT-QUAL-101"]),

    CatalogueEntry("IGOT-PRIV-101", "Statistical Confidentiality and Disclosure Control",
                   "Statutory obligations on unit records, anonymisation and "
                   "re-identification risk.",
                   "DG-PRIV", 1.0, 3.8, 5.0),

    CatalogueEntry("IGOT-COMM-101", "Writing for Statistical Users",
                   "Release notes, metadata and explaining methodology to a non-technical "
                   "reader.",
                   "BEH-COMM", 1.0, 3.4, 4.0),
    CatalogueEntry("NSSTA-COMM-201", "Briefing and Public Communication",
                   "Handling media queries, correcting the record and coordinating through "
                   "the proper channel.",
                   "BEH-COMM", 3.0, 4.5, 3.0, provider="NSSTA",
                   source=CourseSource.NSSTA, requires=["IGOT-COMM-101"]),

    CatalogueEntry("IGOT-LEAD-101", "Supervising Statistical Teams",
                   "Delegation, review practice and resolving methodological disagreement "
                   "without stalling a release.",
                   "BEH-LEAD", 1.0, 3.2, 6.0),
    CatalogueEntry("NSSTA-LEAD-201", "Leading a Division",
                   "Capacity planning, prioritising limited training budget and building "
                   "an annual plan grounded in measured gaps.",
                   "BEH-LEAD", 3.0, 4.7, 8.0, provider="NSSTA",
                   source=CourseSource.NSSTA, requires=["IGOT-LEAD-101"]),
]


class BundledCatalogue:
    """Offline catalogue. Works with no network, which is the point."""

    name = "bundled-catalogue"

    def fetch_catalogue(self) -> list[CatalogueEntry]:
        return BUNDLED_CATALOGUE


class IgotApiCatalogue:
    """Live iGOT integration — not implemented in this deployment.

    The seam exists so production is a configuration change. iGOT is built on
    Sunbird, so this would page a content search endpoint and map each result
    onto CatalogueEntry; nothing above this layer would change.
    """

    name = "igot-api"

    def fetch_catalogue(self) -> list[CatalogueEntry]:
        raise NotImplementedError(
            "Live iGOT access requires a registered client and ministry onboarding"
        )


def get_catalogue_provider() -> CatalogueProvider:
    return BundledCatalogue()


def sync_catalogue(db: Session, provider: CatalogueProvider | None = None) -> dict:
    """Import or refresh the catalogue.

    Upserts on (source, external_id) so a re-sync updates courses rather than
    duplicating them, and rebuilds the prerequisite edges from scratch.
    """
    provider = provider or get_catalogue_provider()
    entries = provider.fetch_catalogue()

    competencies = {c.code: c for c in db.scalars(select(Competency)).all()}
    now = datetime.now(timezone.utc)
    created = updated = 0
    by_external: dict[str, Course] = {}

    for entry in entries:
        competency = competencies.get(entry.competency_code)
        if competency is None:
            log.warning("Skipping %s: unknown competency %s",
                        entry.external_id, entry.competency_code)
            continue

        course = db.scalar(
            select(Course).where(
                Course.source == entry.source, Course.external_id == entry.external_id
            )
        )
        if course is None:
            course = Course(source=entry.source, external_id=entry.external_id)
            db.add(course)
            created += 1
        else:
            updated += 1

        course.title = entry.title
        course.description = entry.description
        course.provider = entry.provider
        course.competency_id = competency.id
        course.level_from = entry.level_from
        course.level_to = entry.level_to
        course.duration_hours = entry.duration_hours
        course.synced_at = now
        course.is_active = True
        db.flush()
        by_external[entry.external_id] = course

    # Rebuild edges rather than diffing them; the graph is small and a stale
    # prerequisite is worse than a rebuild.
    for entry in entries:
        course = by_external.get(entry.external_id)
        if course is None:
            continue
        for existing in list(course.prerequisites):
            db.delete(existing)
        for required_id in entry.requires:
            required = by_external.get(required_id)
            if required is None:
                log.warning("%s requires unknown course %s", entry.external_id, required_id)
                continue
            db.add(CoursePrerequisite(course_id=course.id, requires_id=required.id))

    db.flush()
    return {"provider": provider.name, "created": created, "updated": updated,
            "total": created + updated}
