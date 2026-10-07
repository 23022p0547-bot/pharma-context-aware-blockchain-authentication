import os
import pandas as pd
import matplotlib.pyplot as plt

# ============================================================
# CONFIGURATION
# ============================================================

REG_FILE = "registration_results.csv"
TRANSFER_FILE = "transfer_results.csv"
PROV_FILE = "provenance_validation.csv"

OUTPUT_DIR = "publication_results"
os.makedirs(OUTPUT_DIR, exist_ok=True)

plt.rcParams.update({
    "font.family": "serif",
    "font.size": 10,
    "axes.titlesize": 11,
    "axes.labelsize": 10,
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
    "figure.dpi": 150
})


# ============================================================
# LOAD DATA
# ============================================================

reg = pd.read_csv(REG_FILE)
trans = pd.read_csv(TRANSFER_FILE)
prov = pd.read_csv(PROV_FILE)

print("\nDATASET SIZES")
print("=" * 60)
print("Registrations :", len(reg))
print("Transfers     :", len(trans))
print("Provenance    :", len(prov))


# ============================================================
# DESCRIPTIVE STATISTICS
# ============================================================

def latency_stats(series):
    return {
        "N": len(series),
        "Mean_ms": series.mean(),
        "Median_ms": series.median(),
        "Std_ms": series.std(),
        "Min_ms": series.min(),
        "Max_ms": series.max(),
        "P95_ms": series.quantile(0.95),
        "P99_ms": series.quantile(0.99),
        "CV_percent": (series.std() / series.mean()) * 100
    }


stats = pd.DataFrame({
    "Registration": latency_stats(reg["latencyMs"]),
    "Ownership Transfer": latency_stats(trans["latencyMs"]),
}).T

print("\nLATENCY STATISTICS")
print("=" * 60)
print(stats.round(3))

stats.round(3).to_csv(
    os.path.join(OUTPUT_DIR, "latency_statistics.csv")
)


# ============================================================
# SUCCESS RATES
# ============================================================

reg_success = reg["success"].astype(str).str.lower().eq("true").sum()
trans_success = trans["success"].astype(str).str.lower().eq("true").sum()

success_table = pd.DataFrame({
    "Operation": [
        "Product Registration",
        "Ownership Transfer",
        "All Lifecycle Operations"
    ],
    "Total": [
        len(reg),
        len(trans),
        len(reg) + len(trans)
    ],
    "Successful": [
        reg_success,
        trans_success,
        reg_success + trans_success
    ]
})

success_table["SuccessRate_percent"] = (
    success_table["Successful"]
    / success_table["Total"] * 100
)

print("\nSUCCESS RATES")
print("=" * 60)
print(success_table)

success_table.to_csv(
    os.path.join(OUTPUT_DIR, "success_rates.csv"),
    index=False
)


# ============================================================
# IQR OUTLIER ANALYSIS
# ============================================================

def outlier_analysis(series, name):

    q1 = series.quantile(0.25)
    q3 = series.quantile(0.75)

    iqr = q3 - q1

    lower = q1 - 1.5 * iqr
    upper = q3 + 1.5 * iqr

    mask = (
        (series < lower) |
        (series > upper)
    )

    return {
        "Operation": name,
        "N": len(series),
        "Q1_ms": q1,
        "Q3_ms": q3,
        "IQR_ms": iqr,
        "LowerBound_ms": lower,
        "UpperBound_ms": upper,
        "Outliers": mask.sum(),
        "Outlier_percent": mask.mean() * 100
    }


outlier_table = pd.DataFrame([
    outlier_analysis(
        reg["latencyMs"],
        "Product Registration"
    ),
    outlier_analysis(
        trans["latencyMs"],
        "Ownership Transfer"
    )
])

print("\nIQR OUTLIER ANALYSIS")
print("=" * 60)
print(outlier_table.round(3))

outlier_table.round(3).to_csv(
    os.path.join(OUTPUT_DIR, "outlier_analysis.csv"),
    index=False
)


# ============================================================
# STAGE-WISE TRANSFER STATISTICS
# ============================================================

stage_names = {
    1: "Manufacturer → Distributor",
    2: "Distributor → Wholesaler",
    3: "Wholesaler → Retail Outlet"
}

stage_rows = []

for stage in sorted(trans["stage"].unique()):

    data = trans.loc[
        trans["stage"] == stage,
        "latencyMs"
    ]

    row = latency_stats(data)
    row["Stage"] = stage_names.get(
        stage,
        f"Stage {stage}"
    )

    stage_rows.append(row)


stage_stats = pd.DataFrame(stage_rows)

columns = [
    "Stage",
    "N",
    "Mean_ms",
    "Median_ms",
    "Std_ms",
    "Min_ms",
    "Max_ms",
    "P95_ms",
    "P99_ms",
    "CV_percent"
]

stage_stats = stage_stats[columns]

print("\nSTAGE-WISE TRANSFER STATISTICS")
print("=" * 60)
print(stage_stats.round(3))

stage_stats.round(3).to_csv(
    os.path.join(
        OUTPUT_DIR,
        "stage_wise_transfer_statistics.csv"
    ),
    index=False
)


# ============================================================
# PROVENANCE VALIDATION
# ============================================================

validation_fields = {
    "ownerMatch": "Final owner consistency",
    "historyExactly4": "History completeness",
    "qrHashStable": "QR-hash stability",
    "h0Match": "H0 consistency",
    "h1Match": "H1 consistency",
    "h2Match": "H2 consistency",
    "h3Match": "H3 consistency",
    "ownershipChainValid": "Complete ownership chain",
    "overallValid": "Overall provenance"
}


validation_rows = []

for column, description in validation_fields.items():

    values = (
        prov[column]
        .astype(str)
        .str.lower()
        .eq("true")
    )

    passed = values.sum()
    total = len(values)

    validation_rows.append({
        "ValidationCriterion": description,
        "Passed": passed,
        "Total": total,
        "Rate_percent": passed / total * 100
    })


validation_table = pd.DataFrame(validation_rows)

print("\nCRYPTOGRAPHIC PROVENANCE VALIDATION")
print("=" * 60)
print(validation_table)

validation_table.to_csv(
    os.path.join(
        OUTPUT_DIR,
        "provenance_validation_summary.csv"
    ),
    index=False
)


# ============================================================
# FIGURE 1 — TRANSACTION LATENCY DISTRIBUTION
# ============================================================

fig, ax = plt.subplots(figsize=(6.5, 4.5))

ax.boxplot(
    [
        reg["latencyMs"],
        trans["latencyMs"]
    ],
    tick_labels=[
        "Product Registration\n(n=1,000)",
        "Ownership Transfer\n(n=3,000)"
    ],
    showmeans=True,
    showfliers=True
)

ax.set_ylabel("Transaction latency (ms)")
ax.set_title("Transaction Latency Distribution")

ax.grid(
    axis="y",
    linestyle="--",
    linewidth=0.5,
    alpha=0.6
)

fig.tight_layout()

fig.savefig(
    os.path.join(
        OUTPUT_DIR,
        "Figure_1_Transaction_Latency.png"
    ),
    dpi=600,
    bbox_inches="tight"
)

fig.savefig(
    os.path.join(
        OUTPUT_DIR,
        "Figure_1_Transaction_Latency.pdf"
    ),
    bbox_inches="tight"
)

plt.close(fig)


# ============================================================
# FIGURE 2 — STAGE-WISE TRANSFER LATENCY
# ============================================================

stage_data = [
    trans.loc[
        trans["stage"] == 1,
        "latencyMs"
    ],
    trans.loc[
        trans["stage"] == 2,
        "latencyMs"
    ],
    trans.loc[
        trans["stage"] == 3,
        "latencyMs"
    ]
]

fig, ax = plt.subplots(figsize=(7.5, 4.8))

ax.boxplot(
    stage_data,
    tick_labels=[
        "Manufacturer →\nDistributor",
        "Distributor →\nWholesaler",
        "Wholesaler →\nRetail Outlet"
    ],
    showmeans=True,
    showfliers=True
)

ax.set_ylabel("Transaction latency (ms)")
ax.set_title(
    "Stage-Wise Ownership Transfer Latency"
)

ax.grid(
    axis="y",
    linestyle="--",
    linewidth=0.5,
    alpha=0.6
)

fig.tight_layout()

fig.savefig(
    os.path.join(
        OUTPUT_DIR,
        "Figure_2_Stage_Wise_Transfer_Latency.png"
    ),
    dpi=600,
    bbox_inches="tight"
)

fig.savefig(
    os.path.join(
        OUTPUT_DIR,
        "Figure_2_Stage_Wise_Transfer_Latency.pdf"
    ),
    bbox_inches="tight"
)

plt.close(fig)


# ============================================================
# FIGURE 3 — PROVENANCE VALIDATION
# ============================================================

fig, ax = plt.subplots(figsize=(8, 5.2))

bars = ax.barh(
    validation_table["ValidationCriterion"],
    validation_table["Rate_percent"]
)

ax.set_xlabel("Validation rate (%)")
ax.set_xlim(0, 105)

ax.set_title(
    "Cryptographic Provenance Validation"
)

ax.grid(
    axis="x",
    linestyle="--",
    linewidth=0.5,
    alpha=0.6
)

for bar, row in zip(
    bars,
    validation_table.itertuples()
):

    ax.text(
        row.Rate_percent + 0.5,
        bar.get_y() + bar.get_height() / 2,
        f"{row.Rate_percent:.1f}% "
        f"({row.Passed}/{row.Total})",
        va="center",
        fontsize=8
    )

ax.invert_yaxis()

fig.tight_layout()

fig.savefig(
    os.path.join(
        OUTPUT_DIR,
        "Figure_3_Provenance_Validation.png"
    ),
    dpi=600,
    bbox_inches="tight"
)

fig.savefig(
    os.path.join(
        OUTPUT_DIR,
        "Figure_3_Provenance_Validation.pdf"
    ),
    bbox_inches="tight"
)

plt.close(fig)


print("\n" + "=" * 60)
print("ANALYSIS COMPLETED SUCCESSFULLY")
print("=" * 60)
print("Results saved in:", OUTPUT_DIR)
