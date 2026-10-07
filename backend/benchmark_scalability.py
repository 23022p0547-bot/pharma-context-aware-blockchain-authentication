import csv
import time
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests


BASE_URL = "http://localhost:3000"

DRUG_ID = "D001"
QR_HASH = "QRHASH001"

CONCURRENCY_LEVELS = [1, 5, 10, 20, 50]

REQUESTS_PER_LEVEL = 100


def verify_drug():
    url = f"{BASE_URL}/verify"

    payload = {
        "drugId": DRUG_ID,
        "qrHash": QR_HASH,
    }

    start = time.perf_counter()

    try:
        response = requests.post(
            url,
            json=payload,
            timeout=30,
        )

        latency_ms = (
            time.perf_counter() - start
        ) * 1000

        success = (
            response.status_code == 200
        )

        return latency_ms, success

    except requests.RequestException:
        latency_ms = (
            time.perf_counter() - start
        ) * 1000

        return latency_ms, False


def percentile(values, percentile_value):
    values = sorted(values)

    index = (
        percentile_value / 100
    ) * (len(values) - 1)

    lower = int(index)
    upper = min(
        lower + 1,
        len(values) - 1,
    )

    fraction = index - lower

    return (
        values[lower]
        + (
            values[upper]
            - values[lower]
        )
        * fraction
    )


def run_level(concurrency):

    print("\n" + "=" * 70)
    print(
        f"Concurrency Level: {concurrency}"
    )
    print("=" * 70)

    latencies = []
    successful = 0

    start_batch = time.perf_counter()

    with ThreadPoolExecutor(
        max_workers=concurrency
    ) as executor:

        futures = [
            executor.submit(verify_drug)
            for _ in range(
                REQUESTS_PER_LEVEL
            )
        ]

        for future in as_completed(futures):

            latency, success = future.result()

            latencies.append(latency)

            if success:
                successful += 1

    total_time = (
        time.perf_counter()
        - start_batch
    )

    failed = (
        REQUESTS_PER_LEVEL
        - successful
    )

    success_rate = (
        successful
        / REQUESTS_PER_LEVEL
        * 100
    )

    throughput = (
        successful / total_time
        if total_time > 0
        else 0
    )

    mean_latency = statistics.mean(
        latencies
    )

    median_latency = statistics.median(
        latencies
    )

    p95_latency = percentile(
        latencies,
        95,
    )

    minimum = min(latencies)
    maximum = max(latencies)

    print(
        f"Requests        : "
        f"{REQUESTS_PER_LEVEL}"
    )

    print(
        f"Successful      : {successful}"
    )

    print(
        f"Failed          : {failed}"
    )

    print(
        f"Success Rate    : "
        f"{success_rate:.2f}%"
    )

    print(
        f"Total Time      : "
        f"{total_time:.3f} s"
    )

    print(
        f"Throughput      : "
        f"{throughput:.2f} req/s"
    )

    print(
        f"Mean Latency    : "
        f"{mean_latency:.3f} ms"
    )

    print(
        f"Median Latency  : "
        f"{median_latency:.3f} ms"
    )

    print(
        f"P95 Latency     : "
        f"{p95_latency:.3f} ms"
    )

    print(
        f"Minimum Latency : "
        f"{minimum:.3f} ms"
    )

    print(
        f"Maximum Latency : "
        f"{maximum:.3f} ms"
    )

    return {
        "concurrency": concurrency,
        "requests": REQUESTS_PER_LEVEL,
        "successful": successful,
        "failed": failed,
        "success_rate_percent": round(
            success_rate, 2
        ),
        "total_time_seconds": round(
            total_time, 3
        ),
        "throughput_requests_per_second":
            round(throughput, 3),
        "mean_latency_ms": round(
            mean_latency, 3
        ),
        "median_latency_ms": round(
            median_latency, 3
        ),
        "p95_latency_ms": round(
            p95_latency, 3
        ),
        "minimum_latency_ms": round(
            minimum, 3
        ),
        "maximum_latency_ms": round(
            maximum, 3
        ),
    }


def main():

    print("\n")
    print("=" * 70)
    print(
        "PHARMACHAIN VERIFYDRUG "
        "SCALABILITY BENCHMARK"
    )
    print("=" * 70)

    print(
        f"Drug ID             : {DRUG_ID}"
    )

    print(
        f"QR Hash             : {QR_HASH}"
    )

    print(
        f"Requests per level  : "
        f"{REQUESTS_PER_LEVEL}"
    )

    results = []

    # Warm-up requests
    print("\nPerforming warm-up...")

    for _ in range(5):
        verify_drug()

    print("Warm-up completed.")

    for concurrency in CONCURRENCY_LEVELS:

        result = run_level(
            concurrency
        )

        results.append(result)

        # Short recovery interval
        time.sleep(2)

    with open(
        "scalability_results.csv",
        "w",
        newline="",
        encoding="utf-8",
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=results[0].keys(),
        )

        writer.writeheader()
        writer.writerows(results)

    print("\n" + "=" * 70)
    print("SCALABILITY TEST COMPLETED")
    print("=" * 70)

    print(
        "Results saved to "
        "scalability_results.csv"
    )


if __name__ == "__main__":
    main()
