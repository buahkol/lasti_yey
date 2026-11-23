"""Simulate the ESP32-S3 against the real API using a folder or manifest of JPEGs.

Uses the same HTTP calls as the firmware: one POST /inspections per can, and
POST /production/outputs every 10 cans or 30 s plus a final flush. Prints a
tally to compare with the dashboard (K6) and the per-can round-trip time (K4).
Also the demo backup if the device or Wi-Fi fails.

uv run python tools/fake_device.py --server http://endeavour:8000 --batch B-2311-01 \
    --manifest dataset/manifests/DEMO-CAN.csv --split test --limit 40
uv run python tools/fake_device.py --batch B-2311-01 --dir some/folder --interval 1.5
"""

from __future__ import annotations

import argparse
import csv
import random
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

WIB = timezone(timedelta(hours=7))


def load_items(a) -> list[tuple[Path, str]]:
    if a.manifest:
        with open(a.manifest, newline="") as f:
            rows = [r for r in csv.DictReader(f) if not a.split or r["split"] == a.split]
        items = [(Path(r["path"]), r["label"]) for r in rows]
    else:
        items = [(p, "?") for p in sorted(Path(a.dir).glob("*")) if p.suffix.lower() in {".jpg", ".jpeg", ".png"}]
    if a.shuffle:
        random.Random(a.seed).shuffle(items)
    return items[: a.limit] if a.limit else items


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--server", default="http://localhost:8000")
    ap.add_argument("--key", default="simonpro-dev-key-01")
    ap.add_argument("--batch", required=True)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--manifest")
    src.add_argument("--dir")
    ap.add_argument("--split", default="test")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--shuffle", action="store_true")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--interval", type=float, default=0.5, help="seconds between cans")
    a = ap.parse_args()

    base = a.server.rstrip("/") + "/api/v1"
    headers = {"X-Device-Key": a.key}
    items = load_items(a)
    pending, last_flush = 0, time.monotonic()
    tally = {"sent": 0, "OK": 0, "NG": 0, "error": 0, "tp": 0, "fn": 0, "tn": 0, "fp": 0}
    rtts = []

    def flush(client: httpx.Client) -> None:
        nonlocal pending, last_flush
        if pending == 0:
            return
        r = client.post(f"{base}/production/outputs", headers=headers, json={
            "batchCode": a.batch, "quantity": pending, "timestamp": datetime.now(WIB).isoformat()})
        if r.status_code == 201:
            print(f"  outputs +{pending} -> totalOutput={r.json()['totalOutput']}")
            pending, last_flush = 0, time.monotonic()
        else:
            print(f"  outputs failed {r.status_code}: {r.text} (kept {pending} for retry)")

    with httpx.Client(timeout=5.0) as client:
        for i, (path, label) in enumerate(items, 1):
            pending += 1
            t0 = time.perf_counter()
            try:
                r = client.post(f"{base}/inspections", headers=headers,
                                data={"batchCode": a.batch, "timestamp": datetime.now(WIB).isoformat()},
                                files={"image": (path.name, path.read_bytes(), "image/jpeg")})
            except httpx.HTTPError as exc:
                tally["error"] += 1
                print(f"[{i}] {path.name}: network error {exc}")
                continue
            rtt = (time.perf_counter() - t0) * 1000
            rtts.append(rtt)
            tally["sent"] += 1
            if r.status_code != 201:
                tally["error"] += 1
                print(f"[{i}] {path.name}: HTTP {r.status_code} {r.text}")
            else:
                b = r.json()
                tally[b["result"]] += 1
                if label in ("ok", "ng"):
                    key = {("ng", "NG"): "tp", ("ng", "OK"): "fn", ("ok", "OK"): "tn", ("ok", "NG"): "fp"}
                    tally[key[(label, b["result"])]] += 1
                led = "LED MERAH" if b["reject"] else ""
                print(f"[{i}] {path.name} ({label}) -> {b['result']} score={b['anomalyScore']:.3f} "
                      f"thr={b['threshold']:.3f} {rtt:.0f} ms {led}")
            if pending >= 10 or time.monotonic() - last_flush >= 30:
                flush(client)
            time.sleep(a.interval)
        flush(client)

    print("\nRingkasan:", {k: v for k, v in tally.items() if v})
    if rtts:
        rtts.sort()
        print(f"Round-trip ms: p50={rtts[len(rtts) // 2]:.0f} p95={rtts[int(len(rtts) * 0.95) - 1]:.0f} "
              f"max={rtts[-1]:.0f}")


if __name__ == "__main__":
    main()
