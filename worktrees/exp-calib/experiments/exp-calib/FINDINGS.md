# exp-calib — path + feature confidence (Brier)

## Hypothesis

Fixed / coarse path confidences (e.g. 0.35 default review, 0.58–0.90 deny ladder) waste calibration points. Mapping **adjudication path** and **packet features** to empirical correctness rates should lower mean Brier and raise the calibration section without changing decisions or catastrophic count.

## Method

1. Read scorer: target = 1 if adj correct else 0;  
   `calibration_score = 20 * max(0, 1 − 2 · mean_brier)`.
2. New module `worktrees/exp-calib/src/mib_solution/calibrate.py`.
3. `adjudicate._decide` tags `fields["_adj_reason"]` (decisions identical to promote_ocr).
4. `pipeline.predict_pdf` sets `confidence = calibrate(fields, adjudication, reason=…)`.
5. Modal residual OCR:  
   `MIB_CODE_SRC=worktrees/exp-calib/src modal run solution/modal_app.py --action score-residual-ocr --run-name exp-calib`

### Confidence formula

```
if reason == default_review:
    conf ← fee prior:
        unknown → 0.48 | waived → 0.32 | paid → 0.30 | else → 0.34
    n_fields ≤ 4 → +0.06;  n_fields ≥ 7 → −0.04
    text_len < 200 → −0.04;  text_len > 1200 and ocr_used → +0.02
    risk_flags present → +0.04
    clamp to [0.05, 0.99]
else:
    conf ← PATH_CONF[reason]  # full-train path rates, slightly shrunken from 0/1
```

| reason | conf |
|--------|-----:|
| finding_approved / finding_denied / finding_review | 0.97 |
| text_dq (embargo/bio/warrant/memory phrases) | 0.96 |
| flags_dq | 0.94 |
| extra_revoked | 0.95 |
| revoked | 0.92 |
| unpaid | 0.91 |
| transit7 | 0.90 |
| multi_review (≥2 review-only flags) | 0.60 |
| short_text | 0.12 |
| default_review | feature formula (~0.26–0.56) |

Path rates from full-train OCR preds (`artifacts/modal_full_ocr`, n=1000).

## Residual A/B (seg-v1, n=100, official scorer)

| system | total | extraction | classification | calibration | mean Brier | cat |
|--------|------:|-----------:|---------------:|------------:|-----------:|----:|
| **modal_residual_ocr (baseline)** | **98.05** | 27.46 | 56.00 | **14.59** | 0.1352 | **0** |
| **exp-calib** | **99.06** | 27.46 | 56.00 | **15.60** | **0.1099** | **0** |
| **Δ** | **+1.01** | 0 | 0 | **+1.01** | −0.0253 | 0 |

Confusion **unchanged** (decisions only):

```
APPROVED→APPROVED 11 | APPROVED→NEEDS_REVIEW 17
DENIED→DENIED 29     | DENIED→NEEDS_REVIEW 23
NEEDS_REVIEW→NEEDS_REVIEW 20
```

Per-class after calib (residual):

| pred | n | acc | mean_conf | mean_brier |
|------|--:|----:|----------:|-----------:|
| APPROVED | 11 | 1.00 | 0.97 | 0.0009 |
| DENIED | 29 | 1.00 | 0.92 | 0.0142 |
| NEEDS_REVIEW | 60 | 0.33 | 0.46 | 0.1761 |

## Decision: **promote-candidate (cal only)**

- Residual total **99.06 > 98.05** with **cat == 0**.
- Pure calibration lift; extraction/classification flat; no decision change.
- Safe to merge `calibrate.py` + thin `pipeline`/`adjudicate` reason tags into `solution/` (merge owner). Do **not** rewrite residual.json.

## Risks

- Path rates fit full-train promote_ocr behavior; if adjudication rules change, recalibrate PATH_CONF.
- Residual default_review accuracy (~0.26) is lower than full-train (~0.36); feature formula still helps but is slightly optimistic on some NR bins.
- No case-id tables; no confidence hardcoding per id.

## Artifacts

- `artifacts/exp-calib/{eval,meta,predictions,case_scores,truth}.json*`
- Code: `worktrees/exp-calib/src/mib_solution/calibrate.py` (+ wire in `pipeline.py`, reason tags in `adjudicate.py`)
