#!/usr/bin/env python3
"""Residual farm for lat-psm-lite (MIB_WORKERS=2, OMP=1)."""
from __future__ import annotations

import json
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from mib_solution.pipeline import predict_pdf, write_jsonl

REPO = Path("/root/dev-workspace/mib-doc-challenge")
WT = Path("/root/dev-workspace/mib-doc-challenge/worktrees/lat-psm-lite")
OUT = WT / "artifacts" / "lat-psm-lite"


def one(cid: str):
    t0 = time.perf_counter()
    pred = predict_pdf(REPO / "data/train" / f"{cid}.pdf")
    return cid, pred, time.perf_counter() - t0


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    residual = json.loads((REPO / "artifacts/residual.json").read_text())
    workers = int(os.environ.get("MIB_WORKERS", "2"))
    ids = residual["case_ids"]
    log_path = OUT / "run.log"

    def logp(msg: str) -> None:
        print(msg, flush=True)
        with log_path.open("a") as log:
            log.write(msg + "\n")

    log_path.write_text("")
    logp(
        f"lat-psm-lite residual n={len(ids)} workers={workers} "
        f"OMP={os.environ.get('OMP_THREAD_LIMIT')} "
        f"FULL_PSM={os.environ.get('MIB_OCR_FULL_PSM', '6')} "
        f"CROP_PSM={os.environ.get('MIB_OCR_CROP_PSM', '6')} "
        f"BINARIZE={os.environ.get('MIB_OCR_BINARIZE', '1')}"
    )
    t_wall0 = time.perf_counter()
    preds: list = []
    times: list[float] = []
    done = 0
    with ProcessPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(one, c): c for c in ids}
        for f in as_completed(futs):
            cid, pred, dt = f.result()
            preds.append(pred)
            times.append(dt)
            done += 1
            if done % 10 == 0 or done == len(ids):
                elapsed = time.perf_counter() - t_wall0
                logp(
                    f"  {done}/{len(ids)} last={cid} {dt:.1f}s "
                    f"elapsed={elapsed:.1f}s mean_case={sum(times)/len(times):.1f}s"
                )

    wall = time.perf_counter() - t_wall0
    write_jsonl(OUT / "predictions.jsonl", preds)
    times_sorted = sorted(times)
    (OUT / "case_times.json").write_text(
        json.dumps(
            {
                "wall_s": wall,
                "n": len(times),
                "mean_s": sum(times) / len(times),
                "p50_s": times_sorted[len(times) // 2],
                "p90_s": times_sorted[int(len(times) * 0.9)],
                "max_s": max(times),
                "workers": workers,
                "s_per_pdf_wall": wall / len(times),
            },
            indent=2,
        )
        + "\n"
    )
    logp(f"DONE n={len(preds)} wall={wall:.1f}s mean_case={sum(times)/len(times):.1f}s")


if __name__ == "__main__":
    main()
