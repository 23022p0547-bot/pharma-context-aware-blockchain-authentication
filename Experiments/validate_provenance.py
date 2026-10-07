#!/usr/bin/env python3

import argparse
import csv
import hashlib
import json
import urllib.request


def get_json(url, timeout=60):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def sha256_join(*parts):
    """
    Must match the Go chaincode exactly:

        strings.Join(parts, "|")
        sha256.Sum256(...)
    """
    text = "|".join(str(p).strip() for p in parts)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def get_field(obj, camel, pascal):
    if not isinstance(obj, dict):
        return ""
    return obj.get(camel) or obj.get(pascal) or ""


def main():
    ap = argparse.ArgumentParser()

    ap.add_argument(
        "--products",
        default="products_1000.csv"
    )
    ap.add_argument(
        "--transfers",
        default="ownership_transfers_3000.csv"
    )
    ap.add_argument(
        "--gateway",
        default="http://localhost:3000"
    )
    ap.add_argument(
        "--limit",
        type=int,
        default=0,
        help="0 = validate all 1000 products"
    )
    ap.add_argument(
        "--results",
        default="provenance_validation.csv"
    )

    args = ap.parse_args()

    # ---------------------------------------------------------
    # Load experiment datasets
    # ---------------------------------------------------------

    with open(
        args.products,
        newline="",
        encoding="utf-8"
    ) as f:
        products = list(csv.DictReader(f))

    with open(
        args.transfers,
        newline="",
        encoding="utf-8"
    ) as f:
        transfers = list(csv.DictReader(f))

    # ---------------------------------------------------------
    # Structural dataset validation
    # ---------------------------------------------------------

    assert len(products) == 1000, (
        f"Expected 1000 products, found {len(products)}"
    )

    assert len(transfers) == 3000, (
        f"Expected 3000 transfers, found {len(transfers)}"
    )

    assert len(
        {r["drugID"] for r in products}
    ) == 1000, "Drug IDs are not unique"

    # Organize transfers by product
    transfers_by_drug = {}

    for r in transfers:
        did = r["drugID"]
        transfers_by_drug.setdefault(did, []).append(r)

    for did in transfers_by_drug:
        transfers_by_drug[did].sort(
            key=lambda x: int(x["transferStage"])
        )

    assert all(
        [
            int(x["transferStage"])
            for x in transfers_by_drug.get(
                p["drugID"], []
            )
        ] == [1, 2, 3]
        for p in products
    ), "Every drug must have stages 1, 2, 3"

    # ---------------------------------------------------------
    # Output fields
    # ---------------------------------------------------------

    fields = [
        "drugID",

        "expectedFinalOwner",
        "blockchainFinalOwner",
        "ownerMatch",

        "historyEntries",
        "historyExactly4",

        "qrHashExpected",
        "qrHashStable",

        "h0Expected",
        "h0Blockchain",
        "h0Match",

        "h1Expected",
        "h1Blockchain",
        "h1Match",

        "h2Expected",
        "h2Blockchain",
        "h2Match",

        "h3Expected",
        "h3Blockchain",
        "h3Match",

        "ownershipChainValid",
        "overallValid",

        "error"
    ]

    rows = (
        products[:args.limit]
        if args.limit
        else products
    )

    valid_count = 0

    # ---------------------------------------------------------
    # Validate every product
    # ---------------------------------------------------------

    with open(
        args.results,
        "w",
        newline="",
        encoding="utf-8"
    ) as rf:

        writer = csv.DictWriter(
            rf,
            fieldnames=fields
        )

        writer.writeheader()

        for n, product in enumerate(rows, 1):

            did = product["drugID"]

            error = ""

            expected_final_owner = ""
            blockchain_final_owner = ""

            history_entries = 0

            qr_expected = product["qrHash"].strip()
            qr_stable = False

            h0_expected = ""
            h1_expected = ""
            h2_expected = ""
            h3_expected = ""

            h0_blockchain = ""
            h1_blockchain = ""
            h2_blockchain = ""
            h3_blockchain = ""

            h0_match = False
            h1_match = False
            h2_match = False
            h3_match = False

            owner_match = False
            history_exactly_4 = False
            ownership_chain_valid = False
            overall_valid = False

            try:

                # -------------------------------------------------
                # Expected transfer path from dataset
                # -------------------------------------------------

                t = transfers_by_drug[did]

                t1 = t[0]
                t2 = t[1]
                t3 = t[2]

                initial_owner = product[
                    "initialOwner"
                ].strip()

                expected_final_owner = t3[
                    "newOwner"
                ].strip()

                # -------------------------------------------------
                # Independently reconstruct ownership hashes
                # -------------------------------------------------

                # H0:
                # SHA256(drugID | qrHash | initialOwner)

                h0_expected = sha256_join(
                    did,
                    qr_expected,
                    initial_owner
                )

                # H1:
                # SHA256(H0 | drugID |
                #        previousOwner | newOwner)

                h1_expected = sha256_join(
                    h0_expected,
                    did,
                    t1["previousOwner"],
                    t1["newOwner"]
                )

                # H2

                h2_expected = sha256_join(
                    h1_expected,
                    did,
                    t2["previousOwner"],
                    t2["newOwner"]
                )

                # H3

                h3_expected = sha256_join(
                    h2_expected,
                    did,
                    t3["previousOwner"],
                    t3["newOwner"]
                )

                # -------------------------------------------------
                # Query current Fabric state
                # -------------------------------------------------

                gateway = args.gateway.rstrip("/")

                drug = get_json(
                    f"{gateway}/drugs/{did}"
                )

                blockchain_final_owner = get_field(
                    drug,
                    "currentOwner",
                    "CurrentOwner"
                )

                owner_match = (
                    blockchain_final_owner
                    == expected_final_owner
                )

                # -------------------------------------------------
                # Retrieve Fabric history
                # -------------------------------------------------

                history = get_json(
                    f"{gateway}/drugs/{did}/history"
                )

                if (
                    isinstance(history, dict)
                    and "history" in history
                ):
                    history = history["history"]

                if not isinstance(history, list):
                    raise ValueError(
                        "History response is not a list"
                    )

                history_entries = len(history)

                history_exactly_4 = (
                    history_entries == 4
                )

                if history_entries != 4:
                    raise ValueError(
                        f"Expected exactly 4 history "
                        f"entries, found "
                        f"{history_entries}"
                    )

                # -------------------------------------------------
                # Sort history chronologically
                #
                # Current API returns newest first,
                # but sorting makes validation independent
                # of API response order.
                # -------------------------------------------------

                history_sorted = sorted(
                    history,
                    key=lambda x: x.get(
                        "timestamp", ""
                    )
                )

                history_drugs = []

                for item in history_sorted:

                    state = (
                        item.get("drug")
                        or item.get("Drug")
                    )

                    if not isinstance(state, dict):
                        raise ValueError(
                            "History entry does not "
                            "contain a drug state"
                        )

                    history_drugs.append(state)

                s0 = history_drugs[0]
                s1 = history_drugs[1]
                s2 = history_drugs[2]
                s3 = history_drugs[3]

                # -------------------------------------------------
                # Verify QR hash remained static
                # -------------------------------------------------

                qr_values = [
                    get_field(
                        state,
                        "qrHash",
                        "QRHash"
                    )
                    for state in history_drugs
                ]

                qr_stable = (
                    all(
                        q == qr_expected
                        for q in qr_values
                    )
                )

                # -------------------------------------------------
                # Read ownership hashes from blockchain
                # -------------------------------------------------

                h0_blockchain = get_field(
                    s0,
                    "ownershipHash",
                    "OwnershipHash"
                )

                h1_blockchain = get_field(
                    s1,
                    "ownershipHash",
                    "OwnershipHash"
                )

                h2_blockchain = get_field(
                    s2,
                    "ownershipHash",
                    "OwnershipHash"
                )

                h3_blockchain = get_field(
                    s3,
                    "ownershipHash",
                    "OwnershipHash"
                )

                # -------------------------------------------------
                # Compare expected vs Fabric hashes
                # -------------------------------------------------

                h0_match = (
                    h0_expected
                    == h0_blockchain
                )

                h1_match = (
                    h1_expected
                    == h1_blockchain
                )

                h2_match = (
                    h2_expected
                    == h2_blockchain
                )

                h3_match = (
                    h3_expected
                    == h3_blockchain
                )

                ownership_chain_valid = all([
                    h0_match,
                    h1_match,
                    h2_match,
                    h3_match
                ])

                # -------------------------------------------------
                # Complete provenance validation
                # -------------------------------------------------

                overall_valid = all([
                    owner_match,
                    history_exactly_4,
                    qr_stable,
                    ownership_chain_valid
                ])

                if overall_valid:
                    valid_count += 1

            except Exception as e:
                error = str(e)

            # -----------------------------------------------------
            # Write detailed evidence
            # -----------------------------------------------------

            writer.writerow({
                "drugID":
                    did,

                "expectedFinalOwner":
                    expected_final_owner,

                "blockchainFinalOwner":
                    blockchain_final_owner,

                "ownerMatch":
                    owner_match,

                "historyEntries":
                    history_entries,

                "historyExactly4":
                    history_exactly_4,

                "qrHashExpected":
                    qr_expected,

                "qrHashStable":
                    qr_stable,

                "h0Expected":
                    h0_expected,

                "h0Blockchain":
                    h0_blockchain,

                "h0Match":
                    h0_match,

                "h1Expected":
                    h1_expected,

                "h1Blockchain":
                    h1_blockchain,

                "h1Match":
                    h1_match,

                "h2Expected":
                    h2_expected,

                "h2Blockchain":
                    h2_blockchain,

                "h2Match":
                    h2_match,

                "h3Expected":
                    h3_expected,

                "h3Blockchain":
                    h3_blockchain,

                "h3Match":
                    h3_match,

                "ownershipChainValid":
                    ownership_chain_valid,

                "overallValid":
                    overall_valid,

                "error":
                    error
            })

            print(
                f"[{n}/{len(rows)}] "
                f"{did} "
                f"owner={owner_match} "
                f"history={history_entries} "
                f"QR={qr_stable} "
                f"H0={h0_match} "
                f"H1={h1_match} "
                f"H2={h2_match} "
                f"H3={h3_match} "
                f"chain={ownership_chain_valid} "
                f"overall={overall_valid}"
            )

    # ---------------------------------------------------------
    # Final summary
    # ---------------------------------------------------------

    total = len(rows)

    percentage = (
        valid_count / total * 100
        if total
        else 0
    )

    print()
    print("=" * 72)
    print("CRYPTOGRAPHIC PROVENANCE VALIDATION SUMMARY")
    print("=" * 72)

    print(
        f"Complete valid provenance chains: "
        f"{valid_count}/{total} "
        f"({percentage:.2f}%)"
    )

    print(
        f"Results written to "
        f"{args.results}"
    )


if __name__ == "__main__":
    main()