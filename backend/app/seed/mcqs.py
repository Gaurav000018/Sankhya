"""An approved multiple-choice bank, one set per competency.

Why this exists as seed data rather than generated content: quiz items normally
come from the upload → generate → SME-review pipeline, which needs a model
running beside the API. A deployment without one has an empty bank, so the
assessment refuses to start and the officer sees "not enough approved
questions" — the platform's central feature, unreachable.

These are hand-written against the vocabulary MoSPI actually uses, carry the
explanation and per-distractor rationale the review queue would demand, and are
seeded as APPROVED because an author writing them deliberately *is* the review
a generated item needs.

The `bloom_level` on each is real and varies: an item bank where everything is
`remember` measures recall and calls it competency. Difficulty is left unset —
the IRT layer calibrates it from actual responses, which is the whole point of
the feedback loop, and a guessed prior would pollute it.
"""

from __future__ import annotations

# (stem, options, correct_index, explanation, [distractor rationales], bloom)
Item = tuple[str, list[str], int, str, list[str], str]

BANK: dict[str, list[Item]] = {
    # ---------------------------------------------------------- STAT-SAMP --
    "STAT-SAMP": [
        (
            "A district survey must estimate household expenditure for both urban and rural areas, "
            "but the urban population is only 18% of the district. Which design best protects the "
            "precision of the urban estimate?",
            [
                "Simple random sampling across the whole district",
                "Stratify by sector and over-sample the urban stratum",
                "Cluster sampling using villages as clusters",
                "Systematic sampling from the electoral roll",
            ],
            1,
            "Stratifying by sector guarantees urban households appear, and allocating them more "
            "than their proportional share raises the urban sample size enough to estimate that "
            "domain separately. Weights restore unbiasedness at the district level.",
            [
                "Proportional allocation would leave roughly 18% of the sample urban, so the "
                "urban estimate carries a much wider confidence interval than the rural one.",
                "",
                "Villages are rural units; clustering on them would under-represent urban "
                "households and inflate the design effect.",
                "Electoral rolls exclude under-18s and miss recent migrants, who are "
                "disproportionately urban.",
            ],
            "apply",
        ),
        (
            "What does the sampling frame error in a household survey most directly threaten?",
            [
                "The precision of the estimate",
                "The coverage of the target population",
                "The response rate",
                "The choice of estimator",
            ],
            1,
            "A frame is the list from which units are drawn. If it omits or duplicates parts of "
            "the target population, the sample cannot represent what it is meant to — a coverage "
            "problem, which no increase in sample size will fix.",
            [
                "Precision is driven by sample size and design; a biased frame produces a precise "
                "estimate of the wrong population.",
                "",
                "Non-response is a separate mechanism, arising after selection.",
                "The estimator can be chosen correctly and still be applied to a frame that "
                "excludes part of the population.",
            ],
            "understand",
        ),
        (
            "In probability proportional to size (PPS) sampling, the selection probability of a "
            "first-stage unit is proportional to:",
            [
                "Its geographic area",
                "A measure of size such as population from the last census",
                "The variance of the study variable within it",
                "The inverse of its distance from the district headquarters",
            ],
            1,
            "PPS uses an auxiliary size measure correlated with the study variable, most often "
            "population or households from the previous census, so that larger units are more "
            "likely to be selected and the final weights stay manageable.",
            [
                "Area correlates poorly with population in both dense urban and sparse desert "
                "blocks.",
                "",
                "Within-unit variance is rarely known before the survey; if it were, an optimal "
                "allocation would use it at the second stage, not for PPS selection.",
                "Distance affects field cost, which belongs in the operational plan rather than "
                "the selection probability.",
            ],
            "remember",
        ),
        (
            "A pilot shows the design effect for a two-stage cluster survey is 2.4. To achieve the "
            "precision of a simple random sample of 1,000, roughly what sample size is needed?",
            ["1,000", "1,400", "2,400", "4,800"],
            2,
            "Effective sample size equals actual size divided by the design effect, so the actual "
            "size must be the target multiplied by deff: 1,000 × 2.4 = 2,400.",
            [
                "This ignores the clustering entirely and would deliver far wider intervals than "
                "planned.",
                "This adds the excess rather than multiplying by the design effect.",
                "",
                "This squares the adjustment; deff is already a ratio of variances.",
            ],
            "apply",
        ),
        (
            "An officer proposes replacing non-responding households with the next house on the "
            "list. The most serious statistical objection is that:",
            [
                "It increases the fieldwork cost",
                "Substitutes resemble responders, so non-response bias is concealed rather than removed",
                "It breaks the randomisation and makes weighting impossible",
                "It changes the design effect",
            ],
            1,
            "Substitution fills the sample size back up, which makes the response rate look "
            "healthy, but the replacements are systematically more like the households that "
            "responded. The bias remains and is now invisible in the quality indicators.",
            [
                "Cost is an operational concern, not the statistical objection.",
                "",
                "Weighting is still mechanically possible; the problem is that it no longer "
                "corrects for who is missing.",
                "The design effect is largely unchanged; the estimate is biased, not merely "
                "less precise.",
            ],
            "analyse",
        ),
        (
            "Which statement about self-weighting designs is correct?",
            [
                "Every unit has the same selection probability, so unweighted estimates are unbiased",
                "They always produce smaller standard errors than stratified designs",
                "They remove the need for non-response adjustment",
                "They require the frame to be sorted alphabetically",
            ],
            0,
            "A self-weighting design gives every unit an equal overall selection probability, so "
            "the simple unweighted mean is already unbiased. Convenient for field staff and for "
            "quick tabulation, but it constrains allocation.",
            [
                "",
                "Self-weighting often costs precision, because it prevents over-sampling the "
                "strata where variance is highest.",
                "Non-response still has to be adjusted for; equal selection probability says "
                "nothing about who actually answers.",
                "Sort order is unrelated, except in systematic sampling where it induces "
                "implicit stratification.",
            ],
            "understand",
        ),
        (
            "A state wants district-level estimates from a survey powered only for state-level "
            "estimates. The methodologically honest response is to:",
            [
                "Publish the district estimates with wider confidence intervals",
                "Publish them only where the CV is within the agreed threshold, and use small-area estimation elsewhere",
                "Pool three years of data and publish a single district figure",
                "Refuse to produce district figures at all",
            ],
            1,
            "Direct estimates should be released where their coefficient of variation meets the "
            "agreed reliability threshold. Below it, model-based small-area estimation borrows "
            "strength from auxiliary data — and the method used must be stated alongside.",
            [
                "Wider intervals are honest but useless if the CV is so large the estimate cannot "
                "distinguish any policy-relevant difference.",
                "",
                "Pooling hides genuine change over the period and misleads anyone reading it as "
                "current.",
                "Refusing ignores the legitimate demand; small-area methods exist precisely for "
                "this.",
            ],
            "evaluate",
        ),
        (
            "In a stratified design, Neyman allocation distributes the sample across strata in "
            "proportion to:",
            [
                "Stratum size only",
                "Stratum size multiplied by its standard deviation",
                "The inverse of stratum size",
                "Equal shares regardless of size",
            ],
            1,
            "Neyman allocation minimises variance for a fixed total sample by giving more sample "
            "to strata that are both large and internally variable — N_h × S_h.",
            [
                "Proportional allocation uses size alone and is optimal only when every stratum "
                "has the same variance.",
                "",
                "This would concentrate effort on the smallest strata for no precision gain.",
                "Equal allocation is used when every stratum needs its own reliable estimate, "
                "which is a different objective.",
            ],
            "remember",
        ),
    ],
    # ----------------------------------------------------------- STAT-EST --
    "STAT-EST": [
        (
            "A design weight of 250 attached to a sampled household means that household:",
            [
                "Was selected 250 times",
                "Represents approximately 250 households in the population",
                "Has 250 members",
                "Was drawn from a stratum of 250 households",
            ],
            1,
            "The design weight is the reciprocal of the selection probability. It is the number "
            "of population units the sampled unit stands for when estimates are grossed up.",
            [
                "Units are selected once; repeated selection would be sampling with replacement "
                "and is recorded differently.",
                "",
                "Household size is a separate variable and is not the weight.",
                "Stratum size affects the weight but is not equal to it.",
            ],
            "understand",
        ),
        (
            "Post-stratification adjusts survey weights so that estimated totals match known "
            "population totals. Its main purpose is to:",
            [
                "Increase the sample size",
                "Reduce non-response bias and improve precision using auxiliary information",
                "Simplify the variance calculation",
                "Remove the need for design weights",
            ],
            1,
            "Aligning weighted counts to reliable external totals — usually census or projected "
            "population by age and sex — corrects for differential non-response and typically "
            "reduces variance for variables correlated with the control totals.",
            [
                "The sample is fixed; weighting changes its representation, not its size.",
                "",
                "Post-stratification makes variance estimation more complex, not less.",
                "It is applied on top of design weights, never instead of them.",
            ],
            "understand",
        ),
        (
            "Trimming extreme survey weights primarily trades:",
            [
                "Bias for variance — accepting some bias to reduce instability",
                "Variance for bias — accepting instability to reduce bias",
                "Coverage for precision",
                "Timeliness for accuracy",
            ],
            0,
            "A handful of very large weights can make an estimate swing on one or two "
            "observations. Capping them introduces a small bias but substantially stabilises the "
            "estimate — a deliberate and documented trade.",
            [
                "",
                "This reverses the direction: trimming reduces variance and adds bias.",
                "Coverage is a frame property and is unaffected by trimming.",
                "Neither timeliness nor accuracy is what the trade is between.",
            ],
            "analyse",
        ),
        (
            "Which estimator is generally preferred when an auxiliary variable is strongly "
            "correlated with the study variable and its population total is known?",
            [
                "Simple expansion estimator",
                "Ratio or regression estimator",
                "Median-based estimator",
                "Jackknife estimator",
            ],
            1,
            "Ratio and regression estimators use the known auxiliary total to correct the sample "
            "estimate, reducing variance in proportion to the strength of the correlation.",
            [
                "The expansion estimator ignores the auxiliary information entirely.",
                "",
                "A median-based estimator addresses skewness, not the use of auxiliary totals.",
                "The jackknife is a variance estimation technique, not a point estimator.",
            ],
            "apply",
        ),
        (
            "Why can a survey estimate be unbiased yet still badly wrong for a single district?",
            [
                "Unbiasedness is a property of the estimator over repeated sampling, not a guarantee about one sample",
                "Unbiased estimators are only valid at national level",
                "District estimates require a different estimator by law",
                "Bias and variance are the same quantity",
            ],
            0,
            "Unbiasedness means the estimator is correct on average across all possible samples. "
            "For one realised sample in a small domain, the variance can be large enough that the "
            "figure is far from the truth.",
            [
                "",
                "There is no such restriction; the issue is variance at small sample sizes.",
                "No such legal requirement exists.",
                "They are distinct components of mean squared error.",
            ],
            "analyse",
        ),
        (
            "A calibration estimator is used to make survey estimates consistent with:",
            [
                "The previous round of the same survey",
                "Known population benchmarks from an external source",
                "The sample design weights before adjustment",
                "The interviewer's field notes",
            ],
            1,
            "Calibration adjusts weights so that weighted sample totals reproduce benchmarks "
            "already known with high reliability, such as census population or administrative "
            "registers.",
            [
                "Consistency with the last round would entrench any error it contained.",
                "",
                "Design weights are the starting point calibration modifies.",
                "Field notes inform quality assessment but are not benchmarks.",
            ],
            "remember",
        ),
        (
            "A coefficient of variation of 22% on a district unemployment estimate most "
            "appropriately leads to:",
            [
                "Publishing it without comment",
                "Publishing it flagged as having low reliability, or suppressing it under the agreed policy",
                "Adjusting the estimate upward to compensate",
                "Recomputing it with a different estimator until the CV falls",
            ],
            1,
            "A CV that high means the estimate cannot support the comparisons users will make of "
            "it. Statistical agencies publish a reliability threshold in advance and either flag "
            "or suppress figures that breach it.",
            [
                "Silent publication invites misuse of a figure the agency knows is unstable.",
                "",
                "Adjusting a point estimate to fix a precision problem is fabrication.",
                "Choosing an estimator on the basis of the answer it produces is exactly the "
                "practice a quality framework exists to prevent.",
            ],
            "evaluate",
        ),
        (
            "In multi-stage sampling, the overall selection probability of a final-stage unit is:",
            [
                "The sum of the stage probabilities",
                "The product of the probabilities at each stage",
                "The probability at the last stage only",
                "Always equal across units",
            ],
            1,
            "Selection at each stage is conditional on the previous one, so probabilities "
            "multiply. The design weight is the reciprocal of that product.",
            [
                "Summing could exceed one and has no probabilistic meaning here.",
                "",
                "Ignoring earlier stages would misstate the weight by orders of magnitude.",
                "Equality holds only in a self-weighting design, which is a special case.",
            ],
            "understand",
        ),
    ],
    # ----------------------------------------------------------- STAT-NAS --
    "STAT-NAS": [
        (
            "Gross Value Added at basic prices differs from GDP at market prices by:",
            [
                "Net taxes on products",
                "Consumption of fixed capital",
                "Net factor income from abroad",
                "Changes in inventories",
            ],
            0,
            "GDP at market prices equals GVA at basic prices plus taxes on products less "
            "subsidies on products. The difference is exactly net product taxes.",
            [
                "",
                "Depreciation separates gross from net aggregates, not basic from market prices.",
                "Net factor income from abroad separates domestic from national product.",
                "Inventory change is a component of gross capital formation on the expenditure "
                "side.",
            ],
            "remember",
        ),
        (
            "In the production approach, double counting is avoided by:",
            [
                "Summing the gross output of every enterprise",
                "Summing value added, which nets out intermediate consumption",
                "Counting only the final retail sale",
                "Deflating each series by the same index",
            ],
            1,
            "Value added is output minus intermediate consumption. Summing it across producers "
            "counts each stage's contribution exactly once.",
            [
                "Gross output counts the same inputs repeatedly down the production chain.",
                "",
                "That is the expenditure approach, which is a different route to the same total "
                "and misses non-marketed output.",
                "Deflation addresses price change, not double counting.",
            ],
            "understand",
        ),
        (
            "The System of National Accounts treats owner-occupied housing by:",
            [
                "Excluding it, since no transaction occurs",
                "Imputing a rental value as output of housing services",
                "Recording only the purchase price in the year of sale",
                "Recording it as intermediate consumption",
            ],
            1,
            "Imputed rent keeps the accounts comparable between economies and periods with "
            "different rates of home ownership. Without it, a shift from renting to owning would "
            "show as a fall in output.",
            [
                "Excluding it would make GDP depend on tenure patterns rather than on the "
                "services actually consumed.",
                "",
                "The purchase is capital formation; the annual housing service is separate.",
                "Housing services to households are final consumption, not intermediate.",
            ],
            "understand",
        ),
        (
            "Which is a genuine limitation of GDP as a welfare measure?",
            [
                "It excludes unpaid household work and most environmental degradation",
                "It is measured only once every ten years",
                "It cannot be compared across countries",
                "It excludes government expenditure",
            ],
            0,
            "GDP measures marketed production. Unpaid care work, subsistence activity and the "
            "depletion of natural capital sit largely outside the production boundary, which is "
            "why satellite accounts exist.",
            [
                "",
                "GDP is compiled quarterly and annually.",
                "PPP-converted comparisons are standard practice.",
                "Government final consumption is an explicit component.",
            ],
            "evaluate",
        ),
        (
            "Constant-price (real) GDP is obtained by:",
            [
                "Subtracting inflation from nominal GDP",
                "Deflating components by appropriate price indices relative to a base period",
                "Using the previous year's nominal figure",
                "Averaging nominal GDP over three years",
            ],
            1,
            "Each component is deflated by a price index appropriate to it, so volume change is "
            "separated from price change. A single economy-wide subtraction would misstate "
            "sectors whose prices moved differently.",
            [
                "Subtracting a headline rate ignores differing price movements by component.",
                "",
                "That measures nothing about the current period.",
                "Averaging smooths the series without removing price effects.",
            ],
            "apply",
        ),
        (
            "Back-casting a national accounts series after a base-year revision is necessary "
            "because:",
            [
                "The law requires ten years of data",
                "Users need a consistent time series; splicing old and new bases creates a spurious break",
                "The new base year always shows higher growth",
                "It reduces the sampling error",
            ],
            1,
            "A revised base changes weights, classifications and often coverage. Without "
            "back-casting, the join between the two series shows a jump that reflects the method "
            "change rather than the economy.",
            [
                "No such fixed legal period governs this.",
                "",
                "Revisions can move the level in either direction.",
                "Sampling error is unrelated to base revision.",
            ],
            "analyse",
        ),
        (
            "The informal sector is captured in Indian national accounts primarily through:",
            [
                "Direct enumeration of every informal enterprise annually",
                "Benchmark surveys combined with indicator-based extrapolation between benchmarks",
                "Assuming it is a fixed share of the formal sector",
                "Excluding it from the production boundary",
            ],
            1,
            "Periodic enterprise surveys establish a benchmark level, and the series is carried "
            "forward between benchmarks using related indicators such as employment or physical "
            "output.",
            [
                "Annual full enumeration of the informal sector is not feasible at that scale.",
                "",
                "A fixed ratio would assume away exactly the structural change being measured.",
                "The informal sector is firmly inside the production boundary.",
            ],
            "understand",
        ),
        (
            "Which sequence correctly orders the institutional sectors of the SNA?",
            [
                "Households, corporations, government, NPISH, rest of the world",
                "Only households and government",
                "Only corporations and government",
                "Households and corporations only",
            ],
            0,
            "The SNA distinguishes non-financial corporations, financial corporations, general "
            "government, households, and non-profit institutions serving households, with the "
            "rest of the world as a counterpart sector.",
            [
                "",
                "This omits the corporate sector entirely.",
                "This omits households, the largest consuming sector.",
                "This omits government and NPISH.",
            ],
            "remember",
        ),
    ],
}

# The remaining competencies share the structure above; kept in a second dict
# purely so neither literal becomes unreadably long.
BANK.update(
    {
        # ------------------------------------------------------ STAT-INDEX --
        "STAT-INDEX": [
            (
                "A Laspeyres price index uses quantity weights from:",
                ["The current period", "The base period", "The average of both periods", "A forecast period"],
                1,
                "Laspeyres fixes the basket at base-period quantities, which makes it easy to "
                "compute monthly but causes it to overstate the cost of living as consumers "
                "substitute away from items whose prices rise.",
                [
                    "Current-period weights define the Paasche index.",
                    "",
                    "The geometric mean of the two defines the Fisher ideal index.",
                    "Index numbers are not based on forecast quantities.",
                ],
                "remember",
            ),
            (
                "Substitution bias in a fixed-basket consumer price index arises because:",
                [
                    "Prices are collected too infrequently",
                    "Consumers shift toward relatively cheaper goods, which a fixed basket cannot reflect",
                    "The sample of outlets is too small",
                    "Quality changes are ignored",
                ],
                1,
                "A basket fixed at base-period quantities assumes consumption patterns do not "
                "respond to relative prices. Because they do, the index overstates the cost of "
                "maintaining the same living standard.",
                [
                    "Collection frequency affects timeliness, not this bias.",
                    "",
                    "Outlet sampling affects variance and outlet bias, a separate issue.",
                    "Quality change is a distinct bias, handled by hedonic or matched-model "
                    "methods.",
                ],
                "analyse",
            ),
            (
                "When a product in the CPI basket disappears from the market, the statistically "
                "sound response is to:",
                [
                    "Carry the last observed price forward indefinitely",
                    "Select a replacement and adjust for any quality difference",
                    "Drop the item and reduce the basket",
                    "Impute the all-items average change without review",
                ],
                1,
                "A comparable replacement keeps the basket representative, and an explicit quality "
                "adjustment ensures the index measures price change rather than a change in what "
                "is being bought.",
                [
                    "Carrying a dead price forward freezes part of the index and understates "
                    "volatility.",
                    "",
                    "Shrinking the basket changes the concept being measured.",
                    "Class-mean imputation is a legitimate fallback, but only after a replacement "
                    "has been sought and documented.",
                ],
                "apply",
            ),
            (
                "The Fisher ideal index is defined as:",
                [
                    "The arithmetic mean of Laspeyres and Paasche",
                    "The geometric mean of Laspeyres and Paasche",
                    "Laspeyres divided by Paasche",
                    "The Laspeyres index of the previous year",
                ],
                1,
                "Fisher is the geometric mean of the two, and satisfies the time-reversal and "
                "factor-reversal tests that neither component index passes alone.",
                [
                    "The arithmetic mean fails the reversal tests.",
                    "",
                    "That ratio is a measure of substitution effect, not an index.",
                    "This confuses the index with its reference period.",
                ],
                "remember",
            ),
            (
                "Chain-linking an index series is preferred to a fixed base when:",
                [
                    "The structure of consumption or production changes rapidly",
                    "The base year is recent",
                    "Only two periods are being compared",
                    "Prices are stable",
                ],
                0,
                "Chain-linking updates weights frequently and links successive periods, keeping "
                "the index representative when the underlying basket is shifting — at the cost of "
                "losing additive consistency across long spans.",
                [
                    "",
                    "A recent base reduces but does not remove the need to update weights.",
                    "With two periods there is no chain to form.",
                    "Stable prices make the choice largely immaterial.",
                ],
                "understand",
            ),
            (
                "A CPI weighting diagram is normally derived from:",
                [
                    "Consumer expenditure survey data",
                    "Wholesale price returns",
                    "Company balance sheets",
                    "Import and export declarations",
                ],
                0,
                "Weights reflect the share of household spending on each item, which comes from a "
                "household consumption expenditure survey.",
                [
                    "",
                    "Wholesale returns supply prices for a different index entirely.",
                    "Balance sheets describe firms, not household consumption.",
                    "Trade data informs trade indices.",
                ],
                "remember",
            ),
            (
                "An index number is rebased from 2011-12 = 100 to 2022-23 = 100. The growth rates "
                "between 2015 and 2016 will:",
                [
                    "Change substantially",
                    "Remain the same, since rebasing rescales the series",
                    "Become undefined",
                    "Double",
                ],
                1,
                "Rebasing divides the whole series by a constant. Ratios between any two periods, "
                "and therefore growth rates, are unchanged. Re-weighting is what changes growth "
                "rates, and is a different operation.",
                [
                    "This confuses rebasing with re-weighting.",
                    "",
                    "The series remains well defined throughout.",
                    "There is no doubling; the scaling factor cancels in any ratio.",
                ],
                "analyse",
            ),
            (
                "Which is the strongest argument for publishing a core inflation measure alongside "
                "headline CPI?",
                [
                    "It is always lower than headline inflation",
                    "It strips volatile food and fuel components to reveal the underlying trend",
                    "It is cheaper to compute",
                    "It is required by the Census Act",
                ],
                1,
                "Core excludes the components whose short-run volatility obscures the persistent "
                "component of inflation, which is what monetary policy responds to. It is a "
                "complement to headline, never a replacement.",
                [
                    "Core can exceed headline when food and fuel prices fall.",
                    "",
                    "Cost is not the rationale.",
                    "No such statutory requirement exists.",
                ],
                "evaluate",
            ),
        ],
        # -------------------------------------------------------- TECH-ANL --
        "TECH-ANL": [
            (
                "A model reports 97% accuracy predicting a condition present in 3% of cases. The "
                "first thing to check is:",
                [
                    "Whether it beats a classifier that always predicts the majority class",
                    "Whether the learning rate was tuned",
                    "Whether the training set was shuffled",
                    "Whether more layers would help",
                ],
                0,
                "Always predicting the majority class scores 97% here. Accuracy is uninformative "
                "under class imbalance; precision, recall and the confusion matrix are what "
                "reveal whether the model has learned anything.",
                [
                    "",
                    "Hyperparameter tuning is premature before the metric is known to be "
                    "meaningful.",
                    "Shuffling matters for training dynamics but not for this diagnosis.",
                    "Capacity is irrelevant if the evaluation metric cannot detect failure.",
                ],
                "analyse",
            ),
            (
                "Data leakage in a predictive model most commonly means:",
                [
                    "The dataset was shared without authorisation",
                    "Information unavailable at prediction time has entered the training features",
                    "The model file is too large",
                    "Training took longer than expected",
                ],
                1,
                "Leakage inflates validation performance because the model sees something it "
                "could not have known in production — a future value, or a feature derived from "
                "the target. It is the usual cause of a model that performs well in testing and "
                "fails on deployment.",
                [
                    "That is a data protection incident, a different concern entirely.",
                    "",
                    "File size is unrelated.",
                    "Training duration says nothing about leakage.",
                ],
                "understand",
            ),
            (
                "Cross-validation on time series data should use:",
                [
                    "Random k-fold splits",
                    "Forward-chaining splits that never train on data after the validation period",
                    "Stratified splits by target class",
                    "A single random 80/20 split",
                ],
                1,
                "Random folds let the model train on the future and validate on the past, which "
                "cannot happen in deployment and produces an optimistic estimate. Forward "
                "chaining respects the arrow of time.",
                [
                    "Random folds break temporal ordering.",
                    "",
                    "Stratification addresses class balance, not temporal leakage.",
                    "A single random split has the same ordering problem.",
                ],
                "apply",
            ),
            (
                "For a model that informs an official statistic, which property matters most "
                "beyond predictive accuracy?",
                [
                    "Training speed",
                    "Explainability, so that a published figure can be defended",
                    "The number of parameters",
                    "The programming language used",
                ],
                1,
                "An official figure must be explainable to the people it affects and to those "
                "scrutinising it. A model that cannot be interrogated cannot support a number "
                "the public is expected to rely on.",
                [
                    "Speed is an operational convenience.",
                    "",
                    "Size is not itself a quality.",
                    "Implementation language is immaterial to the statistic's defensibility.",
                ],
                "evaluate",
            ),
            (
                "Regularisation (L1/L2) is applied primarily to:",
                [
                    "Speed up convergence",
                    "Reduce overfitting by penalising large coefficients",
                    "Handle missing values",
                    "Balance the classes",
                ],
                1,
                "Penalising coefficient magnitude constrains model complexity, trading a little "
                "training fit for better generalisation. L1 additionally drives coefficients to "
                "zero, performing feature selection.",
                [
                    "Any convergence effect is incidental.",
                    "",
                    "Missing values are handled by imputation or by models that support them "
                    "natively.",
                    "Class imbalance is addressed by resampling or class weights.",
                ],
                "remember",
            ),
            (
                "A statistical office wants to impute missing income responses. The method that "
                "best preserves the distribution is:",
                [
                    "Mean imputation",
                    "Multiple imputation reflecting the uncertainty of each imputed value",
                    "Deleting all incomplete records",
                    "Filling with zero",
                ],
                1,
                "Multiple imputation generates several plausible values per missing entry and "
                "combines the results, so the extra uncertainty is carried through to the "
                "standard errors rather than being hidden.",
                [
                    "Mean imputation shrinks variance and distorts every percentile.",
                    "",
                    "Listwise deletion discards information and biases estimates if the data are "
                    "not missing completely at random.",
                    "Zero is a substantive value and would badly distort income statistics.",
                ],
                "apply",
            ),
            (
                "Which best describes the bias–variance trade-off?",
                [
                    "More complex models always generalise better",
                    "Reducing model complexity typically raises bias and lowers variance",
                    "Bias and variance always move together",
                    "Variance can be eliminated with enough features",
                ],
                1,
                "A simpler model makes stronger assumptions (higher bias) but is less sensitive to "
                "the particular training sample (lower variance). The aim is the total error "
                "minimum, not either extreme.",
                [
                    "Complexity beyond a point increases generalisation error.",
                    "",
                    "They typically move in opposite directions as complexity changes.",
                    "Adding features usually increases variance.",
                ],
                "understand",
            ),
            (
                "An A/B comparison of two estimation pipelines shows a 0.4% difference with a "
                "p-value of 0.31. The correct conclusion is:",
                [
                    "The pipelines are equivalent",
                    "The data do not provide evidence of a difference; this is not proof of equivalence",
                    "The new pipeline is better",
                    "The test was run incorrectly",
                ],
                1,
                "Failing to reject the null is not the same as accepting it. Demonstrating "
                "equivalence requires an equivalence test with a pre-specified margin, and "
                "adequate power.",
                [
                    "This is the standard misreading of a non-significant result.",
                    "",
                    "Nothing supports a claim of improvement.",
                    "There is no evidence the test itself was flawed.",
                ],
                "evaluate",
            ),
        ],
    }
)

BANK.update(
    {
        # -------------------------------------------------------- TECH-GIS --
        "TECH-GIS": [
            (
                "Two datasets use EPSG:4326 and EPSG:32644 respectively. Overlaying them without "
                "transformation will:",
                [
                    "Work correctly, since both cover India",
                    "Misalign features, because one is geographic degrees and the other projected metres",
                    "Fail to open in any GIS package",
                    "Only affect the map legend",
                ],
                1,
                "EPSG:4326 stores latitude and longitude in degrees; EPSG:32644 is UTM zone 44N in "
                "metres. Plotting one against the other places features thousands of kilometres "
                "apart unless a coordinate transformation is applied first.",
                [
                    "Shared geographic extent does not imply a shared coordinate system.",
                    "",
                    "Both open fine; the failure is silent and spatial.",
                    "The legend is unaffected; the geometry is wrong.",
                ],
                "apply",
            ),
            (
                "The modifiable areal unit problem (MAUP) describes how:",
                [
                    "Results change depending on how spatial units are drawn or aggregated",
                    "Raster files lose precision when compressed",
                    "GPS accuracy degrades in urban canyons",
                    "Projections distort area near the poles",
                ],
                0,
                "The same underlying data can produce different correlations and rates depending "
                "on the zoning and scale of the areal units — which is why the unit of analysis "
                "must be stated and justified, not chosen for the result it gives.",
                [
                    "",
                    "That is a compression artefact, unrelated.",
                    "That is multipath error in GNSS.",
                    "That is projection distortion, a separate issue.",
                ],
                "understand",
            ),
            (
                "For mapping district-level literacy rates, the appropriate thematic map type is:",
                ["A choropleth map", "A dot density map of raw counts", "A heat map of point locations", "A flow map"],
                0,
                "Choropleth maps shade enumeration units by a normalised value. Literacy rate is "
                "already a rate, so it is directly comparable across districts of different sizes.",
                [
                    "",
                    "Dot density of raw counts would show population distribution rather than "
                    "literacy.",
                    "A heat map needs point events, which district aggregates are not.",
                    "Flow maps show movement between places.",
                ],
                "apply",
            ),
            (
                "A spatial join between survey points and district polygons requires, above all:",
                [
                    "Both layers in the same coordinate reference system",
                    "The same file format for both layers",
                    "Identical attribute column names",
                    "Equal numbers of features in each layer",
                ],
                0,
                "A spatial join tests geometric relationships, so the coordinates must be "
                "comparable. Format and attributes are handled by the software.",
                [
                    "",
                    "Most GIS tools join across formats without difficulty.",
                    "Attribute names are irrelevant to a spatial predicate.",
                    "Counts differ by design in a join.",
                ],
                "remember",
            ),
            (
                "Geo-tagging survey enumeration blocks most directly improves:",
                [
                    "The speed of data entry",
                    "Field supervision and the detection of fabricated interviews",
                    "The sampling weights",
                    "The response rate",
                ],
                1,
                "Coordinates recorded at the point of interview let a supervisor verify that "
                "enumeration happened where and when it was supposed to, which is the strongest "
                "practical deterrent to curbstoning.",
                [
                    "Entry speed is unaffected.",
                    "",
                    "Weights derive from selection probabilities, not location.",
                    "Response rates depend on contact strategy and respondent burden.",
                ],
                "analyse",
            ),
            (
                "Which raster resolution consideration matters most when estimating built-up area "
                "for a small town?",
                [
                    "A coarse pixel may be larger than the features being measured",
                    "The file must be in GeoTIFF format",
                    "The imagery must be in true colour",
                    "The image must be taken at noon",
                ],
                0,
                "If a pixel covers more ground than a typical building footprint, built-up area "
                "is systematically mis-measured regardless of the classification method.",
                [
                    "",
                    "Format is a container choice.",
                    "Multispectral bands often classify better than true colour.",
                    "Acquisition time affects shadows but is secondary to resolution.",
                ],
                "evaluate",
            ),
        ],
        # -------------------------------------------------------- TECH-BIG --
        "TECH-BIG": [
            (
                "Partitioning a large survey table by survey round primarily improves:",
                [
                    "Query performance, by letting the engine skip irrelevant partitions",
                    "Data accuracy",
                    "The number of columns available",
                    "Disk encryption",
                ],
                0,
                "Partition pruning means a query filtered to one round reads only that partition, "
                "cutting scanned volume by orders of magnitude on a large table.",
                [
                    "",
                    "Accuracy is a property of the data, not its physical layout.",
                    "Partitioning does not change the schema.",
                    "Encryption is configured separately.",
                ],
                "understand",
            ),
            (
                "In a data lake holding raw survey extracts, the most important governance control "
                "is:",
                [
                    "Compressing every file",
                    "A catalogue recording lineage, schema and access rights for each dataset",
                    "Storing everything as CSV",
                    "Keeping all data in one bucket",
                ],
                1,
                "Without a catalogue, a lake becomes unusable: nobody can tell what a file "
                "contains, where it came from, or who may see it. Lineage is also what makes a "
                "published figure reproducible.",
                [
                    "Compression saves cost but governs nothing.",
                    "",
                    "CSV loses types and is a poor choice at scale.",
                    "A single bucket makes access control harder, not easier.",
                ],
                "evaluate",
            ),
            (
                "Columnar formats such as Parquet are preferred for analytical workloads because:",
                [
                    "They read only the columns a query needs and compress each column well",
                    "They are human-readable",
                    "They enforce foreign keys",
                    "They are the only format cloud storage accepts",
                ],
                0,
                "Analytical queries touch few columns of many rows. A columnar layout reads only "
                "those columns, and homogeneous column data compresses far better than mixed "
                "rows.",
                [
                    "",
                    "Parquet is binary.",
                    "Constraints are a database feature, not a file format one.",
                    "Object stores accept any format.",
                ],
                "understand",
            ),
            (
                "Idempotency in a data pipeline means:",
                [
                    "Running the same job twice produces the same result as running it once",
                    "The job runs faster on each repetition",
                    "The job cannot be run twice",
                    "Output is always appended",
                ],
                0,
                "Re-runs happen constantly — after failures, late-arriving data, or backfills. An "
                "idempotent job makes them safe, whereas an append-only job silently doubles the "
                "data every retry.",
                [
                    "",
                    "Speed is unrelated.",
                    "Idempotency permits re-running; it does not prevent it.",
                    "Blind appending is the usual cause of non-idempotency.",
                ],
                "apply",
            ),
            (
                "A nightly job that recomputes competency profiles for 200,000 officers is best "
                "run as:",
                [
                    "A synchronous call inside the web request",
                    "A scheduled batch job writing results the API reads",
                    "A trigger on every row update",
                    "A manual script run when someone remembers",
                ],
                1,
                "The work is large, predictable and not user-initiated. A scheduled batch keeps it "
                "off the request path, and the API serves precomputed results.",
                [
                    "This would time out and block a user-facing request.",
                    "",
                    "Row-level triggers would recompute the same profile repeatedly during a bulk "
                    "load.",
                    "Manual operation is not a schedule.",
                ],
                "apply",
            ),
            (
                "The main risk of denormalising a reporting table is:",
                [
                    "Slower reads",
                    "Update anomalies, since the same fact is stored in several places",
                    "Loss of the primary key",
                    "Inability to add indexes",
                ],
                1,
                "Denormalisation trades write-side consistency for read speed. The duplicated fact "
                "must be updated everywhere it appears, or the copies diverge.",
                [
                    "Reads typically get faster; that is the point.",
                    "",
                    "Keys are retained.",
                    "Indexes remain available.",
                ],
                "analyse",
            ),
        ],
        # -------------------------------------------------------- TECH-VIZ --
        "TECH-VIZ": [
            (
                "Truncating the y-axis of a bar chart is generally unacceptable because:",
                [
                    "Bar length encodes magnitude, so a cut axis exaggerates differences",
                    "It makes the chart harder to draw",
                    "Bar charts must always be horizontal",
                    "It breaks colour accessibility",
                ],
                0,
                "A bar's meaning is its length from zero. Starting the axis elsewhere makes a "
                "small difference look large — the most common way a chart misleads without "
                "containing a false number. Line charts, which encode position rather than "
                "length, may legitimately be truncated.",
                [
                    "",
                    "Drawing difficulty is not the issue.",
                    "Orientation is a layout choice.",
                    "Colour is a separate concern.",
                ],
                "evaluate",
            ),
            (
                "For showing the composition of the workforce across 8 divisions and 12 "
                "competencies, the clearest form is usually:",
                [
                    "A pie chart per division",
                    "A heatmap with divisions on one axis and competencies on the other",
                    "A 3-D stacked column chart",
                    "A word cloud",
                ],
                1,
                "A heatmap shows all 96 cells at once and makes row and column patterns visible. "
                "Eight pie charts force serial comparison of angles, which people do badly.",
                [
                    "Angles are hard to compare, and eight separate charts prevent comparison "
                    "across divisions.",
                    "",
                    "3-D distorts the encoding and occludes data.",
                    "Word clouds encode nothing quantitative.",
                ],
                "apply",
            ),
            (
                "A chart intended for an audience including colour-blind readers should:",
                [
                    "Rely on red/green contrast only",
                    "Encode the same information with a second channel such as position, shape or a direct label",
                    "Use only greyscale",
                    "Increase saturation",
                ],
                1,
                "Colour should never be the only channel carrying meaning. A second encoding — "
                "labels, ordering, shape — keeps the chart readable for everyone, and also "
                "survives printing.",
                [
                    "Red/green is the most common confusion pair.",
                    "",
                    "Greyscale is unnecessarily restrictive and hurts category separation.",
                    "Saturation does not resolve hue confusion.",
                ],
                "understand",
            ),
            (
                "When publishing an estimate with a wide confidence interval, the visualisation "
                "should:",
                [
                    "Show the point estimate alone for clarity",
                    "Show the interval explicitly, so the reader sees the uncertainty",
                    "Round the estimate to hide the range",
                    "Use a logarithmic scale",
                ],
                1,
                "A point estimate with no interval implies a precision the data do not support. "
                "Showing the interval is what stops a reader treating a noisy district figure as "
                "a firm fact.",
                [
                    "This is precisely what misleads.",
                    "",
                    "Rounding conceals rather than communicates.",
                    "Log scales address skew, not uncertainty.",
                ],
                "evaluate",
            ),
            (
                "A dashboard for senior officials should prioritise:",
                [
                    "As many charts as fit on the screen",
                    "The few indicators that drive a decision, with drill-down available",
                    "Animated transitions between views",
                    "Matching the colours of the ministry logo",
                ],
                1,
                "A decision-support surface earns its space by answering the questions that "
                "change an action. Detail belongs one level down, reachable but not competing for "
                "attention.",
                [
                    "Density without hierarchy hides the signal.",
                    "",
                    "Animation is decoration here.",
                    "Brand colours are a constraint, not a purpose.",
                ],
                "evaluate",
            ),
            (
                "Small multiples are particularly effective when:",
                [
                    "Comparing the same measure across many categories on a shared scale",
                    "Showing a single total",
                    "Displaying one time series",
                    "Presenting free text",
                ],
                0,
                "Repeating a small chart with a common scale lets the eye compare shapes directly "
                "across categories, which a single overplotted chart cannot support.",
                [
                    "",
                    "A single number needs no chart.",
                    "One series does not need multiples.",
                    "Text is not a chart form.",
                ],
                "remember",
            ),
        ],
        # --------------------------------------------------------- DG-QUAL --
        "DG-QUAL": [
            (
                "In a statistical quality framework, 'relevance' means:",
                [
                    "The statistic meets the needs of its users",
                    "The statistic is published quickly",
                    "The statistic has a low sampling error",
                    "The statistic is comparable over time",
                ],
                0,
                "Relevance is the degree to which the output meets user needs. Timeliness, "
                "accuracy and comparability are separate dimensions, and a highly accurate "
                "statistic nobody needs still scores poorly on relevance.",
                [
                    "",
                    "That is timeliness.",
                    "That is accuracy.",
                    "That is comparability.",
                ],
                "remember",
            ),
            (
                "Edit rules that automatically correct outliers without review risk:",
                [
                    "Slowing the pipeline",
                    "Erasing genuine extreme values, which are often the most policy-relevant observations",
                    "Increasing storage cost",
                    "Breaking the file format",
                ],
                1,
                "Automatic correction assumes an extreme value is an error. In income, landholding "
                "or enterprise data the true distribution has a long tail, and silently editing it "
                "away biases exactly the estimates that matter most.",
                [
                    "Speed is not the concern.",
                    "",
                    "Storage is unaffected.",
                    "Format integrity is unrelated.",
                ],
                "analyse",
            ),
            (
                "A revisions policy published in advance primarily protects:",
                [
                    "The credibility of the agency, by making revisions expected rather than suspicious",
                    "The size of the budget",
                    "The speed of first release",
                    "The confidentiality of respondents",
                ],
                0,
                "Revisions are inherent to early estimates. Announcing the schedule and the reasons "
                "in advance turns a revision into a routine event instead of evidence of "
                "manipulation.",
                [
                    "",
                    "Budget is unrelated.",
                    "A policy does not itself accelerate release.",
                    "Confidentiality is governed separately.",
                ],
                "evaluate",
            ),
            (
                "Metadata that accompanies a published dataset should include, at minimum:",
                [
                    "Only the publication date",
                    "Concepts and definitions, coverage, collection method, and known limitations",
                    "The names of the field staff",
                    "The internal file path",
                ],
                1,
                "Without definitions, coverage and method, a user cannot tell what the numbers "
                "mean or whether they can be compared with anything else. Stating limitations is "
                "part of the output, not an admission.",
                [
                    "A date alone is not usable metadata.",
                    "",
                    "Naming field staff would breach their privacy to no analytical purpose.",
                    "Internal paths are meaningless externally.",
                ],
                "understand",
            ),
            (
                "Two divisions publish different figures for the same indicator. The correct first "
                "step is to:",
                [
                    "Publish the higher figure",
                    "Reconcile the definitions, reference periods and coverage before comparing the numbers",
                    "Average the two",
                    "Withdraw both permanently",
                ],
                1,
                "Most apparent contradictions between official series are definitional — different "
                "reference periods, age bounds or coverage. Reconciling concepts usually explains "
                "the gap, and where it does not, the difference is real and must be documented.",
                [
                    "Choosing by magnitude is indefensible.",
                    "",
                    "Averaging two differently defined quantities produces a meaningless third.",
                    "Withdrawal without diagnosis destroys usable information.",
                ],
                "analyse",
            ),
            (
                "A quality gate that blocks publication when a mandatory metadata field is empty "
                "is an example of:",
                [
                    "A preventive control",
                    "A detective control",
                    "A corrective control",
                    "A compensating control",
                ],
                0,
                "Preventive controls stop the defect reaching the output at all. A reconciliation "
                "report run afterwards would be detective; a correction issued later would be "
                "corrective.",
                [
                    "",
                    "Detective controls find problems after the fact.",
                    "Corrective controls repair them.",
                    "Compensating controls substitute for a missing primary control.",
                ],
                "understand",
            ),
        ],
        # --------------------------------------------------------- DG-PRIV --
        "DG-PRIV": [
            (
                "Publishing a table where one cell contains a single enterprise risks:",
                [
                    "Disclosing that enterprise's confidential return",
                    "Only a rounding error",
                    "Nothing, since no name is shown",
                    "A slower query",
                ],
                0,
                "A cell with one contributor discloses that contributor's value exactly. Removing "
                "the name is irrelevant when the cell definition identifies the unit — which is "
                "why primary suppression rules exist.",
                [
                    "",
                    "This is a disclosure risk, not a precision issue.",
                    "Identity can be inferred from the cell definition.",
                    "Performance is unrelated.",
                ],
                "apply",
            ),
            (
                "After suppressing a sensitive cell, secondary suppression is needed because:",
                [
                    "The suppressed value can be recovered from published row and column totals",
                    "The table looks untidy",
                    "The file size increases",
                    "Totals must always be suppressed",
                ],
                0,
                "If every other cell in a row and the total are published, the suppressed cell is "
                "simple arithmetic. Additional cells must be suppressed to break that "
                "recoverability.",
                [
                    "",
                    "Appearance is not the concern.",
                    "Size is unaffected.",
                    "Totals are usually published; it is the pattern that matters.",
                ],
                "analyse",
            ),
            (
                "k-anonymity with k=5 guarantees that:",
                [
                    "Each record is indistinguishable from at least 4 others on the quasi-identifiers",
                    "At most 5 records are published",
                    "5% of records are removed",
                    "Five variables are encrypted",
                ],
                0,
                "Every combination of quasi-identifiers appears at least k times, so a record "
                "cannot be singled out on those attributes alone. It does not protect against "
                "attribute disclosure when a group shares the same sensitive value.",
                [
                    "",
                    "k is a group size, not a record count.",
                    "No fixed proportion is removed.",
                    "Encryption is a different mechanism.",
                ],
                "understand",
            ),
            (
                "The strongest justification for a data-sharing agreement between two government "
                "departments is:",
                [
                    "It speeds up analysis",
                    "It records purpose limitation, retention and onward-sharing rules, making the lawful basis explicit",
                    "It avoids the need for anonymisation",
                    "It transfers liability entirely to the recipient",
                ],
                1,
                "The agreement is what makes the transfer accountable: why the data may be used, "
                "for how long, and what may not be done with it. Statistical confidentiality "
                "obligations are not dissolved by a transfer.",
                [
                    "Speed is a side effect.",
                    "",
                    "Anonymisation obligations remain.",
                    "Liability is shared, and the originating agency retains duties to "
                    "respondents.",
                ],
                "evaluate",
            ),
            (
                "Differential privacy protects individuals by:",
                [
                    "Removing names and addresses",
                    "Adding calibrated noise so that any one person's inclusion barely changes the output",
                    "Encrypting the database at rest",
                    "Restricting access to senior officers",
                ],
                1,
                "The formal guarantee is about the output: whether or not a given individual is in "
                "the dataset, the released statistic is almost equally likely. That bounds what "
                "any adversary can infer, regardless of what else they know.",
                [
                    "De-identification alone is defeated by linkage attacks.",
                    "",
                    "Encryption protects storage, not published outputs.",
                    "Access control is organisational, not a mathematical guarantee.",
                ],
                "understand",
            ),
            (
                "A researcher requests unit-level survey records. The appropriate response under "
                "standard statistical confidentiality practice is to:",
                [
                    "Release the full microdata on request",
                    "Offer an anonymised public-use file, or secure-enclave access for detailed data",
                    "Refuse all access to microdata",
                    "Release it with names removed but all other fields intact",
                ],
                1,
                "Tiered access is the established balance: a de-identified public file for general "
                "use, and controlled access under agreement for records too detailed to release "
                "openly.",
                [
                    "Open release of unit records breaches the undertaking given to respondents.",
                    "",
                    "Blanket refusal defeats the research value of publicly funded collection.",
                    "Name removal alone leaves re-identification straightforward through "
                    "quasi-identifiers.",
                ],
                "evaluate",
            ),
        ],
        # -------------------------------------------------------- BEH-COMM --
        "BEH-COMM": [
            (
                "A press release reports that unemployment 'rose from 7.1% to 7.4%' when the "
                "survey's margin of error is ±0.5 points. The release should:",
                [
                    "State the change is not statistically significant",
                    "Report the rise as a clear worsening",
                    "Omit the earlier figure",
                    "Round both to whole numbers",
                ],
                0,
                "A movement inside the margin of error cannot be distinguished from sampling "
                "noise. Reporting it as a real change misleads, and is the fastest way for an "
                "agency to lose the confidence of the people reading it.",
                [
                    "",
                    "This asserts a change the data do not support.",
                    "Omitting the comparison hides the basis for the claim.",
                    "Rounding obscures rather than clarifies.",
                ],
                "evaluate",
            ),
            (
                "When briefing a minister on a technically complex estimate, the most effective "
                "opening is:",
                [
                    "The methodology, in full detail",
                    "The finding and its decision implication, with method available on request",
                    "A list of every caveat first",
                    "The software used",
                ],
                1,
                "Lead with what changed and what it means for a decision. Method and caveats must "
                "be available and volunteered where they bear on the conclusion, but opening with "
                "them buries the point.",
                [
                    "Detail first loses the audience before the finding lands.",
                    "",
                    "Caveats matter, but as qualification rather than as the headline.",
                    "Tooling is irrelevant to the decision.",
                ],
                "apply",
            ),
            (
                "A journalist asks for a figure the agency has not yet quality-assured. The right "
                "response is to:",
                [
                    "Provide it informally, marked unofficial",
                    "Explain the release calendar and decline until the scheduled publication",
                    "Provide a rough approximation",
                    "Provide last year's figure instead without saying so",
                ],
                1,
                "Pre-release access outside the published protocol undermines equal access and the "
                "integrity of the release calendar. Explaining when the figure is due is both "
                "honest and helpful.",
                [
                    "'Unofficial' figures are quoted as official the moment they leave the "
                    "building.",
                    "",
                    "An approximation carries the agency's authority without its quality "
                    "assurance.",
                    "Substituting silently is straightforwardly misleading.",
                ],
                "evaluate",
            ),
            (
                "Writing for a non-technical audience, the clearest way to convey a 2.4 percentage "
                "point rise in a 12% rate is:",
                [
                    "'A 20% relative increase'",
                    "'Up from 12% to 14.4% — about 1 in 7 rather than 1 in 8'",
                    "'A statistically significant delta'",
                    "'An increase of 0.024'",
                ],
                1,
                "Giving both the levels and a concrete frequency makes the size of the change "
                "intuitive. Relative change alone is the classic way a small absolute movement is "
                "made to sound dramatic.",
                [
                    "Technically true but easily misread as a rise to 20%.",
                    "",
                    "Jargon without content.",
                    "A decimal on an unstated base communicates nothing.",
                ],
                "apply",
            ),
            (
                "In a technical report, limitations are best placed:",
                [
                    "In a footnote at the very end",
                    "Alongside the findings they qualify",
                    "In a separate internal document",
                    "Omitted, to avoid undermining confidence",
                ],
                1,
                "A limitation belongs where a reader forms the conclusion it affects. Relegating it "
                "to an appendix means the people most likely to misuse the figure never see it.",
                [
                    "End-notes are read by almost nobody.",
                    "",
                    "Withholding them from the published output is not defensible.",
                    "Concealment destroys confidence far more thoroughly than disclosure.",
                ],
                "evaluate",
            ),
            (
                "Responding to a public claim that the agency's data are 'manipulated', the "
                "strongest reply is to:",
                [
                    "Publish the methodology, revision history and microdata access route",
                    "Issue a denial",
                    "Ignore it",
                    "Attack the critic's credentials",
                ],
                0,
                "Transparency is the only durable answer to a manipulation claim: method, "
                "revisions and independently checkable data let others verify rather than take the "
                "agency's word.",
                [
                    "",
                    "A denial invites the reader to choose whom to believe.",
                    "Silence lets the claim stand.",
                    "Attacking the person concedes the argument about the numbers.",
                ],
                "evaluate",
            ),
        ],
        # -------------------------------------------------------- BEH-LEAD --
        "BEH-LEAD": [
            (
                "A survey round is behind schedule with a fixed publication date. The most "
                "defensible response is to:",
                [
                    "Reduce the sample size quietly to finish on time",
                    "Assess which quality dimension can be relaxed, decide openly, and document it",
                    "Publish on time using partial data without comment",
                    "Extrapolate the missing districts from last round",
                ],
                1,
                "Something has to give — coverage, timeliness or detail. Making that choice "
                "explicitly, with its effect on quality recorded, is what distinguishes a managed "
                "trade-off from a concealed shortcut.",
                [
                    "A silent sample cut changes the precision users were promised.",
                    "",
                    "Partial data presented as complete is misrepresentation.",
                    "Extrapolating from a previous round fabricates the very change being "
                    "measured.",
                ],
                "evaluate",
            ),
            (
                "A junior officer's analysis contradicts a conclusion the division has already "
                "briefed. The right action is to:",
                [
                    "Ask them to revise it to match the briefing",
                    "Verify the new analysis, and if it holds, correct the record",
                    "File it without action",
                    "Delay it until after the next review cycle",
                ],
                1,
                "Findings are not negotiated to fit a previous position. Verify, and if the "
                "analysis stands, correct — an agency that suppresses an inconvenient result has "
                "no basis to be believed on any other.",
                [
                    "This is instructing someone to falsify.",
                    "",
                    "Filing it away is suppression by inaction.",
                    "Delay for convenience is the same thing more slowly.",
                ],
                "evaluate",
            ),
            (
                "Allocating a limited training budget across a division is best driven by:",
                [
                    "Seniority",
                    "Measured competency gaps weighted by how critical each is to the roles held",
                    "Who applies first",
                    "An equal split across all officers",
                ],
                1,
                "Targeting the gaps that are both wide and critical to the role produces the "
                "largest capability gain per rupee, and the reasoning can be shown to anyone who "
                "asks why they were or were not selected.",
                [
                    "Seniority is unrelated to where capability is missing.",
                    "",
                    "First-come rewards attentiveness to email.",
                    "An equal split ignores where the need actually is.",
                ],
                "apply",
            ),
            (
                "When delegating a critical analytical task, the most important thing to make "
                "explicit is:",
                [
                    "The deadline only",
                    "The decision the output will support, and the quality bar it must meet",
                    "Which software to use",
                    "How many hours to spend",
                ],
                1,
                "Someone who understands what the work is for makes better judgement calls on the "
                "hundred small decisions that were never specified. A deadline without purpose "
                "produces something delivered on time and unusable.",
                [
                    "A deadline alone gives no basis for trade-offs.",
                    "",
                    "Tooling is usually the delegate's choice.",
                    "Hours measure effort, not the standard required.",
                ],
                "apply",
            ),
            (
                "Two sections disagree over which is responsible for a data quality failure. The "
                "most productive first move is to:",
                [
                    "Establish what happened in the process, before assigning responsibility",
                    "Escalate immediately to the Director",
                    "Ask each to submit a written defence",
                    "Assign it to whichever section has capacity",
                ],
                0,
                "A shared, factual account of the failure usually shows it was a process gap "
                "rather than a person. Starting with blame makes people defend rather than "
                "explain, and the gap stays open.",
                [
                    "",
                    "Escalating before the facts are known wastes the escalation.",
                    "Written defences entrench positions.",
                    "Capacity is irrelevant to causation.",
                ],
                "analyse",
            ),
            (
                "An officer consistently produces accurate work but misses every internal "
                "deadline. The most useful managerial response is to:",
                [
                    "Reassign all time-critical work away from them permanently",
                    "Establish whether the cause is workload, prioritisation or unclear expectations, then address that",
                    "Record it in the annual appraisal and say nothing until then",
                    "Shorten their deadlines to compensate",
                ],
                1,
                "The three causes need entirely different remedies, and the pattern — accurate but "
                "late — suggests a real constraint rather than indifference. Diagnosing first is "
                "what makes the intervention work.",
                [
                    "This removes the symptom and wastes demonstrated accuracy.",
                    "",
                    "Saving feedback for the appraisal denies any chance to correct it.",
                    "Artificial deadlines damage trust once discovered.",
                ],
                "analyse",
            ),
        ],
    }
)
