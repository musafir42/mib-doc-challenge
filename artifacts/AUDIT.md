# Audit trail — MIB Doc Challenge (Grok Build)

**Repo:** `musafir42/mib-doc-challenge`  
**Challenge SHA (fork base):** see `artifacts/challenge_sha.txt`  
**Process:** `GROK_BUILD.md`  
**Handoff:** `artifacts/HANDOFF.md`  
**Merge owner:** orchestrating agent (this campaign)

## Stage timeline

| Stage | Tag / name | Outcome |
|-------|------------|---------|
| Setup | process-drill | Layout, scorer smoke, process drill |
| Baseline | `baseline` | Train **98.88 / 150**, cat **0** — pypdf + deny-only |
| Segment | residual_baseline | Residual **seg-v1** n=100 → **62.21**, cat 0; ceiling BINDING.md |
| Explore | exp-extract / exp-adjudicate / exp-risk | Residual 64.24 / **74.85** / 71.60, all cat 0 |
| Integrate | `promote-seg1` | Residual **75.37**, train **106.95**, cat **0** |
| Explore | OCR (Modal historical) | Residual OCR **98.05**, full train **114.20** |
| Explore | fan-out (stamp, deny-recall, evidence, …) | Best residual single **104.87** (deny-recall) |
| Integrate | `promote_integrate` | Residual **108.78**, train **119.27**, cat **0** ← **current product** |
| Ship-align | docker smoke | Image READY (~0.099 GiB); full train/val **not** done |
| Compute pivot | 2026-07-30 | Modal default **retired**; continue on high-CPU VM |

## Scoreboard

Authoritative append-only log: `artifacts/SCOREBOARD.md`.

## Residual freeze

- Identity: `artifacts/residual.json` version **seg-v1**
- Truth filter: `artifacts/residual_truth.csv`
- Harness docs: `solution/experiments/RESIDUAL.md`
- Baseline residual: `artifacts/residual_baseline/`
- Current product residual: `artifacts/promote_integrate/`

Only merge owner rewrites `residual.json`.

## Ceiling / binding

- `artifacts/ceiling/BINDING.md` — binding stage = **adjudication policy**, secondary = **extraction**
- Key diagnostic: baseline extract + oracle adj → **136.99** train (policy headroom)
- Label-only + early rules → cls incomplete even with gold fields

## Promote reasoning (current product)

**In `solution/` now (integrate):**

1. OCR path (poppler + tesseract), stamp crops, deskew-aware preprocessing  
2. Multi-source labeled extract + evidence/page helpers  
3. Deny-recall / Finding-driven adjudication; safe APPROVED only via trusted Finding APPROVED  
4. Calibration module (confidence only)  
5. Docker packaging: TMPDIR/HOME under `/tmp` for read-only challenge mounts  

**Rejected patterns:**

- Multi-field auto-APPROVED → catastrophic false approvals on full train  
- Free-form harvest of SYSTEM answer-key lines as primary field source  
- Modal sandbox bulk as the ship path  

## Compute decision (2026-07-30)

Modal was useful for early full-train OCR and residual maps, then became ops thrash (function maps, sandboxes, hung ship jobs). Human decision: **high-CPU cloud box + Grok Build + Docker** as the continuation environment. Playbook and residual harness updated; ship Modal scripts removed.

## Catastrophic definition (scorer only)

`catastrophic_false_approval`: predict APPROVED when truth is DENIED (`scripts/evaluate.py`).

## Reproduce promote_integrate scores (local)

```bash
# Residual — see solution/experiments/RESIDUAL.md (MIB_RUN_NAME=promote_integrate_repro)
# Full train:
uv run --project solution python -c "
from pathlib import Path
from mib_solution.pipeline import predict_dir, write_jsonl
write_jsonl(Path('artifacts/repro_train/predictions.jsonl'), predict_dir(Path('data/train')))
"
python3 scripts/evaluate.py --truth data/train_labels.csv \
  --submission artifacts/repro_train/predictions.jsonl \
  --output-json artifacts/repro_train/eval.json
```

Prefer `ProcessPoolExecutor` / Docker with many CPUs (see `GROK_BUILD.md`).
