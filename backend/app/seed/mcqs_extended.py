"""The rest of the item bank, written for an adaptive test rather than a paper.

`mcqs.py` came first and was written for a fixed form: six to eight items per
competency, enough to make a quiz. An adaptive test needs something different
from a bank, and the difference is not simply "more".

**It needs a difficulty spread, and it needs depth at every point of it.** The
adaptive engine picks the item nearest the current estimate. If a competency has
twenty items and eighteen of them sit at L3, an officer tracking at L4.5 gets one
well-aimed question and then whatever is left — which is what happened the first
time this ran: the bank for GIS emptied after six items and the last one carried
Fisher information of 0.006, a question worth almost nothing that the officer
still had to answer. Twelve informative items need roughly twenty to choose from,
spread across the range, with two or three at each level.

**Difficulty is authored explicitly here, not inferred from Bloom.** The items in
`mcqs.py` take their difficulty from their Bloom level, which is a reasonable
prior and the only one available for an item written without the ability scale in
mind. But Bloom has five buckets and they map to five discrete difficulties, so a
bank built that way clumps: every "apply" item lands at exactly L3.3 and the
engine cannot tell them apart. The seventh field on each tuple below is the
author's estimate of where the item actually sits, which is what lets this bank
cover the range smoothly.

That estimate is still a guess. An author who knows the answer is a poor judge of
what is hard about a question, and reliably underestimates it. It is a starting
point that lets the test adapt on day one, and `services.adaptive_quiz.calibrate`
replaces it with a measurement as soon as twenty-five people have answered. The
authored value is kept beside the calibrated one precisely so the size of the
author's error stays visible.

Everything here is seeded APPROVED for the same reason the original bank is: an
author writing an item deliberately, with a worked explanation and a reason for
every distractor, *is* the review a generated item needs.
"""

from __future__ import annotations

# (stem, options, correct_index, explanation, [distractor rationales], bloom, level)
#
# `level` is the authored difficulty on the FRAC L1-L5 axis. L3.0 is the middle
# of the scale; the adaptive engine converts it to theta, where L3 is 0.
ExtendedItem = tuple[str, list[str], int, str, list[str], str, float]

EXTENDED: dict[str, list[ExtendedItem]] = {
    # ---------------------------------------------------------- STAT-SAMP --
    "STAT-SAMP": [
        (
            "In a stratified random sample, strata are formed so that units within a stratum "
            "are:",
            [
                "As different from each other as possible",
                "As similar to each other as possible on the variable being estimated",
                "Equal in number across all strata",
                "Selected from the same geographic district",
            ],
            1,
            "Stratification gains precision by removing between-stratum variation from the "
            "sampling error. That gain is largest when each stratum is internally homogeneous, "
            "so what remains inside it — the part the sample has to estimate — is small.",
            [
                "This describes what makes good *clusters*, not good strata. Clustering wants "
                "internally varied groups; stratification wants internally uniform ones.",
                "",
                "Equal stratum sizes are neither required nor usually desirable — allocation "
                "follows size and variability, as in Neyman allocation.",
                "Geography is one possible stratifying variable, not a definition of one.",
            ],
            "understand",
            1.6,
        ),
        (
            "The sampling fraction in a survey is:",
            [
                "The proportion of selected units that respond",
                "The ratio of the sample size to the population size",
                "The share of the budget spent on fieldwork",
                "The proportion of the sample that is urban",
            ],
            1,
            "n/N — how much of the population is being observed. It appears directly in the "
            "finite population correction, which is why a census (fraction 1) has no sampling "
            "error at all.",
            [
                "That is the response rate, which is about non-response rather than selection.",
                "",
                "Not a statistical quantity.",
                "That is the urban share of the sample, a composition figure.",
            ],
            "remember",
            1.3,
        ),
        (
            "NSS surveys commonly use a two-stage design with villages or urban blocks as "
            "first-stage units and households as second-stage units. The main reason for the "
            "first stage is:",
            [
                "It increases the statistical precision of the estimate",
                "It reduces field cost by concentrating fieldwork geographically",
                "It removes the need for a sampling frame",
                "It eliminates non-response",
            ],
            1,
            "Clustering is a cost decision, not a precision one. Sending an investigator to one "
            "village to interview twenty households is far cheaper than twenty scattered visits. "
            "It is accepted *despite* costing precision, which is what the design effect measures.",
            [
                "Clustering almost always reduces precision relative to simple random sampling "
                "of the same size, because households in one village resemble each other.",
                "",
                "It changes what the frame must list — villages rather than every household — "
                "but a frame is still required at each stage.",
                "Non-response is unaffected by the stage structure.",
            ],
            "understand",
            2.2,
        ),
        (
            "A design effect (DEFF) of 2.5 in a household survey means that:",
            [
                "The estimate is 2.5 times larger than it should be",
                "The variance is 2.5 times what simple random sampling of the same size would give",
                "The sample must be reduced by a factor of 2.5",
                "2.5% of the sample was lost to non-response",
            ],
            1,
            "DEFF is the ratio of the actual design variance to the SRS variance at the same "
            "sample size. At 2.5, an achieved sample of 5,000 carries the precision of an SRS of "
            "2,000 — the effective sample size.",
            [
                "DEFF concerns variance, not bias; the point estimate is unaffected.",
                "",
                "The implication runs the other way: a clustered design needs a *larger* sample "
                "to reach a target precision.",
                "That is non-response, a separate quantity.",
            ],
            "apply",
            3.1,
        ),
        (
            "Under Neyman allocation, a stratum receives a larger share of the sample when it:",
            [
                "Is geographically remote",
                "Is both large and internally variable",
                "Has the highest mean value of the study variable",
                "Was under-sampled in the previous round",
            ],
            1,
            "Neyman allocation is proportional to N_h × S_h — stratum size times its standard "
            "deviation. Sample goes where the uncertainty is, which means large strata and "
            "heterogeneous ones both earn more of it.",
            [
                "Remoteness affects cost, which enters *optimum* (cost-weighted) allocation, not "
                "Neyman allocation.",
                "",
                "A high mean contributes nothing on its own — a stratum where everyone reports "
                "a large but near-identical value needs very few units.",
                "History is not an input; allocation is derived from size and spread.",
            ],
            "analyse",
            4.1,
        ),
        (
            "A survey estimates average monthly household expenditure with a relative standard "
            "error of 8%. To halve that to 4%, holding the design fixed, the sample size must be "
            "multiplied by approximately:",
            ["2", "4", "8", "16"],
            1,
            "Standard error falls with the square root of sample size, so halving it requires "
            "quadrupling n. This is the single most consequential fact in survey budgeting: "
            "precision gets expensive fast, and the fourth doubling buys very little.",
            [
                "Doubling n reduces the standard error by a factor of about 1.41, to roughly 5.7%.",
                "",
                "Eight times the sample would over-shoot, reaching about 2.8%.",
                "Sixteen times would reach roughly 2%, at four times the necessary cost.",
            ],
            "apply",
            3.6,
        ),
        (
            "A rotational panel design, in which a fixed proportion of the sample is replaced "
            "each round, is chosen mainly because it:",
            [
                "Eliminates the need for weighting",
                "Improves estimates of change between rounds while limiting respondent fatigue",
                "Removes seasonality from the series",
                "Allows the frame to be updated less often",
            ],
            1,
            "Overlap between rounds correlates the two estimates, and that correlation is exactly "
            "what reduces the variance of their difference. Rotating part of the sample keeps "
            "that benefit without asking the same households to answer indefinitely.",
            [
                "Weights are still required — rotation changes the overlap structure, not the "
                "selection probabilities.",
                "",
                "Seasonality is handled by the timing of enumeration and by adjustment, not by "
                "rotation.",
                "Rotation increases the demand on the frame, since fresh units must be drawn "
                "each round.",
            ],
            "analyse",
            4.4,
        ),
        (
            "Which is a *sampling* error rather than a non-sampling error?",
            [
                "An investigator records income in rupees per year where the schedule asks for "
                "rupees per month",
                "The variation between the estimate and the true population value that arises "
                "from observing only a subset",
                "A household refuses to be interviewed",
                "A data entry operator transposes two digits",
            ],
            1,
            "Sampling error is the variation attributable solely to having measured part of the "
            "population instead of all of it. It is the only error a confidence interval "
            "describes, and the only one that shrinks reliably as the sample grows.",
            [
                "A measurement or specification error — non-sampling, and it would persist in a "
                "complete census.",
                "",
                "Non-response, which is non-sampling and often the larger threat.",
                "A processing error, also non-sampling.",
            ],
            "understand",
            2.0,
        ),
        (
            "Probability proportional to size with replacement (PPSWR) is used at the first "
            "stage, with size measured by the previous census population. Twelve years later the "
            "principal risk to the estimates is that:",
            [
                "The selection probabilities no longer reflect current unit sizes, so weights "
                "misrepresent the population",
                "PPSWR is only valid for one round of a survey",
                "The estimator becomes biased because replacement was allowed",
                "The design effect falls below 1",
            ],
            0,
            "PPS weights are the reciprocal of selection probabilities computed from the measure "
            "of size. Rapid and *uneven* growth since the last census means fast-growing blocks "
            "were under-selected relative to their present size, and the weights no longer map "
            "the sample back onto the population correctly.",
            [
                "",
                "PPSWR is repeatable; the problem is the staleness of the size measure, not the "
                "method.",
                "With-replacement selection is unbiased and in fact simplifies variance "
                "estimation; it is not the issue.",
                "A design effect below 1 would be a gain, and clustering does not produce one.",
            ],
            "evaluate",
            4.8,
        ),
        (
            "The finite population correction factor is negligible when:",
            [
                "The population is small",
                "The sampling fraction is very small relative to the population",
                "The sample is stratified",
                "Non-response is high",
            ],
            1,
            "The FPC is (1 - n/N). When n/N is tiny — a few thousand households out of hundreds "
            "of millions — the factor is essentially 1 and can be dropped. It matters when a "
            "survey takes a substantial share of a small population, as an establishment survey "
            "of a narrow industry does.",
            [
                "The opposite: a small population makes the sampling fraction larger, so the FPC "
                "matters more.",
                "",
                "Stratification changes variance structure, not the FPC.",
                "Non-response affects the achieved sample, not the correction's form.",
            ],
            "apply",
            2.9,
        ),
        (
            "An investigator systematically selects the most accessible household when the "
            "designated one is locked, rather than making a revisit. The result is:",
            [
                "An increase in sampling error only",
                "Substitution bias, because accessibility is correlated with the characteristics "
                "being measured",
                "No effect, since the sample size is preserved",
                "An improvement, since the response rate rises",
            ],
            1,
            "Households at home during working hours differ systematically — more likely to "
            "contain older members, fewer earners, different employment patterns. Substituting on "
            "availability replaces a random selection with a self-selected one, and no amount of "
            "weighting recovers the original design.",
            [
                "This is a bias, not a variance problem. The estimate is wrong in a consistent "
                "direction.",
                "",
                "Preserving the count while breaking the selection mechanism is precisely the "
                "danger — the sample looks complete and is not probabilistic.",
                "A higher response rate achieved by substitution is a worse sample, not a better "
                "one.",
            ],
            "evaluate",
            4.0,
        ),
        (
            "Systematic sampling with a fixed interval can perform badly when:",
            [
                "The population size is not a multiple of the interval",
                "The frame has a periodicity matching the sampling interval",
                "The starting point is chosen at random",
                "The population is ordered by size",
            ],
            1,
            "If the list repeats with a cycle equal to the interval, every selected unit falls at "
            "the same point in that cycle — say, every corner shop in a market list. The sample "
            "is then systematically unrepresentative in a way its size will never reveal.",
            [
                "A manageable arithmetic nuisance, handled by circular systematic sampling.",
                "",
                "A random start is required, not a flaw.",
                "Ordering by size is usually beneficial — it produces implicit stratification.",
            ],
            "analyse",
            3.8,
        ),
    ],

    # ----------------------------------------------------------- STAT-EST --
    "STAT-EST": [
        (
            "A design weight in a sample survey is:",
            [
                "The number of members in the household",
                "The reciprocal of the unit's probability of selection",
                "The relative importance assigned to a question",
                "The count of units in the stratum",
            ],
            1,
            "Each selected unit stands for 1/π others, where π is its selection probability. That "
            "reciprocal is the base weight, before any adjustment for non-response or "
            "calibration.",
            [
                "Household size may be used in some estimators, but it is not the design weight.",
                "",
                "Question importance is not a sampling quantity.",
                "Stratum counts feed into computing the probability, but are not the weight.",
            ],
            "remember",
            1.5,
        ),
        (
            "Non-response adjustment of weights assumes that:",
            [
                "Non-respondents do not exist in the population",
                "Within an adjustment class, respondents and non-respondents are similar on the "
                "variables of interest",
                "Non-response is always below 10%",
                "The survey was a census",
            ],
            1,
            "The adjustment inflates respondent weights to cover the non-respondents in the same "
            "class, which only recovers the population if those two groups resemble each other "
            "within the class. This is an untestable assumption, which is why the choice of "
            "adjustment class matters so much.",
            [
                "They exist; the adjustment is an attempt to represent them.",
                "",
                "There is no threshold that makes the assumption true — though a high rate makes "
                "it far more consequential.",
                "The adjustment is specific to sampling.",
            ],
            "understand",
            2.7,
        ),
        (
            "Calibration (post-stratification) to known population totals primarily aims to:",
            [
                "Increase the sample size",
                "Reduce both coverage bias and variance by forcing weighted totals to match "
                "reliable external benchmarks",
                "Replace missing values in individual records",
                "Simplify variance estimation",
            ],
            1,
            "If the weighted sample reproduces census age-sex-district totals, differential "
            "coverage and non-response on those dimensions are corrected, and estimates "
            "correlated with them gain precision as a side benefit.",
            [
                "The achieved sample is unchanged.",
                "",
                "That is imputation, which operates on records rather than weights.",
                "Calibration makes variance estimation harder, not easier — it introduces "
                "dependence between weights.",
            ],
            "apply",
            3.4,
        ),
        (
            "A ratio estimator is preferred to a simple expansion estimator when:",
            [
                "The auxiliary variable is unrelated to the study variable",
                "There is a strong positive linear relationship through the origin between the "
                "study and auxiliary variables",
                "The sample is very small",
                "The population total of the auxiliary variable is unknown",
            ],
            1,
            "The ratio estimator borrows precision from the auxiliary variable, and the amount it "
            "borrows depends on the strength of the relationship. Through the origin matters: a "
            "relationship with a large intercept is better served by a regression estimator.",
            [
                "With no relationship the ratio estimator adds variance and bias for nothing.",
                "",
                "Small samples make the ratio estimator's bias *more* pronounced, since it is "
                "only approximately unbiased.",
                "Knowing the auxiliary total is a precondition for using it at all.",
            ],
            "analyse",
            4.0,
        ),
        (
            "Weight trimming — capping unusually large survey weights — trades:",
            [
                "Bias for variance: it reduces variance at the cost of introducing some bias",
                "Variance for bias: it reduces bias at the cost of variance",
                "Nothing; it is a pure improvement",
                "Sample size for precision",
            ],
            0,
            "A handful of very large weights lets a few records dominate an estimate, inflating "
            "its variance. Capping them stabilises the estimate but breaks the unbiasedness the "
            "design guaranteed. It is a judgement call, and it should be documented rather than "
            "applied silently.",
            [
                "",
                "The direction is reversed. Untrimmed weights are unbiased by design; trimming "
                "is what introduces bias.",
                "It is explicitly a trade-off, which is why trimming thresholds are contested.",
                "Sample size is unchanged.",
            ],
            "evaluate",
            4.6,
        ),
        (
            "An estimator is described as consistent. This means that:",
            [
                "It gives the same answer every time it is computed",
                "It converges in probability to the true parameter as the sample size grows",
                "It is unbiased in every sample",
                "It has the smallest possible variance",
            ],
            1,
            "Consistency is an asymptotic property about behaviour as n grows. It is weaker than "
            "unbiasedness in one sense and stronger in another: a consistent estimator may be "
            "biased in small samples, but the bias vanishes.",
            [
                "That is determinism, not consistency.",
                "",
                "Unbiasedness is a finite-sample property; the two are distinct and neither "
                "implies the other.",
                "That is efficiency.",
            ],
            "understand",
            2.4,
        ),
        (
            "Small area estimation methods are used when:",
            [
                "The population is small",
                "Direct survey estimates for a domain are too imprecise because few sample units "
                "fall in it",
                "The survey has no weights",
                "Census data are unavailable",
            ],
            1,
            "A national survey designed for state-level precision yields very few units per "
            "district. Small area methods borrow strength across areas and from auxiliary data, "
            "accepting model dependence in exchange for usable district numbers.",
            [
                "The area is small in *sample*, which is not the same as a small population.",
                "",
                "Weights are still required; the problem is domain sample size.",
                "Census and administrative data are usually the auxiliary inputs these methods "
                "depend on, so their absence is a barrier rather than a trigger.",
            ],
            "apply",
            3.7,
        ),
        (
            "In a Fay-Herriot small area model, the estimate for a district is essentially:",
            [
                "The direct survey estimate, always",
                "A weighted compromise between the direct estimate and a regression prediction, "
                "weighted by their relative precision",
                "The state average applied uniformly",
                "The census figure for that district",
            ],
            1,
            "The model shrinks the direct estimate towards the synthetic prediction, and the "
            "amount of shrinkage depends on the sampling variance: a district with a large sample "
            "keeps its own estimate, a district with almost none is pulled towards the model.",
            [
                "Using only the direct estimate is what the method exists to improve on.",
                "",
                "A uniform state average discards all district information — that is the "
                "synthetic extreme the model deliberately avoids.",
                "The census figure may enter as a covariate but does not replace the estimate.",
            ],
            "evaluate",
            4.9,
        ),
        (
            "Imputation of a missing income value using the mean of respondents in the same "
            "class will, if not otherwise corrected:",
            [
                "Inflate the estimated variance of income",
                "Understate the variance of income, because imputed values carry no dispersion",
                "Leave the variance unchanged",
                "Make the mean estimate biased upwards",
            ],
            1,
            "Every imputed record sits exactly at the class mean, so the observed spread is "
            "artificially compressed. The point estimate can be reasonable while the standard "
            "error is badly understated — which is worse than an obviously wrong number, because "
            "it looks confident.",
            [
                "The effect is the opposite; imputed values reduce apparent spread.",
                "",
                "Adding values at the mean necessarily lowers the variance.",
                "Mean imputation preserves the class mean; the bias risk is in the variance.",
            ],
            "analyse",
            4.2,
        ),
        (
            "The coefficient of variation of an estimate is reported as 22%. For most official "
            "publication standards this estimate should be:",
            [
                "Published without qualification",
                "Published with a reliability flag, or suppressed, because it is too imprecise to "
                "stand alone",
                "Recomputed with a different estimator",
                "Multiplied by 0.22 before release",
            ],
            1,
            "Most statistical offices treat a CV above roughly 15-20% as unreliable and flag or "
            "suppress it. The number is not wrong — it is simply too uncertain for a user to act "
            "on without knowing that.",
            [
                "Unflagged publication invites a user to read a very noisy figure as firm.",
                "",
                "A different estimator does not create information that the sample does not "
                "contain.",
                "Not a meaningful operation.",
            ],
            "apply",
            3.2,
        ),
        (
            "Bootstrap and jackknife replication weights are distributed with a survey microdata "
            "file mainly so that users can:",
            [
                "Reproduce the sample selection",
                "Compute standard errors that account for the complex design without access to "
                "confidential design variables",
                "Identify individual respondents",
                "Reduce the file size",
            ],
            1,
            "Stratum and PSU identifiers are disclosive, so they cannot be released. Replicate "
            "weights encode the design's variance structure without revealing it, letting an "
            "outside analyst compute correct standard errors from a safe file.",
            [
                "They do not reconstruct selection.",
                "",
                "The opposite — they exist to *avoid* releasing identifying design variables.",
                "They substantially increase file size.",
            ],
            "evaluate",
            4.5,
        ),
        (
            "A population total is estimated by summing weighted values across the sample. This "
            "is known as:",
            [
                "The Horvitz-Thompson estimator",
                "The bootstrap estimator",
                "The likelihood estimator",
                "The Bayes estimator",
            ],
            0,
            "The Horvitz-Thompson estimator sums y_i / π_i over the sample. It is unbiased for "
            "any probability sampling design, which is what makes it the foundation of "
            "design-based inference.",
            [
                "",
                "The bootstrap is a variance estimation technique, not a point estimator of a "
                "total.",
                "Likelihood estimation is a model-based approach, not this design-based sum.",
                "A Bayes estimator requires a prior and a model.",
            ],
            "remember",
            1.9,
        ),
    ],

    # ----------------------------------------------------------- STAT-NAS --
    "STAT-NAS": [
        (
            "Gross Domestic Product at market prices differs from Gross Value Added at basic "
            "prices by:",
            [
                "Net exports",
                "Product taxes less product subsidies",
                "Consumption of fixed capital",
                "Net factor income from abroad",
            ],
            1,
            "GDP at market prices = GVA at basic prices + product taxes - product subsidies. The "
            "two valuations differ precisely by the taxes and subsidies attached to products, "
            "which is why a change in GST rates moves GDP and GVA differently.",
            [
                "Net exports are a component of expenditure-side GDP, not the bridge between "
                "these two valuations.",
                "",
                "Consumption of fixed capital is the bridge from *gross* to *net*.",
                "Net factor income from abroad is the bridge from domestic to *national* product.",
            ],
            "understand",
            2.6,
        ),
        (
            "In the production approach, value added is computed as:",
            [
                "Output plus intermediate consumption",
                "Output minus intermediate consumption",
                "Output minus wages",
                "Sales minus purchases of fixed assets",
            ],
            1,
            "Value added measures what a producer contributes, so the inputs bought from others "
            "are netted out. Failing to net them is what causes double counting when the same "
            "output is an input somewhere downstream.",
            [
                "Adding intermediate consumption double-counts inputs across the chain.",
                "",
                "Wages are part of value added, being a component of the income the process "
                "generates.",
                "Fixed asset purchases are capital formation, not intermediate consumption.",
            ],
            "remember",
            1.4,
        ),
        (
            "Gross Fixed Capital Formation includes:",
            [
                "Purchases of land",
                "Acquisition of machinery, buildings and intellectual property products used in "
                "production for more than a year",
                "Purchases of shares",
                "Wages paid to construction workers by a household",
            ],
            1,
            "GFCF covers produced fixed assets used repeatedly in production over more than one "
            "accounting period. The 1993 and 2008 SNA revisions progressively brought software, "
            "R&D and other intellectual property products inside this boundary.",
            [
                "Land is a non-produced asset; its purchase is a transfer between sectors, not "
                "capital formation. Improvements to land do count.",
                "",
                "Shares are financial assets, recorded in the financial account.",
                "That is compensation of employees, though the resulting structure would be "
                "capital formation.",
            ],
            "apply",
            3.3,
        ),
        (
            "The base year of a national accounts series is revised periodically mainly because:",
            [
                "The old base year had errors",
                "Relative prices and the structure of the economy change, so old weights "
                "misrepresent current activity",
                "International agreements require it annually",
                "It reduces the size of the dataset",
            ],
            1,
            "Volume measures use base-year prices as weights. As sectors grow and shrink and "
            "relative prices move, those weights drift from the current economy and the growth "
            "rate they produce becomes less meaningful. Rebasing also brings in new data sources.",
            [
                "Rebasing is not error correction — the old series was correct on its own basis.",
                "",
                "There is no annual requirement; base revisions happen every several years.",
                "Dataset size is irrelevant.",
            ],
            "understand",
            2.8,
        ),
        (
            "Quarterly GDP estimates in India rely substantially on indicator-based extrapolation "
            "rather than direct measurement. The main consequence is that:",
            [
                "Quarterly estimates cannot be compared with annual ones",
                "Early quarterly estimates are more prone to revision as firmer annual data "
                "arrive",
                "Quarterly estimates are always higher than annual ones",
                "Seasonal adjustment becomes unnecessary",
            ],
            1,
            "Indicators such as IIP, corporate results and commodity production proxy for value "
            "added in the absence of quarterly enterprise surveys. When annual audited data land, "
            "the benchmark moves and the quarterly path is revised — routine, and not a defect, "
            "but it makes early quarters weak evidence for a turning point.",
            [
                "They are reconciled to annual totals by benchmarking, so they are comparable.",
                "",
                "No systematic upward relationship exists.",
                "Seasonality remains and still requires adjustment.",
            ],
            "analyse",
            4.3,
        ),
        (
            "The 'informal sector' in Indian national accounts is estimated largely through:",
            [
                "Direct enumeration of every unincorporated enterprise each year",
                "Benchmark-indicator methods using labour input from employment surveys and value "
                "added per worker from enterprise surveys",
                "Corporate income tax filings",
                "Import-export records",
            ],
            1,
            "The workforce is estimated from PLFS-type surveys and multiplied by value added per "
            "worker from periodic enterprise surveys such as NSS unincorporated enterprise "
            "rounds. The method's accuracy depends on both inputs, which is why it is the most "
            "debated part of the estimates.",
            [
                "Annual enumeration of the entire informal sector is infeasible at that scale.",
                "",
                "By definition most informal units fall outside corporate tax filings.",
                "Trade records cover a different domain entirely.",
            ],
            "evaluate",
            4.7,
        ),
        (
            "A deflator used to convert a series from current to constant prices is:",
            [
                "Always the Consumer Price Index",
                "A price index appropriate to the specific flow being deflated",
                "The GDP growth rate",
                "The exchange rate",
            ],
            1,
            "Each flow needs a deflator matching its own price behaviour — WPI or PPI components "
            "for many industrial outputs, CPI components for parts of consumption, wage indices "
            "where output is measured by input. Using one economy-wide index everywhere imports "
            "error into every sector it does not fit.",
            [
                "CPI covers household consumption, which is only one part of the accounts.",
                "",
                "The GDP growth rate is an output, not an input.",
                "The exchange rate converts currencies, not prices over time.",
            ],
            "apply",
            3.5,
        ),
        (
            "Imputed rent of owner-occupied dwellings is included in GDP because:",
            [
                "Home owners pay rent to themselves",
                "Excluding it would make GDP fall when a tenant buys the house they live in, with "
                "no change in actual housing services",
                "It increases the level of GDP",
                "International agencies require a higher GDP figure",
            ],
            1,
            "The same dwelling provides the same service whether rented or owner-occupied. "
            "Without imputation, a shift in tenure patterns would move GDP while nothing real "
            "changed, and the series would not be comparable across countries with different "
            "ownership rates.",
            [
                "No transaction occurs; the entry is an imputation, which is exactly what makes "
                "it contentious.",
                "",
                "Raising the level is a consequence, not a reason.",
                "The standard exists for comparability, not for inflation of the figure.",
            ],
            "analyse",
            4.1,
        ),
        (
            "Net National Income differs from Net Domestic Product by:",
            [
                "Consumption of fixed capital",
                "Net factor income from abroad",
                "Indirect taxes",
                "Change in stocks",
            ],
            1,
            "Domestic concepts count production inside the territory; national concepts count "
            "income accruing to residents. The bridge is net factor income from abroad, which for "
            "a large remittance-receiving economy is not a small correction.",
            [
                "That is the gross-to-net bridge, already applied in both terms here.",
                "",
                "Indirect taxes bridge factor cost and market prices.",
                "Change in stocks is a component of capital formation.",
            ],
            "understand",
            2.3,
        ),
        (
            "Chain-linking of volume series is preferred to a fixed base mainly because it:",
            [
                "Produces higher growth rates",
                "Keeps weights close to current relative prices, reducing substitution bias in "
                "the volume measure",
                "Removes the need for deflators",
                "Makes components exactly additive",
            ],
            1,
            "Chain-linking updates weights each period, so the index reflects the economy as it "
            "currently is rather than as it was in a distant base year. The known cost is "
            "non-additivity: chained components no longer sum exactly to the chained total.",
            [
                "The direction of the effect is not fixed and depends on the data.",
                "",
                "Deflators are still required — chain-linking changes how they are combined.",
                "Chain-linking *destroys* additivity, which is its main practical drawback.",
            ],
            "evaluate",
            4.8,
        ),
        (
            "In the 2008 SNA, expenditure on research and development is treated as:",
            [
                "Intermediate consumption",
                "Gross fixed capital formation",
                "A financial transaction",
                "A transfer",
            ],
            1,
            "R&D produces an asset that yields benefits over several periods, so the 2008 SNA "
            "capitalises it. Before that revision it was expensed as intermediate consumption, "
            "which is one reason back-series comparisons across SNA vintages need care.",
            [
                "This was the pre-2008 treatment.",
                "",
                "No financial claim is created.",
                "A transfer involves no quid pro quo, which is not the case here.",
            ],
            "apply",
            3.9,
        ),
        (
            "The statistical discrepancy in national accounts arises because:",
            [
                "Data are falsified",
                "The production, income and expenditure approaches are built from partly "
                "independent sources and do not reconcile exactly",
                "GDP is rounded",
                "Exports are excluded",
            ],
            1,
            "Each approach should in principle give the same total. In practice they draw on "
            "different surveys and administrative records with different coverage and timing, so "
            "a residual remains. Publishing it is a statement of honesty about source quality; "
            "forcing it to zero would conceal the same uncertainty.",
            [
                "It is a measurement artefact, not misconduct.",
                "",
                "Rounding is far too small to explain it.",
                "Exports are included in the expenditure approach.",
            ],
            "analyse",
            3.7,
        ),
    ],

    # -------------------------------------------------------- STAT-INDEX --
    "STAT-INDEX": [
        (
            "A Laspeyres price index uses quantity weights from:",
            [
                "The current period",
                "The base period",
                "The average of both periods",
                "A forecast period",
            ],
            1,
            "Laspeyres fixes the basket at the base period and asks what that basket costs now. "
            "Holding the basket fixed is what makes it computable month to month without "
            "re-surveying quantities, and also what gives it its known upward drift.",
            [
                "Current-period weights define the Paasche index.",
                "",
                "A symmetric average of both is the Fisher index.",
                "Forecast weights are not used in any standard index formula.",
            ],
            "remember",
            1.5,
        ),
        (
            "Substitution bias in a fixed-basket consumer price index means the index tends to:",
            [
                "Understate inflation, because consumers buy more of what became cheaper",
                "Overstate inflation, because it ignores consumers shifting away from goods whose "
                "prices rose",
                "Be unaffected, since the basket is representative",
                "Fluctuate randomly around the true value",
            ],
            1,
            "When a good's price rises, households buy less of it — but the fixed basket keeps "
            "charging them the old quantity at the new price. The index therefore prices a basket "
            "nobody is still buying, and overstates the cost of maintaining living standards.",
            [
                "The direction is reversed. Ignoring substitution inflates the measured cost.",
                "",
                "Representativeness at the base period is exactly what decays as prices move.",
                "The bias is systematic and one-directional, not random.",
            ],
            "understand",
            2.7,
        ),
        (
            "India's Consumer Price Index (Combined) and the Wholesale Price Index can diverge "
            "substantially for an extended period mainly because:",
            [
                "One is computed monthly and the other quarterly",
                "They cover different baskets — WPI excludes services and covers transactions at "
                "wholesale level, while CPI includes services and retail margins",
                "WPI is seasonally adjusted and CPI is not",
                "CPI is published by RBI and WPI by MoSPI",
            ],
            1,
            "WPI has no services component at all and prices goods before retail margins and "
            "taxes; CPI weights services heavily, including housing, education and health. A "
            "shock confined to tradable goods moves WPI far more than CPI, and a services-driven "
            "one does the reverse.",
            [
                "Both are monthly.",
                "",
                "Neither headline series is published seasonally adjusted as the primary figure.",
                "CPI is compiled by NSO under MoSPI; WPI by the Office of the Economic Adviser, "
                "DPIIT. Neither is RBI's.",
            ],
            "analyse",
            3.9,
        ),
        (
            "The Fisher ideal index is the:",
            [
                "Arithmetic mean of Laspeyres and Paasche",
                "Geometric mean of Laspeyres and Paasche",
                "Larger of Laspeyres and Paasche",
                "Laspeyres index with updated weights",
            ],
            1,
            "Fisher is the geometric mean of the two, which is what gives it the time-reversal "
            "and factor-reversal properties neither parent satisfies. It is 'ideal' in that "
            "axiomatic sense rather than in any practical one — it needs current-period "
            "quantities, which usually arrive too late for a monthly release.",
            [
                "The arithmetic mean is sometimes used as an approximation but lacks the "
                "reversal properties.",
                "",
                "Taking the larger has no theoretical justification.",
                "Updating Laspeyres weights produces a chained Laspeyres, not Fisher.",
            ],
            "apply",
            3.6,
        ),
        (
            "Quality adjustment in a price index is required when:",
            [
                "The price of an item changes",
                "An item in the basket is replaced by one with different characteristics, so part "
                "of the price change reflects quality rather than inflation",
                "The weight of an item changes",
                "A new base year is adopted",
            ],
            1,
            "If last year's phone is replaced by a faster one at a higher price, some of that "
            "increase buys more product rather than costing more for the same thing. Without "
            "adjustment — hedonic, option-cost or overlap pricing — the index reads quality "
            "improvement as inflation.",
            [
                "Ordinary price change is what the index is measuring.",
                "",
                "Weight changes are a reweighting issue, handled separately.",
                "Rebasing is a distinct operation.",
            ],
            "analyse",
            4.2,
        ),
        (
            "The Index of Industrial Production measures:",
            [
                "The value of industrial output at current prices",
                "The volume of industrial production relative to a base year",
                "Industrial employment",
                "Industrial profits",
            ],
            1,
            "IIP is a volume index: it tracks physical production against a base period, holding "
            "value weights fixed. That is why it can fall while the value of output rises, if "
            "prices are increasing faster than volumes.",
            [
                "Current-price value would confound price and volume, which is what IIP exists "
                "to separate.",
                "",
                "Employment is measured separately.",
                "Profit is not an output measure.",
            ],
            "remember",
            1.8,
        ),
        (
            "A weighted index shows a large jump in one month traced to a single item with a "
            "small weight. The most likely explanation is:",
            [
                "A computational error, since a small weight cannot move the index",
                "An extreme price relative for that item, since the contribution is weight times "
                "price relative",
                "The base year is wrong",
                "Seasonal adjustment failed",
            ],
            1,
            "Contribution is the product of weight and price change. A 2% weight paired with a "
            "300% price relative contributes as much as a 30% weight with a 20% move — which is "
            "why vegetable prices can dominate a monthly CPI print despite a modest weight.",
            [
                "A small weight constrains the contribution but does not bound it at zero; a "
                "large enough relative overcomes it.",
                "",
                "The base year affects levels, not a single month's movement.",
                "Headline index series are not seasonally adjusted, and this pattern is "
                "consistent with a genuine price spike.",
            ],
            "evaluate",
            4.5,
        ),
        (
            "Splicing two index series with different base years requires:",
            [
                "Discarding the older series",
                "Multiplying the older series by the ratio of the two indices in an overlapping "
                "period",
                "Averaging the two series",
                "Recomputing the older series from original price data",
            ],
            1,
            "The overlap period gives a conversion factor that puts both series on one base. It "
            "preserves the movements each series measured, while making clear that the spliced "
            "history is a linkage rather than a single consistently defined series.",
            [
                "Discarding history loses the comparison the splice exists to permit.",
                "",
                "Averaging mixes two different bases and measures nothing.",
                "Sometimes ideal but rarely possible — the original microdata and weights are "
                "usually unavailable.",
            ],
            "apply",
            3.3,
        ),
        (
            "A chained index differs from a fixed-base index in that it:",
            [
                "Uses no weights",
                "Updates weights each period and links successive period-to-period comparisons",
                "Is always higher",
                "Cannot be used for inflation",
            ],
            1,
            "Chaining multiplies successive links, each computed with near-current weights. It "
            "tracks a changing economy better and, as the price of that, loses transitivity: the "
            "chained comparison between two distant periods depends on the path taken between "
            "them.",
            [
                "Weights are central to chaining; they are simply refreshed.",
                "",
                "Chain drift can run in either direction, and is worst with volatile prices that "
                "bounce back.",
                "Chained indices are used for inflation in many national systems.",
            ],
            "understand",
            3.0,
        ),
        (
            "In constructing a CPI, the weighting diagram is derived from:",
            [
                "Wholesale transaction records",
                "Household consumption expenditure survey data",
                "Producer output volumes",
                "Import tariff schedules",
            ],
            1,
            "Weights represent how households actually allocate spending, which only a "
            "consumption expenditure survey measures. Their age is a standing weakness of any "
            "CPI: weights drawn from a survey a decade old describe a spending pattern that has "
            "since moved.",
            [
                "Wholesale records inform WPI, not CPI weights.",
                "",
                "Producer volumes relate to output indices such as IIP.",
                "Tariffs affect some prices but do not describe household spending.",
            ],
            "apply",
            2.9,
        ),
        (
            "A price index is said to satisfy the time reversal test if:",
            [
                "It gives the same value in every period",
                "The index from period 0 to 1 is the reciprocal of the index from 1 to 0",
                "It can be computed backwards in time",
                "Its base year can be changed freely",
            ],
            1,
            "Formally, P01 × P10 = 1. Laspeyres and Paasche each fail it — reversing the "
            "comparison swaps which period's basket is fixed. Fisher passes, which is the main "
            "reason it is called ideal.",
            [
                "Constancy is not a property any useful index has.",
                "",
                "Computability backwards is not the same as the reciprocal relation holding.",
                "That is a separate matter of rebasing.",
            ],
            "evaluate",
            4.7,
        ),
        (
            "Two states report the same CPI inflation rate, but one has a much higher share of "
            "food in its weighting diagram. A sharp rise in cereal prices will:",
            [
                "Affect both states' indices equally",
                "Raise the index more in the state with the higher food weight",
                "Have no effect until the base year changes",
                "Lower the index in the state with the higher food weight",
            ],
            1,
            "Contribution scales with the weight, so the same price relative moves a "
            "food-heavy index further. This is why a single national inflation figure can "
            "understate what poorer states and poorer households actually face — their baskets "
            "are more concentrated in exactly the items that moved.",
            [
                "Equal effect would require equal weights.",
                "",
                "The effect appears in the month the price moves.",
                "A price rise cannot lower the index.",
            ],
            "apply",
            3.4,
        ),
    ],

    # ---------------------------------------------------------- TECH-ANL --
    "TECH-ANL": [
        (
            "Supervised learning differs from unsupervised learning in that supervised methods:",
            [
                "Require more computing power",
                "Train on data where the target outcome is known for each record",
                "Always produce better accuracy",
                "Cannot be used for classification",
            ],
            1,
            "The label is the defining difference. Supervised methods learn a mapping from "
            "features to a known outcome; unsupervised methods look for structure where no "
            "outcome is given.",
            [
                "Compute requirements depend on the algorithm, not the paradigm.",
                "",
                "Accuracy is not even defined without labels, so the comparison does not hold.",
                "Classification is the archetypal supervised task.",
            ],
            "remember",
            1.4,
        ),
        (
            "A model achieves 97% accuracy predicting whether a household is below the poverty "
            "line, in a population where 96% are above it. This accuracy is:",
            [
                "Excellent evidence the model works",
                "Nearly uninformative, because always predicting the majority class would score "
                "96%",
                "Impossible",
                "Proof of overfitting",
            ],
            1,
            "With severe class imbalance, accuracy is dominated by the majority class. The "
            "model may be identifying almost none of the poor households while scoring 97%. "
            "Recall on the minority class, precision, or the area under the precision-recall "
            "curve are the figures that would actually say.",
            [
                "The headline figure conceals rather than demonstrates performance.",
                "",
                "Entirely possible, and common.",
                "Overfitting is a different failure; this is a metric-choice failure and could "
                "occur with no overfitting at all.",
            ],
            "evaluate",
            4.4,
        ),
        (
            "Cross-validation is used primarily to:",
            [
                "Increase the size of the training set",
                "Estimate how a model will perform on data it has not seen, using the data "
                "available",
                "Remove outliers",
                "Choose the target variable",
            ],
            1,
            "By rotating which fold is held out, every record serves once as test data. It gives "
            "a less optimistic and less noisy estimate of out-of-sample performance than a single "
            "train-test split.",
            [
                "The data volume is unchanged; only its use rotates.",
                "",
                "Outlier handling is a separate preprocessing decision.",
                "The target is defined by the problem.",
            ],
            "understand",
            2.5,
        ),
        (
            "Overfitting is best described as a model that:",
            [
                "Has too few parameters to capture the pattern",
                "Fits noise in the training data and therefore generalises poorly",
                "Runs too slowly",
                "Uses too many records",
            ],
            1,
            "An overfitted model has learned the particular sample rather than the underlying "
            "relationship. The signature is a large and widening gap between training and "
            "validation performance.",
            [
                "That is underfitting.",
                "",
                "Speed is unrelated.",
                "More records generally reduce overfitting.",
            ],
            "remember",
            1.9,
        ),
        (
            "Regularisation such as L1 (lasso) is applied in order to:",
            [
                "Increase model complexity",
                "Penalise large coefficients, shrinking some to zero and so performing variable "
                "selection",
                "Speed up data loading",
                "Convert categorical variables to numeric",
            ],
            1,
            "L1 adds a penalty proportional to the absolute size of coefficients. Because the "
            "penalty has a corner at zero, it drives weak predictors exactly to zero, which is "
            "why it doubles as a feature selector where L2 does not.",
            [
                "Regularisation constrains complexity.",
                "",
                "It is a modelling technique, not an I/O one.",
                "That is encoding.",
            ],
            "apply",
            3.5,
        ),
        (
            "A statistical office deploys a model that predicts which enterprises are likely to "
            "misreport turnover, and directs audits accordingly. Audited firms found to misreport "
            "are fed back as training data. The main methodological danger is:",
            [
                "The training set grows too large",
                "A feedback loop: the model only ever learns about firms it already flagged, so "
                "its blind spots become self-confirming",
                "The model becomes too slow",
                "Auditors will disagree with the model",
            ],
            1,
            "Labels arrive only for firms the model selected, so misreporting among firms it "
            "never flags is never observed. Accuracy on the audited subset rises while coverage "
            "of the real problem may not. A random audit reserve, sampled outside the model's "
            "recommendations, is the standard remedy.",
            [
                "Volume is not the issue.",
                "",
                "Latency is an engineering concern, not a methodological one.",
                "Disagreement is manageable and is not the structural flaw here.",
            ],
            "evaluate",
            4.9,
        ),
        (
            "In a confusion matrix for a binary classifier, recall is:",
            [
                "True positives divided by all predicted positives",
                "True positives divided by all actual positives",
                "True negatives divided by all actual negatives",
                "Correct predictions divided by total predictions",
            ],
            1,
            "Recall asks what share of the real cases the model caught. Precision — the first "
            "option — asks what share of its alarms were real. Which one matters depends "
            "entirely on the cost of a miss against the cost of a false alarm.",
            [
                "That is precision.",
                "",
                "That is specificity.",
                "That is accuracy.",
            ],
            "understand",
            2.8,
        ),
        (
            "Multicollinearity among predictors in a linear regression primarily:",
            [
                "Biases the coefficient estimates",
                "Inflates the standard errors of individual coefficients, making them unstable "
                "and hard to interpret",
                "Reduces the model's predictive accuracy severely",
                "Prevents the model from converging",
            ],
            1,
            "With correlated predictors the data cannot separate their individual contributions, "
            "so coefficients swing wildly between samples. Predictions from the model as a whole "
            "can remain perfectly good — which is why multicollinearity matters for explanation "
            "far more than for forecasting.",
            [
                "Estimates stay unbiased; it is their variance that suffers.",
                "",
                "Predictive accuracy is often largely unaffected.",
                "Convergence fails only under exact collinearity.",
            ],
            "analyse",
            4.1,
        ),
        (
            "Data leakage in a predictive model means that:",
            [
                "Records were lost during processing",
                "Information unavailable at prediction time has entered the training features, "
                "inflating measured performance",
                "The dataset was disclosed publicly",
                "Missing values were imputed",
            ],
            1,
            "A feature derived from the outcome, or from after the prediction point, lets the "
            "model appear to know things it could not know in production. The signature is "
            "validation performance that looks too good and collapses on deployment.",
            [
                "That is data loss.",
                "",
                "That is a disclosure incident — a real problem, but a different one.",
                "Imputation done correctly is not leakage; imputing using the full dataset "
                "before splitting is.",
            ],
            "analyse",
            4.0,
        ),
        (
            "A random forest improves on a single decision tree mainly by:",
            [
                "Growing one much deeper tree",
                "Averaging many de-correlated trees, which reduces variance",
                "Removing all categorical variables",
                "Requiring less data",
            ],
            1,
            "Bootstrap samples and random feature subsets make the trees differ from one another, "
            "and averaging predictors that err in different directions cancels much of the "
            "variance a single tree suffers from.",
            [
                "Depth alone increases overfitting.",
                "",
                "Trees handle categorical predictors natively.",
                "Ensembles typically need at least as much data.",
            ],
            "apply",
            3.2,
        ),
        (
            "The difference between correlation and causation matters most when a model is used "
            "to:",
            [
                "Rank records by predicted risk",
                "Decide which intervention to apply, since acting on a non-causal predictor will "
                "not change the outcome",
                "Compute summary statistics",
                "Visualise a distribution",
            ],
            1,
            "A predictive model can rank well on correlations alone. The moment its output drives "
            "an intervention, the question changes from 'what goes together' to 'what happens if "
            "I change this', and only a causal claim answers that.",
            [
                "Ranking is exactly where correlational models are legitimate.",
                "",
                "Descriptive statistics make no causal claim.",
                "Visualisation is descriptive.",
            ],
            "evaluate",
            4.6,
        ),
        (
            "Standardising features before applying k-means clustering is important because:",
            [
                "It makes the algorithm run faster",
                "The distance metric is dominated by variables measured on larger numeric scales",
                "It removes missing values",
                "It guarantees a global optimum",
            ],
            1,
            "Euclidean distance adds squared differences across dimensions, so a variable in "
            "rupees swamps one measured as a proportion. Standardising puts them on comparable "
            "footing — otherwise the clustering is effectively driven by units of measurement.",
            [
                "Any speed effect is incidental.",
                "",
                "Missing values need separate handling.",
                "k-means converges to a local optimum regardless of scaling.",
            ],
            "apply",
            3.7,
        ),
    ],

    # ---------------------------------------------------------- TECH-GIS --
    "TECH-GIS": [
        (
            "A coordinate reference system defines:",
            [
                "The colour scheme of a map",
                "How positions on the curved earth are represented as coordinates",
                "The scale bar length",
                "The file format of spatial data",
            ],
            1,
            "A CRS ties coordinates to locations on the earth, combining a datum, an ellipsoid "
            "and — for projected systems — a projection. Without it a pair of numbers is not a "
            "location.",
            [
                "Symbology is a cartographic choice, separate from the CRS.",
                "",
                "The scale bar reflects the CRS but does not define it.",
                "Format (shapefile, GeoPackage, GeoJSON) is independent of CRS.",
            ],
            "remember",
            1.5,
        ),
        (
            "Vector and raster data models differ in that vector data represents features as:",
            [
                "A grid of cells with values",
                "Points, lines and polygons with explicit coordinates",
                "Colour photographs only",
                "Tables without geometry",
            ],
            1,
            "Vector stores discrete geometry — administrative boundaries, roads, survey points. "
            "Raster stores a continuous grid, which suits surfaces like elevation, land cover or "
            "night-lights.",
            [
                "That describes raster.",
                "",
                "Imagery is one kind of raster, not the definition of vector.",
                "Geometry is exactly what vector data carries.",
            ],
            "remember",
            1.7,
        ),
        (
            "A buffer analysis around health facilities is most directly used to:",
            [
                "Calculate the area of each district",
                "Identify the population or features within a specified distance of each facility",
                "Reproject the dataset",
                "Compress the data",
            ],
            1,
            "Buffering generates zones at a set distance, which can then be intersected with "
            "population layers to answer access questions — how many people live within 5 km of "
            "a primary health centre.",
            [
                "Area calculation is a separate geometric operation.",
                "",
                "Reprojection is a coordinate operation.",
                "Compression is a storage concern.",
            ],
            "apply",
            2.6,
        ),
        (
            "Spatial autocorrelation means that:",
            [
                "Spatial data are always inaccurate",
                "Nearby locations tend to have more similar values than distant ones",
                "Coordinates are duplicated",
                "The data must be projected before use",
            ],
            1,
            "Tobler's first law. It violates the independence assumption behind ordinary "
            "regression, which is why spatial data usually need explicit spatial models — and "
            "why a standard error computed as though observations were independent is too small.",
            [
                "Autocorrelation is a property of the phenomenon, not an error.",
                "",
                "Duplication is a data quality issue.",
                "Projection is unrelated.",
            ],
            "understand",
            3.0,
        ),
        (
            "Moran's I is a statistic that measures:",
            [
                "The area of a polygon",
                "The degree of spatial autocorrelation in a variable across a study area",
                "The accuracy of a GPS reading",
                "The number of features in a layer",
            ],
            1,
            "Moran's I runs from roughly -1 to +1: positive values mean like values cluster "
            "together, negative values mean they alternate, and a value near its expectation "
            "indicates a spatially random pattern.",
            [
                "Area is a geometric measurement.",
                "",
                "GPS accuracy is a positional quality measure.",
                "Feature count is a simple tally.",
            ],
            "apply",
            3.8,
        ),
        (
            "Topological errors such as slivers and gaps between adjacent administrative polygons "
            "matter most because they:",
            [
                "Make the map look untidy",
                "Cause area totals and spatial joins to be wrong, so records fall into no unit or "
                "two units",
                "Increase file size only",
                "Prevent the file from opening",
            ],
            1,
            "A household point in a sliver joins to nothing and disappears from every district "
            "total; an overlap assigns it twice. The visual defect is trivial next to the "
            "silent distortion of the statistics built on the layer.",
            [
                "Appearance is the least of it.",
                "",
                "Size effects are marginal.",
                "The file usually opens perfectly well, which is what makes this dangerous.",
            ],
            "analyse",
            4.0,
        ),
        (
            "Geocoding is the process of:",
            [
                "Encrypting spatial data",
                "Converting an address or place description into geographic coordinates",
                "Compressing raster tiles",
                "Assigning colours to map classes",
            ],
            1,
            "Geocoding turns textual location into coordinates. Its match rate and positional "
            "accuracy are themselves data quality measures — a 70% match rate means nearly a "
            "third of records are missing from any spatial analysis that follows.",
            [
                "Encryption is a security operation.",
                "",
                "Tiling and compression are storage operations.",
                "That is classification and symbology.",
            ],
            "remember",
            1.9,
        ),
        (
            "When overlaying a 30 m resolution land-cover raster with village boundaries to "
            "estimate built-up area, the principal source of error is:",
            [
                "The projection is always wrong",
                "Mixed pixels at boundaries, where a single cell contains more than one land "
                "cover class",
                "Raster files cannot be overlaid with vectors",
                "Village boundaries have no area",
            ],
            1,
            "At 30 m a single cell covers 900 m². Near edges and in sparsely built villages a "
            "large share of cells are mixed, and assigning each wholly to one class produces "
            "errors that do not average out — they are systematic in the direction of whichever "
            "class dominates the assignment rule.",
            [
                "Projection mismatch is a real risk but a correctable one, not inherent.",
                "",
                "Raster-vector overlay is routine.",
                "Polygons have area by definition.",
            ],
            "evaluate",
            4.6,
        ),
        (
            "A choropleth map showing total population by district is misleading mainly because:",
            [
                "Colours cannot represent counts",
                "Larger districts appear more prominent regardless of density, so area distorts "
                "the reading",
                "Districts change over time",
                "Population is not spatial",
            ],
            1,
            "Choropleths fill areas, so the eye weights each unit by its size. Raw counts should "
            "normally be mapped as rates or densities, or shown with proportional symbols, so "
            "that a sparsely populated large district does not read as a hotspot.",
            [
                "Colour can encode counts; the problem is the area weighting.",
                "",
                "Boundary change is a separate comparability issue.",
                "Population is very much spatial.",
            ],
            "analyse",
            4.2,
        ),
        (
            "The datum component of a coordinate reference system specifies:",
            [
                "The map's title block",
                "The reference ellipsoid and its orientation relative to the earth, fixing where "
                "coordinates actually sit",
                "The line thickness of boundaries",
                "The compression algorithm",
            ],
            1,
            "Two systems can share a projection and still disagree by hundreds of metres if their "
            "datums differ — WGS84 against a local datum, for instance. Datum mismatch is the "
            "classic cause of layers that look right individually and misalign when combined.",
            [
                "Cartographic furniture, not geodesy.",
                "",
                "Symbology.",
                "Storage.",
            ],
            "evaluate",
            4.8,
        ),
        (
            "Kriging differs from inverse distance weighting for spatial interpolation in that "
            "kriging:",
            [
                "Ignores distance entirely",
                "Uses a fitted model of spatial correlation and also yields a prediction variance",
                "Can only be used for elevation",
                "Requires no sample points",
            ],
            1,
            "Kriging fits a variogram describing how similarity decays with distance, and uses it "
            "to weight neighbours optimally. Its by-product — a variance surface showing where "
            "the prediction is weak — is often more useful than the prediction itself.",
            [
                "Distance is central to kriging.",
                "",
                "It applies to any continuous variable.",
                "Sample points are essential.",
            ],
            "evaluate",
            4.9,
        ),
        (
            "Boundary changes from district reorganisation break a time series of district-level "
            "indicators. The standard remedy is to:",
            [
                "Discard all data before the change",
                "Construct a consistent geography by aggregating to units stable across the whole "
                "period, or apportioning using a common small-area layer",
                "Ignore the change and compare the names",
                "Use a different projection",
            ],
            1,
            "Either roll up to parent units that did not change, or split and reallocate using "
            "sub-district building blocks. Comparing by name is the trap: a district keeps its "
            "name while losing half its territory, and the series shows a collapse that never "
            "happened.",
            [
                "Discarding history loses the comparison entirely.",
                "",
                "Name matching across a reorganisation is exactly the error to avoid.",
                "Projection is irrelevant to boundary change.",
            ],
            "analyse",
            4.4,
        ),
    ],

    # ---------------------------------------------------------- TECH-BIG --
    "TECH-BIG": [
        (
            "In distributed storage, replicating each data block across multiple nodes primarily "
            "provides:",
            [
                "Faster write speed",
                "Fault tolerance, so a node failure does not lose data",
                "Smaller storage footprint",
                "Stronger encryption",
            ],
            1,
            "Replication trades storage for durability: a three-way replicated cluster survives "
            "two node losses per block. Writes get slower, not faster, because every copy must be "
            "acknowledged.",
            [
                "Writes are slower, since more copies must be committed.",
                "",
                "It multiplies the footprint — typically threefold.",
                "Replication and encryption are independent concerns.",
            ],
            "understand",
            2.4,
        ),
        (
            "A columnar storage format such as Parquet is preferred over row-oriented CSV for "
            "analytical workloads because it:",
            [
                "Is human readable",
                "Lets a query read only the columns it needs, and compresses similar values "
                "together",
                "Supports more data types",
                "Requires no schema",
            ],
            1,
            "Analytical queries touch a handful of columns from wide tables. Columnar layout "
            "means the other columns are never read from disk at all, and storing like values "
            "adjacently compresses far better than mixed-type rows.",
            [
                "Parquet is binary and not human readable — a real cost of the format.",
                "",
                "Type support is a secondary difference.",
                "Parquet carries an explicit embedded schema; CSV is the one without.",
            ],
            "apply",
            3.4,
        ),
        (
            "The 'volume, velocity, variety' characterisation of big data identifies velocity as:",
            [
                "The size of the dataset",
                "The rate at which new data arrive and must be processed",
                "The number of different formats",
                "The speed of the network card",
            ],
            1,
            "Velocity is about arrival rate and the latency budget for acting on it. A stream of "
            "GST e-invoices arriving continuously poses a different problem from the same annual "
            "volume delivered as one file.",
            [
                "That is volume.",
                "",
                "That is variety.",
                "Hardware throughput is an implementation detail.",
            ],
            "remember",
            1.6,
        ),
        (
            "Eventual consistency in a distributed database means that:",
            [
                "Data are never consistent",
                "Replicas converge to the same value given no new writes, but a read may briefly "
                "return a stale value",
                "Writes are rejected during partitions",
                "Only one node may be written to",
            ],
            1,
            "It is a deliberate relaxation, trading immediate consistency for availability during "
            "network partitions. It is fine for a page view counter and dangerous for a "
            "confirmation that a statutory return was filed.",
            [
                "They converge; the guarantee is about timing, not absence.",
                "",
                "Rejecting writes during a partition is the strongly consistent choice.",
                "Single-writer designs are a different model.",
            ],
            "analyse",
            4.3,
        ),
        (
            "Partitioning a large table by survey round and state before analysis mainly:",
            [
                "Reduces the total data volume",
                "Lets the query engine skip partitions irrelevant to the filter, cutting scan "
                "time",
                "Improves data accuracy",
                "Removes the need for indexes",
            ],
            1,
            "Partition pruning means a query for one state in one round never reads the other "
            "partitions. The gain depends entirely on queries filtering on the partition key — "
            "partition by a column nobody filters on and it buys nothing.",
            [
                "Volume is unchanged.",
                "",
                "Accuracy is unaffected.",
                "Indexes remain useful within partitions.",
            ],
            "apply",
            3.6,
        ),
        (
            "Batch processing differs from stream processing in that batch jobs:",
            [
                "Process records one at a time as they arrive",
                "Process a bounded set of accumulated data at scheduled intervals",
                "Cannot be scheduled",
                "Always use less memory",
            ],
            1,
            "Batch works over a finite, complete dataset; streaming works over an unbounded one "
            "with no natural end. The distinction drives everything downstream — how failures are "
            "retried, how late-arriving records are handled, how results are revised.",
            [
                "That is streaming.",
                "",
                "Scheduling is central to batch.",
                "Batch jobs often use far more memory at once.",
            ],
            "understand",
            2.2,
        ),
        (
            "A data lake differs from a data warehouse principally in that a lake:",
            [
                "Holds only structured data",
                "Stores raw data in its native format, applying schema when the data are read",
                "Cannot be queried",
                "Is always cheaper to query",
            ],
            1,
            "Schema-on-read keeps options open and admits semi-structured sources, at the cost of "
            "pushing interpretation onto every consumer. Without catalogue discipline a lake "
            "becomes a swamp, which is the standard failure mode.",
            [
                "Lakes are built for mixed and unstructured data.",
                "",
                "Lakes are queried routinely.",
                "Query cost is often higher, since no schema optimisation was done on write.",
            ],
            "analyse",
            4.0,
        ),
        (
            "A statistical office wants to use mobile network operator data to estimate migration "
            "flows. The most serious representativeness threat is that:",
            [
                "The data volume is too large to process",
                "Phone ownership and network coverage vary systematically by income, gender, age "
                "and region",
                "The data are updated too frequently",
                "Operators use different file formats",
            ],
            1,
            "The coverage bias is structural, not random. Women, the elderly and the poorest are "
            "under-represented among subscribers, and multi-SIM users are double-counted — so the "
            "signal is strong and the population it describes is not the population of India.",
            [
                "Volume is an engineering problem with known solutions.",
                "",
                "Frequent updates are a benefit.",
                "Format differences are trivially handled.",
            ],
            "evaluate",
            4.7,
        ),
        (
            "Idempotency in a data pipeline means that:",
            [
                "Each record is processed exactly once, always",
                "Re-running the same job with the same input produces the same result, without "
                "duplicating effects",
                "The pipeline runs continuously",
                "Errors are silently ignored",
            ],
            1,
            "Distributed jobs fail and get retried, so a step that appends on every run doubles "
            "its output after one retry. Idempotent steps make retry safe, which is what makes a "
            "pipeline operable at all.",
            [
                "Exactly-once delivery is a stronger and much harder guarantee; idempotency is "
                "how systems approximate its effect.",
                "",
                "That is a streaming characteristic.",
                "Ignoring errors is the opposite of a well-built pipeline.",
            ],
            "evaluate",
            4.5,
        ),
        (
            "Horizontal scaling means:",
            [
                "Adding more memory and CPU to one machine",
                "Adding more machines that share the workload",
                "Storing data in wider tables",
                "Increasing the screen resolution of dashboards",
            ],
            1,
            "Scaling out rather than up. It is the model distributed frameworks assume, and it "
            "brings coordination costs — partitioning, shuffling, consistency — that a single "
            "larger machine avoids entirely.",
            [
                "That is vertical scaling.",
                "",
                "Table width is a schema matter.",
                "Unrelated.",
            ],
            "remember",
            1.8,
        ),
        (
            "Data lineage tracking in a production statistical pipeline is valuable mainly "
            "because it:",
            [
                "Reduces storage cost",
                "Shows which published outputs are affected when an upstream source is found to "
                "be wrong",
                "Encrypts intermediate outputs",
                "Speeds up computation",
            ],
            1,
            "When a source file turns out to have been misparsed, the immediate question is what "
            "has been published from it. Lineage answers that in minutes instead of days, and "
            "makes a targeted correction possible instead of a blanket one.",
            [
                "It adds metadata and so adds cost.",
                "",
                "Encryption is separate.",
                "It has no effect on runtime.",
            ],
            "apply",
            3.1,
        ),
        (
            "Running a job on a cloud platform with auto-scaling enabled, an analyst finds the "
            "cost far exceeded the estimate although the job completed on time. The most likely "
            "cause is:",
            [
                "Auto-scaling is always more expensive",
                "A skewed partition kept a few nodes busy while the cluster stayed scaled up "
                "waiting for them",
                "The data were compressed",
                "The cluster used too few nodes",
            ],
            1,
            "Data skew means one key holds a disproportionate share of records. Most tasks finish "
            "quickly, the straggler runs for an hour, and the entire scaled-up cluster is billed "
            "for that hour while nearly idle. Wall-clock time looks fine; utilisation does not.",
            [
                "Auto-scaling usually reduces cost when load varies.",
                "",
                "Compression reduces cost.",
                "Too few nodes would have shown as a longer runtime, which did not occur.",
            ],
            "evaluate",
            4.8,
        ),
    ],

    # ---------------------------------------------------------- TECH-VIZ --
    "TECH-VIZ": [
        (
            "A line chart is more appropriate than a bar chart when the horizontal axis "
            "represents:",
            [
                "Unordered categories",
                "A continuous ordered dimension such as time",
                "Percentages",
                "Geographic regions",
            ],
            1,
            "A line asserts that the space between points is meaningful and that intermediate "
            "values exist. That is true of time and false of categories, where a line implies a "
            "progression that is not there.",
            [
                "Connecting unordered categories implies an order that does not exist.",
                "",
                "Percentages can appear on either chart type.",
                "Regions are categorical unless deliberately ordered.",
            ],
            "understand",
            1.9,
        ),
        (
            "Truncating the vertical axis of a bar chart so it does not begin at zero is "
            "problematic because:",
            [
                "Bars cannot be drawn that way",
                "Bar length encodes magnitude, so a truncated axis exaggerates differences",
                "It changes the underlying data",
                "Colour becomes meaningless",
            ],
            1,
            "The reader compares bar lengths as proportional to values. Cut the baseline and a 2% "
            "difference can occupy half the chart. Line charts, which encode position rather than "
            "length, can legitimately be truncated.",
            [
                "It is drawable, which is precisely the problem.",
                "",
                "The data are unchanged; the encoding misleads.",
                "Colour is a separate channel.",
            ],
            "analyse",
            3.3,
        ),
        (
            "A rainbow colour scale is a poor choice for a continuous variable mainly because:",
            [
                "It uses too many colours",
                "It is not perceptually uniform, so equal numeric steps appear as unequal visual "
                "steps and false boundaries emerge",
                "It cannot be printed",
                "It is unavailable in most software",
            ],
            1,
            "The rainbow has sharp perceptual transitions — notably around cyan and yellow — that "
            "the eye reads as structure in the data. It also fails for the most common forms of "
            "colour vision deficiency. Perceptually uniform scales such as viridis avoid both.",
            [
                "Count is not the issue; ordering and uniformity are.",
                "",
                "It prints, though poorly in greyscale.",
                "It is widely available, which is why it persists.",
            ],
            "evaluate",
            4.4,
        ),
        (
            "When a chart must convey a category distinction, relying on colour alone is "
            "inadequate because:",
            [
                "Colour printing is expensive",
                "Readers with colour vision deficiency, and anyone reading a greyscale copy, "
                "lose the distinction entirely",
                "Colour takes longer to render",
                "Colour cannot be used in official publications",
            ],
            1,
            "Around one in twelve men has some colour vision deficiency. Pairing colour with a "
            "second channel — direct labels, pattern, position, shape — keeps the chart readable "
            "without it, which is an accessibility obligation for official statistics.",
            [
                "Cost is a minor consideration.",
                "",
                "Rendering time is negligible.",
                "Colour is permitted and widely used.",
            ],
            "understand",
            2.7,
        ),
        (
            "A pie chart becomes hard to read mainly when:",
            [
                "It has two segments",
                "It has many segments of similar size, since angle is judged poorly",
                "It uses percentages",
                "It is drawn in greyscale",
            ],
            1,
            "Human judgement of angle and area is considerably worse than judgement of position "
            "or length. Two or three well-separated shares are fine; nine similar slices are "
            "better served by a sorted bar chart.",
            [
                "Two segments are the case pies handle best.",
                "",
                "Percentages are the natural unit for a pie.",
                "Greyscale is a colour issue, addressable with labels.",
            ],
            "apply",
            2.5,
        ),
        (
            "A dashboard intended for a district officer who must act on it should prioritise:",
            [
                "The maximum number of indicators per screen",
                "The few indicators the officer can actually influence, with a clear comparison "
                "point for each",
                "Animated transitions",
                "Three-dimensional charts",
            ],
            1,
            "A dashboard is a decision surface, not a data dump. A number without a comparison — "
            "target, previous period, peer district — cannot be acted on, and twenty such numbers "
            "compete for the attention that one would have received.",
            [
                "Density defeats the purpose.",
                "",
                "Animation rarely aids comprehension of static values.",
                "3D adds distortion without information.",
            ],
            "evaluate",
            4.2,
        ),
        (
            "Small multiples are particularly effective for:",
            [
                "Showing a single value prominently",
                "Comparing the same chart structure across many categories on a common scale",
                "Hiding outliers",
                "Reducing the number of charts",
            ],
            1,
            "Repeating one chart form across panels on a shared scale lets the eye compare "
            "directly, because everything except the data is held constant. It is usually clearer "
            "than overplotting twenty series in one frame.",
            [
                "A single value calls for a large clear number.",
                "",
                "They tend to reveal outliers rather than hide them.",
                "They increase chart count deliberately.",
            ],
            "apply",
            3.5,
        ),
        (
            "When publishing an estimate with a wide confidence interval in a public-facing "
            "chart, good practice is to:",
            [
                "Show the point estimate alone for clarity",
                "Display the interval visually, so the reader sees the uncertainty rather than "
                "inferring precision",
                "Round the estimate to a whole number",
                "Omit the estimate entirely",
            ],
            1,
            "A bare point estimate reads as exact. Error bars or a shaded band cost little space "
            "and prevent a reader from treating a noisy district figure as a firm one — which is "
            "the most common way official statistics get over-interpreted.",
            [
                "Clarity that misrepresents precision is not clarity.",
                "",
                "Rounding conveys some imprecision but not how much.",
                "Suppression is for estimates too unreliable to publish at all.",
            ],
            "analyse",
            3.8,
        ),
        (
            "A stacked area chart of state contributions to a national total makes it difficult "
            "to:",
            [
                "See the overall total",
                "Judge the trend of any individual series except the bottom one, because each "
                "sits on a moving baseline",
                "Use colour",
                "Label the axes",
            ],
            1,
            "Only the bottom band has a flat baseline. Every band above it is read against a "
            "wobbling floor, so an apparent rise may be entirely due to the series beneath it. "
            "The total reads well; the components do not.",
            [
                "The total is the one thing it shows clearly.",
                "",
                "Colour works normally.",
                "Labelling is unaffected.",
            ],
            "evaluate",
            4.6,
        ),
        (
            "A chart's title should generally state:",
            [
                "The chart type",
                "The finding or subject the reader should take away",
                "The software used",
                "The file name",
            ],
            1,
            "'Rural unemployment fell in twelve of sixteen districts' orients the reader before "
            "they parse the geometry. 'Bar chart of unemployment' describes what they can already "
            "see.",
            [
                "The reader can see it is a bar chart.",
                "",
                "Provenance belongs in a footnote.",
                "Not meaningful to a reader.",
            ],
            "remember",
            1.5,
        ),
        (
            "Publishing the underlying data table alongside a visualisation matters mainly "
            "because it:",
            [
                "Makes the page load faster",
                "Lets users verify, reuse and re-analyse the figures rather than reading values "
                "off a picture",
                "Reduces the need for axis labels",
                "Improves the colour scheme",
            ],
            1,
            "A chart is a reading of the data, not the data. Publishing the table — with units, "
            "reference period and source — is what makes an official figure reusable, and it is "
            "the difference between dissemination and display.",
            [
                "It adds weight to the page.",
                "",
                "Labels remain necessary.",
                "Unrelated.",
            ],
            "understand",
            2.9,
        ),
        (
            "Two districts are shaded identically on a map of literacy rate, but one is based on "
            "40 sampled households and the other on 400. Good cartographic practice is to:",
            [
                "Present them identically, since the estimates are equal",
                "Signal the difference in reliability — by hatching, greying, or suppressing the "
                "unreliable estimate",
                "Use a brighter colour for the smaller sample",
                "Merge the two districts",
            ],
            1,
            "Identical shading asserts identical knowledge. A map that does not distinguish a "
            "well-measured district from a barely-measured one hands the reader a false sense of "
            "uniform coverage, and it is the small-sample districts that most often drive "
            "misplaced conclusions.",
            [
                "Equal point estimates from very unequal samples are not equally trustworthy.",
                "",
                "Brightness would imply a data value rather than reliability.",
                "Merging destroys the geography the map exists to show.",
            ],
            "evaluate",
            4.8,
        ),
    ],

    # ----------------------------------------------------------- DG-QUAL --
    "DG-QUAL": [
        (
            "Metadata in a statistical dataset describes:",
            [
                "The most recent values",
                "The context of the data — definitions, units, reference period, method and "
                "source",
                "Only the file size",
                "The names of the respondents",
            ],
            1,
            "Metadata is what makes a number interpretable. A figure without its reference "
            "period, unit and definition cannot be compared with anything, however accurate it "
            "is.",
            [
                "That is the data itself.",
                "",
                "File size is one trivial technical attribute.",
                "Respondent identity is confidential and is not metadata.",
            ],
            "remember",
            1.4,
        ),
        (
            "A primary key constraint on a database table guarantees that:",
            [
                "Values are correct",
                "Each row is uniquely identifiable and the key is never null",
                "The table is indexed by date",
                "No data can be deleted",
            ],
            1,
            "Uniqueness and non-nullity, enforced by the database rather than by convention. It "
            "prevents the duplicate-record class of error at the point of insertion, which is far "
            "cheaper than detecting it later.",
            [
                "Correctness of values is a validation matter, not a key constraint.",
                "",
                "Indexing by date is a separate choice.",
                "Deletion is governed by permissions and foreign keys.",
            ],
            "understand",
            2.1,
        ),
        (
            "Referential integrity between a household table and a member table ensures that:",
            [
                "Every household has at least one member",
                "No member record references a household that does not exist",
                "Members are sorted by age",
                "Household size is correct",
            ],
            1,
            "A foreign key prevents orphan records. It does not require that every household has "
            "members — that is a separate business rule needing its own check.",
            [
                "That would require an additional constraint; a foreign key does not impose it.",
                "",
                "Ordering is unrelated.",
                "Size accuracy is a validation rule.",
            ],
            "apply",
            3.2,
        ),
        (
            "Edit rules in survey data processing are used to:",
            [
                "Delete records that look unusual",
                "Detect values that are impossible or improbable given other responses, for "
                "review or imputation",
                "Encrypt the dataset",
                "Reduce the sample size",
            ],
            1,
            "A fifteen-year-old reported as a widowed pensioner fails a consistency edit. The "
            "rule flags it; what happens next — recontact, correction, imputation — is a "
            "documented decision, not an automatic deletion.",
            [
                "Automatic deletion of unusual records removes genuine extremes and biases the "
                "distribution.",
                "",
                "Encryption is a security control.",
                "Editing does not change the sample.",
            ],
            "apply",
            3.0,
        ),
        (
            "In the standard dimensions of statistical quality, 'timeliness' refers to:",
            [
                "How long the survey took to design",
                "The lag between the reference period and the release of results",
                "How quickly a user can download the file",
                "The frequency of revision",
            ],
            1,
            "Timeliness is the reference-to-release lag, and it trades directly against accuracy: "
            "publishing sooner means publishing on less complete source data, which is why early "
            "estimates get revised.",
            [
                "Design duration is a project matter.",
                "",
                "Download speed is accessibility infrastructure.",
                "Revision frequency relates to reliability.",
            ],
            "understand",
            2.6,
        ),
        (
            "A dataset scores well on accuracy but poorly on coherence. This most likely means:",
            [
                "The values are wrong",
                "The values are individually sound but use definitions or classifications "
                "inconsistent with related datasets",
                "The file is corrupted",
                "The sample was too small",
            ],
            1,
            "Coherence is about comparability across sources and over time. An employment series "
            "using a different activity reference period from the national standard can be "
            "internally impeccable and still not line up with anything else.",
            [
                "That would be an accuracy failure, which is not what was described.",
                "",
                "Corruption is a technical integrity problem.",
                "Sample size drives precision.",
            ],
            "analyse",
            4.1,
        ),
        (
            "A data steward's role in a statistical organisation is best described as:",
            [
                "Writing all the code that processes data",
                "Holding accountability for the definition, quality and appropriate use of a "
                "specific data domain",
                "Managing the physical servers",
                "Approving all budget requests",
            ],
            1,
            "Stewardship is accountability for a domain, not a technical function. The steward "
            "decides what a variable means and who may use it for what — which is why the role "
            "usually sits with the business owner rather than with IT.",
            [
                "That is data engineering.",
                "",
                "That is infrastructure operations.",
                "That is finance.",
            ],
            "understand",
            2.8,
        ),
        (
            "Two administrative sources report different counts of registered enterprises for the "
            "same district and year. The best first step is to:",
            [
                "Average the two figures",
                "Compare the unit definitions, coverage rules and reference dates before treating "
                "the difference as an error",
                "Publish the higher figure",
                "Discard both",
            ],
            1,
            "Most such discrepancies are definitional — one counts registrations and the other "
            "active filers, or the dates differ by a quarter. Reconciling definitions usually "
            "explains most of the gap, and averaging would bury a real and informative "
            "difference.",
            [
                "Averaging two differently defined quantities produces a number measuring "
                "neither.",
                "",
                "Choosing the larger is arbitrary.",
                "Both may be correct for their own definitions.",
            ],
            "evaluate",
            4.5,
        ),
        (
            "Version control applied to statistical outputs primarily ensures that:",
            [
                "Files take up less space",
                "Any published figure can be traced to the exact code, inputs and parameters that "
                "produced it",
                "Data are encrypted at rest",
                "Users always see the latest figure",
            ],
            1,
            "Reproducibility is the point. When a figure is challenged months later, being able "
            "to reconstruct exactly what produced it is the difference between an explanation and "
            "an apology.",
            [
                "History increases storage.",
                "",
                "Encryption is separate.",
                "Serving the latest version is a publication concern.",
            ],
            "apply",
            3.4,
        ),
        (
            "An automated validation suite passes on a new data load, but a downstream analyst "
            "finds a whole district missing. This most likely indicates:",
            [
                "The analyst is mistaken",
                "The validation checks values present in the file but has no completeness check "
                "against an expected list of units",
                "The file was encrypted",
                "The database rejected the load",
            ],
            1,
            "Validation usually checks what is there — ranges, types, consistency. Absence passes "
            "every such rule silently. Completeness has to be asserted positively, against an "
            "expected roster of units, or missing data is the one error that never fails a test.",
            [
                "Dismissing the finding is the wrong first move.",
                "",
                "Encryption would prevent parsing.",
                "A rejected load would have raised an error.",
            ],
            "evaluate",
            4.7,
        ),
        (
            "Classification standards such as NIC and NCO exist mainly to:",
            [
                "Reduce the number of variables collected",
                "Ensure that economic activity and occupation are coded consistently across "
                "surveys, over time and against international standards",
                "Simplify data entry screens",
                "Assign sampling weights",
            ],
            1,
            "Without a shared classification, an 'industry' total from one survey cannot be "
            "compared with another's. Revisions to these standards are themselves a comparability "
            "break that has to be managed with concordance tables.",
            [
                "They add coding detail rather than reducing it.",
                "",
                "Entry convenience is incidental.",
                "Weights come from the sample design.",
            ],
            "apply",
            3.6,
        ),
        (
            "The principle that statistical outputs should be revisable, with a published "
            "revisions policy, reflects the view that:",
            [
                "Initial estimates are usually fabricated",
                "Early estimates rest on incomplete source data, and correcting them openly is "
                "more credible than defending them",
                "Users prefer changing numbers",
                "Revisions eliminate the need for quality control",
            ],
            1,
            "A revisions policy states in advance when and why figures will change, so a revision "
            "reads as the system working rather than as an admission of failure. Unscheduled, "
            "unexplained revisions are what damage trust.",
            [
                "Early estimates are genuine estimates from partial data.",
                "",
                "Users tolerate revision when it is predictable; they do not prefer it.",
                "Revision and quality control are complementary.",
            ],
            "evaluate",
            4.3,
        ),
    ],

    # ----------------------------------------------------------- DG-PRIV --
    "DG-PRIV": [
        (
            "Direct identifiers in a microdata file are:",
            [
                "Variables that uniquely identify an individual, such as name or Aadhaar number",
                "Variables measured with error",
                "Variables with missing values",
                "Variables used as sampling weights",
            ],
            0,
            "Direct identifiers name a person outright and are removed before any release. "
            "Removing them is necessary and nowhere near sufficient — combinations of "
            "quasi-identifiers re-identify people routinely.",
            [
                "",
                "Measurement error is a quality issue.",
                "Missingness is a completeness issue.",
                "Weights are design variables.",
            ],
            "remember",
            1.5,
        ),
        (
            "A quasi-identifier is a variable that:",
            [
                "Identifies a person on its own",
                "Does not identify anyone alone but can do so in combination with others",
                "Is always suppressed",
                "Contains only numeric codes",
            ],
            1,
            "Age, sex, district and occupation are each innocuous. Together they can single out "
            "one person in a district, which is why disclosure control works on combinations "
            "rather than on individual variables.",
            [
                "That is a direct identifier.",
                "",
                "They are frequently released, in coarsened form.",
                "The data type is irrelevant.",
            ],
            "understand",
            2.4,
        ),
        (
            "k-anonymity with k = 5 means that:",
            [
                "Five variables have been removed",
                "Every combination of quasi-identifiers in the released file is shared by at "
                "least five records",
                "Five percent of records were suppressed",
                "Only five users may access the file",
            ],
            1,
            "No record can be narrowed below a group of five on the quasi-identifiers. It bounds "
            "identity disclosure but not attribute disclosure — if all five share the same "
            "sensitive value, that value is revealed anyway.",
            [
                "It is about record groupings, not variable counts.",
                "",
                "Suppression is one technique for achieving it, not its definition.",
                "Access control is a separate mechanism.",
            ],
            "apply",
            3.5,
        ),
        (
            "Cell suppression in a published table is applied when:",
            [
                "A cell value is zero",
                "A cell is based on too few contributing units, so an individual's value could be "
                "inferred",
                "A cell is large",
                "The row total is unknown",
            ],
            1,
            "A cell with one or two contributors effectively publishes their values. Primary "
            "suppression hides those cells; secondary suppression must then hide enough others "
            "that the first cannot be recovered by subtraction from the margins.",
            [
                "Zero is often publishable, though structural zeros need care.",
                "",
                "Large cells are generally safe.",
                "Missing totals are a completeness matter.",
            ],
            "apply",
            3.3,
        ),
        (
            "Differential privacy provides a guarantee that:",
            [
                "No data are ever published",
                "The published output is nearly unchanged whether or not any one individual is in "
                "the dataset, bounded by a privacy budget",
                "Only aggregated data are released",
                "Identifiers have been removed",
            ],
            1,
            "The guarantee is about the mechanism, not the output: it bounds how much any single "
            "person's presence can influence what is published. That bound is the epsilon budget, "
            "and it is consumed cumulatively across every query answered.",
            [
                "Publication continues, with calibrated noise.",
                "",
                "Aggregation alone offers no formal guarantee.",
                "De-identification is a much weaker, non-formal protection.",
            ],
            "evaluate",
            4.7,
        ),
        (
            "Purpose limitation as a data protection principle requires that personal data:",
            [
                "Be stored in one location",
                "Be collected for specified, explicit purposes and not further processed "
                "incompatibly with them",
                "Be encrypted",
                "Be retained indefinitely",
            ],
            1,
            "Data gathered for a statistical purpose may not be repurposed for enforcement or "
            "administration against the same individuals. For a statistical office this "
            "separation is foundational — it is what makes truthful responses safe to give.",
            [
                "Location is a storage decision.",
                "",
                "Encryption is a security measure, not this principle.",
                "Indefinite retention contradicts storage limitation.",
            ],
            "understand",
            2.9,
        ),
        (
            "Data minimisation means:",
            [
                "Compressing files",
                "Collecting only the personal data actually necessary for the stated purpose",
                "Reducing the sample size",
                "Deleting data after one year",
            ],
            1,
            "The least intrusive route to the required output. Data not collected cannot leak, "
            "cannot be repurposed, and does not need protecting — which makes minimisation the "
            "cheapest privacy control available.",
            [
                "That is compression.",
                "",
                "Sample size is a design question, though it interacts with minimisation.",
                "That is retention limitation, a separate principle.",
            ],
            "remember",
            1.8,
        ),
        (
            "A researcher requests unit-level records with district, age, sex, occupation and "
            "income for a rare occupation. The appropriate response is to:",
            [
                "Release the file, since names are removed",
                "Assess re-identification risk from the combination and offer a controlled access "
                "route or a coarsened file",
                "Refuse all research access",
                "Release only the income column",
            ],
            1,
            "A rare occupation within a district can identify a single person even with names "
            "removed. The answer is neither blanket release nor blanket refusal: coarsen the "
            "geography or occupation, or provide access through a secure research environment "
            "where output is checked.",
            [
                "Name removal does not address combination risk, which is the whole issue here.",
                "",
                "Refusing all access sacrifices legitimate research value unnecessarily.",
                "Income alone without context has little research value.",
            ],
            "evaluate",
            4.8,
        ),
        (
            "The main privacy risk of releasing a synthetic dataset generated from real microdata "
            "is that:",
            [
                "Synthetic data are always identifiable",
                "A model that overfits can reproduce real records or rare combinations almost "
                "exactly",
                "Synthetic data cannot be analysed",
                "It requires more storage",
            ],
            1,
            "Synthetic does not mean safe by construction. A generator that memorises its "
            "training data can emit near-copies of real individuals, which is why synthetic "
            "releases need their own disclosure assessment rather than being assumed private.",
            [
                "Well-generated synthetic data are not identifiable; the risk is conditional on "
                "the method.",
                "",
                "Analysis is the purpose of the release.",
                "Storage is not a privacy concern.",
            ],
            "analyse",
            4.4,
        ),
        (
            "Role-based access control in a statistical system means access is granted:",
            [
                "To everyone equally",
                "According to the function a person performs, rather than individually per person",
                "Only to senior officials",
                "Permanently once granted",
            ],
            1,
            "Permissions attach to roles, and people are assigned roles. It scales, it survives "
            "staff turnover, and it makes access reviewable — you can answer 'who can see "
            "microdata' by reading the role definitions rather than auditing every account.",
            [
                "Uniform access defeats the purpose.",
                "",
                "Seniority is not the criterion; function and need are.",
                "Access should be reviewed and revoked when the role changes.",
            ],
            "understand",
            2.2,
        ),
        (
            "An audit log of access to confidential microdata is valuable primarily because it:",
            [
                "Prevents all unauthorised access",
                "Creates accountability and makes misuse detectable after the fact",
                "Encrypts the records",
                "Speeds up queries",
            ],
            1,
            "Logging is detective, not preventive. Its deterrent value comes precisely from "
            "people knowing that access is attributable — and its investigative value from being "
            "able to establish what was actually looked at.",
            [
                "Prevention is the job of access controls.",
                "",
                "Logging and encryption are separate controls.",
                "It adds overhead.",
            ],
            "apply",
            3.1,
        ),
        (
            "A published table of employment by district and disability status has several cells "
            "suppressed for small counts, but every row and column total is published. The "
            "residual risk is that:",
            [
                "There is no risk once cells are suppressed",
                "A single suppressed cell in a row can be recovered exactly by subtracting the "
                "published cells from the total",
                "Totals are always confidential",
                "Suppression makes the table unusable",
            ],
            1,
            "This is why secondary suppression exists. One suppressed cell per row or column is "
            "arithmetically recoverable, so enough additional cells must be suppressed to leave "
            "the value genuinely ambiguous — which is a harder combinatorial problem than it "
            "first appears.",
            [
                "Primary suppression alone is frequently insufficient.",
                "",
                "Totals are usually publishable; the problem is their interaction with "
                "suppressed cells.",
                "Usability is reduced, but that is not the disclosure risk.",
            ],
            "evaluate",
            4.9,
        ),
    ],

    # ---------------------------------------------------------- BEH-COMM --
    "BEH-COMM": [
        (
            "A statistical release intended for a general audience should lead with:",
            [
                "The methodology section",
                "The main finding in plain language, with the number and its reference period",
                "A table of contents",
                "The list of contributors",
            ],
            1,
            "Readers who leave after one paragraph should still have the finding. Methodology is "
            "essential and belongs where those who need it will look for it — which is not the "
            "opening line.",
            [
                "Method-first loses the general reader immediately.",
                "",
                "Navigation aids come after substance.",
                "Attribution belongs at the end.",
            ],
            "understand",
            1.7,
        ),
        (
            "When a journalist asks whether a 0.3 percentage point change is 'significant', the "
            "most accurate response is to:",
            [
                "Say yes, since the number changed",
                "Explain whether the change is larger than the sampling error of the estimate, "
                "and give the interval",
                "Decline to comment",
                "Say the change is too small to discuss",
            ],
            1,
            "'Significant' means one thing in statistics and another in ordinary speech. The "
            "useful answer supplies the interval so the journalist can see whether the movement "
            "is distinguishable from noise, rather than a yes that will be quoted as certainty.",
            [
                "Any change in a sample estimate moves; that is not significance.",
                "",
                "Declining leaves the interpretation to someone with less information.",
                "Dismissal without the interval is as unhelpful as overclaiming.",
            ],
            "apply",
            3.4,
        ),
        (
            "A footnote indicating that an estimate is based on fewer than 30 sample observations "
            "exists to:",
            [
                "Take up space",
                "Warn the user that the estimate is imprecise and should not be relied on alone",
                "Indicate the data are confidential",
                "Show the survey was small",
            ],
            1,
            "It is a reliability signal attached to the specific cell. Without it a small-sample "
            "district figure sits in the table looking identical to a well-measured one and will "
            "be read the same way.",
            [
                "Footnotes carry meaning.",
                "",
                "Confidentiality is flagged differently, usually by suppression.",
                "It concerns the cell, not the whole survey.",
            ],
            "understand",
            2.3,
        ),
        (
            "Presenting the same statistic to a minister, a district officer and a researcher "
            "should differ primarily in:",
            [
                "The value of the statistic",
                "The level of detail, framing and the decision each audience has to make",
                "The reference period used",
                "The confidentiality applied",
            ],
            1,
            "The number does not change; what surrounds it does. A minister needs the implication "
            "and the confidence in it, a district officer needs their own unit and what to do, a "
            "researcher needs the method and the microdata.",
            [
                "Changing the value for an audience is misconduct.",
                "",
                "The reference period is a property of the data.",
                "Confidentiality rules are not audience-negotiable.",
            ],
            "analyse",
            3.7,
        ),
        (
            "A chart in a press release shows a sharp rise in a series. Before publication the "
            "most important check is whether:",
            [
                "The colours match the department's palette",
                "The rise is genuine rather than an artefact of a definitional change, a base "
                "revision or a series break",
                "The font is large enough",
                "The file size is small",
            ],
            1,
            "A break in the series produces a visually dramatic and entirely spurious movement. "
            "Publishing it uncaveated is the single most common way an official chart misleads, "
            "and it is very hard to retract once it has been reported.",
            [
                "Branding is cosmetic.",
                "",
                "Typography matters less than validity.",
                "File size is irrelevant.",
            ],
            "evaluate",
            4.5,
        ),
        (
            "In a technical report, the appropriate place for detailed sampling error tables is:",
            [
                "The opening paragraph",
                "An annexe, referenced from the main text where estimates are discussed",
                "Omitted entirely",
                "The press release headline",
            ],
            1,
            "They must be available and they must not obstruct. An annexe with clear pointers "
            "serves both the general reader and the analyst who needs to check a CV before "
            "quoting a district figure.",
            [
                "Detail at the opening buries the finding.",
                "",
                "Omission removes the basis for judging reliability.",
                "A headline cannot carry a table.",
            ],
            "apply",
            2.8,
        ),
        (
            "Writing 'the unemployment rate rose from 4.1% to 4.4%' when both estimates have a "
            "margin of error of ±0.5 percentage points is:",
            [
                "Accurate and complete",
                "Misleading, because the two estimates are not distinguishable and the sentence "
                "asserts a rise",
                "Acceptable if the data are official",
                "Preferable to giving the interval",
            ],
            1,
            "Overlapping intervals mean the data cannot support the claim of a rise. The honest "
            "formulation states that the rate was broadly unchanged, giving both figures and "
            "their uncertainty.",
            [
                "It is arithmetically true and inferentially wrong.",
                "",
                "Official provenance does not license an unsupported inference.",
                "The interval is exactly what makes the sentence honest.",
            ],
            "evaluate",
            4.6,
        ),
        (
            "The main purpose of an advance release calendar is to:",
            [
                "Give staff deadlines",
                "Assure users that release timing is fixed in advance and not influenced by what "
                "the figures show",
                "Reduce the number of releases",
                "Allow more time for analysis",
            ],
            1,
            "Pre-announced dates remove the suspicion that an inconvenient figure was delayed. "
            "That credibility function is why release calendars are a core element of "
            "international statistical standards rather than an administrative convenience.",
            [
                "Internal planning is a side benefit.",
                "",
                "Release frequency is a separate decision.",
                "Timelines are usually tighter, not looser.",
            ],
            "analyse",
            3.9,
        ),
        (
            "Responding to a public claim that official figures are 'manipulated', the most "
            "effective institutional response is to:",
            [
                "Ignore it",
                "Publish the method, the microdata access route and the revisions history so the "
                "claim can be checked independently",
                "Issue a denial",
                "Restrict access to the data",
            ],
            1,
            "Transparency is the only response that scales, because it lets third parties verify "
            "rather than asking them to trust. A denial invites a symmetric counter-assertion; "
            "restricting access confirms the suspicion.",
            [
                "Silence lets the claim settle.",
                "",
                "An unsupported denial is an assertion against an assertion.",
                "Restriction is the worst possible signal.",
            ],
            "evaluate",
            4.8,
        ),
        (
            "An executive summary differs from an abstract in that the summary:",
            [
                "Is shorter",
                "States the findings and their implications so a decision-maker need not read "
                "further",
                "Contains no numbers",
                "Is written first",
            ],
            1,
            "An abstract describes what the document does; an executive summary delivers what it "
            "concluded. The test is whether someone who reads only the summary can act "
            "correctly.",
            [
                "It is usually longer than an abstract.",
                "",
                "Key figures belong in it.",
                "Both are typically written last.",
            ],
            "understand",
            2.6,
        ),
        (
            "When a previously published figure must be corrected, best practice is to:",
            [
                "Quietly replace the number on the website",
                "Publish the corrected figure with a dated note explaining what changed and why",
                "Wait for the next release cycle",
                "Correct it only if a user complains",
            ],
            1,
            "Silent replacement means anyone holding the old figure never learns it was wrong, "
            "and anyone who notices the change loses confidence in everything else. A dated "
            "correction note is a smaller cost than either.",
            [
                "Silent edits destroy trust when discovered, and they are discovered.",
                "",
                "Delay leaves a known error in circulation.",
                "Correction should not be complaint-driven.",
            ],
            "apply",
            3.2,
        ),
        (
            "A district officer says the survey estimate for their district 'is simply wrong' "
            "because it conflicts with their administrative records. The most constructive first "
            "response is to:",
            [
                "Defend the survey estimate",
                "Compare definitions, reference periods and coverage between the two sources "
                "before judging either",
                "Revise the estimate to match the records",
                "Refer the officer to the methodology annexe",
            ],
            1,
            "Survey and administrative sources routinely measure subtly different things. "
            "Establishing what each actually counts usually explains most of the gap, and it "
            "treats the officer's local knowledge as evidence rather than as an objection to be "
            "managed.",
            [
                "Defending before understanding forecloses a genuine data quality signal.",
                "",
                "Adjusting an estimate to match a challenge is indefensible.",
                "Technically correct and unhelpful as a first move.",
            ],
            "analyse",
            4.1,
        ),
    ],

    # ---------------------------------------------------------- BEH-LEAD --
    "BEH-LEAD": [
        (
            "Delegating a task effectively requires that the person receiving it is given:",
            [
                "The task only",
                "The task, the authority to make the decisions it needs, and a clear definition "
                "of done",
                "A longer deadline",
                "Detailed step-by-step instructions for every action",
            ],
            1,
            "Responsibility without authority produces someone who must escalate every decision, "
            "which is slower than not delegating. A clear definition of done is what lets them "
            "know when to stop.",
            [
                "The task alone leaves them unable to act.",
                "",
                "Time does not substitute for authority.",
                "Prescribing every step is supervision, not delegation.",
            ],
            "understand",
            2.4,
        ),
        (
            "Two investigators in a field team consistently disagree about how to code a "
            "borderline occupation. The supervisor's best response is to:",
            [
                "Let each continue with their own interpretation",
                "Establish the correct coding against the classification manual and record the "
                "decision so the whole team applies it",
                "Assign them to different districts",
                "Ask them to average their codes",
            ],
            1,
            "Inconsistent coding is a data quality defect that propagates into every estimate "
            "using that variable. Resolving it once, in writing, fixes it for the team and "
            "creates a precedent for the next borderline case.",
            [
                "Divergent coding makes the data incomparable across investigators.",
                "",
                "Separation hides the inconsistency without resolving it.",
                "Codes are categorical; averaging is meaningless.",
            ],
            "apply",
            3.3,
        ),
        (
            "A team member's work is consistently late but of high quality. The most useful first "
            "step is to:",
            [
                "Reassign their work to others",
                "Understand whether the cause is workload, unclear priorities, dependencies or "
                "something else, before deciding on a response",
                "Issue a formal warning",
                "Extend all deadlines",
            ],
            1,
            "The same symptom has very different causes and each needs a different remedy. Acting "
            "before diagnosing risks penalising someone who is absorbing work nobody assigned "
            "them.",
            [
                "Reassignment without diagnosis may remove capability from the team.",
                "",
                "A formal step before understanding the cause is disproportionate.",
                "Blanket extension conceals the problem.",
            ],
            "analyse",
            3.6,
        ),
        (
            "Psychological safety in a survey team most directly improves data quality because "
            "it:",
            [
                "Makes the team more agreeable",
                "Makes people willing to report errors and field problems early rather than "
                "concealing them",
                "Reduces the need for supervision",
                "Eliminates disagreement",
            ],
            1,
            "An investigator who fears blame for a mis-enumerated block will not report it, and "
            "the error reaches the published estimate. Safety is not comfort — it is the "
            "condition under which bad news travels upward fast enough to be fixed.",
            [
                "Agreeableness is not the mechanism and can be counterproductive.",
                "",
                "Supervision remains necessary.",
                "Healthy disagreement is a feature of safe teams.",
            ],
            "evaluate",
            4.5,
        ),
        (
            "Setting a team objective as 'complete enumeration of all allotted blocks by 31 "
            "March with fewer than 2% non-response' is better than 'work hard on the survey' "
            "because it is:",
            [
                "Shorter",
                "Specific and measurable, so the team can tell whether they achieved it",
                "More demanding",
                "Easier to achieve",
            ],
            1,
            "An objective nobody can evaluate cannot guide effort or be reviewed. Specificity is "
            "what lets a team self-correct mid-course rather than discovering at the end that "
            "expectations differed.",
            [
                "Length is irrelevant.",
                "",
                "Demand level is a separate question.",
                "It is more exacting, not less.",
            ],
            "apply",
            2.7,
        ),
        (
            "When a capacity-building need is identified across a division, the most effective "
            "approach is usually to:",
            [
                "Send everyone on the same generic course",
                "Target training to the specific competency gaps identified, at the level each "
                "officer actually needs",
                "Wait for officers to request training",
                "Train only the most senior officers",
            ],
            1,
            "Uniform training is convenient to administer and wastes the time of everyone already "
            "competent while leaving the genuinely weak under-served. Targeting requires knowing "
            "the gaps, which is the harder prerequisite.",
            [
                "Generic delivery ignores the distribution of need.",
                "",
                "Self-selection systematically misses those least aware of their gaps.",
                "Seniority does not track competency need.",
            ],
            "analyse",
            3.8,
        ),
        (
            "A supervisor rates every team member as 'outstanding'. The main consequence is "
            "that:",
            [
                "Morale improves permanently",
                "The ratings carry no information, so genuinely strong performers are not "
                "distinguished and weak performance goes unaddressed",
                "The team receives more resources",
                "Nothing, since ratings are subjective",
            ],
            1,
            "A scale everyone tops has no variance and therefore no signal. It also removes the "
            "documented basis for both development support and recognition — the two things "
            "ratings exist to enable.",
            [
                "Any morale gain is short-lived and undermines the instrument.",
                "",
                "Resource allocation does not follow inflated ratings.",
                "Subjectivity is a reason to calibrate, not to abandon discrimination.",
            ],
            "evaluate",
            4.4,
        ),
        (
            "Coordinating a survey across several districts with different field conditions "
            "requires most attention to:",
            [
                "Enforcing identical procedures everywhere regardless of conditions",
                "Maintaining consistent definitions and quality standards while allowing local "
                "adaptation of logistics",
                "Letting each district design its own approach",
                "Minimising communication to avoid confusion",
            ],
            1,
            "What must be uniform is what affects comparability — concepts, definitions, "
            "reference periods, quality thresholds. How a team reaches a remote block is a local "
            "decision and forcing uniformity there costs coverage.",
            [
                "Rigid uniformity on logistics harms field operations without helping "
                "comparability.",
                "",
                "Full local autonomy destroys comparability.",
                "Coordination requires more communication, not less.",
            ],
            "evaluate",
            4.7,
        ),
        (
            "Giving developmental feedback is most effective when it:",
            [
                "Is delivered only at the annual review",
                "Is specific, timely, and addresses observable behaviour rather than character",
                "Focuses on personality traits",
                "Is delivered in front of the team",
            ],
            1,
            "Specific and behavioural feedback names something the person can change. Character "
            "judgements invite defence rather than adjustment, and delay strips the feedback of "
            "the context that would have made it actionable.",
            [
                "Annual-only feedback arrives too late to act on.",
                "",
                "Traits are not actionable.",
                "Public correction damages the safety that makes feedback usable.",
            ],
            "understand",
            2.9,
        ),
        (
            "A project is behind schedule. Adding more people to it late in the work often makes "
            "it later because:",
            [
                "New people are less capable",
                "Onboarding and coordination consume the existing team's time, and communication "
                "paths grow faster than headcount",
                "Budgets are fixed",
                "The work cannot be divided at all",
            ],
            1,
            "Brooks's observation. Existing staff must stop producing in order to bring newcomers "
            "up to speed, and each addition multiplies the coordination overhead. Re-scoping or "
            "extending is usually the better lever late in a project.",
            [
                "Capability is not the mechanism.",
                "",
                "Budget is a constraint, not the cause.",
                "Much work is divisible; the cost is in coordination, not in principle.",
            ],
            "analyse",
            4.2,
        ),
        (
            "The primary purpose of a structured handover when an officer is transferred is to:",
            [
                "Satisfy an administrative requirement",
                "Preserve operational knowledge — pending decisions, informal context and "
                "commitments — that is not written down anywhere else",
                "Delay the transfer",
                "Assign blame for incomplete work",
            ],
            1,
            "Files record what was decided; they rarely record what was about to be, who was "
            "consulted, or which commitments are outstanding. That undocumented context is what a "
            "handover exists to transfer, and what is lost when one is skipped.",
            [
                "Compliance is a by-product.",
                "",
                "Delay is not the objective.",
                "Handover is not an accountability exercise.",
            ],
            "apply",
            3.0,
        ),
        (
            "A team consistently meets its targets but reports very high overtime and rising "
            "attrition. Reading only the target achievement would lead a manager to conclude the "
            "team is performing well. The error is that:",
            [
                "Targets are the only valid measure",
                "Output is being sustained by drawing down capacity that is not measured, so "
                "current performance is borrowed from future performance",
                "Attrition is unrelated to workload",
                "Overtime indicates commitment",
            ],
            1,
            "A measure that captures output but not the cost of producing it will read a team "
            "running itself down as a team succeeding. By the time attrition shows in the output "
            "figures, the institutional knowledge has already gone.",
            [
                "Targets capture one dimension of performance.",
                "",
                "Sustained overtime is a well-established driver of attrition.",
                "Commitment and unsustainable load are not distinguishable from the overtime "
                "figure alone.",
            ],
            "evaluate",
            4.9,
        ),
    ],
}


# --------------------------------------------------------------------------- #
# The foundation band
# --------------------------------------------------------------------------- #
#
# These exist because `/item-bank/health` said they were missing.
#
# With the two banks above loaded, test information at L1 ranged from 0.53 down
# to 0.03 — and information below about 1.0 means a standard error wider than a
# whole FRAC level. In plain terms the assessment could not tell an officer at
# L1 from an officer at L2. Team Leadership was the worst of it: its easiest
# item sat at L2.4, so an officer below that was answering questions pitched
# entirely above them, learning nothing and being told nothing.
#
# That is the failure mode adaptive testing is supposed to prevent, and it is
# the one that matters most politically: the officers a capacity-building
# programme most needs to identify are precisely the ones at the bottom of the
# scale. A bank that measures L3 to L5 beautifully and cannot resolve L1 is
# measuring the people who need it least.
#
# So: four items per competency in the L1.2-L2.3 band, deliberately
# definitional. Easy items are not filler — they are what makes a low estimate
# trustworthy rather than merely low.
FOUNDATION: dict[str, list[ExtendedItem]] = {
    "STAT-SAMP": [
        (
            "A population in survey sampling means:",
            [
                "Everyone living in the country",
                "The complete set of units about which the survey aims to draw conclusions",
                "The people who respond to the survey",
                "The number of households in a village",
            ],
            1,
            "The population is defined by the survey's objective — it might be all factories, "
            "all persons aged 15 and above, or all farms. It is a definition, not a headcount.",
            [
                "That is one possible population among many.",
                "",
                "Those are the respondents, a subset of the achieved sample.",
                "That is a count of one kind of unit in one place.",
            ],
            "remember",
            1.2,
        ),
        (
            "A census differs from a sample survey in that a census:",
            [
                "Uses a questionnaire",
                "Attempts to enumerate every unit in the population",
                "Is always more accurate in every respect",
                "Is conducted by private agencies",
            ],
            1,
            "Complete enumeration is the defining feature. It removes sampling error entirely, "
            "though it does not remove non-sampling error — and at census scale those can be "
            "larger than a well-run survey's total error.",
            [
                "Both use questionnaires.",
                "",
                "A census has no sampling error but is more exposed to coverage and measurement "
                "error because of its scale.",
                "In India the Census is conducted by the Registrar General.",
            ],
            "remember",
            1.5,
        ),
        (
            "The sample size of a survey refers to:",
            [
                "The number of questions asked",
                "The number of units selected for enumeration",
                "The number of districts covered",
                "The length of the questionnaire",
            ],
            1,
            "It counts selected units — households, persons, establishments — and is the main "
            "driver of sampling precision.",
            [
                "That is the questionnaire length.",
                "",
                "That is geographic coverage, a separate design choice.",
                "Also questionnaire length.",
            ],
            "remember",
            1.3,
        ),
        (
            "Non-response in a survey occurs when:",
            [
                "A question is poorly worded",
                "A selected unit cannot be contacted or declines to participate",
                "The sample is too small",
                "The data are entered incorrectly",
            ],
            1,
            "Non-response is a selected unit that yields no data. It matters because those who "
            "do not respond usually differ from those who do, so the shortfall is rarely random.",
            [
                "That is a questionnaire design issue.",
                "",
                "Sample size is a design decision.",
                "That is a processing error.",
            ],
            "remember",
            1.7,
        ),
    ],
    "STAT-EST": [
        (
            "An estimate in survey statistics is:",
            [
                "The true population value",
                "A value computed from the sample that stands in for the unknown population value",
                "A guess made without data",
                "The largest observed value",
            ],
            1,
            "The population value is unknown; the estimate is the sample's best reading of it, "
            "and it comes with a margin of error describing how far off it might be.",
            [
                "The true value is what the estimate is trying to approximate.",
                "",
                "An estimate is computed from observed data.",
                "That is the maximum, one particular statistic.",
            ],
            "remember",
            1.3,
        ),
        (
            "The standard error of an estimate measures:",
            [
                "How wrong the estimate is",
                "How much the estimate would vary across repeated samples",
                "The number of records used",
                "The time taken to compute it",
            ],
            1,
            "It describes the spread of the estimate under repeated sampling. A small standard "
            "error means the sample would give a similar answer again; it says nothing about "
            "bias, which would shift every sample the same way.",
            [
                "It cannot measure the actual error, since the true value is unknown.",
                "",
                "Sample size influences it but is not it.",
                "Computation time is unrelated.",
            ],
            "remember",
            1.8,
        ),
        (
            "A confidence interval around an estimate is used to show:",
            [
                "That the estimate is certainly correct",
                "A range within which the true value plausibly lies, at a stated level of "
                "confidence",
                "The highest and lowest values in the sample",
                "The budget range of the survey",
            ],
            1,
            "It converts a point estimate into an honest statement about uncertainty. A wide "
            "interval is not a defect in the calculation — it is the sample telling you how much "
            "it knows.",
            [
                "Certainty is exactly what an interval declines to claim.",
                "",
                "That is the range of the data, a different quantity.",
                "Not a statistical concept.",
            ],
            "understand",
            2.1,
        ),
        (
            "Bias in an estimator means that:",
            [
                "The estimate varies between samples",
                "The estimator is systematically off in one direction, on average across samples",
                "The sample was too small",
                "The data contain outliers",
            ],
            1,
            "Bias is a systematic tendency, not random variation. It is the more dangerous of the "
            "two because a larger sample reduces variance but leaves bias exactly where it was.",
            [
                "That is sampling variance.",
                "",
                "Sample size affects precision, not bias.",
                "Outliers are a data characteristic.",
            ],
            "understand",
            2.2,
        ),
    ],
    "STAT-NAS": [
        (
            "Gross Domestic Product measures:",
            [
                "The total wealth held by residents",
                "The value of goods and services produced within a country in a given period",
                "Total government spending",
                "The money supply",
            ],
            1,
            "GDP is a flow over a period, not a stock at a point in time. It counts production "
            "within the territory, whoever owns the producing units.",
            [
                "Wealth is a stock; GDP is a flow.",
                "",
                "Government spending is one component of expenditure-side GDP.",
                "That is a monetary aggregate.",
            ],
            "remember",
            1.2,
        ),
        (
            "Nominal GDP differs from real GDP in that nominal GDP:",
            [
                "Excludes services",
                "Is measured at current prices and so includes the effect of price change",
                "Covers only the organised sector",
                "Is measured per person",
            ],
            1,
            "Real GDP holds prices fixed at a base period so that changes reflect volume alone. "
            "Nominal GDP can rise while real output falls, if prices rise faster.",
            [
                "Both include services.",
                "",
                "Both cover the whole economy.",
                "That is per capita GDP.",
            ],
            "understand",
            1.9,
        ),
        (
            "The three approaches to measuring GDP are:",
            [
                "Production, income and expenditure",
                "Sampling, census and estimation",
                "Federal, state and local",
                "Primary, secondary and tertiary",
            ],
            0,
            "Each measures the same total from a different side — what was produced, what income "
            "it generated, and what was spent on it. In principle they agree; in practice a "
            "statistical discrepancy remains.",
            [
                "",
                "These are data collection methods.",
                "These are levels of government.",
                "These are sectors of the economy, not approaches to measurement.",
            ],
            "remember",
            1.6,
        ),
        (
            "The primary sector in national accounts covers:",
            [
                "Manufacturing",
                "Agriculture, forestry, fishing and mining — activities drawing directly on "
                "natural resources",
                "Banking and insurance",
                "Government administration",
            ],
            1,
            "Primary activities extract or grow. Manufacturing is secondary; services are "
            "tertiary. The split matters because the three behave very differently over a cycle.",
            [
                "Manufacturing is the secondary sector.",
                "",
                "Financial services are tertiary.",
                "Public administration is tertiary.",
            ],
            "remember",
            1.4,
        ),
    ],
    "STAT-INDEX": [
        (
            "An index number is used to measure:",
            [
                "The absolute value of a variable",
                "Relative change in a variable over time or between groups, against a reference "
                "point",
                "The number of items in a dataset",
                "The position of a record in a file",
            ],
            1,
            "An index expresses change relative to a base, conventionally set to 100. Its level "
            "is meaningless alone; its movement is the point.",
            [
                "Absolute levels are what an index deliberately abstracts from.",
                "",
                "That is a count.",
                "That is a database index, a different sense of the word.",
            ],
            "remember",
            1.3,
        ),
        (
            "If a price index has a base year value of 100 and now stands at 128, prices have:",
            [
                "Fallen by 28%",
                "Risen by 28% since the base year",
                "Risen by 128%",
                "Remained unchanged",
            ],
            1,
            "The index is a ratio to the base times 100, so 128 means the basket costs 1.28 times "
            "what it did. The percentage change is the index minus 100, not the index itself.",
            [
                "A fall would show a value below 100.",
                "",
                "128% would correspond to an index of 228.",
                "Unchanged prices would hold the index at 100.",
            ],
            "apply",
            1.9,
        ),
        (
            "The Consumer Price Index measures changes in:",
            [
                "Wholesale prices of industrial goods",
                "The retail prices of a basket of goods and services bought by households",
                "Export prices",
                "Land prices",
            ],
            1,
            "CPI tracks what households actually pay at retail, including services. It is the "
            "index used for indexation of wages and pensions, which is why its basket and weights "
            "are politically consequential.",
            [
                "That is closer to the Wholesale Price Index.",
                "",
                "Export prices are covered by trade indices.",
                "Land is not in the CPI basket.",
            ],
            "remember",
            1.5,
        ),
        (
            "The 'basket' of a consumer price index refers to:",
            [
                "The container used to collect price data",
                "The fixed set of goods and services whose prices are tracked",
                "The list of districts surveyed",
                "The set of shops visited",
            ],
            1,
            "The basket, with its weights, defines what the index measures. Keeping it fixed is "
            "what makes month-to-month comparison meaningful — and what makes the index drift "
            "from reality as consumption patterns change.",
            [
                "Not a technical term.",
                "",
                "That is the geographic sample.",
                "That is the outlet sample, a related but separate design element.",
            ],
            "understand",
            1.8,
        ),
    ],
    "TECH-ANL": [
        (
            "The mean of a set of values is:",
            [
                "The middle value when sorted",
                "The sum of the values divided by how many there are",
                "The most frequent value",
                "The difference between the largest and smallest",
            ],
            1,
            "The arithmetic mean. It uses every value, which makes it efficient and also makes it "
            "sensitive to extremes — the reason median income is usually reported instead of mean "
            "income.",
            [
                "That is the median.",
                "",
                "That is the mode.",
                "That is the range.",
            ],
            "remember",
            1.2,
        ),
        (
            "For a strongly right-skewed distribution such as household income, the median is "
            "often preferred to the mean because the median:",
            [
                "Is easier to compute",
                "Is not pulled upward by a small number of very large values",
                "Is always larger",
                "Uses more of the data",
            ],
            1,
            "A few very high incomes drag the mean above what a typical household receives. The "
            "median reports the middle household, which is usually the more informative summary.",
            [
                "Computation is not the reason.",
                "",
                "In a right-skewed distribution the median is typically smaller than the mean.",
                "The median uses less of the data, which is precisely why it resists outliers.",
            ],
            "understand",
            2.2,
        ),
        (
            "A variable that takes categories with no natural ordering — such as state of "
            "residence — is:",
            ["Ordinal", "Nominal", "Continuous", "Discrete numeric"],
            1,
            "Nominal variables label without ranking. The distinction governs what may legally be "
            "computed: a mean state code is meaningless.",
            [
                "Ordinal categories have an order, such as education level.",
                "",
                "Continuous variables take values on a scale.",
                "Discrete numeric variables are counts.",
            ],
            "remember",
            1.6,
        ),
        (
            "A scatter plot of two variables is used mainly to:",
            [
                "Show the frequency of one variable",
                "Reveal the relationship, if any, between the two variables",
                "Display a time series",
                "Compare category totals",
            ],
            1,
            "Each point is one record positioned by both variables, so the shape of the cloud "
            "shows the association — including non-linear patterns a correlation coefficient "
            "would miss.",
            [
                "That is a histogram.",
                "",
                "A line chart suits time.",
                "A bar chart suits category totals.",
            ],
            "understand",
            1.9,
        ),
    ],
    "TECH-GIS": [
        (
            "Latitude and longitude specify:",
            [
                "Elevation above sea level",
                "A position on the earth's surface",
                "The area of a region",
                "The direction of travel",
            ],
            1,
            "Latitude measures north-south angular distance from the equator, longitude east-west "
            "from the prime meridian. Together they locate a point.",
            [
                "That is altitude, a third dimension.",
                "",
                "Area is computed from geometry.",
                "That is bearing.",
            ],
            "remember",
            1.2,
        ),
        (
            "A map layer in a GIS is:",
            [
                "A printed copy of the map",
                "A dataset of one theme — such as roads or district boundaries — displayed over "
                "others",
                "The colour palette",
                "The map's legend",
            ],
            1,
            "Layers keep themes separate so they can be styled, queried and analysed "
            "independently, then combined visually or by overlay.",
            [
                "That is a hard copy.",
                "",
                "Symbology is a property of a layer.",
                "The legend explains the symbology.",
            ],
            "remember",
            1.4,
        ),
        (
            "A shapefile stores:",
            [
                "Satellite imagery only",
                "Vector geometry together with attributes for each feature",
                "Statistical tables without location",
                "Map printing settings",
            ],
            1,
            "The classic vector exchange format — geometry, attributes and projection across "
            "several companion files, which is why a shapefile with a missing .prj or .dbf is a "
            "common and confusing failure.",
            [
                "Imagery is raster and uses formats such as GeoTIFF.",
                "",
                "Shapefiles carry geometry by definition.",
                "Printing is an application setting.",
            ],
            "understand",
            1.9,
        ),
        (
            "Overlaying a district boundary layer on a village point layer allows an analyst to:",
            [
                "Change the map projection",
                "Determine which district each village falls in",
                "Compress the files",
                "Translate the labels",
            ],
            1,
            "This is a point-in-polygon spatial join, the most common GIS operation in official "
            "statistics — it is how survey records get assigned to administrative units.",
            [
                "Reprojection is a separate operation.",
                "",
                "Compression is a storage function.",
                "Translation is a text operation.",
            ],
            "apply",
            2.3,
        ),
    ],
    "TECH-BIG": [
        (
            "Structured data is best described as data that:",
            [
                "Has been checked for errors",
                "Is organised in a predefined format such as rows and columns with defined types",
                "Is stored on a server",
                "Contains only numbers",
            ],
            1,
            "Structure refers to a known, enforced schema. A survey table is structured; an "
            "audio recording of an interview is not, regardless of how carefully either was "
            "checked.",
            [
                "That is data quality, a separate property.",
                "",
                "Location of storage is irrelevant.",
                "Structured data routinely includes text and dates.",
            ],
            "remember",
            1.3,
        ),
        (
            "A relational database stores data in:",
            [
                "Folders of documents",
                "Tables of rows and columns linked by keys",
                "A single continuous file of text",
                "Images",
            ],
            1,
            "Tables plus keys plus constraints. The relational model's value is that the database "
            "itself enforces the relationships, rather than relying on every program that touches "
            "the data to get them right.",
            [
                "That is a document store or file system.",
                "",
                "Flat files lack the relational structure.",
                "Images are unstructured content.",
            ],
            "remember",
            1.5,
        ),
        (
            "A backup differs from an archive in that a backup is primarily intended to:",
            [
                "Preserve data permanently for future reference",
                "Allow recovery of current data after loss or corruption",
                "Reduce storage costs",
                "Share data with the public",
            ],
            1,
            "Backups exist to restore the present; archives exist to preserve the past. Confusing "
            "them produces the common failure of a short backup retention window being relied on "
            "as a permanent record.",
            [
                "That is an archive.",
                "",
                "Backups add storage cost.",
                "Publication is a separate activity.",
            ],
            "understand",
            2.1,
        ),
        (
            "An API in the context of data systems is:",
            [
                "A type of database",
                "A defined interface through which one system requests data or services from "
                "another",
                "A statistical method",
                "A file format",
            ],
            1,
            "An API is a contract between systems. It is what lets a dashboard read fresh figures "
            "without anyone emailing a spreadsheet, and what lets the provider change their "
            "internals without breaking the consumer.",
            [
                "Databases are storage systems.",
                "",
                "Not a statistical concept.",
                "Formats such as JSON are what an API returns, not what it is.",
            ],
            "understand",
            2.0,
        ),
    ],
    "TECH-VIZ": [
        (
            "The horizontal and vertical axes of a chart should always:",
            [
                "Be the same length",
                "Be labelled with what they represent and their units",
                "Start at 100",
                "Use a logarithmic scale",
            ],
            1,
            "An unlabelled axis makes a chart unreadable and, in an official publication, "
            "unciteable. Units matter as much as the variable name — 'expenditure' could be "
            "rupees, lakhs or crores.",
            [
                "Aspect ratio is a design choice.",
                "",
                "The appropriate starting point depends on the chart type.",
                "Log scales suit particular data, not all.",
            ],
            "remember",
            1.3,
        ),
        (
            "A histogram is used to show:",
            [
                "The relationship between two variables",
                "The distribution of a single continuous variable across intervals",
                "Change over time",
                "Parts of a whole",
            ],
            1,
            "Bars represent counts falling in each interval, so the shape shows where values "
            "concentrate — and the choice of interval width materially changes that shape, which "
            "is worth stating alongside the chart.",
            [
                "That is a scatter plot.",
                "",
                "That is a line chart.",
                "That is a pie or stacked bar.",
            ],
            "remember",
            1.6,
        ),
        (
            "Every chart published by a statistical office should carry:",
            [
                "An animated transition",
                "Its source and the reference period of the data",
                "A photograph",
                "The author's contact details",
            ],
            1,
            "Provenance is what makes a figure citable and checkable. A chart circulating without "
            "its source and period will be quoted against the wrong year within a week.",
            [
                "Animation is unnecessary and often unhelpful.",
                "",
                "Decoration is not required.",
                "Useful in some contexts but not essential to the chart.",
            ],
            "understand",
            1.9,
        ),
        (
            "Presenting district counts of a disease as raw numbers rather than as rates per "
            "100,000 population is misleading because:",
            [
                "Counts are harder to compute",
                "Districts with larger populations will show larger counts regardless of risk",
                "Counts cannot be mapped",
                "Rates are always smaller numbers",
            ],
            1,
            "Without normalising by population, the map largely reproduces where people live. "
            "Rates answer the question a reader is actually asking: where is risk highest.",
            [
                "Counts are the simpler computation.",
                "",
                "Counts can be mapped, which is what makes the error easy to commit.",
                "Magnitude is not the issue.",
            ],
            "apply",
            2.3,
        ),
    ],
    "DG-QUAL": [
        (
            "Data quality in official statistics refers to:",
            [
                "The file format used",
                "Fitness for the purpose the data are intended to serve, across dimensions such "
                "as accuracy, timeliness and coherence",
                "The size of the dataset",
                "The speed of the database",
            ],
            1,
            "Quality is multi-dimensional and relative to use. The same dataset can be excellent "
            "for one purpose and unfit for another, which is why quality reports describe "
            "dimensions rather than issuing a single verdict.",
            [
                "Format is a technical detail.",
                "",
                "Volume says nothing about quality.",
                "Performance is an engineering property.",
            ],
            "remember",
            1.4,
        ),
        (
            "A duplicate record in a dataset is a problem because it:",
            [
                "Uses extra storage",
                "Causes the same unit to be counted more than once, distorting totals",
                "Slows down queries",
                "Changes the file format",
            ],
            1,
            "Double-counting inflates totals and biases means. The storage cost is trivial next "
            "to a published total that is wrong.",
            [
                "Storage is a minor consideration.",
                "",
                "Performance is secondary.",
                "Format is unaffected.",
            ],
            "understand",
            1.7,
        ),
        (
            "A missing value in a survey dataset should normally be:",
            [
                "Replaced with zero",
                "Recorded with a code distinguishing 'not applicable' from 'refused' from 'not "
                "known'",
                "Deleted along with the whole record",
                "Left as an empty string",
            ],
            1,
            "Zero is a value and means something different from absence. Distinguishing why a "
            "value is missing is what lets an analyst choose between excluding, imputing, or "
            "treating the category as legitimate.",
            [
                "Coding absence as zero silently corrupts every mean and total computed from the "
                "column.",
                "",
                "Dropping whole records discards valid data and can bias the sample.",
                "An untyped blank loses the reason for the absence.",
            ],
            "apply",
            2.3,
        ),
        (
            "A data dictionary for a dataset lists:",
            [
                "The names of the survey staff",
                "Each variable with its definition, permitted values and units",
                "The dates of fieldwork only",
                "The budget of the survey",
            ],
            1,
            "It is what makes a dataset usable by someone who did not collect it. Without it, "
            "every reuse begins with guessing what a column means.",
            [
                "Staff records are administrative.",
                "",
                "Fieldwork dates are part of broader metadata.",
                "Budget is a financial matter.",
            ],
            "remember",
            1.5,
        ),
    ],
    "DG-PRIV": [
        (
            "Confidentiality in official statistics means that:",
            [
                "No statistics may be published",
                "Information collected about an identifiable person or enterprise is not "
                "disclosed or used against them",
                "Only senior staff may see the data",
                "Data must be stored offline",
            ],
            1,
            "It is a legal and ethical obligation, and a practical one: the assurance of "
            "confidentiality is what makes honest responses possible. A single breach damages "
            "response rates for years.",
            [
                "Aggregate publication is the purpose of collection.",
                "",
                "Access control is a means to confidentiality, not its definition.",
                "Storage medium is an implementation choice.",
            ],
            "remember",
            1.5,
        ),
        (
            "Anonymising a dataset means:",
            [
                "Encrypting the file",
                "Removing or altering information so that individuals can no longer reasonably be "
                "identified",
                "Deleting the dataset",
                "Restricting who may log in",
            ],
            1,
            "Anonymisation acts on the data itself. Encryption protects a file from outsiders but "
            "leaves it fully identifying to anyone holding the key, which is a different "
            "protection against a different threat.",
            [
                "Encryption is a security control, not anonymisation.",
                "",
                "Deletion removes the data entirely.",
                "That is access control.",
            ],
            "understand",
            1.9,
        ),
        (
            "Publishing a table cell based on a single respondent is unacceptable because it:",
            [
                "Looks untidy",
                "Effectively discloses that individual's value",
                "Takes up space",
                "Is difficult to compute",
            ],
            1,
            "With one contributor, the cell value *is* that respondent's value. Anyone who knows "
            "who the respondent is has been given their data.",
            [
                "Appearance is irrelevant.",
                "",
                "Space is not the concern.",
                "It is trivial to compute, which is the danger.",
            ],
            "understand",
            2.1,
        ),
        (
            "The principle of informed consent in data collection requires that respondents:",
            [
                "Sign a legal contract",
                "Are told what the data will be used for and by whom before providing it",
                "Are paid for their time",
                "Are surveyed only once",
            ],
            1,
            "Consent is meaningful only when it is informed. For statutory collections the legal "
            "basis differs, but the obligation to explain purpose and use remains.",
            [
                "A contract is not the usual instrument.",
                "",
                "Payment is a separate decision.",
                "Frequency is a design matter.",
            ],
            "understand",
            2.0,
        ),
    ],
    "BEH-COMM": [
        (
            "The audience for a statistical press release is primarily:",
            [
                "Other statisticians",
                "Journalists and the general public, who need the finding in plain language",
                "The finance department",
                "International agencies",
            ],
            1,
            "A press release is written for readers without statistical training. Technical users "
            "are served by the full report, which the release should point to.",
            [
                "Specialists are served by the technical report.",
                "",
                "Internal departments have other channels.",
                "Agencies receive structured data submissions.",
            ],
            "remember",
            1.3,
        ),
        (
            "A table published without units of measurement is problematic because:",
            [
                "It looks incomplete",
                "The numbers cannot be interpreted — rupees, lakhs and crores differ by orders of "
                "magnitude",
                "It takes longer to read",
                "It cannot be printed",
            ],
            1,
            "Units are not decoration. A figure of 4,500 means nothing until the reader knows "
            "whether it is households, thousands of households, or rupees per month.",
            [
                "Appearance is the least of it.",
                "",
                "Reading time is not the issue.",
                "It prints perfectly well, which is the problem.",
            ],
            "understand",
            1.6,
        ),
        (
            "When explaining a statistical result to a non-technical audience, it is best to:",
            [
                "Use as much technical vocabulary as possible to appear rigorous",
                "State the finding in plain words first, then give the qualifications that matter",
                "Present only the methodology",
                "Avoid giving any numbers",
            ],
            1,
            "Lead with what was found, then say how confident you are and what it does not show. "
            "Jargon-first loses the reader before the qualifications arrive.",
            [
                "Vocabulary that excludes the audience defeats the purpose.",
                "",
                "Method without finding does not answer the question asked.",
                "The numbers are the substance.",
            ],
            "understand",
            1.9,
        ),
        (
            "A report that will be read by officers across several states should avoid:",
            [
                "Tables",
                "Unexplained local abbreviations and office-specific shorthand",
                "Any use of percentages",
                "Charts",
            ],
            1,
            "Internal shorthand is invisible to the person who wrote it and opaque to everyone "
            "else. Expanding an abbreviation at first use costs one line and removes a whole "
            "class of misreading.",
            [
                "Tables are appropriate and useful.",
                "",
                "Percentages are standard.",
                "Charts aid comprehension.",
            ],
            "apply",
            2.2,
        ),
    ],
    "BEH-LEAD": [
        (
            "A team briefing before fieldwork begins is mainly intended to:",
            [
                "Satisfy a procedural requirement",
                "Ensure everyone understands the objectives, procedures and their own "
                "responsibilities",
                "Fill time before the work starts",
                "Allocate the budget",
            ],
            1,
            "Shared understanding before dispersal is what prevents twenty investigators applying "
            "twenty interpretations in the field, where correcting them is far more expensive.",
            [
                "Compliance is incidental.",
                "",
                "It is substantive preparation.",
                "Budgeting happens separately.",
            ],
            "remember",
            1.4,
        ),
        (
            "Clear allocation of responsibilities within a team primarily prevents:",
            [
                "Staff from taking leave",
                "Tasks being duplicated by two people or missed by everyone",
                "The need for meetings",
                "Changes to the work plan",
            ],
            1,
            "Ambiguous ownership produces both failure modes at once — the visible task gets done "
            "twice and the unglamorous one gets done by nobody.",
            [
                "Leave is a separate matter.",
                "",
                "Coordination still requires communication.",
                "Plans change regardless.",
            ],
            "understand",
            1.7,
        ),
        (
            "When a team member raises a problem with the field procedure, a supervisor should "
            "first:",
            [
                "Tell them to follow the procedure regardless",
                "Understand the problem, since the person doing the work often sees issues the "
                "procedure did not anticipate",
                "Report them for non-compliance",
                "Change the procedure immediately",
            ],
            1,
            "Field staff encounter the cases the manual did not foresee. Listening first costs "
            "little and is often the cheapest source of quality improvement available; acting "
            "comes after understanding.",
            [
                "Dismissal discourages the reporting that catches problems early.",
                "",
                "Treating a concern as misconduct guarantees it is the last one raised.",
                "Changing procedure before understanding risks introducing inconsistency "
                "mid-round.",
            ],
            "apply",
            2.2,
        ),
        (
            "Regular progress review meetings during a survey round are useful mainly because "
            "they:",
            [
                "Demonstrate that the supervisor is busy",
                "Surface delays and problems early enough to act on them",
                "Replace written reporting entirely",
                "Reduce the total workload",
            ],
            1,
            "A problem found in week two can be fixed; the same problem found at submission "
            "cannot. The value is in the timing, not in the meeting.",
            [
                "Activity is not the purpose.",
                "",
                "Written records remain necessary.",
                "Meetings add to the workload; they earn it back by preventing rework.",
            ],
            "understand",
            1.9,
        ),
    ],
}
