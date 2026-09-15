"""Which technical terms an answer used, and which it was expected to use.

Deterministic, not model-judged. A language model asked "did they use the right
terminology" gives a different answer on a re-run and cannot say why; a glossary
match gives the same answer every time and can point at the exact words. The
model's job is the harder question — whether a term was used *correctly* — and
that lives in the judge's `mistakes`, not here.

Two things the matching has to survive:

* **Speech recognition splits compounds.** "Undercoverage" comes back as
  "under coverage" and "non-response" as "non response". Every term matches with
  or without its internal space or hyphen, or an officer who said it perfectly
  is told they never did.
* **Plurals and simple inflections.** "Strata" for "stratum", "weights" for
  "weight". Each term lists the forms that count.

What "expected" means is taken from the question's own expected points, not
from the whole competency glossary. An answer about sampling frames is not
short of vocabulary for failing to mention Neyman allocation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Term:
    name: str
    forms: tuple[str, ...]


def _t(name: str, *forms: str) -> Term:
    return Term(name=name, forms=(name, *forms))


GLOSSARY: dict[str, tuple[Term, ...]] = {
    "STAT-SAMP": (
        _t("sampling frame", "frame"),
        _t("stratified sampling", "stratification", "stratify", "stratified"),
        _t("stratum", "strata"),
        _t("cluster sampling", "clustering", "clusters"),
        _t("Neyman allocation", "optimal allocation"),
        _t("proportional allocation"),
        _t("undercoverage", "under coverage", "coverage error"),
        _t("simple random sampling", "srs"),
        _t("sample size"),
        _t("design effect"),
        _t("multi-stage sampling", "multistage"),
        _t("probability sampling", "selection probability"),
    ),
    "STAT-EST": (
        _t("design weight", "design weights", "sampling weight", "weights"),
        _t("non-response", "nonresponse", "non response", "response rate"),
        _t("non-response adjustment", "weighting class", "weighting adjustment"),
        _t("post-stratification", "poststratification", "control totals"),
        _t("bias", "biased"),
        _t("variance", "standard error", "sampling error"),
        _t("estimator", "estimate", "estimation"),
        _t("imputation", "impute"),
        _t("calibration"),
        _t("confidence interval"),
    ),
    "STAT-NAS": (
        _t("gross value added", "gva"),
        _t("gross domestic product", "gdp"),
        _t("intermediate consumption"),
        _t("basic prices"),
        _t("market prices"),
        _t("product taxes", "taxes on products"),
        _t("subsidies", "subsidy"),
        _t("deflator", "deflators", "deflation"),
        _t("base year", "base revision"),
        _t("constant prices", "real terms"),
        _t("double counting"),
    ),
    "STAT-INDEX": (
        _t("Laspeyres index", "laspeyres"),
        _t("Paasche index", "paasche"),
        _t("Fisher index", "fisher"),
        _t("base period", "base year"),
        _t("weights", "weighting pattern"),
        _t("substitution bias", "substitution"),
        _t("price relative", "price relatives"),
        _t("chain index", "chaining", "chain linking"),
        _t("basket"),
    ),
    "TECH-ANL": (
        _t("overfitting", "over fitting", "overfit"),
        _t("test set", "holdout", "hold out", "validation set"),
        _t("training data", "training set"),
        _t("cross-validation", "cross validation"),
        _t("class imbalance", "imbalanced"),
        _t("accuracy"),
        _t("precision"),
        _t("recall", "sensitivity"),
        _t("correlation", "correlated"),
        _t("causation", "causal"),
        _t("feature", "features"),
    ),
    "TECH-GIS": (
        _t("coordinate reference system", "crs", "projection", "reprojection"),
        _t("satellite imagery", "satellite", "remote sensing"),
        _t("shapefile", "vector layer", "vector data"),
        _t("raster", "raster layer"),
        _t("geocoding", "geocode", "geo coding"),
        _t("spatial join", "overlay"),
        _t("modifiable areal unit problem", "maup"),
        _t("field verification", "ground truthing", "ground truth", "field check"),
        _t("settlement layer", "settlements", "built-up area", "built up area"),
        _t("boundaries", "boundary"),
    ),
    "TECH-BIG": (
        _t("partitioning", "partition", "partitions"),
        _t("schema", "schema validation", "schema checks"),
        _t("pipeline", "data pipeline", "etl"),
        _t("distributed", "cluster computing"),
        _t("data lake", "data warehouse"),
        _t("reproducibility", "reproducible", "version control", "versioning"),
        _t("administrative data", "admin data"),
        _t("ingestion", "ingest"),
    ),
    "TECH-VIZ": (
        _t("bar chart", "bar graph"),
        _t("axis", "baseline", "zero baseline"),
        _t("colour", "color", "colour vision deficiency", "colour blind", "color blind"),
        _t("uncertainty", "confidence interval", "error bars", "margin of error"),
        _t("legend", "labels", "labelling"),
        _t("accessibility", "accessible"),
        _t("dashboard"),
        _t("dissemination", "release"),
    ),
    "DG-QUAL": (
        _t("validation rules", "validation", "edit checks"),
        _t("outlier", "outliers"),
        _t("imputation", "impute"),
        _t("response rate"),
        _t("revision policy", "revisions", "revision"),
        _t("metadata"),
        _t("quality report", "quality framework"),
        _t("timeliness"),
        _t("coherence", "consistency"),
    ),
    "DG-PRIV": (
        _t("statistical disclosure control", "disclosure control", "sdc"),
        _t("primary suppression", "cell suppression", "suppression", "suppress"),
        _t("secondary suppression", "complementary suppression"),
        _t("anonymisation", "anonymization", "anonymise", "anonymize", "anonymous"),
        _t("pseudonymisation", "pseudonymization", "pseudonymous"),
        _t("re-identification", "reidentification", "re identification"),
        _t("quasi-identifier", "quasi identifier", "quasi-identifiers"),
        _t("microdata"),
        _t("personal data", "dpdp"),
        _t("threshold rule", "minimum cell size"),
    ),
    "BEH-COMM": (
        _t("headline", "key message", "lead with"),
        _t("audience", "non-specialist", "general reader"),
        _t("plain language", "plain english", "jargon"),
        _t("revision", "revised estimate"),
        _t("press release", "statistical release", "release"),
        _t("methodology", "metadata"),
        _t("seasonally adjusted", "seasonal adjustment"),
        _t("provisional", "preliminary estimate"),
    ),
    "BEH-LEAD": (
        _t("delegation", "delegate"),
        _t("escalation", "escalate"),
        _t("stakeholder", "stakeholders"),
        _t("criteria", "decision criteria"),
        _t("deadline", "timeline"),
        _t("accountability", "accountable"),
        _t("conflict resolution", "disagreement"),
        _t("feedback"),
        _t("prioritisation", "prioritization", "prioritise", "prioritize"),
    ),
}


def _pattern(form: str) -> re.Pattern:
    """Word-bounded, tolerant of a missing or extra space or hyphen inside."""
    parts = re.split(r"[\s\-]+", form.strip().lower())
    body = r"[\s\-]*".join(re.escape(p) for p in parts if p)
    return re.compile(rf"(?<![a-z0-9]){body}(?![a-z0-9])")


_COMPILED: dict[str, list[tuple[Term, list[re.Pattern]]]] = {
    code: [(term, [_pattern(f) for f in term.forms]) for term in terms]
    for code, terms in GLOSSARY.items()
}


def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower())


def _found(patterns: list[re.Pattern], text: str) -> bool:
    return any(p.search(text) for p in patterns)


@dataclass
class TermAnalysis:
    used: list[str] = field(default_factory=list)
    expected: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)

    @property
    def coverage(self) -> float | None:
        """Share of this question's expected terms the answer used."""
        if not self.expected:
            return None
        return round((len(self.expected) - len(self.missing)) / len(self.expected), 2)

    def as_dict(self) -> dict:
        return {
            "used": self.used,
            "expected": self.expected,
            "missing": self.missing,
            "coverage": self.coverage,
        }


def analyse_terms(
    transcript: str, competency_code: str | None, expected_points: list[str] | None
) -> TermAnalysis:
    """Terms used in the answer, and the question's expected terms it missed."""
    entries = _COMPILED.get(competency_code or "", [])
    if not entries:
        return TermAnalysis()

    spoken = _normalise(transcript)
    rubric = _normalise(" ".join(expected_points or []))

    analysis = TermAnalysis()
    for term, patterns in entries:
        if _found(patterns, spoken):
            analysis.used.append(term.name)
        if rubric and _found(patterns, rubric):
            analysis.expected.append(term.name)

    analysis.missing = [t for t in analysis.expected if t not in analysis.used]
    return analysis
