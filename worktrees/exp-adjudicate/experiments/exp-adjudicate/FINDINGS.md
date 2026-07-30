# exp-adjudicate FINDINGS

Date: 2026-07-30  
Worktree: `worktrees/exp-adjudicate/`  
Residual: `artifacts/residual.json` version **seg-v1** (n=100)

## Goal

Beat residual baseline adjudication without catastrophic false approvals.

## A/B scores (residual hard set)

| Run | total | extraction | classification | calibration | cat |
|-----|------:|-----------:|---------------:|------------:|----:|
| residual_baseline | **62.21** | 16.62 | 33.00 | 12.59 | **0** |
| exp-adjudicate | **74.85** | 16.62 | **44.60** | **13.63** | **0** |
| Δ | **+12.64** | 0.00 | **+11.60** | **+1.04** | 0 |

Artifacts: `artifacts/exp-adjudicate/{predictions.jsonl,eval.json,case_scores.jsonl,meta.json}`

### Confusion (residual)

| | baseline | exp-adjudicate |
|--|---------:|---------------:|
| DENIED→DENIED | 2 | **13** |
| DENIED→NEEDS_REVIEW | 50 | 39 |
| APPROVED→APPROVED | 0 | **8** |
| APPROVED→NEEDS_REVIEW | 27 | 20 |
| APPROVED→DENIED | 1 | **0** |
| NEEDS_REVIEW→NEEDS_REVIEW | 20 | 20 |
| cat false approvals | 0 | 0 |

## Analysis

Ceiling: baseline extract + oracle adj ≈ 137 train points; residual is dominated by
`DENIED→NEEDS_REVIEW` and `APPROVED→NEEDS_REVIEW` under deny-only baseline rules.

Train patterns used (no case-id tables):

- Visible `Finding: APPROVED|DENIED|NEEDS_REVIEW` adjudicator notes are **perfectly
  aligned** with labels on full train (n=162) — highest-trust evidence per FIELD_MANUAL.
- `fee_status=unpaid` is always DENIED (including DIP-1); baseline wrongly exempted DIP-1.
- DQ risk flags / TRANSIT-7 remain hard denies.
- Secondary text: `EMBARGO REVIEW`, biohazard / warrant / memory-tamper phrases when
  structured `risk_flags` miss registry language.
- ≥2 review-only flags → DENIED (manual edge case).
- Extra revoked sponsors (`SPN-9090`, `SPN-2718`, `SPN-7331`) only when multi-field clean
  and not DIP-1.
- Safe APPROVED only when multi-field clean, `risk_flags=none`, paid (or DIP-1 waived),
  and sponsor not revoked.
- Manual `sponsor is SPN-####` correction overrides intake field (avoids false revoke).

## Rule changes (`src/mib_solution/adjudicate.py`)

1. **Finding-note priority** — parse `Finding:` from `_text` before field rules.
2. **Always deny unpaid** — drop DIP-1 exception.
3. **Text secondary DQ phrases** — embargo / biohazard / warrant / memory tamper.
4. **Multi review-only flags** → DENIED.
5. **Extra revoked sponsors** under multi-field confidence.
6. **Careful APPROVED** multi-field clean path.
7. **Manual sponsor correction** before revoke checks.

Extraction unchanged; classification + calibration drive the gain.

## Residual headroom remaining

Still ~39 `DENIED→NEEDS_REVIEW` (many DQ stamps image-only / empty text layer) and
~20 `APPROVED→NEEDS_REVIEW` (extract-poor packets without Finding notes). Further gains
need extract/OCR, not more aggressive auto-APPROVED.

## Decision

**PROMOTE candidate for adjudication policy** on residual:

- residual total **74.85 > 62.21**
- catastrophic **0**
- no case-id answer tables
