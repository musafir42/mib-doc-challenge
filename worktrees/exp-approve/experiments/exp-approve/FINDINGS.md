# exp-approve FINDINGS

Date: 2026-07-30  
Worktree: `worktrees/exp-approve/`  
Residual: `artifacts/residual.json` version **seg-v1** (n=100)  
Compare baseline: `artifacts/modal_residual_ocr/` (**98.05**, cat **0**)

## Goal

Add a **safe APPROVED** path that lifts residual score above the Modal OCR
baseline **without any catastrophic false approvals** (true DENIED → pred APPROVED).

## A/B scores (residual, Modal OCR map)

| Run | total | extraction | classification | calibration | cat |
|-----|------:|-----------:|---------------:|------------:|----:|
| modal_residual_ocr (baseline) | **98.05** | 27.46 | 56.00 | 14.59 | **0** |
| exp-approve | **100.49** | 27.46 | **58.40** | 14.63 | **0** |
| Δ | **+2.44** | 0.00 | **+2.40** | +0.04 | 0 |

Artifacts: `artifacts/exp-approve/{predictions.jsonl,eval.json,case_scores.jsonl,meta.json}`

Command:

```bash
export MIB_CODE_SRC=worktrees/exp-approve/src
modal run solution/modal_app.py --action score-residual-ocr --run-name exp-approve
```

### Confusion (residual OCR)

| | modal_residual_ocr | exp-approve |
|--|-------------------:|------------:|
| APPROVED→APPROVED | 11 | **13** |
| APPROVED→NEEDS_REVIEW | 17 | 15 |
| DENIED→DENIED | 29 | **31** |
| DENIED→NEEDS_REVIEW | 23 | 21 |
| NEEDS_REVIEW→NEEDS_REVIEW | 20 | 20 |
| cat false approvals | 0 | **0** |

### Residual adjudication deltas (all correct)

| case_id | truth | base → exp | rule |
|---------|-------|------------|------|
| MIB-000002 | APPROVED | NR → APPROVED | multi-signal approve triad |
| MIB-000037 | APPROVED | NR → APPROVED | multi-signal approve triad |
| MIB-000676 | DENIED | NR → DENIED | stale non-DIP arrival |
| MIB-000745 | DENIED | NR → DENIED | stale non-DIP arrival |

No regressions vs OCR baseline on residual.

## Analysis

Baseline OCR already recovers Finding notes and many DENIED signals. Remaining
headroom on residual was mostly:

1. **True APPROVED** packets with complete fields but no `Finding:` stamp → stuck
   at NEEDS_REVIEW (safe default).
2. **True DENIED** with image-only DQ stamps that look field-clean if approved
   naively (catastrophic risk).
3. **Stale arrivals** (FIELD_MANUAL: arrival >180 days before packet receipt,
   except DIP-1).

### Why multi-field-only APPROVED is unsafe

On residual OCR predictions, naive multi-field clean + paid + risk=none would
approve:

- 3 true APPROVED (gain)
- **1 true DENIED** (MIB-000033, biohazard image-only → **catastrophic**)
- 1 true NEEDS_REVIEW

`Registry Status: CLEAR` alone is also insufficient: train text-layer has many
DENIED packets that still print CLEAR while the disqualifier is stamp/image-only.

### Safe multi-signal APPROVED (precision first)

Require **all** of:

1. Pass all existing deny gates (Finding, DQ text, flags, TRANSIT-7, unpaid,
   revoked sponsors, multi review-only flags, extra revoked under multi-clean).
2. Multi-field completeness (name, species, world, purpose, arrival, visa in
   work set, sponsor present, text_len ≥ 400).
3. `risk_flags` empty / none (including review-only flags).
4. Fee `paid` (or `waived` only for DIP-1).
5. **Positive triad in trusted text** (text-layer and/or OCR merge):
   - `Registry Status` → `CLEAR`
   - labeled `Fee Status` → `paid`
   - biometric `Observed flags: none`
6. Species not `OCR_FALLBACK` (approve path only).

Train text-layer simulation of this triad + gates: **9 true APPROVED, 0 DENIED,
0 NEEDS_REVIEW** false approvals among non-Finding packets.

### Stale arrival DENIED

`PACKET_RECEIPT_DATE = 2026-07-07` (public data version date) and `STALE_DAYS = 180`.

- Non-DIP known visas (`XW-1`, `XW-2`, `MED-3`, `TRANSIT-7`) with arrival age >180
  → **DENIED**.
- DIP-1 exempt (train: all APPROVED age>180 are DIP-1; 0 wrong under this rule).
- Unknown visa → no stale deny (prefer NEEDS_REVIEW).

Train text-layer: stale rule hit **22** true DENIED, **0** wrong.

## Rule changes (`src/mib_solution/adjudicate.py`)

1. **`_positive_approve_evidence`** — Registry CLEAR + Fee Status paid + Observed
   flags none must all appear in `_text`.
2. **Multi-signal APPROVED** — multi-clean + no flags + fee ok + not revoked +
   positive triad → APPROVED @ conf 0.72.
3. **Stale non-DIP deny** — arrival >180 days before 2026-07-07 for known non-DIP
   visas → DENIED @ conf 0.66.
4. **`_species_trusted`** — block `OCR_FALLBACK` on approve only (preserve extra
   revoked deny path when species is weak).

Finding-note APPROVED/DENIED and all prior deny rules unchanged. No case-id
tables. Extraction/OCR pipeline unchanged.

## Residual headroom remaining

Still ~15 `APPROVED→NEEDS_REVIEW` (incomplete extract, missing CLEAR/fee/bio
triad, or waived non-paid paths) and ~21 `DENIED→NEEDS_REVIEW` (image-only DQ
stamps not visible to text/OCR risk extract). Further DENIED gains need stamp
OCR / vision, not looser approve.

## Decision

**PROMOTE candidate** for adjudication approve path on residual:

- residual total **100.49 > 98.05**
- catastrophic **0**
- no case-id answer tables
- prefer NEEDS_REVIEW preserved when triad incomplete

**Do not** ship multi-field-only APPROVED without the CLEAR+paid+bio triad — that
path is catastrophic on residual (MIB-000033) and on full train.
