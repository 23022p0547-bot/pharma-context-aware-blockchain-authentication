import csv
import statistics
import time

import requests


CLOUDFLARE_URL = input(
    "Enter current Cloudflare URL: "
).strip().rstrip("/")

DRUG_ID = "D001"
QR_HASH = "QRHASH001"

TRIALS = 20

url = (
    f"{CLOUDFLARE_URL}"
    f"/verify-qr/{DRUG_ID}/{QR_HASH}"
)

latencies = []

print("\nEnd-to-End Cross-Network Verification")
print("=" * 60)
print("URL:", url)
print("=" * 60)

for trial in range(1, TRIALS + 1):

    try:
        start = time.perf_counter()

        response = requests.get(
            url,
            timeout=30,
        )

        end = time.perf_counter()

        latency_ms = (
            end - start
        ) * 1000

        print(
            f"Trial {trial:02d}: "
            f"{latency_ms:.2f} ms "
            f"HTTP {response.status_code}"
        )

        if response.status_code == 200:
            latencies.append(latency_ms)

    except requests.RequestException as error:
        print(
            f"Trial {trial:02d}: FAILED - {error}"
        )


if latencies:

    minimum = min(latencies)
    maximum = max(latencies)
    mean = statistics.mean(latencies)
    median = statistics.median(latencies)

    std_dev = (
        statistics.stdev(latencies)
        if len(latencies) > 1
        else 0
    )

    print("\n" + "=" * 60)
    print("END-TO-END RESULTS")
    print("=" * 60)

    print("Successful trials :", len(latencies))
    print(f"Minimum           : {minimum:.3f} ms")
    print(f"Maximum           : {maximum:.3f} ms")
    print(f"Mean              : {mean:.3f} ms")
    print(f"Median            : {median:.3f} ms")
    print(f"Std. Deviation    : {std_dev:.3f} ms")

    with open(
        "e2e_cross_network_results.csv",
        "w",
        newline="",
    ) as file:

        writer = csv.writer(file)

        writer.writerow([
            "trial",
            "latency_ms",
        ])

        for trial, latency in enumerate(
            latencies,
            start=1,
        ):
            writer.writerow([
                trial,
                round(latency, 3),
            ])

    print(
        "\nResults saved to "
        "e2e_cross_network_results.csv"
    )

else:

    print(
        "\nNo successful measurements were recorded."
    )
