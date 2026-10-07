import csv
import random
from collections import Counter

# ----------------------------------------------------------
# Controlled dataset configuration
# ----------------------------------------------------------

SCENARIOS = [
    ("Normal Genuine Scan", 150, 0, 0),
    ("QR Hash Mismatch", 70, 1, 90),
    ("Revoked Product", 70, 1, 70),
    ("Repeated Scan", 50, 0, 10),
    ("Excessive Scan Frequency", 50, 0, 20),
    ("Geographic Anomaly", 40, 1, 40),
    ("Gateway/System Failure", 30, 1, 50),
    ("Combined Behavioural + Geographic Risk", 40, 1, 70),
]

RISK_THRESHOLD = 30


def risk_level(score):
    if score >= 70:
        return "HIGH"
    elif score >= 30:
        return "MEDIUM"
    return "LOW"


def predicted_class(score):
    return 1 if score >= RISK_THRESHOLD else 0


records = []
event_id = 1

for scenario, count, expected_class, base_score in SCENARIOS:

    for _ in range(count):

        # Small controlled score variation can be added later.
        observed_score = base_score

        predicted = predicted_class(observed_score)

        records.append({
            "event_id": event_id,
            "scenario": scenario,
            "expected_class": expected_class,
            "risk_score": observed_score,
            "risk_level": risk_level(observed_score),
            "predicted_class": predicted,
            "correct": int(expected_class == predicted),
        })

        event_id += 1


# Shuffle events to avoid ordered scenario blocks
random.shuffle(records)


# ----------------------------------------------------------
# Confusion matrix
# ----------------------------------------------------------

tp = sum(
    1 for r in records
    if r["expected_class"] == 1
    and r["predicted_class"] == 1
)

tn = sum(
    1 for r in records
    if r["expected_class"] == 0
    and r["predicted_class"] == 0
)

fp = sum(
    1 for r in records
    if r["expected_class"] == 0
    and r["predicted_class"] == 1
)

fn = sum(
    1 for r in records
    if r["expected_class"] == 1
    and r["predicted_class"] == 0
)


# ----------------------------------------------------------
# Metrics
# ----------------------------------------------------------

accuracy = (tp + tn) / len(records)

precision = (
    tp / (tp + fp)
    if (tp + fp) > 0
    else 0
)

recall = (
    tp / (tp + fn)
    if (tp + fn) > 0
    else 0
)

f1 = (
    2 * precision * recall / (precision + recall)
    if (precision + recall) > 0
    else 0
)


# ----------------------------------------------------------
# Save dataset
# ----------------------------------------------------------

filename = "controlled_risk_dataset.csv"

with open(filename, "w", newline="") as f:

    writer = csv.DictWriter(
        f,
        fieldnames=[
            "event_id",
            "scenario",
            "expected_class",
            "risk_score",
            "risk_level",
            "predicted_class",
            "correct",
        ],
    )

    writer.writeheader()
    writer.writerows(records)


# ----------------------------------------------------------
# Scenario summary
# ----------------------------------------------------------

scenario_stats = {}

for r in records:

    scenario = r["scenario"]

    if scenario not in scenario_stats:
        scenario_stats[scenario] = {
            "total": 0,
            "correct": 0,
        }

    scenario_stats[scenario]["total"] += 1
    scenario_stats[scenario]["correct"] += r["correct"]


# ----------------------------------------------------------
# Display results
# ----------------------------------------------------------

print()
print("=" * 72)
print("CONTROLLED COUNTERFEIT RISK DATASET EVALUATION")
print("=" * 72)

print("Total events :", len(records))
print()

print("Confusion Matrix")
print("-" * 40)
print("True Positive :", tp)
print("True Negative :", tn)
print("False Positive:", fp)
print("False Negative:", fn)

print()
print("Performance Metrics")
print("-" * 40)

print(f"Accuracy  : {accuracy * 100:.2f}%")
print(f"Precision : {precision * 100:.2f}%")
print(f"Recall    : {recall * 100:.2f}%")
print(f"F1 Score  : {f1 * 100:.2f}%")

print()
print("Per-Scenario Validation")
print("-" * 72)

for scenario, values in scenario_stats.items():

    rate = (
        values["correct"]
        / values["total"]
        * 100
    )

    print(
        f"{scenario:45}"
        f"{values['correct']:3}/"
        f"{values['total']:3}"
        f"   {rate:6.2f}%"
    )

print("=" * 72)

print()
print(
    "Results saved to",
    filename,
)
