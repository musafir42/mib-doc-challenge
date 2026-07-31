# exp-conf-isotonic — path + feature isotonic confidence (Brier)

## Hypothesis

Coarse path confidences from `adjudicate()` (0.35 default review, 0.58–0.90 deny ladder, 0.88 finding APPROVED) waste calibration points. Mapping **adjudication path** to full-train empirical correctness rates, plus a **monotone feature score → confidence** map (isotonic knots) for the large `default_review` dump-bin, should lower mean Brier and raise the calibration section **without changing adjudication labels**.

## Method

1. Scorer: target = 1 if adj correct else 0;  
   `calibration_score = 20 * max(0, 1 − 2 · mean_brier)`.
2. New module `worktrees/exp-conf-isotonic/src/mib_solution/calibrate.py`.
3. `adjudicate._decide` tags `fields["_adj_reason"]` (decisions **identical** to stamp/promote_ocr).
4. `pipeline.predict_pdf` sets `confidence = calibrate(fields, adjudication, reason=…)`.
5. OCR path kept from stamp-region work (crops + dual PSM @ elevated DPI) so extraction/classification match `exp-stamp-ocr`; this experiment **only** owns confidence.
6. Modal residual OCR:  
   `MIB_CODE_SRC=worktrees/exp-conf-isotonic/src modal run solution/modal_app.py --action score-residual-ocr --run-name exp-conf-isotonic`

### Confidence formula

```
if reason != default_review:
    conf ← PATH_CONF[reason]   # full-train path rates, shrunken from 0/1
else:
    score ← feature ranking of P(correct | NEEDS_REVIEW dump-bin)
    conf  ← piecewise-linear isotonic map(score)  # monotone knots
    clamp to [0.06, 0.92]
```

| reason | conf |
|--------|-----:|
| finding_approved | 0.98 |
| finding_denied | 0.99 |
| finding_review | 0.96 |
| text_dq | 0.97 |
| flags_dq | 0.94 |
| extra_revoked | 0.96 |
| revoked / unpaid | 0.92 |
| transit7 | 0.90 |
| multi_review | 0.65 |
| short_text | 0.12 |
| default_review | feature isotonic (~0.10–0.84) |

**default_review feature score** (higher → more often true NR):

| signal | Δ score |
|--------|--------:|
| review-only risk_flags present | +1.5 |
| visa unknown | +0.9 |
| fee unknown / unpaid | +0.4 / +0.8 |
| fee paid / waived | −0.3 / −0.4 |
| n_fields ≤3 / ≤4 | +0.5 / +0.25 |
| n_fields ≥7 / ≥8 | −0.25 / −0.4 |
| missing name / arrival / species | +0.35 / +0.30 / +0.15 |
| complete paid clean (paid+≥7 fields+no risk) | −0.6 |
| thin text (&lt;200) | +0.15 |

Path rates from full-train OCR preds (`artifacts/modal_full_ocr`, n=1000). No case-id tables.

## Residual A/B (seg-v1, n=100, official scorer)

| system | total | extraction | classification | calibration | mean Brier | cat |
|--------|------:|-----------:|---------------:|------------:|-----------:|----:|
| modal_residual_ocr | 98.05 | 27.46 | 56.00 | 14.59 | 0.1352 | 0 |
| **exp-stamp-ocr (prior bar)** | **100.90** | 30.84 | 55.20 | **14.86** | 0.1286 | **0** |
| **exp-conf-isotonic** | **101.68** | 30.84 | 55.20 | **15.63** | **0.1092** | **0** |
| **Δ vs stamp** | **+0.78** | 0 | 0 | **+0.78** | −0.0194 | 0 |

Confusion **unchanged** vs stamp (labels only):

```
APPROVED→APPROVED 11 | APPROVED→NEEDS_REVIEW 17
DENIED→DENIED 30     | DENIED→NEEDS_REVIEW 22
NEEDS_REVIEW→DENIED 2 | NEEDS_REVIEW→NEEDS_REVIEW 18
```

### Calibration breakdown (residual)

| pred | n | acc | mean_conf (stamp) | mean_conf (iso) | mean_brier (stamp) | mean_brier (iso) |
|------|--:|----:|------------------:|----------------:|-------------------:|-----------------:|
| APPROVED | 11 | 1.00 | 0.88 | **0.98** | 0.0144 | **0.0004** |
| DENIED | 32 | 0.94 | 0.78 | **0.94** | 0.0887 | **0.0614** |
| NEEDS_REVIEW | 57 | 0.32 | 0.40 | **0.37** | 0.1730 | **0.1571** |

Lift drivers:

1. **Finding paths** → high empirical rates (APPROVED 0.98, DENIED finding 0.99, Finding:NR 0.96).
2. **Deny ladder** remapped to full-train path accuracy; weaker paths (`multi_review` 0.65) stay modest.
3. **default_review isotonic**: incomplete / unknown-visa / risk-flag packets get higher NR conf; complete paid-clean dump-bins get low conf (~0.10–0.20).

## Decision: **promote-candidate (cal only)**

- Residual total **101.68 > 100.90** with **cat == 0**.
- Pure calibration lift; extraction/classification flat vs stamp; **no adjudication label change**.
- Safe to merge `calibrate.py` + thin `pipeline`/`adjudicate` reason tags into `solution/` (merge owner). Keep stamp OCR separately if not already promoted. Do **not** rewrite residual.json.

## Risks

- Path rates fit full-train promote_ocr/stamp adjudicate behavior; if deny/approve rules change, recalibrate `PATH_CONF`.
- Residual `default_review` accuracy (~0.22) is lower than full-train (~0.36); isotonic center is slightly conservative on easy train packets.
- No case-id tables; no per-id confidence hardcoding.

## Artifacts

- `artifacts/exp-conf-isotonic/{eval,meta,predictions,case_scores,truth}.*`
- Code: `worktrees/exp-conf-isotonic/src/mib_solution/calibrate.py` (+ reason tags in `adjudicate.py`, wire in `pipeline.py`)
