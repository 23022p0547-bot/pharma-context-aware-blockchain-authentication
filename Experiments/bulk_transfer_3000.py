#!/usr/bin/env python3
import argparse, csv, json, time, urllib.request, urllib.error
from datetime import datetime, timezone

def request_json(url, method="GET", payload=None, timeout=90):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, headers={"Content-Type":"application/json"}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read().decode("utf-8")
            return r.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        try: parsed = json.loads(body)
        except Exception: parsed = {"message": body}
        return e.code, parsed

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default="ownership_transfers_3000.csv")
    ap.add_argument("--gateway", default="http://localhost:3000")
    ap.add_argument("--limit", type=int, default=0, help="0 = all; use 15 for pilot (5 products x 3 stages)")
    ap.add_argument("--results", default="transfer_results.csv")
    args = ap.parse_args()

    with open(args.csv, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    rows.sort(key=lambda r: (r["drugID"], int(r["transferStage"])))
    if args.limit: rows = rows[:args.limit]

    fields = ["sequence","transferID","drugID","stage","previousOwner","expectedNewOwner","blockchainOwner",
              "operation","startedUTC","endedUTC","latencyMs","httpStatus","success","ownerMatch","message"]
    with open(args.results, "w", newline="", encoding="utf-8") as rf:
        w = csv.DictWriter(rf, fieldnames=fields); w.writeheader()
        for n,row in enumerate(rows,1):
            url = f"{args.gateway.rstrip('/')}/drugs/{row['drugID']}/transfer"
            start_iso = datetime.now(timezone.utc).isoformat(); t0=time.perf_counter()
            try:
                status, body = request_json(url, "POST", {"newOwner": row["newOwner"]})
                drug = body.get("drug") if isinstance(body,dict) else {}
                owner = (drug or {}).get("currentOwner") or (drug or {}).get("CurrentOwner") or ""
                ok = status == 200 and bool(body.get("success", True))
                owner_match = ok and owner == row["newOwner"]
                msg = body.get("message") or body.get("error") or ""
            except Exception as e:
                status, ok, owner_match, owner, msg = 0, False, False, "", str(e)
            latency=(time.perf_counter()-t0)*1000; end_iso=datetime.now(timezone.utc).isoformat()
            w.writerow({"sequence":n,"transferID":row["transferID"],"drugID":row["drugID"],"stage":row["transferStage"],
                        "previousOwner":row["previousOwner"],"expectedNewOwner":row["newOwner"],"blockchainOwner":owner,
                        "operation":"TransferOwnership","startedUTC":start_iso,"endedUTC":end_iso,
                        "latencyMs":f"{latency:.3f}","httpStatus":status,"success":ok,
                        "ownerMatch":owner_match,"message":msg})
            rf.flush()
            print(f"[{n}/{len(rows)}] {row['drugID']} stage={row['transferStage']} status={status} ownerMatch={owner_match} latency={latency:.1f} ms")
            if not ok:
                print("STOP: transfer failed. Fix the issue before continuing to preserve chain order.")
                break
    print(f"Results written to {args.results}")

if __name__ == "__main__":
    main()
