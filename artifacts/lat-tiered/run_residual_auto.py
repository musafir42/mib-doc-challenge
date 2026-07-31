#!/usr/bin/env python3
"""Residual n=100 with MIB_OCR_TIER=auto (lat-tiered)."""
import json
import os
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

os.environ["OMP_THREAD_LIMIT"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ.setdefault("MIB_OCR_TIER", "auto")

from mib_solution.pipeline import predict_pdf, write_jsonl

ROOT = Path(__file__).resolve().parents[2]


def one(cid: str):
    os.environ["OMP_THREAD_LIMIT"] = "1"
    os.environ["OMP_NUM_THREADS"] = "1"
    os.environ["MIB_OCR_TIER"] = os.environ.get("MIB_OCR_TIER", "auto")
    t0 = time.perf_counter()
    pred = predict_pdf(ROOT / "data/train" / f"{cid}.pdf")
    dt = time.perf_counter() - t0
    return pred, dt, pred.get("_ocr_tier"), pred.get("_ocr_used")


def main() -> None:
    residual = json.loads((ROOT / "artifacts/residual.json").read_text())
    out = ROOT / "artifacts" / "lat-tiered"
    out.mkdir(parents=True, exist_ok=True)
    workers = int(os.environ.get("MIB_WORKERS", "2"))
    tier = os.environ.get("MIB_OCR_TIER", "auto")
    ids = residual["case_ids"]
    tag = tier

    t0 = time.perf_counter()
    preds: list = []
    tiers: list = []
    times: list = []
    done = 0
    with ProcessPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(one, c): c for c in ids}
        for f in as_completed(futs):
            pred, dt, t, ocr = f.result()
            preds.append(pred)
            tiers.append(t)
            times.append(dt)
            done += 1
            if done % 5 == 0 or done == len(ids):
                print(
                    f"  {done}/{len(ids)} last={pred.get('case_id')} tier={t} {dt:.1f}s",
                    flush=True,
                )
    wall = time.perf_counter() - t0
    pred_path = out / f"predictions_{tag}.jsonl"
    write_jsonl(pred_path, preds)
    tc = Counter(tiers)
    times_s = sorted(times)
    meta = {
        "run": f"lat-tiered-{tag}",
        "MIB_OCR_TIER": tag,
        "n": len(preds),
        "workers": workers,
        "OMP_THREAD_LIMIT": 1,
        "wall_s": round(wall, 2),
        "avg_s": round(sum(times) / len(times), 3),
        "p50_s": round(times_s[len(times_s) // 2], 3),
        "p95_s": round(times_s[int(len(times_s) * 0.95)], 3),
        "tier_counts": dict(tc),
        "pct_heavy": round(100.0 * tc.get("heavy", 0) / len(preds), 1),
        "pct_light": round(100.0 * tc.get("light", 0) / len(preds), 1),
        "pct_none": round(100.0 * tc.get("none", 0) / len(preds), 1),
    }
    (out / f"meta_{tag}.json").write_text(json.dumps(meta, indent=2))
    print(json.dumps(meta, indent=2), flush=True)
    print("DONE", len(preds), "→", pred_path, flush=True)


if __name__ == "__main__":
    main()
