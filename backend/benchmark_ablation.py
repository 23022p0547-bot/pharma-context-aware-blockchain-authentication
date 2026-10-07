from dataclasses import dataclass

# ============================================================
# CONTROLLED SCENARIOS
# ============================================================

@dataclass
class Scenario:
    name: str
    blockchain_failure: int = 0
    revoked: int = 0
    repeated: int = 0
    excessive: int = 0
    geographic: int = 0
    expected_actionable: int = 0


SCENARIOS = [
    Scenario(
        "Normal Genuine Scan",
        expected_actionable=0,
    ),
    Scenario(
        "Legitimate Single Repeat",
        expected_actionable=0,
    ),
    Scenario(
        "Repeated Scan",
        repeated=1,
        expected_actionable=0,
    ),
    Scenario(
        "Excessive Scan Frequency",
        excessive=1,
        expected_actionable=0,
    ),
    Scenario(
        "QR Hash Mismatch",
        blockchain_failure=1,
        expected_actionable=1,
    ),
    Scenario(
        "Revoked Product",
        revoked=1,
        expected_actionable=1,
    ),
    Scenario(
        "Impossible Geographic Movement",
        geographic=1,
        expected_actionable=1,
    ),
    Scenario(
        "Repeated + Excessive + Geographic",
        repeated=1,
        excessive=1,
        geographic=1,
        expected_actionable=1,
    ),
]

# ============================================================
# MODEL DEFINITIONS
# ============================================================

def m1_blockchain_only(s):
    """
    M1:
    Blockchain/QR verification only.
    """
    score = (
        90 * s.blockchain_failure
        + 70 * s.revoked
    )

    return min(score, 100)


def m2_blockchain_behavioral(s):
    """
    M2:
    Blockchain + behavioral scan analysis.
    """
    score = (
        90 * s.blockchain_failure
        + 70 * s.revoked
        + 10 * s.repeated
        + 20 * s.excessive
    )

    return min(score, 100)


def m3_context_aware(s):
    """
    M3:
    Proposed context-aware framework.
    """
    score = (
        90 * s.blockchain_failure
        + 70 * s.revoked
        + 10 * s.repeated
        + 20 * s.excessive
        + 40 * s.geographic
    )

    return min(score, 100)


def risk_level(score):

    if score >= 70:
        return "HIGH"

    if score >= 30:
        return "MEDIUM"

    return "LOW"


def actionable(score):
    return 1 if score >= 30 else 0


# ============================================================
# EVALUATION
# ============================================================

MODELS = [
    ("M1 Blockchain Only", m1_blockchain_only),
    ("M2 Blockchain + Behavioral",
     m2_blockchain_behavioral),
    ("M3 Proposed Context-Aware",
     m3_context_aware),
]


print()
print("=" * 110)
print("BASELINE / ABLATION COMPARISON")
print("=" * 110)

header = (
    f"{'Scenario':42}"
    f"{'Expected':12}"
    f"{'M1':18}"
    f"{'M2':18}"
    f"{'M3':18}"
)

print(header)
print("-" * 110)


for s in SCENARIOS:

    scores = []

    for _, model in MODELS:

        score = model(s)

        scores.append(
            f"{score:3} {risk_level(score):6}"
        )

    expected = (
        "ACTIONABLE"
        if s.expected_actionable
        else "NORMAL"
    )

    print(
        f"{s.name:42}"
        f"{expected:12}"
        f"{scores[0]:18}"
        f"{scores[1]:18}"
        f"{scores[2]:18}"
    )


print()
print("=" * 110)
print("MODEL-LEVEL PERFORMANCE")
print("=" * 110)


for model_name, model in MODELS:

    tp = tn = fp = fn = 0

    for s in SCENARIOS:

        prediction = actionable(
            model(s)
        )

        actual = s.expected_actionable

        if prediction == 1 and actual == 1:
            tp += 1

        elif prediction == 0 and actual == 0:
            tn += 1

        elif prediction == 1 and actual == 0:
            fp += 1

        elif prediction == 0 and actual == 1:
            fn += 1

    accuracy = (
        (tp + tn) / len(SCENARIOS)
    )

    precision = (
        tp / (tp + fp)
        if (tp + fp) else 0
    )

    recall = (
        tp / (tp + fn)
        if (tp + fn) else 0
    )

    f1 = (
        2 * precision * recall
        / (precision + recall)
        if (precision + recall) else 0
    )

    print()
    print(model_name)
    print("-" * 50)

    print(
        f"TP={tp}  TN={tn}  "
        f"FP={fp}  FN={fn}"
    )

    print(
        f"Accuracy  : {accuracy * 100:.2f}%"
    )

    print(
        f"Precision : {precision * 100:.2f}%"
    )

    print(
        f"Recall    : {recall * 100:.2f}%"
    )

    print(
        f"F1 Score  : {f1 * 100:.2f}%"
    )


print()
print("=" * 110)
