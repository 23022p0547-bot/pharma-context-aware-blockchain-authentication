import csv
import statistics
import time
from datetime import datetime

import requests

BASE_URL = "http://localhost:3000"
TRIALS = 20


def measure_request(method, url, **kwargs):
    start = time.perf_counter()

    response = requests.request(
        method,
        url,
        timeout=30,
        **kwargs,
    )

    end = time.perf_counter()

    latency_ms = (end - start) * 1000

    return response, latency_ms


def summarize(values):
    return {
        "min_ms": min(values),
        "max_ms": max(values),
        "mean_ms": statistics.mean(values),
        "median_ms": statistics.median(values),
        "std_dev_ms": (
            statistics.stdev(values)
            if len(values) > 1
            else 0
        ),
    }


def benchmark_verify():
    values = []

    drug_id = "D001"

    # Use the actual QR hash of D001
    qr_hash = input(
        "Enter QR hash for D001: "
    ).strip()

    for i in range(TRIALS):
        response, latency = measure_request(
            "POST",
            f"{BASE_URL}/verify",
            json={
                "drugId": drug_id,
                "qrHash": qr_hash,
            },
        )

        print(
            f"Verify trial {i + 1}: "
            f"{latency:.2f} ms "
            f"HTTP {response.status_code}"
        )

        values.append(latency)

    return values


def benchmark_registration():
    values = []

    for i in range(TRIALS):
        number = 1000 + i

        payload = {
            "drugID": f"BMARK{number}",
            "drugName": "BenchmarkDrug 500mg",
            "manufacturer": "Benchmark Pharma",
            "batchNumber": f"BM{number}",
            "manufactureDate": "2026-08-08",
            "expiryDate": "2028-08-08",
            "currentOwner": "Benchmark Pharma",
            "qrHash": f"BENCHMARKHASH{number}",
        }

        response, latency = measure_request(
            "POST",
            f"{BASE_URL}/drugs",
            json=payload,
        )

        print(
            f"Register trial {i + 1}: "
            f"{latency:.2f} ms "
            f"HTTP {response.status_code}"
        )

        if response.ok:
            values.append(latency)
        else:
            print(response.text)

    return values


def benchmark_transfer():
    values = []

    for i in range(TRIALS):
        drug_id = f"BMARK{1000 + i}"

        response, latency = measure_request(
            "POST",
            f"{BASE_URL}/drugs/{drug_id}/transfer",
            json={
                "newOwner": "Benchmark Distributor"
            },
        )

        print(
            f"Transfer trial {i + 1}: "
            f"{latency:.2f} ms "
            f"HTTP {response.status_code}"
        )

        if response.ok:
            values.append(latency)
        else:
            print(response.text)

    return values


def benchmark_revoke():
    values = []

    for i in range(TRIALS):
        drug_id = f"BMARK{1000 + i}"

        response, latency = measure_request(
            "POST",
            f"{BASE_URL}/drugs/{drug_id}/revoke",
            json={
                "reason": "Benchmark performance test"
            },
        )

        print(
            f"Revoke trial {i + 1}: "
            f"{latency:.2f} ms "
            f"HTTP {response.status_code}"
        )

        if response.ok:
            values.append(latency)
        else:
            print(response.text)

    return values


def save_results(all_results):
    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    raw_filename = (
        f"benchmark_raw_{timestamp}.csv"
    )

    summary_filename = (
        f"benchmark_summary_{timestamp}.csv"
    )

    with open(
        raw_filename,
        "w",
        newline="",
    ) as file:
        writer = csv.writer(file)

        writer.writerow([
            "operation",
            "trial",
            "latency_ms",
        ])

        for operation, values in all_results.items():
            for index, value in enumerate(
                values,
                start=1,
            ):
                writer.writerow([
                    operation,
                    index,
                    round(value, 3),
                ])

    with open(
        summary_filename,
        "w",
        newline="",
    ) as file:
        writer = csv.writer(file)

        writer.writerow([
            "operation",
            "trials",
            "min_ms",
            "max_ms",
            "mean_ms",
            "median_ms",
            "std_dev_ms",
        ])

        for operation, values in all_results.items():
            if not values:
                continue

            stats = summarize(values)

            writer.writerow([
                operation,
                len(values),
                round(stats["min_ms"], 3),
                round(stats["max_ms"], 3),
                round(stats["mean_ms"], 3),
                round(stats["median_ms"], 3),
                round(stats["std_dev_ms"], 3),
            ])

    print("\nSaved:")
    print(raw_filename)
    print(summary_filename)


def main():
    all_results = {}

    print("\n=== REGISTER DRUG ===")
    all_results["RegisterDrug"] = (
        benchmark_registration()
    )

    print("\n=== VERIFY DRUG ===")
    all_results["VerifyDrug"] = (
        benchmark_verify()
    )

    print("\n=== TRANSFER OWNERSHIP ===")
    all_results["TransferOwnership"] = (
        benchmark_transfer()
    )

    print("\n=== REVOKE DRUG ===")
    all_results["RevokeDrug"] = (
        benchmark_revoke()
    )

    save_results(all_results)


if __name__ == "__main__":
    main()