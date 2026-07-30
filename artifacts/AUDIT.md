# Audit trail — MIB Doc Challenge (Grok Build)

**Repo:** `musafir42/mib-doc-challenge`  
**Challenge SHA (fork base):** see `artifacts/challenge_sha.txt`  
**Process:** `GROK_BUILD.md`  
**Merge owner:** orchestrating agent (this campaign)

## Stage timeline

| Stage | Tag / name | Outcome |
|-------|------------|---------|
| Setup | process-drill | Layout, scorer smoke, Modal auth, process drill |
| Baseline | `baseline` | Train **98.88 / 150**, cat **0** — pypdf + deny-only |
| Segment | residual_baseline | Residual **seg-v1** n=100 → **62.21**, cat 0; ceiling BINDING.md |
| Explore | exp-extract / exp-adjudicate / exp-risk | Residual 64.24 / **74.85** / 71.60, all cat 0 |
| Integrate | `promote-seg1` | Residual **75.37**, train **106.95**, cat **0** |

## Scoreboard

Authoritative append-only log: `artifacts/SCOREBOARD.md`.

## Residual freeze

- Identity: `artifacts/residual.json` version **seg-v1**
- Truth filter: `artifacts/residual_truth.csv`
- Harness docs: `solution/experiments/RESIDUAL.md`
- Baseline residual: `artifacts/residual_baseline/`

Only merge owner rewrites `residual.json`.

## Ceiling / binding

- `artifacts/ceiling/BINDING.md` — binding stage = **adjudication policy**, secondary = **extraction**
- Key diagnostic: baseline extract + oracle adj → **136.99** train (policy headroom)
- Label-only + current rules → cls only 55.6/80 (rules incomplete even with gold fields)

## Promote reasoning (`promote-seg1`)

**Merged into `solution/`:**
1. `exp-extract` multi-source Label/Value extract (purpose/fee/home/sponsor/registry aliases)
2. `exp-adjudicate` Finding-note priority + deny expansion (unpaid always deny, EMBARGO text, multi review flags)

**Rejected / dialed back:**
- Multi-field auto-APPROVED → **removed** after full-train showed **30 catastrophic false approvals** (image-only DQ stamps invisible to text extract)
- APPROVED only via trusted visible `Finding: APPROVED` notes

**Not a ship win:** Docker Ship-align checklist not completed.

## Explore worktrees (code snapshots)

| Worktree | Role | FINDINGS |
|----------|------|----------|
| `worktrees/exp-extract/` | Extraction A/B | `experiments/exp-extract/FINDINGS.md` |
| `worktrees/exp-adjudicate/` | Adjudication A/B | `experiments/exp-adjudicate/FINDINGS.md` |
| `worktrees/exp-risk/` | Risk/registry signals | `experiments/exp-risk/FINDINGS.md` |

## Catastrophic definition (scorer only)

`catastrophic_false_approval`: predict APPROVED when truth is DENIED (`scripts/evaluate.py`).

## OCR path (next)

Many remaining missed DENIED have DQ flags present only on stamp/image pages. Explore OCR fallback on residual without case-id tables. See scoreboard rows after `exp-ocr` runs.

## Commands to reproduce promote_seg1 scores

```bash
# Residual
uv run --project solution python -c "
import json
from pathlib import Path
from mib_solution.pipeline import predict_pdf, write_jsonl
ids=json.loads(Path('artifacts/residual.json').read_text())['case_ids']
write_jsonl(Path('artifacts/repro/predictions.jsonl'),
  [predict_pdf(Path(f'data/train/{c}.pdf')) for c in ids])
"
python3 scripts/evaluate.py --truth artifacts/residual_truth.csv \
  --submission artifacts/repro/predictions.jsonl --output-json artifacts/repro/eval.json

# Full train
uv run --project solution mib-solution data/train artifacts/repro/train_predictions.jsonl
python3 scripts/evaluate.py --truth data/train_labels.csv \
  --submission artifacts/repro/train_predictions.jsonl --output-json artifacts/repro/train_eval.json
```
