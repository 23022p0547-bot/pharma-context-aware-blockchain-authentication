#!/usr/bin/env python3
import argparse, csv, json, time, urllib.request, urllib.error
from datetime import datetime, timezone

def post_json(url, payload, timeout=90):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type":"application/json"}, method="POST")
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
    ap.add_argument("--csv", default="products_1000.csv")
    ap.add_argument("--gateway", default="http://localhost:3000")
    ap.add_argument("--limit", type=int, default=0, help="0 = all rows; use 10 for pilot")
    ap.add_argument("--results", default="registration_results.csv")
    args = ap.parse_args()

    with open(args.csv, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if args.limit: rows = rows[:args.limit]

    fields = ["sequence","drugID","operation","startedUTC","endedUTC","latencyMs","httpStatus","success","message"]
    with open(args.results, "w", newline="", encoding="utf-8") as rf:
        w = csv.DictWriter(rf, fieldnames=fields); w.writeheader()
        for n,row in enumerate(rows,1):
            payload = {k: row[k] for k in ["drugID","drugName","manufacturer","batchNumber","manufactureDate","expiryDate","qrHash"]}
            start_iso = datetime.now(timezone.utc).isoformat()
            t0 = time.perf_counter()
            try:
                status, body = post_json(args.gateway.rstrip("/") + "/drugs", payload)
                ok = status == 201 and bool(body.get("success", True))
                msg = body.get("message") or body.get("error") or ""
            except Exception as e:
                status, ok, msg = 0, False, str(e)
            latency = (time.perf_counter()-t0)*1000
            end_iso = datetime.now(timezone.utc).isoformat()
            w.writerow({"sequence":n,"drugID":row["drugID"],"operation":"RegisterDrug","startedUTC":start_iso,
                        "endedUTC":end_iso,"latencyMs":f"{latency:.3f}","httpStatus":status,
                        "success":ok,"message":msg})
            rf.flush()
            print(f"[{n}/{len(rows)}] {row['drugID']} status={status} success={ok} latency={latency:.1f} ms")
    print(f"Results written to {args.results}")

if __name__ == "__main__":
    main()
