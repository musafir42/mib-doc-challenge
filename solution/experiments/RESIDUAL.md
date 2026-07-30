# Residual harness

Score a frozen hard-failure subset (`artifacts/residual.json`) with the current `solution/`.

## Residual identity

- File: `artifacts/residual.json`
- Shape: `{"case_ids": ["MIB-######", ...], "notes": "..."}` (merge owner freezes)
- Inputs: PDFs under `data/train/` matching those case ids
- Labels: `data/train_labels.csv` filtered to residual ids

## Command path (local, tiny debug)

From repo root:

```bash
# 1) Predict residual cases only
uv run --project solution python - <<'PY'
import json
from pathlib import Path
from mib_solution.pipeline import predict_pdf, write_jsonl

root = Path(".")
residual = json.loads((root / "artifacts/residual.json").read_text())
ids = residual["case_ids"]
preds = []
for cid in ids:
    pdf = root / "data/train" / f"{cid}.pdf"
    if pdf.exists():
        preds.append(predict_pdf(pdf))
run_name = "residual_local"
out = root / "artifacts" / run_name
out.mkdir(parents=True, exist_ok=True)
write_jsonl(out / "predictions.jsonl", preds)
print(len(preds), "preds →", out / "predictions.jsonl")
PY

# 2) Official score (filter truth with residual ids if needed — scorer uses full truth;
#    missing non-residual cases incur missing penalty. Prefer residual-truth CSV:)
uv run --project solution python - <<'PY'
import csv, json
from pathlib import Path
root = Path(".")
residual = json.loads((root / "artifacts/residual.json").read_text())
ids = set(residual["case_ids"])
rows = list(csv.DictReader((root / "data/train_labels.csv").open()))
out = root / "artifacts/residual_truth.csv"
with out.open("w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=rows[0].keys())
    w.writeheader()
    for r in rows:
        if r["case_id"] in ids:
            w.writerow(r)
print("wrote", out, "n=", sum(1 for r in rows if r["case_id"] in ids))
PY

python3 scripts/evaluate.py \
  --truth artifacts/residual_truth.csv \
  --submission artifacts/residual_local/predictions.jsonl \
  --output-json artifacts/residual_local/eval.json \
  --case-scores-jsonl artifacts/residual_local/case_scores.jsonl

# 3) meta.json (git sha, residual identity, command)
```

## Command path (Modal — preferred for residual A/B)

```bash
# After modal auth + data Volume populated:
modal run solution/modal_app.py --action score-residual --run-name <name>
# Pulls artifacts/<name>/{predictions.jsonl,eval.json,meta.json}
```

## Rules

- Same `solution/uv.lock` as ship config
- Only merge owner rewrites `artifacts/residual.json`
- Residual A/B before any full-data promote score
