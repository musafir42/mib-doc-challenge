# Residual harness

Score the frozen hard-failure subset with the current `solution/`.

## Residual identity

- **File:** `artifacts/residual.json`
- **Version:** `seg-v1` (merge owner freezes; only merge owner rewrites)
- **Shape:** `{"version", "case_ids", "n", "notes", ...}`
- **Inputs:** `data/train/<case_id>.pdf`
- **Labels:** filter `data/train_labels.csv` → `artifacts/residual_truth.csv`

## Command path (local — default)

From **repo root**. Prefer multi-process on a high-CPU box.

```bash
# 0) env
export MIB_WORKERS="${MIB_WORKERS:-$(nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 4)}"

# 1) Predictions on residual ids
uv run --project solution python - <<'PY'
import json, os
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from mib_solution.pipeline import predict_pdf, write_jsonl

root = Path(".")
residual = json.loads((root / "artifacts/residual.json").read_text())
run_name = os.environ.get("MIB_RUN_NAME", "residual_local")
out = root / "artifacts" / run_name
out.mkdir(parents=True, exist_ok=True)
workers = int(os.environ.get("MIB_WORKERS", "4"))
ids = residual["case_ids"]

def one(cid: str):
    return predict_pdf(root / "data/train" / f"{cid}.pdf")

preds = []
with ProcessPoolExecutor(max_workers=workers) as ex:
    futs = [ex.submit(one, c) for c in ids]
    for f in as_completed(futs):
        preds.append(f.result())
write_jsonl(out / "predictions.jsonl", preds)
print(len(preds), "→", out / "predictions.jsonl", "workers=", workers)
PY

# 2) Residual truth CSV (once per residual version; reusable)
uv run --project solution python - <<'PY'
import csv, json
from pathlib import Path
root = Path(".")
ids = set(json.loads((root / "artifacts/residual.json").read_text())["case_ids"])
rows = list(csv.DictReader((root / "data/train_labels.csv").open()))
out = root / "artifacts/residual_truth.csv"
with out.open("w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=rows[0].keys())
    w.writeheader()
    for r in rows:
        if r["case_id"] in ids:
            w.writerow(r)
print("wrote", out)
PY

# 3) Official score
python3 scripts/evaluate.py \
  --truth artifacts/residual_truth.csv \
  --submission artifacts/<run_name>/predictions.jsonl \
  --output-json artifacts/<run_name>/eval.json \
  --case-scores-jsonl artifacts/<run_name>/case_scores.jsonl

# 4) meta.json: git sha, residual version, command, MIB_WORKERS
```

**Baseline residual row:** `artifacts/residual_baseline/` (Segment freeze).  
**Current integrate residual:** `artifacts/promote_integrate/` (~108.78).

## Docker residual / train (Ship-align path)

```bash
docker build -t mib-submission:latest solution/
# residual: copy residual PDFs into a dir, or mount full train and score a filtered pred file later
docker run --rm --network none --cpus $(nproc) --memory 32g \
  --read-only --tmpfs /tmp:rw,nosuid,nodev,size=8g \
  -v "$PWD/data/train:/input:ro" -v "$PWD/artifacts/docker_train:/output" \
  mib-submission:latest /input /output/predictions.jsonl
```

## Modal (legacy — optional only)

Modal was used historically for residual/full OCR maps. It is **not** the default farm. Prefer local multi-process or Docker on a high-CPU VM. If you still have a Volume with data, `solution/modal_app.py` may remain as optional glue — do not rebuild ship around it.

## Rules

- Same `solution/uv.lock` as ship config
- Residual A/B before any full-data promote score
- Compare primary total + catastrophic vs scoreboard residual rows
- Max score is always **/150** (residual and full train share the scale)
