import csv
from datetime import datetime, timedelta

from app import (
    app,
    assess_scan_risk,
    generate_explanation,
)
from models import ScanLog, db


PREFIX = "RISKTEST_"


def risk_level(score):
    if score >= 70:
        return "HIGH"
    elif score >= 30:
        return "MEDIUM"
    return "LOW"


def clear_test_data():
    ScanLog.query.filter(
        ScanLog.drug_id.like(f"{PREFIX}%")
    ).delete(synchronize_session=False)

    db.session.commit()


def add_scan(
    drug_id,
    minutes_ago=0,
    seconds_ago=0,
    latitude=None,
    longitude=None,
    country=None,
):
    scan_time = (
        datetime.utcnow()
        - timedelta(
            minutes=minutes_ago,
            seconds=seconds_ago,
        )
    )

    log = ScanLog(
        drug_id=drug_id,
        qr_hash="RISK_TEST_HASH",
        result="GENUINE",
        message="Risk-engine benchmark fixture",
        scan_time=scan_time,
        ip_address="127.0.0.1",
        forwarded_ip="203.0.113.10",
        user_agent="Risk Engine Benchmark",
        device="Mobile",
        browser="Benchmark",
        operating_system="TestOS",
        city="Test City",
        region="Test Region",
        country=country,
        latitude=latitude,
        longitude=longitude,
        risk_score=0,
    )

    db.session.add(log)


def evaluate(
    scenario,
    drug_id,
    status,
    location,
    expected_score,
):
    result = {
        "isValid": status == "GENUINE",
        "status": status,
        "message": f"Benchmark scenario: {scenario}",
        "drug": None,
    }

    observed_score, alert = assess_scan_risk(
        drug_id=drug_id,
        verification_result=result,
        location=location,
    )

    observed_level = risk_level(observed_score)
    expected_level = risk_level(expected_score)

    generated_level, explanation, recommendation = (
        generate_explanation(
            result,
            observed_score,
            location,
        )
    )

    passed = (
        observed_score == expected_score
        and observed_level == expected_level
        and generated_level == expected_level
    )

    return {
        "scenario": scenario,
        "status": status,
        "expected_score": expected_score,
        "observed_score": observed_score,
        "expected_level": expected_level,
        "observed_level": observed_level,
        "alert": alert or "None",
        "explanation": explanation,
        "recommendation": recommendation,
        "result": "PASS" if passed else "FAIL",
    }


def main():
    rows = []

    with app.app_context():

        clear_test_data()

        # -------------------------------------------------
        # Scenario 1: Normal genuine scan
        # -------------------------------------------------
        rows.append(
            evaluate(
                scenario="Normal Genuine Scan",
                drug_id=f"{PREFIX}GENUINE",
                status="GENUINE",
                location={
                    "city": "Vijayawada",
                    "region": "Andhra Pradesh",
                    "country": "India",
                    "latitude": 16.5062,
                    "longitude": 80.6480,
                },
                expected_score=0,
            )
        )

        # -------------------------------------------------
        # Scenario 2: Revoked pharmaceutical
        # -------------------------------------------------
        rows.append(
            evaluate(
                scenario="Revoked Product",
                drug_id=f"{PREFIX}REVOKED",
                status="REVOKED",
                location={
                    "city": "Vijayawada",
                    "region": "Andhra Pradesh",
                    "country": "India",
                    "latitude": 16.5062,
                    "longitude": 80.6480,
                },
                expected_score=70,
            )
        )

        # -------------------------------------------------
        # Scenario 3: QR mismatch
        # -------------------------------------------------
        rows.append(
            evaluate(
                scenario="QR Hash Mismatch",
                drug_id=f"{PREFIX}MISMATCH",
                status="QR_MISMATCH",
                location={},
                expected_score=90,
            )
        )

        # -------------------------------------------------
        # Scenario 4: Gateway/system error
        # -------------------------------------------------
        rows.append(
            evaluate(
                scenario="Gateway Unavailable",
                drug_id=f"{PREFIX}GATEWAY",
                status="GATEWAY_UNAVAILABLE",
                location={},
                expected_score=50,
            )
        )

        # -------------------------------------------------
        # Scenario 5: Repeated scans
        # 3 previous scans within 1 minute
        # -------------------------------------------------
        repeated_id = f"{PREFIX}REPEATED"

        for seconds in (10, 20, 30):
            add_scan(
                repeated_id,
                seconds_ago=seconds,
                country="India",
            )

        db.session.commit()

        rows.append(
            evaluate(
                scenario="Repeated Scan",
                drug_id=repeated_id,
                status="GENUINE",
                location={},
                expected_score=10,
            )
        )

        # -------------------------------------------------
        # Scenario 6: Excessive scans only
        # 10 scans in 10 min, but none within last minute
        # -------------------------------------------------
        excessive_id = f"{PREFIX}EXCESSIVE"

        for minutes in (
            1.5,
            2.0,
            2.5,
            3.0,
            4.0,
            5.0,
            6.0,
            7.0,
            8.0,
            9.0,
        ):
            add_scan(
                excessive_id,
                minutes_ago=minutes,
                country="India",
            )

        db.session.commit()

        rows.append(
            evaluate(
                scenario="Excessive Scan Frequency",
                drug_id=excessive_id,
                status="GENUINE",
                location={},
                expected_score=20,
            )
        )

        # -------------------------------------------------
        # Scenario 7:
        # Repeated + excessive scans
        # -------------------------------------------------
        combined_id = f"{PREFIX}COMBINED"

        for seconds in (10, 20, 30):
            add_scan(
                combined_id,
                seconds_ago=seconds,
                country="India",
            )

        for minutes in (2, 3, 4, 5, 6, 7, 8):
            add_scan(
                combined_id,
                minutes_ago=minutes,
                country="India",
            )

        db.session.commit()

        rows.append(
            evaluate(
                scenario="Repeated and Excessive Scans",
                drug_id=combined_id,
                status="GENUINE",
                location={},
                expected_score=30,
            )
        )

        # -------------------------------------------------
        # Scenario 8: Geographic anomaly
        # Previous India scan; immediate US scan
        # -------------------------------------------------
        geo_id = f"{PREFIX}GEO"

        add_scan(
            geo_id,
            minutes_ago=5,
            latitude=16.5062,
            longitude=80.6480,
            country="India",
        )

        db.session.commit()

        rows.append(
            evaluate(
                scenario="Impossible Geographic Movement",
                drug_id=geo_id,
                status="GENUINE",
                location={
                    "city": "New York",
                    "region": "New York",
                    "country": "United States",
                    "latitude": 40.7128,
                    "longitude": -74.0060,
                },
                expected_score=40,
            )
        )

        # -------------------------------------------------
        # Scenario 9:
        # Repeated + excessive + geographic anomaly
        # -------------------------------------------------
        high_id = f"{PREFIX}HIGHCOMBINED"

        # Previous location record
        add_scan(
            high_id,
            minutes_ago=5,
            latitude=16.5062,
            longitude=80.6480,
            country="India",
        )

        # Rapid recent scans
        for seconds in (10, 20, 30):
            add_scan(
                high_id,
                seconds_ago=seconds,
                country="India",
            )

        # Additional scans within ten minutes
        for minutes in (2, 3, 4, 6, 7, 8):
            add_scan(
                high_id,
                minutes_ago=minutes,
                country="India",
            )

        db.session.commit()

        rows.append(
            evaluate(
                scenario="Combined Behavioural and Geographic Risk",
                drug_id=high_id,
                status="GENUINE",
                location={
                    "city": "New York",
                    "region": "New York",
                    "country": "United States",
                    "latitude": 40.7128,
                    "longitude": -74.0060,
                },
                expected_score=70,
            )
        )

        # -------------------------------------------------
        # Results
        # -------------------------------------------------
        print("\n")
        print("=" * 90)
        print("COUNTERFEIT RISK ENGINE VALIDATION")
        print("=" * 90)

        for row in rows:
            print(
                f"{row['scenario']:<42}"
                f"Expected={row['expected_score']:>3}  "
                f"Observed={row['observed_score']:>3}  "
                f"Level={row['observed_level']:<6}  "
                f"{row['result']}"
            )

        passed = sum(
            1
            for row in rows
            if row["result"] == "PASS"
        )

        total = len(rows)

        validation_rate = (
            passed / total * 100
        )

        print("=" * 90)
        print(f"Passed scenarios : {passed}/{total}")
        print(
            f"Rule validation rate: "
            f"{validation_rate:.2f}%"
        )
        print("=" * 90)

        # -------------------------------------------------
        # CSV
        # -------------------------------------------------
        with open(
            "risk_engine_validation.csv",
            "w",
            newline="",
            encoding="utf-8",
        ) as file:

            fieldnames = [
                "scenario",
                "status",
                "expected_score",
                "observed_score",
                "expected_level",
                "observed_level",
                "alert",
                "explanation",
                "recommendation",
                "result",
            ]

            writer = csv.DictWriter(
                file,
                fieldnames=fieldnames,
            )

            writer.writeheader()
            writer.writerows(rows)

        print(
            "\nResults saved to "
            "risk_engine_validation.csv"
        )

        # Remove artificial benchmark records
        clear_test_data()


if __name__ == "__main__":
    main()