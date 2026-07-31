#!/usr/bin/env bash
set -euo pipefail
ROOT=/root/dev-workspace/mib-doc-challenge
WT=$ROOT/worktrees/lat-dpi
ART=$ROOT/artifacts/lat-dpi
mkdir -p "$ART"
export OMP_THREAD_LIMIT=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 MIB_WORKERS=2
cd "$WT"
exec > >(tee -a "$ART/run.log") 2>&1
echo "=== lat-dpi start $(date -Is) load=$(cut -d' ' -f1-3 /proc/loadavg) ==="

echo "=== microbench lean vs fat (serial ocr_pdf_text) ==="
uv run python - <<'PY'
import json, os, time
from pathlib import Path
from mib_solution.ocr import ocr_pdf_text

root = Path("/root/dev-workspace/mib-doc-challenge")
ids = json.loads((root / "artifacts/residual.json").read_text())["case_ids"][:5]
paths = [root / "data/train" / f"{cid}.pdf" for cid in ids]
print("microbench ids:", ids, flush=True)

def bench(label, env_extra):
    for k in list(os.environ):
        if k.startswith("MIB_OCR_"):
            del os.environ[k]
    os.environ.update(env_extra)
    times, chars = [], []
    for cid, p in zip(ids, paths):
        t0 = time.perf_counter()
        txt = ocr_pdf_text(p)
        dt = time.perf_counter() - t0
        times.append(dt); chars.append(len(txt))
        print(f"  {label} {cid}: {dt:.2f}s chars={len(txt)}", flush=True)
    return {
        "label": label,
        "env": env_extra,
        "ids": ids,
        "per_pdf_s": times,
        "mean_s": sum(times)/len(times),
        "sum_s": sum(times),
        "chars": chars,
    }

results = []
print("\n=== LEAN defaults dpi=200 max_pages=4 ===", flush=True)
results.append(bench("lean_200_4", {}))
print("\n=== FAT env dpi=275 max_pages=6 ===", flush=True)
results.append(bench("fat_275_6", {"MIB_OCR_DPI": "275", "MIB_OCR_MAX_PAGES": "6"}))

lean, fat = results[0], results[1]
out = {
    "note": "serial ocr_pdf_text only; machine may be contended by peer latency agents",
    "load_at_end": open("/proc/loadavg").read().strip(),
    "results": results,
    "speedup_fat_over_lean": fat["mean_s"] / lean["mean_s"] if lean["mean_s"] else None,
    "lean_mean_s": lean["mean_s"],
    "fat_mean_s": fat["mean_s"],
}
Path("/root/dev-workspace/mib-doc-challenge/artifacts/lat-dpi/microbench.json").write_text(json.dumps(out, indent=2))
print("\nSUMMARY lean_mean={:.2f}s fat_mean={:.2f}s fat/lean={:.3f}".format(
    lean["mean_s"], fat["mean_s"], fat["mean_s"]/lean["mean_s"]), flush=True)
PY

echo "=== residual n=100 workers=2 ==="
unset MIB_OCR_DPI MIB_OCR_MAX_PAGES MIB_OCR_BINARIZE || true
uv run python - <<'PY'
import json, os, time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from mib_solution.pipeline import predict_pdf, write_jsonl

root = Path("/root/dev-workspace/mib-doc-challenge")
residual = json.loads((root / "artifacts/residual.json").read_text())
out = root / "artifacts" / "lat-dpi"
out.mkdir(parents=True, exist_ok=True)
workers = int(os.environ.get("MIB_WORKERS", "2"))
ids = residual["case_ids"]
print(f"n={len(ids)} workers={workers} OMP={os.environ.get('OMP_THREAD_LIMIT')}", flush=True)

def one(cid: str):
    t0 = time.perf_counter()
    pred = predict_pdf(root / "data/train" / f"{cid}.pdf")
    return pred, time.perf_counter() - t0

t0 = time.perf_counter()
preds, times = [], []
with ProcessPoolExecutor(max_workers=workers) as ex:
    futs = {ex.submit(one, c): c for c in ids}
    done = 0
    for f in as_completed(futs):
        pred, dt = f.result()
        preds.append(pred)
        times.append(dt)
        done += 1
        if done % 10 == 0 or done == len(ids):
            print(f"  {done}/{len(ids)} last={pred.get('case_id')} {dt:.1f}s elapsed={time.perf_counter()-t0:.1f}s", flush=True)

preds.sort(key=lambda p: str(p.get("case_id") or ""))
write_jsonl(out / "predictions.jsonl", preds)
wall = time.perf_counter() - t0
meta = {
    "run_name": "lat-dpi",
    "hypothesis": "Lower OCR cost via dpi=200 max_pages=4 defaults (env overrides kept) protects residual primary (≥104.45 target) with cat 0",
    "n": len(preds),
    "workers": workers,
    "OMP_THREAD_LIMIT": os.environ.get("OMP_THREAD_LIMIT"),
    "OMP_NUM_THREADS": os.environ.get("OMP_NUM_THREADS"),
    "defaults": {"dpi": 200, "max_pages": 4},
    "env_overrides": ["MIB_OCR_DPI", "MIB_OCR_MAX_PAGES", "MIB_OCR_BINARIZE"],
    "wall_sec": wall,
    "s_per_pdf_wall": wall / max(1, len(preds)),
    "mean_per_pdf_sec": sum(times) / max(1, len(times)),
    "median_per_pdf_sec": sorted(times)[len(times)//2] if times else None,
    "load_note": "may be contended by peer lat-* residual runs",
    "baseline_compare": {
        "residual_reconfirm_no_cv2": 104.45,
        "residual_reconfirm_cv2": 104.74,
        "promote_integrate": 108.78,
    },
}
(out / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")
print(json.dumps(meta, indent=2), flush=True)
print(f"DONE wrote {len(preds)} -> {out / 'predictions.jsonl'}", flush=True)
PY

python3 "$ROOT/scripts/evaluate.py" \
  --truth "$ROOT/artifacts/residual_truth.csv" \
  --submission "$ART/predictions.jsonl" \
  --output-json "$ART/eval.json" \
  --case-scores-jsonl "$ART/case_scores.jsonl"

python3 - <<'PY'
import json
from pathlib import Path
art = Path("/root/dev-workspace/mib-doc-challenge/artifacts/lat-dpi")
d = json.loads((art / "eval.json").read_text())
meta = json.loads((art / "meta.json").read_text())
meta["primary"] = d["scores"]["total_score"]
meta["extraction"] = d["scores"]["extraction_score"]
meta["classification"] = d["scores"]["classification_score"]
meta["calibration"] = d["scores"]["calibration_score"]
meta["catastrophic"] = d["raw"]["catastrophic_false_approvals"]
meta["scores"] = d["scores"]
meta["raw"] = {k: d["raw"][k] for k in ("catastrophic_false_approvals", "classification_raw", "extraction_raw", "mean_confidence_brier")}
(art / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")
print("PRIMARY", meta["primary"])
print("CAT", meta["catastrophic"])
print(json.dumps(d["scores"], indent=2))
PY

echo "=== lat-dpi end $(date -Is) load=$(cut -d' ' -f1-3 /proc/loadavg) ==="
