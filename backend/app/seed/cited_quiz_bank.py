"""Assessment items with verified citations, one passage per competency.

Sits alongside `quiz_bank.py`, which loads the hand-written bank from
`mcqs.py`. That bank attaches its items to a synthetic material with no
passages; these carry a real passage each, so the citation trail and the
"view source" screen have something to show for them.

Without this the Assessment tab is dead on a freshly seeded database: quizzes
refuse to start because nothing has been through SME review, which is correct
behaviour and a terrible first impression. The interview bank is already seeded;
this closes the same gap for multiple-choice items.

Two things this does not do.

**It does not bypass citation verification.** Every quote below is copied out of
the passage above it, and `seed_quiz_bank` runs the real `verify_citation`
against the stored chunk before approving anything. A question whose citation
does not verify is dropped with a warning rather than seeded, which means this
file cannot quietly rot into a set of items that the platform's own integrity
rule would reject.

**It does not pretend to be reviewed by a person.** Each item carries a review
note saying it was seeded, so an SME opening the bank can tell demonstration
content from something a colleague actually approved.

The passages are written for this file rather than lifted from MoSPI
publications: real official-statistics content, no copyright question, and
short enough that a reviewer can check every citation by eye.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.models_content import (
    GeneratedQuestion,
    Material,
    MaterialChunk,
    MaterialStatus,
    QuestionStatus,
)
from app.services.quizgen import verify_citation

log = logging.getLogger("sankhya.seed.quiz")


@dataclass
class Item:
    stem: str
    options: list[str]
    correct_index: int
    explanation: str
    quote: str
    bloom: str = "understand"
    distractor_rationale: list[str] = field(default_factory=list)


@dataclass
class Topic:
    competency_code: str
    title: str
    passage: str
    items: list[Item]


TOPICS: list[Topic] = [
    Topic(
        competency_code="STAT-SAMP",
        title="Sampling design and frames",
        passage=(
            "Stratified sampling divides the population into homogeneous strata "
            "before selection, so that variation within each stratum is smaller "
            "than variation across the population as a whole. Allocation across "
            "strata may be proportional to stratum size, or optimal, which also "
            "accounts for within-stratum variance and the cost of enumeration.\n\n"
            "A sampling frame is the list from which units are drawn. Frame "
            "errors include undercoverage, duplication and out-of-scope units. "
            "Undercoverage is the most damaging of the three because the omitted "
            "units cannot be represented by any weighting adjustment applied "
            "afterwards.\n\n"
            "Cluster sampling selects groups of units rather than units "
            "individually, which lowers travel cost but raises the variance of "
            "the estimate whenever units inside a cluster resemble one another."
        ),
        items=[
            Item(
                stem="Why does optimal allocation sometimes assign a larger sample to a "
                     "small stratum than proportional allocation would?",
                options=[
                    "Because it accounts for within-stratum variance and the cost of enumeration",
                    "Because small strata are always harder to reach",
                    "Because it equalises the sample size across every stratum",
                    "Because proportional allocation is only valid for two strata",
                ],
                correct_index=0,
                explanation=(
                    "Optimal allocation samples more heavily where a stratum is "
                    "internally variable or cheap to enumerate, which can outweigh its "
                    "share of the population. Proportional allocation looks only at size."
                ),
                quote=(
                    "Allocation across strata may be proportional to stratum size, or "
                    "optimal, which also accounts for within-stratum variance and the "
                    "cost of enumeration."
                ),
                distractor_rationale=[
                    "Reachability is a fieldwork consideration, not what allocation optimises",
                    "Equal allocation is a different scheme again",
                    "Proportional allocation has no such restriction",
                ],
            ),
            Item(
                stem="Which frame error cannot be repaired by adjusting weights after "
                     "collection?",
                options=[
                    "Undercoverage",
                    "Duplication",
                    "Out-of-scope units",
                    "Unit non-response",
                ],
                correct_index=0,
                explanation=(
                    "Duplicates and out-of-scope units are in the frame and can be "
                    "identified and corrected. Units the frame never contained cannot be "
                    "weighted up, because nothing in the sample stands for them."
                ),
                quote=(
                    "Undercoverage is the most damaging of the three because the omitted "
                    "units cannot be represented by any weighting adjustment applied "
                    "afterwards."
                ),
                bloom="analyse",
                distractor_rationale=[
                    "Duplicates can be detected and de-duplicated",
                    "Out-of-scope units can be identified and excluded",
                    "Non-response is a response problem, not a frame problem",
                ],
            ),
            Item(
                stem="A survey switches from simple random sampling to cluster sampling to "
                     "cut travel costs. What is the likely effect on the estimate?",
                options=[
                    "Variance rises where units within a cluster resemble one another",
                    "Variance falls because clusters are internally consistent",
                    "The estimate becomes biased in proportion to cluster size",
                    "There is no effect provided the clusters are equally sized",
                ],
                correct_index=0,
                explanation=(
                    "Similar units inside a cluster carry overlapping information, so a "
                    "cluster of ten contributes less than ten independent observations. "
                    "The design is cheaper per unit and less precise per unit."
                ),
                quote=(
                    "Cluster sampling selects groups of units rather than units "
                    "individually, which lowers travel cost but raises the variance of "
                    "the estimate whenever units inside a cluster resemble one another."
                ),
                bloom="apply",
                distractor_rationale=[
                    "Internal consistency is what raises variance here, not lowers it",
                    "Clustering affects precision, not bias, when correctly weighted",
                    "Equal cluster sizes do not remove the design effect",
                ],
            ),
            Item(
                stem="What defines a sampling frame?",
                options=[
                    "The list from which units are drawn",
                    "The set of units that responded",
                    "The population totals used for post-stratification",
                    "The strata boundaries agreed before selection",
                ],
                correct_index=0,
                explanation=(
                    "The frame is the operational list standing in for the population. "
                    "How well it does so determines coverage error."
                ),
                quote="A sampling frame is the list from which units are drawn.",
                distractor_rationale=[
                    "Respondents are a subset of the selected sample, not the frame",
                    "Control totals are used in estimation, after selection",
                    "Strata partition the frame; they are not the frame itself",
                ],
            ),
        ],
    ),
    Topic(
        competency_code="STAT-EST",
        title="Weighting and estimation",
        passage=(
            "Design weights are the inverse of the probability of selection at each "
            "stage of a multi-stage sample. Where a selected household does not "
            "respond, a further adjustment is applied so that responding units "
            "represent the non-responding ones within the same weighting class.\n\n"
            "Post-stratification aligns the weighted sample totals to known "
            "population control totals, usually drawn from the most recent census "
            "projections. This reduces variance for characteristics correlated with "
            "the control variables, but it cannot repair a frame that has omitted "
            "part of the population altogether.\n\n"
            "Increasing the sample size does not correct non-response bias. A larger "
            "sample of the same responding population estimates the wrong quantity "
            "more precisely."
        ),
        items=[
            Item(
                stem="A survey has 40% non-response. The team proposes doubling the "
                     "sample size to fix it. What is wrong with this?",
                options=[
                    "A larger sample of the same responding population estimates the wrong quantity more precisely",
                    "Doubling the sample doubles the design weights",
                    "Nothing — non-response bias falls as sample size rises",
                    "It is only wrong if the response rate falls below 50%",
                ],
                correct_index=0,
                explanation=(
                    "Non-response bias comes from who is missing, not from how many "
                    "responded. More of the same respondents narrows the confidence "
                    "interval around a biased figure."
                ),
                quote=(
                    "A larger sample of the same responding population estimates the "
                    "wrong quantity more precisely."
                ),
                bloom="analyse",
                distractor_rationale=[
                    "Weights follow selection probabilities, not sample size directly",
                    "This is the misconception the item is testing",
                    "No threshold makes the reasoning valid",
                ],
            ),
            Item(
                stem="What are design weights?",
                options=[
                    "The inverse of the probability of selection at each stage",
                    "The ratio of respondents to non-respondents",
                    "Population control totals from census projections",
                    "Adjustment factors applied only to out-of-scope units",
                ],
                correct_index=0,
                explanation=(
                    "A unit selected with probability 1 in 500 stands for roughly 500 "
                    "units, which is what its weight records."
                ),
                quote=(
                    "Design weights are the inverse of the probability of selection at "
                    "each stage of a multi-stage sample."
                ),
                distractor_rationale=[
                    "That ratio describes response, not selection",
                    "Control totals are used in post-stratification",
                    "Out-of-scope handling is a separate step",
                ],
            ),
            Item(
                stem="What is post-stratification unable to fix?",
                options=[
                    "A frame that has omitted part of the population altogether",
                    "Variance in characteristics correlated with the control variables",
                    "Differences between weighted totals and census projections",
                    "Unequal selection probabilities across stages",
                ],
                correct_index=0,
                explanation=(
                    "Aligning to control totals reweights the units you have. It cannot "
                    "conjure representation for units the frame never contained."
                ),
                quote=(
                    "This reduces variance for characteristics correlated with the "
                    "control variables, but it cannot repair a frame that has omitted "
                    "part of the population altogether."
                ),
                bloom="analyse",
                distractor_rationale=[
                    "Reducing that variance is precisely what it does",
                    "Aligning to those totals is its purpose",
                    "Design weights handle unequal selection",
                ],
            ),
            Item(
                stem="Within a weighting class, what does the non-response adjustment "
                     "assume?",
                options=[
                    "Responding units can represent the non-responding ones",
                    "Non-respondents were never eligible for the survey",
                    "Non-response is unrelated to any measured characteristic",
                    "The class contains equal numbers of both groups",
                ],
                correct_index=0,
                explanation=(
                    "The adjustment redistributes non-respondent weight onto respondents "
                    "in the same class, which only holds if the two are alike within it. "
                    "Choosing classes well is what makes the assumption defensible."
                ),
                quote=(
                    "Where a selected household does not respond, a further adjustment is "
                    "applied so that responding units represent the non-responding ones "
                    "within the same weighting class."
                ),
                bloom="analyse",
                distractor_rationale=[
                    "Ineligible units are removed, not adjusted for",
                    "The assumption is conditional independence within the class",
                    "No balance of that kind is assumed",
                ],
            ),
        ],
    ),
    Topic(
        competency_code="STAT-NAS",
        title="National accounts",
        passage=(
            "Gross Value Added at basic prices measures output net of intermediate "
            "consumption, before taxes on products are added and subsidies deducted. "
            "Gross Domestic Product at market prices is obtained by adding product "
            "taxes to Gross Value Added and subtracting product subsidies.\n\n"
            "Nominal series are converted to constant prices using deflators. Using "
            "a deflator whose basket differs from the series being deflated "
            "introduces error that grows as the two baskets drift apart, which is "
            "why base revisions matter.\n\n"
            "Double counting is avoided by deducting intermediate consumption: only "
            "the value added at each stage enters the aggregate."
        ),
        items=[
            Item(
                stem="How is GDP at market prices obtained from Gross Value Added at "
                     "basic prices?",
                options=[
                    "Add product taxes and subtract product subsidies",
                    "Subtract product taxes and add product subsidies",
                    "Add both product taxes and product subsidies",
                    "Deduct intermediate consumption a second time",
                ],
                correct_index=0,
                explanation=(
                    "Basic prices exclude taxes on products and include subsidies, so the "
                    "adjustment to market prices runs in that direction."
                ),
                quote=(
                    "Gross Domestic Product at market prices is obtained by adding "
                    "product taxes to Gross Value Added and subtracting product subsidies."
                ),
                distractor_rationale=[
                    "This reverses the adjustment",
                    "Subsidies are deducted, not added",
                    "Intermediate consumption is deducted once, in GVA",
                ],
            ),
            Item(
                stem="What does deducting intermediate consumption prevent?",
                options=[
                    "Double counting, so only value added at each stage enters the aggregate",
                    "The need for a price deflator",
                    "Differences between basic and market prices",
                    "Revision of the base year",
                ],
                correct_index=0,
                explanation=(
                    "Without the deduction, inputs bought from another industry would be "
                    "counted once in that industry's output and again in this one's."
                ),
                quote=(
                    "Double counting is avoided by deducting intermediate consumption: "
                    "only the value added at each stage enters the aggregate."
                ),
                distractor_rationale=[
                    "Deflation is a separate, price-related step",
                    "That gap is about taxes and subsidies",
                    "Base revision is about weights and reference periods",
                ],
            ),
            Item(
                stem="Why does using a mismatched deflator become more damaging over "
                     "time?",
                options=[
                    "The error grows as the two baskets drift apart",
                    "Deflators lose precision at a fixed rate each year",
                    "Nominal series are revised more often than real series",
                    "Constant-price series are unaffected by base years",
                ],
                correct_index=0,
                explanation=(
                    "A deflator built on a different basket tracks a different price "
                    "movement, and the two diverge further the longer the base is left "
                    "unrevised."
                ),
                quote=(
                    "Using a deflator whose basket differs from the series being deflated "
                    "introduces error that grows as the two baskets drift apart, which is "
                    "why base revisions matter."
                ),
                bloom="analyse",
                distractor_rationale=[
                    "There is no fixed decay rate",
                    "Revision frequency is not the mechanism",
                    "Base years are exactly what constant-price series depend on",
                ],
            ),
        ],
    ),
    Topic(
        competency_code="STAT-INDEX",
        title="Index numbers",
        passage=(
            "A Laspeyres index holds quantities at the base period and prices the "
            "same basket in the current period. Because consumers substitute away "
            "from goods that become relatively expensive, a Laspeyres index tends to "
            "overstate the rise in the cost of living.\n\n"
            "A Paasche index uses current-period quantities and, for the mirror "
            "reason, tends to understate it. A Fisher index is the geometric mean of "
            "the two.\n\n"
            "Weights become unrepresentative as consumption patterns change, which "
            "is why the base is revised periodically rather than held indefinitely."
        ),
        items=[
            Item(
                stem="Why does a Laspeyres price index tend to overstate the rise in the "
                     "cost of living?",
                options=[
                    "Consumers substitute away from goods that become relatively expensive",
                    "It uses current-period quantities throughout",
                    "It excludes services from the basket",
                    "It is a geometric rather than arithmetic mean",
                ],
                correct_index=0,
                explanation=(
                    "Holding the basket fixed keeps buying goods people have already "
                    "moved away from, so the index charges for a pattern nobody follows "
                    "any more."
                ),
                quote=(
                    "Because consumers substitute away from goods that become relatively "
                    "expensive, a Laspeyres index tends to overstate the rise in the cost "
                    "of living."
                ),
                bloom="analyse",
                distractor_rationale=[
                    "Current-period quantities define Paasche, not Laspeyres",
                    "Coverage is a separate design decision",
                    "Fisher is the geometric mean of the two",
                ],
            ),
            Item(
                stem="What is a Fisher index?",
                options=[
                    "The geometric mean of the Laspeyres and Paasche indices",
                    "A Laspeyres index with updated weights",
                    "The arithmetic average of price relatives",
                    "A chained index with annual rebasing",
                ],
                correct_index=0,
                explanation=(
                    "Sitting between the two, it splits the difference between their "
                    "opposite substitution biases."
                ),
                quote="A Fisher index is the geometric mean of the two.",
                distractor_rationale=[
                    "Reweighting a Laspeyres index does not make it Fisher",
                    "That describes a simple unweighted average",
                    "Chaining is a separate technique",
                ],
            ),
            Item(
                stem="Why is the base period of an index revised rather than held "
                     "indefinitely?",
                options=[
                    "Weights become unrepresentative as consumption patterns change",
                    "The arithmetic becomes unstable after a fixed number of periods",
                    "International guidance forbids bases older than five years",
                    "Because deflators cannot be applied to an old base",
                ],
                correct_index=0,
                explanation=(
                    "The basket is a snapshot of how people spent in the base period, and "
                    "spending moves on."
                ),
                quote=(
                    "Weights become unrepresentative as consumption patterns change, "
                    "which is why the base is revised periodically rather than held "
                    "indefinitely."
                ),
                distractor_rationale=[
                    "There is no arithmetic instability of that kind",
                    "Guidance recommends revision; it does not set that rule",
                    "Deflators work with any consistent base",
                ],
            ),
        ],
    ),
    Topic(
        competency_code="TECH-ANL",
        title="Analytics for official statistics",
        passage=(
            "A model that fits its training data closely but performs poorly on "
            "unseen data is overfitting. Holding out a test set that is never used "
            "for tuning is the basic guard against reporting a figure that will not "
            "reproduce.\n\n"
            "Correlation between two series does not establish that one causes the "
            "other, and in official statistics a spurious association reported as a "
            "finding is more costly than no finding at all.\n\n"
            "Class imbalance makes accuracy misleading: a classifier that always "
            "predicts the majority class can score highly while identifying none of "
            "the cases that matter."
        ),
        items=[
            Item(
                stem="A classifier flags fraudulent returns, which are 2% of filings, and "
                     "reports 98% accuracy. What should be checked first?",
                options=[
                    "Whether it identifies any fraudulent returns at all",
                    "Whether the training set was large enough",
                    "Whether the features were standardised",
                    "Whether the model converged",
                ],
                correct_index=0,
                explanation=(
                    "Predicting 'not fraud' every time scores 98% on this data and catches "
                    "nothing. Accuracy alone cannot distinguish that model from a useful "
                    "one, so recall on the minority class is the figure that matters."
                ),
                quote=(
                    "Class imbalance makes accuracy misleading: a classifier that always "
                    "predicts the majority class can score highly while identifying none "
                    "of the cases that matter."
                ),
                bloom="analyse",
                distractor_rationale=[
                    "Size does not change the arithmetic of the imbalance",
                    "Standardisation affects fitting, not this metric",
                    "A converged model can still be useless here",
                ],
            ),
            Item(
                stem="What is the basic guard against overfitting?",
                options=[
                    "A test set that is never used for tuning",
                    "Adding more features to the model",
                    "Increasing the number of training iterations",
                    "Reporting accuracy rather than error",
                ],
                correct_index=0,
                explanation=(
                    "Once a set has influenced any choice about the model, it can no "
                    "longer tell you how the model behaves on data it has not seen."
                ),
                quote=(
                    "Holding out a test set that is never used for tuning is the basic "
                    "guard against reporting a figure that will not reproduce."
                ),
                distractor_rationale=[
                    "More features generally worsens overfitting",
                    "More iterations fit the training data harder",
                    "The metric is not the issue",
                ],
            ),
            Item(
                stem="Two published series move together closely. What does this alone "
                     "establish?",
                options=[
                    "Nothing about one causing the other",
                    "That one causes the other with some lag",
                    "That both are driven by a common cause",
                    "That the correlation will persist",
                ],
                correct_index=0,
                explanation=(
                    "A common cause, coincidence, or reverse causation all produce the "
                    "same pattern. In official statistics the cost of publishing a "
                    "spurious association is borne by whoever acts on it."
                ),
                quote=(
                    "Correlation between two series does not establish that one causes "
                    "the other, and in official statistics a spurious association "
                    "reported as a finding is more costly than no finding at all."
                ),
                bloom="analyse",
                distractor_rationale=[
                    "Lagged correlation is still correlation",
                    "A common cause is one possibility among several",
                    "Persistence is an empirical question",
                ],
            ),
        ],
    ),
    Topic(
        competency_code="TECH-GIS",
        title="Geo-spatial data for statistics",
        passage=(
            "Comparing two spatial layers requires them to share a coordinate "
            "reference system. Overlaying layers in different projections misplaces "
            "features by distances that can exceed the size of the units being "
            "measured.\n\n"
            "Satellite imagery can reveal settlements that a census frame has "
            "missed, but built-up area is not the same as an occupied dwelling, so "
            "what imagery suggests has to be verified in the field before the frame "
            "is changed.\n\n"
            "The modifiable areal unit problem is the finding that results change "
            "when the same point data is aggregated to different boundaries."
        ),
        items=[
            Item(
                stem="Two layers are overlaid and the features do not line up. What is the "
                     "first thing to check?",
                options=[
                    "Whether the layers share a coordinate reference system",
                    "Whether the attribute tables have matching column names",
                    "Whether the imagery is recent enough",
                    "Whether the file format supports overlay",
                ],
                correct_index=0,
                explanation=(
                    "Mismatched projections displace features systematically, often by "
                    "more than the size of the units in question."
                ),
                quote=(
                    "Overlaying layers in different projections misplaces features by "
                    "distances that can exceed the size of the units being measured."
                ),
                bloom="apply",
                distractor_rationale=[
                    "Attribute names do not affect geometry",
                    "Currency matters for content, not alignment",
                    "Format rarely prevents overlay",
                ],
            ),
            Item(
                stem="Imagery shows built-up area where the frame records none. What "
                     "follows?",
                options=[
                    "It must be verified in the field before the frame is changed",
                    "The frame should be updated directly from the imagery",
                    "The area should be marked out of scope",
                    "The imagery should be reprojected and re-examined",
                ],
                correct_index=0,
                explanation=(
                    "Built-up area is not an occupied dwelling — it may be a warehouse, "
                    "a construction site or an abandoned structure. Imagery tells you "
                    "where to look, not what is there."
                ),
                quote=(
                    "built-up area is not the same as an occupied dwelling, so what "
                    "imagery suggests has to be verified in the field before the frame is "
                    "changed"
                ),
                bloom="apply",
                distractor_rationale=[
                    "This is the shortcut the passage warns against",
                    "Nothing yet shows it is out of scope",
                    "Reprojection does not answer what is on the ground",
                ],
            ),
            Item(
                stem="What is the modifiable areal unit problem?",
                options=[
                    "Results change when the same point data is aggregated to different boundaries",
                    "Boundaries drift between census rounds",
                    "Areal units cannot be compared across states",
                    "Point data cannot be aggregated without a projection",
                ],
                correct_index=0,
                explanation=(
                    "The same underlying points, grouped differently, produce different "
                    "figures — which means the choice of boundary is itself an analytical "
                    "decision to be justified."
                ),
                quote=(
                    "The modifiable areal unit problem is the finding that results change "
                    "when the same point data is aggregated to different boundaries."
                ),
                bloom="analyse",
                distractor_rationale=[
                    "Boundary change over time is a related but different issue",
                    "Comparison across states is possible with care",
                    "Projection is needed, but that is not this problem",
                ],
            ),
        ],
    ),
    Topic(
        competency_code="TECH-BIG",
        title="Large-scale data platforms",
        passage=(
            "Partitioning a large table by the column most queries filter on reduces "
            "the volume scanned, because partitions that cannot contain matching "
            "rows are skipped entirely.\n\n"
            "Administrative data arrives on the holder's schedule and in the "
            "holder's format, so a pipeline built on it needs schema checks at "
            "ingestion rather than assumptions carried from the last delivery.\n\n"
            "Reproducibility requires that a published figure can be regenerated "
            "from stored inputs and stored code, which means retaining the version "
            "of both that produced it."
        ),
        items=[
            Item(
                stem="Why does partitioning a table on the column most queries filter on "
                     "speed those queries up?",
                options=[
                    "Partitions that cannot contain matching rows are skipped entirely",
                    "Each partition is automatically indexed",
                    "It compresses the data more effectively",
                    "It moves the table into memory",
                ],
                correct_index=0,
                explanation=(
                    "The gain is from data never read. Partitioning on a column nobody "
                    "filters on gives none of it."
                ),
                quote=(
                    "Partitioning a large table by the column most queries filter on "
                    "reduces the volume scanned, because partitions that cannot contain "
                    "matching rows are skipped entirely."
                ),
                bloom="apply",
                distractor_rationale=[
                    "Indexing is a separate mechanism",
                    "Compression is unrelated to partition pruning",
                    "Partitioning does not imply caching",
                ],
            ),
            Item(
                stem="Why does a pipeline built on administrative data need schema checks "
                     "at ingestion?",
                options=[
                    "It arrives on the holder's schedule and in the holder's format",
                    "Administrative data is always larger than survey data",
                    "Schema checks are required before any statistical estimation",
                    "It removes the need for a sampling frame",
                ],
                correct_index=0,
                explanation=(
                    "You do not control the source. A column silently renamed upstream "
                    "will otherwise surface as a wrong published figure rather than an "
                    "ingestion failure."
                ),
                quote=(
                    "Administrative data arrives on the holder's schedule and in the "
                    "holder's format, so a pipeline built on it needs schema checks at "
                    "ingestion rather than assumptions carried from the last delivery."
                ),
                bloom="analyse",
                distractor_rationale=[
                    "Size is not the reason",
                    "This overstates a general rule",
                    "Frames and admin data are different concerns",
                ],
            ),
            Item(
                stem="What does reproducing a published figure require?",
                options=[
                    "The stored version of both the inputs and the code that produced it",
                    "The final output file and its checksum",
                    "A description of the method in the release note",
                    "Access to the original analyst",
                ],
                correct_index=0,
                explanation=(
                    "Code alone regenerates nothing without its inputs, and inputs alone "
                    "leave the transformations unspecified."
                ),
                quote=(
                    "Reproducibility requires that a published figure can be regenerated "
                    "from stored inputs and stored code, which means retaining the "
                    "version of both that produced it."
                ),
                distractor_rationale=[
                    "A checksum proves integrity, not derivation",
                    "A prose description is rarely sufficient to regenerate",
                    "Reproducibility must not depend on one person",
                ],
            ),
        ],
    ),
    Topic(
        competency_code="TECH-VIZ",
        title="Presenting statistics",
        passage=(
            "A bar chart whose value axis does not begin at zero exaggerates "
            "differences between the bars, because the reader compares bar lengths "
            "and those lengths no longer stand in proportion to the values.\n\n"
            "Colour alone should never be the only channel carrying meaning, since "
            "readers with colour vision deficiency lose the distinction entirely. "
            "Pairing colour with a label, a shape or a position keeps the chart "
            "readable.\n\n"
            "A chart of estimates without any indication of uncertainty invites the "
            "reader to treat small differences as real."
        ),
        items=[
            Item(
                stem="Why is a truncated value axis a problem specifically for bar charts?",
                options=[
                    "Readers compare bar lengths, which no longer stand in proportion to the values",
                    "Bars cannot be drawn below the axis minimum",
                    "It makes the gridlines uneven",
                    "Bar charts require a linear scale by convention",
                ],
                correct_index=0,
                explanation=(
                    "The bar encodes value as length from zero. Move the baseline and the "
                    "encoding no longer means what the reader assumes."
                ),
                quote=(
                    "A bar chart whose value axis does not begin at zero exaggerates "
                    "differences between the bars, because the reader compares bar "
                    "lengths and those lengths no longer stand in proportion to the values."
                ),
                bloom="analyse",
                distractor_rationale=[
                    "They can, and that is a separate issue",
                    "Gridlines are cosmetic here",
                    "Convention is not the mechanism",
                ],
            ),
            Item(
                stem="A chart distinguishes four categories by colour only. What is the "
                     "accessibility problem?",
                options=[
                    "Readers with colour vision deficiency lose the distinction entirely",
                    "Four categories exceed the recommended maximum",
                    "Colour printing costs more",
                    "Colours render differently on different screens",
                ],
                correct_index=0,
                explanation=(
                    "Around one in twelve men has some colour vision deficiency. Adding a "
                    "label, shape or position keeps the chart readable for them without "
                    "harming anyone else."
                ),
                quote=(
                    "Colour alone should never be the only channel carrying meaning, "
                    "since readers with colour vision deficiency lose the distinction "
                    "entirely."
                ),
                bloom="apply",
                distractor_rationale=[
                    "There is no such fixed maximum",
                    "Cost is not an accessibility argument",
                    "Rendering variation is a lesser, separate concern",
                ],
            ),
            Item(
                stem="What does omitting uncertainty from a chart of estimates encourage?",
                options=[
                    "Treating small differences as real",
                    "Overestimating the sample size",
                    "Confusing the axis units",
                    "Assuming the series is seasonally adjusted",
                ],
                correct_index=0,
                explanation=(
                    "Two bars of visibly different height read as different, whether or "
                    "not the difference exceeds sampling error."
                ),
                quote=(
                    "A chart of estimates without any indication of uncertainty invites "
                    "the reader to treat small differences as real."
                ),
                distractor_rationale=[
                    "Sample size is not conveyed either way",
                    "Units are a labelling matter",
                    "Adjustment is a separate disclosure",
                ],
            ),
        ],
    ),
    Topic(
        competency_code="DG-QUAL",
        title="Data quality assurance",
        passage=(
            "Validation rules are most useful at the point of collection, because a "
            "value corrected by the enumerator while still in the field costs far "
            "less than the same value queried months later in the office.\n\n"
            "An outlier is not automatically an error. Deleting values because they "
            "are extreme removes exactly the units that a survey of establishments "
            "most needs to capture, so treatment has to be justified and recorded.\n\n"
            "A quality report accompanying a release should state the response rate, "
            "the coverage of the frame and the revision policy, so that a user can "
            "judge fitness for their own purpose rather than assuming it."
        ),
        items=[
            Item(
                stem="Why are validation rules most useful at the point of collection?",
                options=[
                    "A value corrected in the field costs far less than one queried months later",
                    "Field staff are more accurate than office staff",
                    "Office systems cannot run validation rules",
                    "It removes the need for a quality report",
                ],
                correct_index=0,
                explanation=(
                    "The respondent is still present and the answer is still known. "
                    "Afterwards, the same query means a callback or an imputation."
                ),
                quote=(
                    "Validation rules are most useful at the point of collection, because "
                    "a value corrected by the enumerator while still in the field costs "
                    "far less than the same value queried months later in the office."
                ),
                bloom="apply",
                distractor_rationale=[
                    "Not a claim about staff accuracy",
                    "They can, just later and at higher cost",
                    "The quality report serves a different purpose",
                ],
            ),
            Item(
                stem="An establishment survey finds one firm reporting turnover ten times "
                     "the next largest. What is the correct first step?",
                options=[
                    "Investigate and record the treatment, since an outlier is not automatically an error",
                    "Delete the value as an obvious error",
                    "Cap the value at the second largest",
                    "Exclude the firm from the frame in future rounds",
                ],
                correct_index=0,
                explanation=(
                    "In establishment surveys the largest units often genuinely are that "
                    "large, and they carry most of the total. Removing them because they "
                    "are extreme biases the aggregate downward."
                ),
                quote=(
                    "Deleting values because they are extreme removes exactly the units "
                    "that a survey of establishments most needs to capture, so treatment "
                    "has to be justified and recorded."
                ),
                bloom="analyse",
                distractor_rationale=[
                    "This is the error the passage warns against",
                    "Capping is a treatment that still needs justification",
                    "Frame exclusion compounds the problem",
                ],
            ),
            Item(
                stem="What should a quality report accompanying a release state?",
                options=[
                    "Response rate, frame coverage and revision policy",
                    "The names of the analysts responsible",
                    "The full microdata underlying the estimates",
                    "Only figures that met the target quality threshold",
                ],
                correct_index=0,
                explanation=(
                    "These let a user judge fitness for their own purpose, which is not "
                    "something the producer can decide on their behalf."
                ),
                quote=(
                    "A quality report accompanying a release should state the response "
                    "rate, the coverage of the frame and the revision policy, so that a "
                    "user can judge fitness for their own purpose rather than assuming it."
                ),
                distractor_rationale=[
                    "Attribution is not a quality measure",
                    "Microdata release is governed separately by confidentiality",
                    "Suppressing figures that missed a threshold hides the problem",
                ],
            ),
        ],
    ),
    Topic(
        competency_code="DG-PRIV",
        title="Confidentiality and disclosure control",
        passage=(
            "Statistical disclosure control protects respondents by ensuring that no "
            "published figure allows an individual or establishment to be identified. "
            "A cell built from very few units is suppressed, because the "
            "contributors can often work out one another's values.\n\n"
            "Suppressing one cell is not enough on its own: if the row and column "
            "totals remain, the suppressed value can be recovered by subtraction, so "
            "secondary suppression is applied as well.\n\n"
            "Removing names and identifiers does not by itself make a dataset "
            "anonymous, because combinations of ordinary attributes can single a "
            "person out."
        ),
        items=[
            Item(
                stem="A table suppresses one cell but publishes all row and column totals. "
                     "What is wrong?",
                options=[
                    "The suppressed value can be recovered by subtraction",
                    "Totals should never be published in official tables",
                    "The suppression threshold was set too low",
                    "Nothing, provided the cell had fewer than three units",
                ],
                correct_index=0,
                explanation=(
                    "One unknown in an equation with a known total is not unknown. "
                    "Secondary suppression removes enough further cells to leave the "
                    "value genuinely underdetermined."
                ),
                quote=(
                    "if the row and column totals remain, the suppressed value can be "
                    "recovered by subtraction, so secondary suppression is applied as well"
                ),
                bloom="analyse",
                distractor_rationale=[
                    "Totals are normally published",
                    "The threshold is not the failure here",
                    "The threshold does not prevent recovery",
                ],
            ),
            Item(
                stem="Why is removing names and identifiers insufficient to anonymise a "
                     "dataset?",
                options=[
                    "Combinations of ordinary attributes can single a person out",
                    "Identifiers can be recovered from backups",
                    "The data controller retains a mapping table",
                    "Anonymisation requires encryption of every field",
                ],
                correct_index=0,
                explanation=(
                    "Age, district, occupation and household size together often describe "
                    "exactly one person, without any name being present."
                ),
                quote=(
                    "Removing names and identifiers does not by itself make a dataset "
                    "anonymous, because combinations of ordinary attributes can single a "
                    "person out."
                ),
                bloom="analyse",
                distractor_rationale=[
                    "Backups are an access-control question",
                    "A mapping table describes pseudonymisation",
                    "Encryption protects storage, not published output",
                ],
            ),
            Item(
                stem="Why is a cell built from very few units suppressed?",
                options=[
                    "The contributors can often work out one another's values",
                    "Small cells are statistically unreliable",
                    "The estimate would have a wide confidence interval",
                    "Small cells cannot be weighted correctly",
                ],
                correct_index=0,
                explanation=(
                    "With two contributors, each knows the total and their own value, so "
                    "each learns the other's. That is a disclosure, not an imprecision."
                ),
                quote=(
                    "A cell built from very few units is suppressed, because the "
                    "contributors can often work out one another's values."
                ),
                bloom="analyse",
                distractor_rationale=[
                    "Reliability is a real but different concern",
                    "Precision is not why disclosure control acts",
                    "Weighting is unrelated to suppression",
                ],
            ),
        ],
    ),
    Topic(
        competency_code="BEH-COMM",
        title="Communicating statistics",
        passage=(
            "A statistical release should lead with what changed and what it means, "
            "before the methodology that supports it. A reader who has to reach "
            "paragraph nine to learn the headline has usually stopped reading.\n\n"
            "Technical terms should be defined at first use when writing for a "
            "general audience. Terms such as seasonally adjusted or provisional carry "
            "specific meanings that a non-specialist will otherwise guess at.\n\n"
            "Where an estimate is revised, saying plainly what changed and why "
            "protects confidence better than presenting the revised figure alone."
        ),
        items=[
            Item(
                stem="A release opens with three paragraphs of methodology before the "
                     "headline figure. What is the main problem?",
                options=[
                    "A reader who reaches the headline at paragraph nine has usually stopped reading",
                    "Methodology should not appear in a public release",
                    "It makes the release longer than the guidance permits",
                    "Journalists are not interested in methodology",
                ],
                correct_index=0,
                explanation=(
                    "The methodology matters and belongs in the release. Ordering it first "
                    "means the people it was written for never see the finding."
                ),
                quote=(
                    "A reader who has to reach paragraph nine to learn the headline has "
                    "usually stopped reading."
                ),
                bloom="apply",
                distractor_rationale=[
                    "It should appear, just not first",
                    "Length is not the issue",
                    "Some are; the ordering is still wrong",
                ],
            ),
            Item(
                stem="Why should a term like 'seasonally adjusted' be defined at first use "
                     "for a general audience?",
                options=[
                    "It carries a specific meaning a non-specialist will otherwise guess at",
                    "It is a recent addition to statistical vocabulary",
                    "Its definition varies between countries",
                    "Undefined terms are prohibited in official releases",
                ],
                correct_index=0,
                explanation=(
                    "A reader who guesses wrongly draws a wrong conclusion from a correct "
                    "figure, which is the failure mode a definition prevents."
                ),
                quote=(
                    "Terms such as seasonally adjusted or provisional carry specific "
                    "meanings that a non-specialist will otherwise guess at."
                ),
                distractor_rationale=[
                    "It is long established",
                    "The concept is standard internationally",
                    "There is no such prohibition",
                ],
            ),
            Item(
                stem="An estimate is revised between releases. What best protects "
                     "confidence in the series?",
                options=[
                    "Saying plainly what changed and why",
                    "Publishing the revised figure without comment",
                    "Delaying publication until revisions are unlikely",
                    "Presenting only the range spanned by both figures",
                ],
                correct_index=0,
                explanation=(
                    "Revision is normal and expected. A revision that appears without "
                    "explanation is what invites the suspicion that something was wrong."
                ),
                quote=(
                    "Where an estimate is revised, saying plainly what changed and why "
                    "protects confidence better than presenting the revised figure alone."
                ),
                bloom="analyse",
                distractor_rationale=[
                    "This is the approach the passage contrasts against",
                    "Delay trades timeliness for a false impression of stability",
                    "A range obscures rather than explains",
                ],
            ),
        ],
    ),
    Topic(
        competency_code="BEH-LEAD",
        title="Leading statistical teams",
        passage=(
            "Delegation means handing over the decision along with the task. "
            "Assigning work while retaining every decision produces a bottleneck at "
            "the supervisor and teaches the team nothing.\n\n"
            "Where two officers disagree on method, the disagreement is resolved "
            "faster by making the criteria explicit than by seniority, because "
            "criteria can be checked against the evidence and seniority cannot.\n\n"
            "A deadline that cannot be met is best escalated as early as it is known, "
            "with the options and their consequences set out, rather than reported "
            "once it has passed."
        ),
        items=[
            Item(
                stem="A supervisor assigns tasks but keeps every decision. What does the "
                     "passage identify as the consequence?",
                options=[
                    "A bottleneck at the supervisor, and a team that learns nothing",
                    "Faster delivery at the cost of quality",
                    "Better consistency across the division",
                    "Reduced need for escalation",
                ],
                correct_index=0,
                explanation=(
                    "Every decision queues behind one person, and nobody else develops "
                    "the judgement to take those decisions later."
                ),
                quote=(
                    "Assigning work while retaining every decision produces a bottleneck "
                    "at the supervisor and teaches the team nothing."
                ),
                bloom="analyse",
                distractor_rationale=[
                    "It is usually slower, not faster",
                    "Consistency does not offset the bottleneck",
                    "Escalation tends to increase",
                ],
            ),
            Item(
                stem="Two officers disagree about which method to use. What resolves it "
                     "fastest?",
                options=[
                    "Making the criteria explicit, because criteria can be checked against evidence",
                    "A decision by the senior of the two",
                    "Adopting whichever method was used last time",
                    "Escalating to the division head",
                ],
                correct_index=0,
                explanation=(
                    "Once the criteria are stated, the disagreement becomes a question "
                    "the evidence can answer, and the answer holds next time too."
                ),
                quote=(
                    "the disagreement is resolved faster by making the criteria explicit "
                    "than by seniority, because criteria can be checked against the "
                    "evidence and seniority cannot"
                ),
                bloom="apply",
                distractor_rationale=[
                    "Seniority settles who decides, not what is right",
                    "Precedent may itself have been wrong",
                    "Escalation defers rather than resolves",
                ],
            ),
            Item(
                stem="A release deadline will clearly be missed. When should it be "
                     "escalated?",
                options=[
                    "As early as it is known, with options and consequences set out",
                    "Once the deadline has passed and the position is certain",
                    "At the next scheduled review meeting",
                    "Only if the delay exceeds a week",
                ],
                correct_index=0,
                explanation=(
                    "Early escalation leaves choices open. Reporting after the fact "
                    "removes every option except explaining the failure."
                ),
                quote=(
                    "A deadline that cannot be met is best escalated as early as it is "
                    "known, with the options and their consequences set out, rather than "
                    "reported once it has passed."
                ),
                bloom="apply",
                distractor_rationale=[
                    "By then the choices have gone",
                    "The schedule should not dictate the timing",
                    "No threshold justifies waiting",
                ],
            ),
        ],
    ),
]


def seed_cited_quiz_bank(db: Session, competencies: dict, reviewer_id: int | None = None) -> int:
    """Create the starter item bank. Returns how many items were approved.

    `competencies` maps competency code to the ORM object, as `build_framework`
    returns it.
    """
    approved = 0
    rejected = 0

    for topic in TOPICS:
        competency = competencies.get(topic.competency_code)
        if competency is None:
            log.warning("No competency %s; skipping its items", topic.competency_code)
            continue

        material = Material(
            title=topic.title,
            filename=f"seed-{topic.competency_code.lower()}.txt",
            content_type="text/plain",
            competency_id=competency.id,
            uploaded_by_id=reviewer_id,
            status=MaterialStatus.READY,
            page_count=1,
            char_count=len(topic.passage),
        )
        db.add(material)
        db.flush()

        chunk = MaterialChunk(
            material_id=material.id,
            ordinal=0,
            page=1,
            text=topic.passage,
        )
        db.add(chunk)
        db.flush()

        for item in topic.items:
            # The real check, against the real chunk. If a quote here drifts out
            # of step with its passage, the item is dropped rather than seeded —
            # this file cannot smuggle in an item the platform would reject.
            check = verify_citation(chunk.text, item.quote)
            if not check:
                rejected += 1
                log.warning(
                    "Seed item rejected for %s: %s — %r",
                    topic.competency_code, check.reason, item.stem[:60],
                )
                continue

            db.add(GeneratedQuestion(
                material_id=material.id,
                competency_id=competency.id,
                stem=item.stem,
                options=item.options,
                correct_index=item.correct_index,
                explanation=item.explanation,
                distractor_rationale=item.distractor_rationale or None,
                bloom_level=item.bloom,
                citation_chunk_id=chunk.id,
                citation_quote=item.quote,
                citation_page=1,
                status=QuestionStatus.APPROVED,
                reviewed_by_id=reviewer_id,
                review_note=(
                    "Seeded demonstration item. Written for the seed data, not "
                    "reviewed by a subject-matter expert — replace before this "
                    "platform assesses anyone real."
                ),
            ))
            approved += 1

    db.flush()
    if rejected:
        log.warning("%d seed items failed citation verification and were dropped", rejected)
    return approved
