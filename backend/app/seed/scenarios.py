"""Authored situations for the role simulation.

Written rather than generated, because a situational exercise is only fair if
the rubric can be defended to the officer it scored. A model inventing both the
crisis and the marking scheme leaves nothing to appeal against.

Each one is a decision a statistical officer could actually be asked to make,
with the constraint that turns it from recall into judgement. `expected_points`
is what a strong answer covers; `common_traps` are the answers that look right
and are not — named so the feedback can say why, not only what was missed.
"""

from __future__ import annotations

# code, competency code, title, situation, task, constraint, expected, traps, level, minutes
SCENARIOS: list[tuple] = [
    (
        "SIM-FLOOD-01",
        "BEH-LEAD",
        "Flood disrupts fieldwork in three blocks",
        "You supervise field operations for a consumption survey in a district. "
        "Heavy flooding has cut off three of the twelve sampled blocks. Two are "
        "reachable by boat at roughly four times the usual cost per household. "
        "The third is unreachable for at least six weeks. Fieldwork is due to "
        "close in ten days and the release calendar is published.",
        "Say what you would do, in what order, and explain the reasoning behind "
        "each decision. Be explicit about what you would tell users.",
        "Your remaining budget covers extra cost in one block, not two.",
        [
            "Reach at least one cut-off block rather than dropping all three, since "
            "flood-affected households differ systematically from the rest",
            "Treat the unreachable block as non-response and adjust weights, stating "
            "the adjustment publicly",
            "Do not substitute households from accessible blocks, which would hide "
            "the bias rather than remove it",
            "Decide between delaying the release and publishing with a documented "
            "coverage note, and say which you choose and why",
            "Inform users through the release calendar before the due date, not after",
        ],
        [
            "Replacing flooded households with nearby accessible ones — the substitutes "
            "resemble responders, so the bias survives and becomes invisible",
            "Publishing on time with no coverage note, which puts a figure into "
            "circulation whose limitations only you know about",
            "Dropping all three blocks to stay in budget, which silently removes the "
            "population the flood affected most",
        ],
        4.0,
        20,
    ),
    (
        "SIM-VALID-01",
        "DG-QUAL",
        "A state return fails validation two days before release",
        "A quarterly return from a state office arrives two days before publication. "
        "Thirty per cent of records fail your edit rules. The failures are "
        "concentrated in one district and in one field: monthly household "
        "expenditure, where values are roughly a hundred times larger than expected.",
        "Describe what you would do and in what order, and say what you would "
        "publish and when.",
        "The state office's data entry team is unavailable until after the release date.",
        [
            "Diagnose before correcting — a hundredfold error in one district and one "
            "field points to a unit or scaling mistake, not random respondent error",
            "Check whether that district used a different form version or instruction",
            "Do not auto-correct the outliers, which would erase a real systematic error",
            "Hold the release or publish without that district, stating which and why",
            "Fix the instruction or form so the same error does not recur next quarter",
        ],
        [
            "Applying an automatic outlier rule and publishing on time, which converts "
            "a visible data problem into an invisible one",
            "Treating the failures as respondent error when the concentration in one "
            "field and one district says otherwise",
            "Publishing on schedule with the failures included and no note",
        ],
        4.0,
        15,
    ),
    (
        "SIM-SAMP-01",
        "STAT-SAMP",
        "A district asks for estimates the survey cannot support",
        "A district collector asks for block-level unemployment estimates from a "
        "state survey designed to be reliable at district level. Producing them "
        "directly gives coefficients of variation between 25% and 40%.",
        "Explain what you would give the collector, what you would not, and how "
        "you would justify the decision to someone who wants a number today.",
        "The collector needs the figures for a scheme allocation decision this month.",
        [
            "Explain that a CV of 25-40% cannot distinguish the differences the "
            "allocation would rest on",
            "Offer small-area estimation using auxiliary data, and state that the "
            "result is model-based",
            "Publish direct estimates only where the CV meets the agreed threshold",
            "Give the collector something usable rather than a flat refusal",
            "State the method alongside the figures so the decision is auditable",
        ],
        [
            "Supplying the direct block estimates with no reliability warning because "
            "the request is urgent",
            "Refusing outright, which pushes the collector to a worse source",
            "Pooling several years to shrink the CV, which hides current change",
        ],
        3.5,
        15,
    ),
    (
        "SIM-PRIV-01",
        "DG-PRIV",
        "A researcher requests unit-level records",
        "A university researcher requests unit-level records from a recent "
        "enterprise survey, including turnover and employment by establishment. "
        "They have a genuine research proposal and offer to remove names.",
        "Set out your response and the conditions you would attach.",
        "Several districts in the survey contain only one or two large enterprises.",
        [
            "Removing names does not anonymise — a single large enterprise in a district "
            "is identifiable from its size and sector alone",
            "Offer a de-identified public-use file, or controlled access under agreement "
            "for the detailed records",
            "Apply primary and secondary suppression so suppressed cells cannot be "
            "recovered from published totals",
            "Record purpose limitation, retention and onward-sharing in writing",
            "The obligation to respondents survives the transfer to the researcher",
        ],
        [
            "Releasing the records with names stripped, which defeats nothing when "
            "quasi-identifiers remain",
            "Refusing all access, which wastes publicly funded data",
            "Relying on the researcher's assurance instead of an agreement",
        ],
        4.0,
        15,
    ),
    (
        "SIM-COMM-01",
        "BEH-COMM",
        "A minister's office queries a fall in a headline series",
        "An index you publish has fallen 0.4 points this month. The margin of "
        "error is ±0.6. A minister's office asks you to confirm in writing that "
        "the fall shows the policy introduced last quarter is working.",
        "Draft what you would say back, and explain your reasoning to your own "
        "director.",
        "You are asked for a written reply the same day.",
        [
            "A movement inside the margin of error cannot be distinguished from "
            "sampling noise, and must not be reported as a real change",
            "The index measures an outcome; attributing it to one policy requires "
            "a causal design this data does not have",
            "Offer what the data can support — the series, its interval, and the "
            "period needed before a trend could be called",
            "Reply in writing, courteously and on time, rather than avoiding it",
            "Copy the reply to your director so the agency's position is consistent",
        ],
        [
            "Confirming the interpretation because the request came from senior level",
            "Refusing to reply, which leaves the interpretation standing unchallenged",
            "Sending the raw series with no interval, letting the reader draw the "
            "conclusion you would not put your name to",
        ],
        4.5,
        15,
    ),
    (
        "SIM-NAS-01",
        "STAT-NAS",
        "A base-year revision shifts the growth series",
        "Your division has completed a base-year revision. Under the new base, "
        "growth for two earlier years is 0.6 points higher than previously "
        "published. Commentators have already noticed and are asking whether the "
        "numbers were changed for political reasons.",
        "Explain how you would handle the release and the criticism.",
        "The back-cast series for years before the new base is not yet complete.",
        [
            "Publish the methodology and the reasons for the revision alongside the "
            "figures, not afterwards",
            "Explain that a revised base changes weights, classifications and coverage, "
            "so a level shift is expected",
            "Complete and publish the back-cast, since splicing two bases creates a "
            "break that looks like a real change",
            "Point to the published revisions policy, which announces the schedule in "
            "advance",
            "Answer with transparency rather than denial — let others verify",
        ],
        [
            "Issuing a denial, which invites the reader to choose whom to believe",
            "Delaying publication until the criticism dies down",
            "Publishing the new series without the back-cast and without saying so",
        ],
        4.5,
        20,
    ),
    (
        "SIM-ANL-01",
        "TECH-ANL",
        "A model that looks too good",
        "A colleague has built a model predicting which enterprises will fail to "
        "respond to a survey, reporting 96% accuracy. Non-response in the frame "
        "runs at about 5%. They propose using it to target follow-up effort.",
        "Say what you would check before this is used, and what you would "
        "recommend.",
        "The follow-up budget is already allocated on the assumption the model works.",
        [
            "96% accuracy is what predicting 'everyone responds' would score at a 5% "
            "base rate — ask for precision, recall and the confusion matrix",
            "Check for leakage: any feature recorded after contact cannot be used to "
            "predict contact",
            "Validate on a period after the training data, not a random split",
            "Consider what a wrong prediction costs — a missed non-responder is not "
            "the same error as a wasted visit",
            "Recommend a decision rule and a monitoring plan, not just a model",
        ],
        [
            "Accepting the accuracy figure because it is high",
            "Rejecting the model outright rather than asking for the right metrics",
            "Deploying it on the basis that the budget is already committed",
        ],
        4.0,
        15,
    ),
    (
        "SIM-EST-01",
        "STAT-EST",
        "Weights that swing the estimate",
        "In a state sample, eleven households carry design weights more than "
        "twenty times the median, after a non-response adjustment. Together they "
        "move the state mean expenditure estimate by nearly 4%.",
        "Explain what you would investigate and what you would do about it.",
        "The estimate is due for release in a week and the fieldwork cannot be redone.",
        [
            "Trace why the weights are extreme — usually a stratum with heavy "
            "non-response, or a frame error",
            "Trimming caps the weights and stabilises the estimate, at the cost of "
            "some bias; the trade must be stated",
            "Post-stratify to known population totals to reduce the reliance on those "
            "few households",
            "Report the estimate with its variance, and document whatever adjustment "
            "was applied",
            "Record the frame or non-response problem so the next round can fix it",
        ],
        [
            "Dropping the eleven households, which removes the part of the population "
            "they were selected to represent",
            "Trimming silently, so the published estimate has an undisclosed bias",
            "Publishing unadjusted on the grounds that the weights are 'correct'",
        ],
        4.0,
        15,
    ),
]
