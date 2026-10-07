import csv
import time
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests


BASE_URL = "http://localhost:3000"

DRUG_ID = "D001"
QR_HASH = "QRHASH001"

CONCURRENCY_LEVELS = [1, 5, 10, 20, 50, 75, 100]

REQUESTS_PER_RUN = 100
RUNS_PER_LEVEL = 3


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


def run_once(concurrency, run_number):

    print("\n" + "=" * 78)

    print(
        f"Concurrency={concurrency} "
        f"| Run={run_number}/{RUNS_PER_LEVEL}"
    )

    print("=" * 78)

    latencies = []
    successful = 0

    start_batch = time.perf_counter()

    with ThreadPoolExecutor(
        max_workers=concurrency
    ) as executor:

        futures = [
            executor.submit(verify_drug)
            for _ in range(
                REQUESTS_PER_RUN
            )
        ]

        for future in as_completed(futures):

            latency, success = (
                future.result()
            )

            latencies.append(latency)

            if success:
                successful += 1

    total_time = (
        time.perf_counter()
        - start_batch
    )

    failed = (
        REQUESTS_PER_RUN
        - successful
    )

    success_rate = (
        successful
        / REQUESTS_PER_RUN
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

    p99_latency = percentile(
        latencies,
        99,
    )

    minimum_latency = min(latencies)
    maximum_latency = max(latencies)

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
        f"P99 Latency     : "
        f"{p99_latency:.3f} ms"
    )

    return {
        "concurrency": concurrency,
        "run": run_number,
        "requests": REQUESTS_PER_RUN,
        "successful": successful,
        "failed": failed,
        "success_rate_percent": round(
            success_rate,
            2,
        ),
        "total_time_seconds": round(
            total_time,
            3,
        ),
        "throughput_requests_per_second":
            round(
                throughput,
                3,
            ),
        "mean_latency_ms": round(
            mean_latency,
            3,
        ),
        "median_latency_ms": round(
            median_latency,
            3,
        ),
        "p95_latency_ms": round(
            p95_latency,
            3,
        ),
        "p99_latency_ms": round(
            p99_latency,
            3,
        ),
        "minimum_latency_ms": round(
            minimum_latency,
            3,
        ),
        "maximum_latency_ms": round(
            maximum_latency,
            3,
        ),
    }


def aggregate_results(all_results):

    summary = []

    for concurrency in CONCURRENCY_LEVELS:

        rows = [
            r
            for r in all_results
            if r["concurrency"]
            == concurrency
        ]

        success_rates = [
            r["success_rate_percent"]
            for r in rows
        ]

        throughputs = [
            r[
                "throughput_requests_per_second"
            ]
            for r in rows
        ]

        means = [
            r["mean_latency_ms"]
            for r in rows
        ]

        medians = [
            r["median_latency_ms"]
            for r in rows
        ]

        p95s = [
            r["p95_latency_ms"]
            for r in rows
        ]

        p99s = [
            r["p99_latency_ms"]
            for r in rows
        ]

        summary.append({
            "concurrency":
                concurrency,

            "runs":
                RUNS_PER_LEVEL,

            "total_requests":
                REQUESTS_PER_RUN
                * RUNS_PER_LEVEL,

            "mean_success_rate_percent":
                round(
                    statistics.mean(
                        success_rates
                    ),
                    2,
                ),

            "mean_throughput_req_per_sec":
                round(
                    statistics.mean(
                        throughputs
                    ),
                    3,
                ),

            "throughput_std_dev":
                round(
                    statistics.stdev(
                        throughputs
                    )
                    if len(
                        throughputs
                    ) > 1
                    else 0,
                    3,
                ),

            "mean_latency_ms":
                round(
                    statistics.mean(
                        means
                    ),
                    3,
                ),

            "mean_median_latency_ms":
                round(
                    statistics.mean(
                        medians
                    ),
                    3,
                ),

            "mean_p95_latency_ms":
                round(
                    statistics.mean(
                        p95s
                    ),
                    3,
                ),

            "mean_p99_latency_ms":
                round(
                    statistics.mean(
                        p99s
                    ),
                    3,
                ),
        })

    return summary


def main():

    print("\n" + "=" * 78)

    print(
        "PHARMACHAIN EXTENDED "
        "VERIFYDRUG SCALABILITY BENCHMARK"
    )

    print("=" * 78)

    print(
        f"Drug ID            : {DRUG_ID}"
    )

    print(
        f"QR Hash            : {QR_HASH}"
    )

    print(
        f"Concurrency levels : "
        f"{CONCURRENCY_LEVELS}"
    )

    print(
        f"Requests per run   : "
        f"{REQUESTS_PER_RUN}"
    )

    print(
        f"Runs per level     : "
        f"{RUNS_PER_LEVEL}"
    )

    total_requests = (
        len(CONCURRENCY_LEVELS)
        * REQUESTS_PER_RUN
        * RUNS_PER_LEVEL
    )

    print(
        f"Total requests     : "
        f"{total_requests}"
    )

    print("\nPerforming warm-up...")

    for _ in range(10):
        verify_drug()

    print("Warm-up completed.")

    all_results = []

    for concurrency in (
        CONCURRENCY_LEVELS
    ):

        for run_number in range(
            1,
            RUNS_PER_LEVEL + 1,
        ):

            result = run_once(
                concurrency,
                run_number,
            )

            all_results.append(
                result
            )

            # Recovery interval
            time.sleep(2)

        # Additional recovery before
        # moving to next concurrency level
        time.sleep(3)

    # --------------------------------------------------------
    # Save all 21 individual runs
    # --------------------------------------------------------

    with open(
        "scalability_extended_runs.csv",
        "w",
        newline="",
        encoding="utf-8",
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=(
                all_results[0].keys()
            ),
        )

        writer.writeheader()
        writer.writerows(
            all_results
        )

    # --------------------------------------------------------
    # Aggregate the three runs
    # --------------------------------------------------------

    summary = aggregate_results(
        all_results
    )

    with open(
        "scalability_extended_summary.csv",
        "w",
        newline="",
        encoding="utf-8",
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=(
                summary[0].keys()
            ),
        )

        writer.writeheader()
        writer.writerows(summary)

    # --------------------------------------------------------
    # Print summary
    # --------------------------------------------------------

    print("\n" + "=" * 108)

    print(
        "AGGREGATED EXTENDED "
        "SCALABILITY RESULTS"
    )

    print("=" * 108)

    print(
        f"{'Conc.':>6}"
        f"{'Success':>11}"
        f"{'Throughput':>14}"
        f"{'Mean':>12}"
        f"{'Median':>12}"
        f"{'P95':>12}"
        f"{'P99':>12}"
    )

    print("-" * 108)

    for row in summary:

        print(
            f"{row['concurrency']:>6}"
            f"{row['mean_success_rate_percent']:>10.2f}%"
            f"{row['mean_throughput_req_per_sec']:>14.2f}"
            f"{row['mean_latency_ms']:>12.2f}"
            f"{row['mean_median_latency_ms']:>12.2f}"
            f"{row['mean_p95_latency_ms']:>12.2f}"
            f"{row['mean_p99_latency_ms']:>12.2f}"
        )

    print("=" * 108)

    print(
        "\nDetailed runs saved to:"
        "\nscalability_extended_runs.csv"
    )

    print(
        "\nAggregated results saved to:"
        "\nscalability_extended_summary.csv"
    )


if __name__ == "__main__":
    main()
