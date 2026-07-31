# exp-review-merge FINDINGS

Date: 2026-07-30  
Worktree: `worktrees/exp-review-merge/`  
Owns: `src/mib_solution/extract.py` (conflict flags), `src/mib_solution/adjudicate.py`  
Residual: `artifacts/residual.json` version **seg-v1** (n=100)  
Compare bars: `artifacts/exp-stamp-ocr/` (**100.90**, cat **0**), `artifacts/modal_residual_ocr/` (**98.05**, cat **0**)

## Hypothesis

Packets with **unresolved multi-source disagreements** on applicant name, sponsor
ID, or risk labels are almost never true APPROVED (train text-layer: 0/24
unresolved name/sponsor conflicts labeled APPROVED; 23/24 NEEDS_REVIEW). Policy:

1. Detect multi-source field conflicts in extract and surface conflict bits.
2. Adjudicate → **NEEDS_REVIEW** on unresolved conflicts.
3. **Never resolve a field conflict with APPROVED** (including Finding:APPROVED
   when conflict bits remain set).
4. Manual correction notes **resolve** the corresponding field (not a conflict).

Secondary (score headroom, same adjudicate file): port conservative multi-signal
APPROVED + stale non-DIP deny from `exp-approve`, gated on no field conflict.

## Method

### Extract (`extract.py`)

| Signal | Sources | Unresolved when |
|--------|---------|-----------------|
| name | manual correction, labeled Applicant/Registry/Full Name, attestation | ≥2 **clean** name clusters after OCR-tolerant clustering; no manual |
| sponsor | manual, labeled Sponsor ID, attestation | ≥2 distinct `SPN-####`; no manual |
| risk | Risk Flags labels + Observed flags lines | distinct review-only/none sets (DQ merge is not soft-conflict) |

Implementation details:

- **OCR-tolerant name compare** (edit ratio + token Jaccard + substring) collapses
  near-duplicates before counting a conflict.
- **Clean-name filter** (2+ alpha tokens, no passport/image/digit junk) so OCR
  fragments do not mass-flag identity conflicts.
- Conflict bits returned as `_name_conflict`, `_sponsor_conflict`,
  `_risk_conflict`, `_field_conflict` (pipeline strips `_` keys from submission).
- **No synthetic injection** of `identity_conflict` / `sponsor_mismatch` into
  submitted `risk_flags` (early attempts polluted residual extraction and caused
  dual review-only false DENIED).

### Adjudicate (`adjudicate.py`)

Priority:

1. Finding note — APPROVED blocked if `_field_conflict`; DENIED/NR unchanged.
2. Text/structured DQ (embargo, biohazard, warrant, memory, flags, TRANSIT-7,
   unpaid, revoked sponsors, multi review-only).
3. Unresolved field conflict → **NEEDS_REVIEW** (never multi-signal APPROVED).
4. Single review-only flag → NEEDS_REVIEW.
5. Stale non-DIP arrival (>180d before 2026-07-07) → DENIED.
6. Multi-signal APPROVED only if multi-field clean + fee ok + no flags +
   Registry CLEAR + labeled Fee paid + Observed flags none.
7. Else NEEDS_REVIEW.

No case-id tables / label lookup.

### Farm

```bash
PATH=$HOME/.local/bin:$PATH
MIB_CODE_SRC=worktrees/exp-review-merge/src \
  modal run solution/modal_app.py --action score-residual-ocr --run-name exp-review-merge
```

OCR path inherits stamp-region OCR already present in this worktree (`ocr.py`).

## Residual A/B (seg-v1, n=100, official scorer)

| system | primary | extraction | classification | calibration | catastrophic |
|--------|--------:|-----------:|---------------:|------------:|-------------:|
| modal_residual_ocr | 98.05 | 27.46 | 56.00 | 14.59 | **0** |
| exp-stamp-ocr | **100.90** | 30.84 | 55.20 | 14.86 | **0** |
| **exp-review-merge** | **102.47** | **30.93** | **57.00** | 14.54 | **0** |
| Δ vs stamp-ocr | **+1.57** | +0.09 | **+1.80** | −0.32 | 0 |

Confusion vs stamp-ocr:

| cell | stamp-ocr | exp-review-merge |
|------|----------:|-----------------:|
| APPROVED→APPROVED | 11 | **12** |
| APPROVED→NEEDS_REVIEW | 17 | 16 |
| DENIED→DENIED | 30 | **32** |
| DENIED→NEEDS_REVIEW | 22 | 20 |
| NEEDS_REVIEW→NEEDS_REVIEW | 18 | 18 |
| NEEDS_REVIEW→DENIED | 2 | 2 |

Net adjudication deltas vs stamp-ocr (all cat-safe):

| effect | cases (patterns) | rule |
|--------|------------------|------|
| WIN | true APPROVED recovered | multi-signal triad APPROVED |
| WIN | true DENIED recovered | stale non-DIP arrival |
| LOSS | 1 true APPROVED (Finding) demoted | field-conflict gate on Finding:APPROVED (OCR multi-name still tripped clean filter on one residual packet) |

## Ablations / failed paths (same experiment)

| attempt | residual primary | note |
|---------|-----------------:|------|
| conflict + inject identity into risk_flags + approve | 96.16 | OCR false multi-name → mass `identity_conflict`, demoted Finding APPROVED |
| fuzzy cluster + hard inject only | 100.58 | better; still dual-flag NR→DENIED from inject+illegible |
| **clean names, no risk inject, conflict gate + approve/stale** | **102.47** | beat stamp bar, cat 0 |

Train text-layer policy check (not scored): unresolved multi-source name/sponsor
conflicts → 23 NEEDS_REVIEW / 1 DENIED / **0 APPROVED** among gold labels.

## Decision: **promote candidate** (residual gate)

- Residual primary **102.47 > 100.90** (stamp bar) and **> 98.05** (OCR baseline)
- Catastrophic false approvals **0**
- Implements stated policy: multi-source conflict → NEEDS_REVIEW; never APPROVED
  on unresolved conflict
- No case-id answer tables

### Residual risks / follow-ups

- One residual Finding:APPROVED still demoted by OCR multi-name conflict — tighten
  clean-name / page-role evidence before ship if full-train shows more demotions.
- NR→DENIED (2) unchanged vs stamp (image-only / thin OCR fee+visa noise) — owned
  by OCR/deny-recall experiments, not conflict merge.
- Conflict bits are internal; merge owner should keep them out of JSONL schema.

## Artifacts

- `artifacts/exp-review-merge/{predictions.jsonl,eval.json,case_scores.jsonl,meta.json,truth.csv}`
- Code: `worktrees/exp-review-merge/src/mib_solution/{extract,adjudicate}.py`
- Text-layer smoke only: `artifacts/exp-review-merge/eval_text_smoke.json` (not residual bar)
