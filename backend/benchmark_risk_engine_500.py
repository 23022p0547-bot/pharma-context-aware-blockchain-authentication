import csv
import random
from datetime import datetime, timedelta

from app import app, assess_scan_risk
from models import db, ScanLog


# ============================================================
# CONFIGURATION
# ============================================================

TOTAL_EVENTS = 500
RISK_THRESHOLD = 30

random.seed(42)


# ------------------------------------------------------------
# Scenario distribution
#
# expected_class:
#     0 = NORMAL / non-actionable
#     1 = SUSPICIOUS / actionable
#
# The labels are assigned from scenario semantics,
# NOT from the risk score returned by the engine.
# ------------------------------------------------------------

SCENARIOS = [
    {
        "name": "Normal Genuine Scan",
        "count": 100,
        "expected_class": 0,
    },
    {
        "name": "Legitimate Single Repeat",
        "count": 50,
        "expected_class": 0,
    },
    {
        "name": "Repeated Scan",
        "count": 40,
        "expected_class": 0,
    },
    {
        "name": "Excessive Scan Frequency",
        "count": 40,
        "expected_class": 0,
    },
    {
        "name": "QR Hash Mismatch",
        "count": 60,
        "expected_class": 1,
    },
    {
        "name": "Revoked Product",
        "count": 60,
        "expected_class": 1,
    },
    {
        "name": "Gateway Failure",
        "count": 40,
        "expected_class": 1,
    },
    {
        "name": "Impossible Geographic Movement",
        "count": 50,
        "expected_class": 1,
    },
    {
        "name": "Combined Behavioural Geographic Risk",
        "count": 60,
        "expected_class": 1,
    },
]


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def risk_level(score):
    if score >= 70:
        return "HIGH"
    elif score >= 30:
        return "MEDIUM"
    return "LOW"


def predicted_class(score):
    return 1 if score >= RISK_THRESHOLD else 0


def add_history_scan(
    drug_id,
    scan_time,
    latitude=16.5033,
    longitude=80.6465,
    country="India",
):
    """
    Inserts a temporary previous scan.

    db.session.flush() makes it visible to the real risk-engine
    SQL queries without committing it permanently.
    """

    log = ScanLog(
        drug_id=drug_id,
        qr_hash="BENCH_HASH",
        result="GENUINE",
        scan_time=scan_time,
        forwarded_ip="203.0.113.10",
        ip_address="127.0.0.1",
        latitude=latitude,
        longitude=longitude,
        city="BenchmarkCity",
        region="BenchmarkRegion",
        country=country,
        device="Mobile",
        browser="Google Chrome",
        operating_system="Android",
        risk_score=0,
    )

    db.session.add(log)


def prepare_scenario(
    scenario_name,
    drug_id,
):
    """
    Construct the input conditions for one event.

    Returns:
        verification_result
        location
    """

    now = datetime.utcnow()

    # --------------------------------------------------------
    # 1. Normal genuine verification
    # --------------------------------------------------------

    if scenario_name == "Normal Genuine Scan":

        verification_result = {
            "status": "GENUINE",
            "isValid": True,
        }

        location = {
            "country": "India",
            "region": "Andhra Pradesh",
            "city": "Vijayawada",
            "latitude": 16.5033,
            "longitude": 80.6465,
        }

    # --------------------------------------------------------
    # 2. One normal repeat / browser refresh
    #
    # Engine deliberately should NOT penalize this.
    # --------------------------------------------------------

    elif scenario_name == "Legitimate Single Repeat":

        add_history_scan(
            drug_id,
            now - timedelta(seconds=30),
        )

        verification_result = {
            "status": "GENUINE",
            "isValid": True,
        }

        location = {
            "country": "India",
            "region": "Andhra Pradesh",
            "city": "Vijayawada",
            "latitude": 16.5033,
            "longitude": 80.6465,
        }

    # --------------------------------------------------------
    # 3. Repeated scan
    #
    # >= 3 previous scans inside one minute.
    # Expected risk contribution = 10.
    # This remains LOW under current policy.
    # --------------------------------------------------------

    elif scenario_name == "Repeated Scan":

        for seconds in [10, 20, 30]:

            add_history_scan(
                drug_id,
                now - timedelta(seconds=seconds),
            )

        verification_result = {
            "status": "GENUINE",
            "isValid": True,
        }

        location = {
            "country": "India",
            "region": "Andhra Pradesh",
            "city": "Vijayawada",
            "latitude": 16.5033,
            "longitude": 80.6465,
        }

    # --------------------------------------------------------
    # 4. Excessive scanning
    #
    # Ten previous scans inside ten minutes.
    # This also activates the repeated-scan condition,
    # therefore the real engine may produce 30.
    # --------------------------------------------------------

    elif scenario_name == "Excessive Scan Frequency":

        for index in range(10):

            add_history_scan(
                drug_id,
                now - timedelta(
                    minutes=2,
                    seconds=index * 10,
                ),
            )

        verification_result = {
            "status": "GENUINE",
            "isValid": True,
        }

        location = {
            "country": "India",
            "region": "Andhra Pradesh",
            "city": "Vijayawada",
            "latitude": 16.5033,
            "longitude": 80.6465,
        }

    # --------------------------------------------------------
    # 5. QR mismatch
    # --------------------------------------------------------

    elif scenario_name == "QR Hash Mismatch":

        verification_result = {
            "status": "QR_MISMATCH",
            "isValid": False,
        }

        location = {
            "country": "India",
            "region": "Andhra Pradesh",
            "city": "Vijayawada",
            "latitude": 16.5033,
            "longitude": 80.6465,
        }

    # --------------------------------------------------------
    # 6. Revoked product
    # --------------------------------------------------------

    elif scenario_name == "Revoked Product":

        verification_result = {
            "status": "REVOKED",
            "isValid": False,
        }

        location = {
            "country": "India",
            "region": "Andhra Pradesh",
            "city": "Vijayawada",
            "latitude": 16.5033,
            "longitude": 80.6465,
        }

    # --------------------------------------------------------
    # 7. Gateway failure
    # --------------------------------------------------------

    elif scenario_name == "Gateway Failure":

        verification_result = {
            "status": "GATEWAY_UNAVAILABLE",
            "isValid": False,
        }

        location = {
            "country": "India",
            "region": "Andhra Pradesh",
            "city": "Vijayawada",
            "latitude": 16.5033,
            "longitude": 80.6465,
        }

    # --------------------------------------------------------
    # 8. Impossible geographic movement
    #
    # Previous scan = India
    # Current scan  = USA
    #
    # Very short elapsed interval ensures >900 km/h.
    # --------------------------------------------------------

    elif scenario_name == "Impossible Geographic Movement":

        add_history_scan(
            drug_id,
            now - timedelta(minutes=10),
            latitude=16.5033,
            longitude=80.6465,
            country="India",
        )

        verification_result = {
            "status": "GENUINE",
            "isValid": True,
        }

        location = {
            "country": "United States",
            "region": "New York",
            "city": "New York",
            "latitude": 40.7128,
            "longitude": -74.0060,
        }

    # --------------------------------------------------------
    # 9. Combined behavioral + geographic anomaly
    #
    # >= 10 historical scans plus cross-country movement.
    # --------------------------------------------------------

    elif (
        scenario_name
        == "Combined Behavioural Geographic Risk"
    ):

        for index in range(10):

            add_history_scan(
                drug_id,
                now - timedelta(
                    seconds=20 + index,
                ),
                latitude=16.5033,
                longitude=80.6465,
                country="India",
            )

        verification_result = {
            "status": "GENUINE",
            "isValid": True,
        }

        location = {
            "country": "United States",
            "region": "New York",
            "city": "New York",
            "latitude": 40.7128,
            "longitude": -74.0060,
        }

    else:

        raise ValueError(
            f"Unknown scenario: {scenario_name}"
        )

    db.session.flush()

    return verification_result, location


# ============================================================
# BENCHMARK
# ============================================================

def main():

    records = []

    event_number = 1

    print()
    print("=" * 86)
    print(
        "REAL RISK-ENGINE CONTROLLED "
        "500-EVENT VALIDATION"
    )
    print("=" * 86)

    try:

        with app.app_context():

            for scenario in SCENARIOS:

                scenario_name = scenario["name"]
                count = scenario["count"]
                expected_class = (
                    scenario["expected_class"]
                )

                for _ in range(count):

                    # Every event gets its own Drug ID.
                    # Therefore histories cannot interfere
                    # with other benchmark events.
                    drug_id = (
                        f"BENCH_{event_number:04d}"
                    )

                    (
                        verification_result,
                        location,
                    ) = prepare_scenario(
                        scenario_name,
                        drug_id,
                    )

                    # ----------------------------------------
                    # CALL THE REAL APPLICATION RISK ENGINE
                    # ----------------------------------------

                    risk_score, alert = (
                        assess_scan_risk(
                            drug_id=drug_id,
                            verification_result=(
                                verification_result
                            ),
                            location=location,
                        )
                    )

                    observed_level = (
                        risk_level(risk_score)
                    )

                    predicted = predicted_class(
                        risk_score
                    )

                    correct = int(
                        predicted == expected_class
                    )

                    records.append({
                        "event_id": event_number,
                        "drug_id": drug_id,
                        "scenario": scenario_name,
                        "expected_class":
                            expected_class,
                        "risk_score":
                            risk_score,
                        "risk_level":
                            observed_level,
                        "predicted_class":
                            predicted,
                        "correct":
                            correct,
                        "alert":
                            alert or "",
                    })

                    event_number += 1

            # -----------------------------------------------
            # Do not keep any BENCH_* records.
            #
            # Nothing has been committed.
            # This rollback removes every temporary history
            # record inserted during this experiment.
            # -----------------------------------------------

            db.session.rollback()

    except Exception:

        with app.app_context():
            db.session.rollback()

        raise


    # ========================================================
    # CONFUSION MATRIX
    # ========================================================

    tp = sum(
        1
        for r in records
        if r["expected_class"] == 1
        and r["predicted_class"] == 1
    )

    tn = sum(
        1
        for r in records
        if r["expected_class"] == 0
        and r["predicted_class"] == 0
    )

    fp = sum(
        1
        for r in records
        if r["expected_class"] == 0
        and r["predicted_class"] == 1
    )

    fn = sum(
        1
        for r in records
        if r["expected_class"] == 1
        and r["predicted_class"] == 0
    )


    # ========================================================
    # METRICS
    # ========================================================

    total = len(records)

    accuracy = (
        (tp + tn) / total
        if total
        else 0
    )

    precision = (
        tp / (tp + fp)
        if (tp + fp)
        else 0
    )

    recall = (
        tp / (tp + fn)
        if (tp + fn)
        else 0
    )

    specificity = (
        tn / (tn + fp)
        if (tn + fp)
        else 0
    )

    f1 = (
        2 * precision * recall
        / (precision + recall)
        if (precision + recall)
        else 0
    )


    # ========================================================
    # SAVE CSV
    # ========================================================

    output_file = (
        "risk_engine_500_validation.csv"
    )

    with open(
        output_file,
        "w",
        newline="",
        encoding="utf-8",
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=[
                "event_id",
                "drug_id",
                "scenario",
                "expected_class",
                "risk_score",
                "risk_level",
                "predicted_class",
                "correct",
                "alert",
            ],
        )

        writer.writeheader()
        writer.writerows(records)


    # ========================================================
    # PER-SCENARIO RESULTS
    # ========================================================

    scenario_summary = {}

    for record in records:

        name = record["scenario"]

        if name not in scenario_summary:

            scenario_summary[name] = {
                "total": 0,
                "correct": 0,
                "scores": [],
            }

        scenario_summary[name]["total"] += 1

        scenario_summary[name]["correct"] += (
            record["correct"]
        )

        scenario_summary[name]["scores"].append(
            record["risk_score"]
        )


    # ========================================================
    # TERMINAL OUTPUT
    # ========================================================

    print()
    print("Total events :", total)

    print()
    print("=" * 45)
    print("CONFUSION MATRIX")
    print("=" * 45)

    print("True Positive  :", tp)
    print("True Negative  :", tn)
    print("False Positive :", fp)
    print("False Negative :", fn)

    print()
    print("=" * 45)
    print("PERFORMANCE METRICS")
    print("=" * 45)

    print(
        f"Accuracy    : "
        f"{accuracy * 100:.2f}%"
    )

    print(
        f"Precision   : "
        f"{precision * 100:.2f}%"
    )

    print(
        f"Recall      : "
        f"{recall * 100:.2f}%"
    )

    print(
        f"Specificity : "
        f"{specificity * 100:.2f}%"
    )

    print(
        f"F1 Score    : "
        f"{f1 * 100:.2f}%"
    )

    print()
    print("=" * 86)
    print("PER-SCENARIO VALIDATION")
    print("=" * 86)

    for name, values in scenario_summary.items():

        total_scenario = values["total"]
        correct_scenario = values["correct"]

        detection_rate = (
            correct_scenario
            / total_scenario
            * 100
        )

        average_score = (
            sum(values["scores"])
            / len(values["scores"])
        )

        print(
            f"{name:45}"
            f"{correct_scenario:3}/"
            f"{total_scenario:<3}"
            f"  "
            f"Correct={detection_rate:6.2f}%"
            f"  "
            f"MeanRisk={average_score:6.2f}"
        )

    print("=" * 86)

    print()
    print(
        "Results saved to",
        output_file,
    )

    print(
        "Temporary BENCH_* database "
        "records were rolled back."
    )


if __name__ == "__main__":
    main()
