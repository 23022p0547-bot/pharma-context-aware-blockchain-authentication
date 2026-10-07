#!/usr/bin/env python3
import argparse, csv, json, urllib.request

def get_json(url, timeout=60):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--products", default="products_1000.csv")
    ap.add_argument("--transfers", default="ownership_transfers_3000.csv")
    ap.add_argument("--gateway", default="http://localhost:3000")
    ap.add_argument("--limit", type=int, default=0, help="0 = validate all 1000 final owners")
    ap.add_argument("--results", default="provenance_validation.csv")
    args=ap.parse_args()

    with open(args.products,newline="",encoding="utf-8") as f: products=list(csv.DictReader(f))
    with open(args.transfers,newline="",encoding="utf-8") as f: transfers=list(csv.DictReader(f))
    final_owner={}
    stages={}
    for r in transfers:
        did=r["drugID"]; stages.setdefault(did,[]).append(int(r["transferStage"]))
        if int(r["transferStage"])==3: final_owner[did]=r["newOwner"]

    assert len(products)==1000, f"Expected 1000 products, found {len(products)}"
    assert len(transfers)==3000, f"Expected 3000 transfers, found {len(transfers)}"
    assert len({r["drugID"] for r in products})==1000, "Drug IDs are not unique"
    assert all(sorted(stages.get(r["drugID"],[]))==[1,2,3] for r in products), "Every drug must have stages 1,2,3"

    rows=products[:args.limit] if args.limit else products
    fields=["drugID","expectedFinalOwner","blockchainOwner","ownerMatch","historyEntries","historyAtLeast4","error"]
    ok_count=0
    with open(args.results,"w",newline="",encoding="utf-8") as rf:
        w=csv.DictWriter(rf,fieldnames=fields); w.writeheader()
        for n,p in enumerate(rows,1):
            did=p["drugID"]; err=""; owner=""; hcount=0
            try:
                drug=get_json(f"{args.gateway.rstrip('/')}/drugs/{did}")
                owner=drug.get("currentOwner") or drug.get("CurrentOwner") or ""
                hist=get_json(f"{args.gateway.rstrip('/')}/drugs/{did}/history")
                if isinstance(hist,dict) and "history" in hist: hist=hist["history"]
                hcount=len(hist) if isinstance(hist,list) else 0
            except Exception as e: err=str(e)
            match=(owner==final_owner[did]); hist_ok=hcount>=4
            if match and hist_ok: ok_count+=1
            w.writerow({"drugID":did,"expectedFinalOwner":final_owner[did],"blockchainOwner":owner,
                        "ownerMatch":match,"historyEntries":hcount,"historyAtLeast4":hist_ok,"error":err})
            print(f"[{n}/{len(rows)}] {did} ownerMatch={match} history={hcount}")
    print(f"Complete provenance validations: {ok_count}/{len(rows)} ({ok_count/len(rows)*100:.2f}%)")
    print(f"Results written to {args.results}")

if __name__=="__main__":
    main()
