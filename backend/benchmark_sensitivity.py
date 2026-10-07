import csv
from collections import defaultdict

# ============================================================
# Production risk-engine parameters
# ============================================================

BASE_WEIGHTS = {
    "Critical Verification Failure": 90,
    "Gateway/System Failure": 50,
    "Revoked Product": 70,
    "Repeated Scan": 10,
    "Excessive Scan Frequency": 20,
    "Geographic Anomaly": 40,
}

VARIATIONS = [-20, -10, 0, 10, 20]

LOW_THRESHOLD = 30
HIGH_THRESHOLD = 70
MAX_SCORE = 100


def risk_level(score):
    if score >= HIGH_THRESHOLD:
        return "HIGH"
    elif score >= LOW_THRESHOLD:
        return "MEDIUM"
    return "LOW"


def capped_score(value):
    return min(value, MAX_SCORE)


# ============================================================
# Controlled scenarios corresponding to the implemented rules
#
# Each scenario lists the risk components activated by that
# scenario. Scores are therefore derived from the same weights
# used by the production risk engine.
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





def calculate_score(scenario, weights):
    score = sum(
        weights[component]
        for component in scenario["components"]
    )
    return capped_score(score)


# ============================================================
# Baseline
# ============================================================

baseline_results = {}

for scenario in SCENARIOS:
    score = calculate_score(scenario, BASE_WEIGHTS)
    baseline_results[scenario["name"]] = {
        "score": score,
        "level": risk_level(score),
    }


# ============================================================
# Sensitivity experiment
# One weight at a time; all other weights remain unchanged.
# ============================================================

detail_rows = []
summary_rows = []

for rule_name, baseline_weight in BASE_WEIGHTS.items():

    for variation in VARIATIONS:

        tested_weight = baseline_weight * (
            1 + variation / 100.0
        )

        test_weights = BASE_WEIGHTS.copy()
        test_weights[rule_name] = tested_weight

        changed = 0
        unchanged = 0
        absolute_score_changes = []

        for scenario in SCENARIOS:

            baseline_score = baseline_results[
                scenario["name"]
            ]["score"]

            baseline_level = baseline_results[
                scenario["name"]
            ]["level"]

            tested_score = calculate_score(
                scenario,
                test_weights,
            )

            tested_level = risk_level(tested_score)

            score_change = tested_score - baseline_score

            classification_changed = (
                tested_level != baseline_level
            )

            if classification_changed:
                changed += 1
            else:
                unchanged += 1

            absolute_score_changes.append(
                abs(score_change)
            )

            detail_rows.append({
                "rule": rule_name,
                "variationPercent": variation,
                "baselineWeight": baseline_weight,
                "testedWeight": round(tested_weight, 2),
                "scenario": scenario["name"],
                "baselineScore": round(
                    baseline_score, 2
                ),
                "testedScore": round(
                    tested_score, 2
                ),
                "scoreChange": round(
                    score_change, 2
                ),
                "baselineLevel": baseline_level,
                "testedLevel": tested_level,
                "classificationChanged":
                    classification_changed,
            })

        total = len(SCENARIOS)

        agreement_rate = (
            unchanged / total * 100
        )

        mean_absolute_score_change = (
            sum(absolute_score_changes) / total
        )

        summary_rows.append({
            "rule": rule_name,
            "variationPercent": variation,
            "baselineWeight": baseline_weight,
            "testedWeight": round(tested_weight, 2),
            "cases": total,
            "unchangedClassifications": unchanged,
            "changedClassifications": changed,
            "decisionAgreementRatePercent":
                round(agreement_rate, 2),
            "meanAbsoluteScoreChange":
                round(mean_absolute_score_change, 2),
        })


# ============================================================
# Save detailed CSV
# ============================================================

detail_file = "backend/risk_weight_sensitivity_detail.csv"

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
# Save summary CSV
# ============================================================

summary_file = "backend/risk_weight_sensitivity_summary.csv"

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
# Console report
# ============================================================

print()
print("=" * 78)
print("RISK-WEIGHT SENSITIVITY ANALYSIS")
print("=" * 78)

print()
print("Classification thresholds:")
print("LOW    : score < 30")
print("MEDIUM : 30 <= score < 70")
print("HIGH   : score >= 70")

print()
print("Baseline scenario results")
print("-" * 78)

for scenario in SCENARIOS:
    result = baseline_results[scenario["name"]]

    print(
        f"{scenario['name']:<45}"
        f"{result['score']:>8.2f}  "
        f"{result['level']}"
    )


print()
print("Sensitivity summary")
print("-" * 78)

header = (
    f"{'Rule':<31}"
    f"{'Var':>7}"
    f"{'Weight':>9}"
    f"{'Changed':>10}"
    f"{'DAR %':>9}"
    f"{'Mean Δ':>10}"
)

print(header)
print("-" * 78)

for row in summary_rows:

    print(
        f"{row['rule']:<31}"
        f"{row['variationPercent']:>+6}%"
        f"{row['testedWeight']:>9.2f}"
        f"{row['changedClassifications']:>10}"
        f"{row['decisionAgreementRatePercent']:>9.2f}"
        f"{row['meanAbsoluteScoreChange']:>10.2f}"
    )


print()
print("Classification changes")
print("-" * 78)

change_count = 0

for row in detail_rows:

    if row["classificationChanged"]:

        change_count += 1

        print(
            f"{row['rule']} | "
            f"{row['variationPercent']:+}% | "
            f"{row['scenario']} | "
            f"{row['baselineScore']} "
            f"{row['baselineLevel']} -> "
            f"{row['testedScore']} "
            f"{row['testedLevel']}"
        )

if change_count == 0:
    print("No risk-classification changes detected.")

print()
print(f"Detailed results : {detail_file}")
print(f"Summary results  : {summary_file}")
print("=" * 78)
