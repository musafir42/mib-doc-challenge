# Residual harness

Score the frozen hard-failure subset with the current `solution/`.

## Residual identity

- **File:** `artifacts/residual.json`
- **Version:** `seg-v1` (merge owner freezes; only merge owner rewrites)
- **Shape:** `{"version", "case_ids", "n", "notes", ...}`
- **Inputs:** `data/train/<case_id>.pdf`
- **Labels:** filter `data/train_labels.csv` → `artifacts/residual_truth.csv`

## Command path (local — default for tiny/residual)

From **repo root**:

```bash
# 1) Predictions on residual ids
uv run --project solution python - <<'PY'
import json
from pathlib import Path
from mib_solution.pipeline import predict_pdf, write_jsonl

root = Path(".")
residual = json.loads((root / "artifacts/residual.json").read_text())
run_name = "residual_local"  # or artifacts/<exp_name>
out = root / "artifacts" / run_name
out.mkdir(parents=True, exist_ok=True)
preds = []
for cid in residual["case_ids"]:
    pdf = root / "data/train" / f"{cid}.pdf"
    if pdf.exists():
        preds.append(predict_pdf(pdf))
write_jsonl(out / "predictions.jsonl", preds)
print(len(preds), "→", out / "predictions.jsonl")
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

# 4) meta.json: git sha, residual version, command
```

**Baseline residual row:** `artifacts/residual_baseline/` (Segment freeze).

## Command path (Modal — preferred for parallel A/B)

```bash
# After Volume has data/train:
modal run solution/modal_app.py --action score-residual --run-name <name>
```

Pulls `artifacts/<name>/{predictions.jsonl,eval.json,meta.json}`.

## Rules

- Same `solution/uv.lock` as ship config
- Residual A/B before any full-data promote score
- Compare primary total + catastrophic vs `residual_baseline` scoreboard row
