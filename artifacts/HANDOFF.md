# Handoff — continue on high-CPU cloud machine

**Date:** 2026-07-30  
**Repo:** `musafir42/mib-doc-challenge` (branch `main`)  
**Process:** `GROK_BUILD.md` (read Campaign handoff first)

## Why this handoff exists

The campaign used **Modal** as a batch farm for residual/full OCR scoring. That worked for learning and for the best measured full-train score, but it was **overkill and fragile** for this offline-Docker challenge. Continuation is intended on a **single high-CPU VM** with local Docker + multi-process scoring.

## Current product state

| Item | Value |
|------|--------|
| Product tree | `solution/` |
| Pipeline | OCR (tesseract/poppler) → extract → adjudicate → calibrate |
| Residual (seg-v1, n=100) | **108.78 / 150**, cat **0** → `artifacts/promote_integrate/` |
| Full train (n=1000) | **119.27 / 150**, cat **0** → `artifacts/promote_integrate_full/` |
| Docker smoke (10 PDFs) | READY — `artifacts/docker_ship/READY.md` (~0.099 GiB image) |
| Ship-align full train/val | **NOT DONE** |
| Validation submission | **NOT DONE** |

Integrated Explore wins (non-exhaustive): OCR, stamp crops, deny-recall, evidence, page-router pieces, approve-safe Finding path, calibration. See `artifacts/SCOREBOARD.md` and worktree FINDINGS.

## Residual freeze (do not rewrite casually)

- File: `artifacts/residual.json` version **seg-v1**, n=100  
- Truth: `artifacts/residual_truth.csv`  
- Harness: `solution/experiments/RESIDUAL.md`  
- Only merge owner rewrites residual  

## What not to bring back

| Removed / frozen | Why |
|------------------|-----|
| Modal sandbox bulk ship (`ship_docker_*`, `ship_align_*`) | Hung jobs, empty preds, thrash |
| `modal_bulk_runner.py` | Farm glue only |
| Stale ACTIVE multi-agent rows | All Explore batch finished or abandoned |
| Modal as default in playbook | Wrong abstraction for this problem |

Historical Modal scores (`artifacts/modal_*`) stay for audit. Do not treat them as the live farm path.

## Data on the new machine

PDFs are **gitignored**. You must copy or re-download:

```text
data/train/*.pdf          # 1000
data/validation/*.pdf     # 5000
data/train_labels.csv
data/validation_manifest.csv
```

Source: challenge zip / laptop `data/` / prior Modal volume export if you still have one.

## Day-1 checklist on the new box

1. Clone repo; install uv, Docker, tesseract, poppler (or rely on Docker image for OCR).  
2. Restore `data/`.  
3. `cd solution && uv sync`.  
4. Residual re-score → expect ~108.78.  
5. `docker build -t mib-submission:latest solution/` and smoke 10 PDFs.  
6. Full train Docker or ProcessPool → expect ~119.27.  
7. Validation 5000 preds → `scripts/validate_submission.py`.  
8. Only then Segment-2 Explore.

## Reproduce residual score (local)

```bash
# From repo root; see also GROK_BUILD.md and solution/experiments/RESIDUAL.md
uv run --project solution python - <<'PY'
import json, os
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from mib_solution.pipeline import predict_pdf, write_jsonl
root = Path('.')
ids = json.loads((root / 'artifacts/residual.json').read_text())['case_ids']
workers = int(os.environ.get('MIB_WORKERS', os.cpu_count() or 4))
def one(cid):
    return predict_pdf(root / 'data/train' / f'{cid}.pdf')
preds = []
with ProcessPoolExecutor(max_workers=workers) as ex:
    for f in as_completed([ex.submit(one, c) for c in ids]):
        preds.append(f.result())
out = root / 'artifacts' / 'residual_reconfirm'
out.mkdir(parents=True, exist_ok=True)
write_jsonl(out / 'predictions.jsonl', preds)
print(len(preds), 'workers', workers)
PY
python3 scripts/evaluate.py \
  --truth artifacts/residual_truth.csv \
  --submission artifacts/residual_reconfirm/predictions.jsonl \
  --output-json artifacts/residual_reconfirm/eval.json \
  --case-scores-jsonl artifacts/residual_reconfirm/case_scores.jsonl
```

## Scoreboard authority

`artifacts/SCOREBOARD.md` is append-only for the merge owner.  
Full narrative: `artifacts/AUDIT.md`.

## Human decision (2026-07-30)

> Modal seems overkill; prefer a ~$20 high-CPU cloud box, install Grok Build there, continue.

This document exists so the next session does not re-open the Modal farm by default.
