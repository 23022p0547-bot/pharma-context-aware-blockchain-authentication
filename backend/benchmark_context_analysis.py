import csv

from app import app
from models import ScanLog


FIELDS = [
    "forwarded_ip",
    "city",
    "region",
    "country",
    "latitude",
    "longitude",
    "device",
    "browser",
    "operating_system",
]


def field_available(value):
    if value is None:
        return False

    if isinstance(value, str):
        return value.strip() not in {
            "",
            "Unknown",
            "None",
        }

    return True


def main():
    with app.app_context():

        logs = (
            ScanLog.query
            .filter(ScanLog.forwarded_ip.isnot(None))
            .order_by(ScanLog.id.desc())
            .limit(20)
            .all()
        )

        if not logs:
            print(
                "No public/Cloudflare scan records found."
            )
            return

        rows = []

        print("\n" + "=" * 90)
        print("CONTEXT ANALYSIS VALIDATION")
        print("=" * 90)

        for log in logs:

            values = {
                "forwarded_ip": log.forwarded_ip,
                "city": log.city,
                "region": log.region,
                "country": log.country,
                "latitude": log.latitude,
                "longitude": log.longitude,
                "device": log.device,
                "browser": log.browser,
                "operating_system": (
                    log.operating_system
                ),
            }

            available_count = sum(
                1
                for field in FIELDS
                if field_available(values[field])
            )

            completeness = (
                available_count
                / len(FIELDS)
                * 100
            )

            rows.append({
                "log_id": log.id,
                "drug_id": log.drug_id,
                **values,
                "available_fields": available_count,
                "total_fields": len(FIELDS),
                "completeness_percent": round(
                    completeness,
                    2,
                ),
            })

            print(
                f"Log {log.id:<4} "
                f"Drug={log.drug_id:<8} "
                f"Context completeness="
                f"{completeness:6.2f}%"
            )

        total_records = len(rows)

        complete_records = sum(
            1
            for row in rows
            if row[
                "completeness_percent"
            ] == 100.0
        )

        complete_rate = (
            complete_records
            / total_records
            * 100
        )

        field_success = {}

        for field in FIELDS:

            count = sum(
                1
                for row in rows
                if field_available(row[field])
            )

            field_success[field] = (
                count
                / total_records
                * 100
            )

        print("\n" + "-" * 90)
        print("SUMMARY")
        print("-" * 90)

        print(
            "Public scan records evaluated :",
            total_records,
        )

        print(
            "Fully populated records       :",
            complete_records,
        )

        print(
            f"Complete context rate         : "
            f"{complete_rate:.2f}%"
        )

        print("\nField-level extraction:")

        for field, rate in field_success.items():
            print(
                f"{field:<20}: "
                f"{rate:6.2f}%"
            )

        with open(
            "context_analysis_validation.csv",
            "w",
            newline="",
            encoding="utf-8",
        ) as file:

            writer = csv.DictWriter(
                file,
                fieldnames=rows[0].keys(),
            )

            writer.writeheader()
            writer.writerows(rows)

        print(
            "\nResults saved to "
            "context_analysis_validation.csv"
        )


if __name__ == "__main__":
    main()