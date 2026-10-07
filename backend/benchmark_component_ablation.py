import csv

# ============================================================
# Production risk-engine configuration
# ============================================================

BASE_WEIGHTS = {
    "Critical Verification Failure": 90,
    "Gateway/System Failure": 50,
    "Revoked Product": 70,
    "Repeated Scan": 10,
    "Excessive Scan Frequency": 20,
    "Geographic Anomaly": 40,
}

LOW_THRESHOLD = 30
HIGH_THRESHOLD = 70
MAX_SCORE = 100


def risk_level(score):
    if score >= HIGH_THRESHOLD:
        return "HIGH"
    elif score >= LOW_THRESHOLD:
        return "MEDIUM"
    return "LOW"


def calculate_score(scenario, weights):
    score = sum(
        weights[component]
        for component in scenario["components"]
    )
    return min(score, MAX_SCORE)


# ============================================================
# Controlled scenarios
#
# These correspond to the implemented production rules.
# ============================================================

SCENARIOS = [
    {
        "name": "Normal Genuine Scan",
        "components": [],
    },
    {
        "name": "Legitimate Single Repeat",
        "components": [],
    },
    {
        "name": "Repeated Scan",
        "components": ["Repeated Scan"],
    },
    {
        "name": "Excessive Scan Frequency",
        "components": [
            "Excessive Scan Frequency",
        ],
    },
    {
        "name": "QR Hash Mismatch",
        "components": [
            "Critical Verification Failure",
        ],
    },
    {
        "name": "Revoked Product",
        "components": [
            "Revoked Product",
        ],
    },
    {
        "name": "Gateway Failure",
        "components": [
            "Gateway/System Failure",
        ],
    },
    {
        "name": "Impossible Geographic Movement",
        "components": [
            "Geographic Anomaly",
        ],
    },
    {
        "name": "Combined Behavioural Geographic Risk",
        "components": [
            "Repeated Scan",
            "Excessive Scan Frequency",
            "Geographic Anomaly",
        ],
    },
]



# ============================================================
# Baseline model
# ============================================================

baseline_results = {}

for scenario in SCENARIOS:
    score = calculate_score(
        scenario,
        BASE_WEIGHTS,
    )

    baseline_results[scenario["name"]] = {
        "score": score,
        "level": risk_level(score),
    }


# ============================================================
# Ablation experiment
#
# Remove one component at a time by setting its contribution
# to zero. All other weights and thresholds remain unchanged.
# ============================================================

detail_rows = []
summary_rows = []

for removed_component in BASE_WEIGHTS:

    ablated_weights = BASE_WEIGHTS.copy()
    ablated_weights[removed_component] = 0

    changed = 0
    unchanged = 0

    absolute_changes = []
    signed_changes = []

    transition_counts = {}

    for scenario in SCENARIOS:

        baseline_score = baseline_results[
            scenario["name"]
        ]["score"]

        baseline_level = baseline_results[
            scenario["name"]
        ]["level"]

        ablated_score = calculate_score(
            scenario,
            ablated_weights,
        )

        ablated_level = risk_level(
            ablated_score
        )

        score_change = (
            ablated_score - baseline_score
        )

        absolute_changes.append(
            abs(score_change)
        )

        signed_changes.append(
            score_change
        )

        classification_changed = (
            baseline_level != ablated_level
        )

        if classification_changed:
            changed += 1

            transition = (
                f"{baseline_level}"
                f"->{ablated_level}"
            )

            transition_counts[transition] = (
                transition_counts.get(
                    transition,
                    0,
                )
                + 1
            )

        else:
            unchanged += 1

        detail_rows.append({
            "removedComponent":
                removed_component,
            "scenario":
                scenario["name"],
            "baselineScore":
                baseline_score,
            "ablatedScore":
                ablated_score,
            "scoreChange":
                score_change,
            "absoluteScoreChange":
                abs(score_change),
            "baselineLevel":
                baseline_level,
            "ablatedLevel":
                ablated_level,
            "classificationChanged":
                classification_changed,
        })

    total = len(SCENARIOS)

    agreement_rate = (
        unchanged / total * 100
    )

    mean_absolute_change = (
        sum(absolute_changes) / total
    )

    mean_signed_change = (
        sum(signed_changes) / total
    )

    transitions = (
        "; ".join(
            f"{name}:{count}"
            for name, count
            in sorted(
                transition_counts.items()
            )
        )
        if transition_counts
        else "None"
    )

    summary_rows.append({
        "removedComponent":
            removed_component,
        "cases":
            total,
        "unchangedClassifications":
            unchanged,
        "changedClassifications":
            changed,
        "decisionAgreementRatePercent":
            round(agreement_rate, 2),
        "meanAbsoluteScoreChange":
            round(mean_absolute_change, 2),
        "meanSignedScoreChange":
            round(mean_signed_change, 2),
        "classTransitions":
            transitions,
    })


# ============================================================
# Save detailed results
# ============================================================

detail_file = (
    "backend/component_ablation_detail.csv"
)

with open(
    detail_file,
    "w",
    newline="",
    encoding="utf-8",
) as file:

    writer = csv.DictWriter(
        file,
        fieldnames=detail_rows[0].keys(),
    )

    writer.writeheader()
    writer.writerows(detail_rows)


# ============================================================
# Save summary results
# ============================================================

summary_file = (
    "backend/component_ablation_summary.csv"
)

with open(
    summary_file,
    "w",
    newline="",
    encoding="utf-8",
) as file:

    writer = csv.DictWriter(
        file,
        fieldnames=summary_rows[0].keys(),
    )

    writer.writeheader()
    writer.writerows(summary_rows)


# ============================================================
# Console output
# ============================================================

print()
print("=" * 84)
print("COMPONENT-LEVEL RISK ABLATION ANALYSIS")
print("=" * 84)

print()
print("Baseline scenario classifications")
print("-" * 84)

for scenario in SCENARIOS:

    result = baseline_results[
        scenario["name"]
    ]

    print(
        f"{scenario['name']:<48}"
        f"{result['score']:>7.2f}  "
        f"{result['level']}"
    )


print()
print("Ablation summary")
print("-" * 84)

header = (
    f"{'Removed component':<32}"
    f"{'Changed':>9}"
    f"{'DAR %':>10}"
    f"{'Mean |Δ|':>11}"
    f"{'Transitions':>20}"
)

print(header)
print("-" * 84)

for row in summary_rows:

    print(
        f"{row['removedComponent']:<32}"
        f"{row['changedClassifications']:>9}"
        f"{row['decisionAgreementRatePercent']:>10.2f}"
        f"{row['meanAbsoluteScoreChange']:>11.2f}"
        f"{row['classTransitions']:>20}"
    )


print()
print("Detailed classification changes")
print("-" * 84)

change_count = 0

for row in detail_rows:

    if row["classificationChanged"]:

        change_count += 1

        print(
            f"Remove {row['removedComponent']} | "
            f"{row['scenario']} | "
            f"{row['baselineScore']} "
            f"{row['baselineLevel']} -> "
            f"{row['ablatedScore']} "
            f"{row['ablatedLevel']}"
        )


if change_count == 0:
    print(
        "No classification changes "
        "were observed."
    )


print()
print(
    "Interpretation note:"
)

print(
    "This experiment measures the contribution "
    "of individual deterministic risk components. "
    "It does not measure predictive accuracy on "
    "independently labelled counterfeit data."
)

print()
print(
    f"Detailed results : {detail_file}"
)

print(
    f"Summary results  : {summary_file}"
)

print("=" * 84)
