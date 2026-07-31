# exp-uncertainty — honest uncertainty (Brier calibration)

## Hypothesis

Stamp-OCR residual (**100.90**) still wastes calibration points: fixed ladder confidences (0.35 dump-review, 0.58–0.90 deny) do not track whether the decision is likely correct. Mapping **adjudication path + packet features** to empirical correctness rates should lower mean Brier and raise calibration without changing labels or catastrophic count.

## Method

1. Read scorer: target = 1 if adj correct else 0;  
   `calibration_score = 20 * max(0, 1 − 2 · mean_brier)`.
2. Base pipeline = **exp-stamp-ocr** OCR (DPI 275 + stamp crops) so extraction/classification match 100.90.
3. New module `worktrees/exp-uncertainty/src/mib_solution/calibrate.py`.
4. `adjudicate._decide` tags `fields["_adj_reason"]` (decisions identical to stamp/promote_ocr).
5. `pipeline.predict_pdf` sets `_ocr_used`, `_page_count`, and  
   `confidence = calibrate(fields, adjudication, reason=…)`.
6. Modal residual OCR:  
   `MIB_CODE_SRC=worktrees/exp-uncertainty/src modal run solution/modal_app.py --action score-residual-ocr --run-name exp-uncertainty`

### Features → confidence

| feature | role |
|---------|------|
| `_adj_reason` / Finding present | path family (finding_* vs deny vs default_review) |
| `_ocr_used` | OCR-only thin packets → lower conf |
| `_text_len` / page-count proxy | thin / short-page → lower conf |
| field completeness (9 keys) | sparse packet → lower conf |
| risk_flags present | dump-review more often correct when risk present |
| unresolved conflicts (review-only flags) | mild boost for true review |
| adjudication type | APPROVED only via Finding; DENIED path rates |

### Confidence formula

```
if reason == short_text:
    conf ← 0.10

elif reason starts with finding_*:
    conf ← 0.98 (approved/denied) or 0.96 (finding_review)
    thin packet → −0.02; clamp [0.85, 0.99]

elif reason == default_review:
    if risk_flags present OR unresolved conflict flags:
        conf ← 0.58
        conflict → +0.04; fee unknown → +0.05; n_fields≥8 → +0.04
        thin → −0.06; clamp [0.05, 0.88]
    else:  # no structured risk — often missed A/D
        fee prior: unknown→0.34 | waived→0.20 | paid→0.22 | else→0.26
        thin → min(conf, 0.14); n_fields≥8 → −0.04
        ocr_used and thin → −0.03; text_len<200 → −0.03
        text_len>1200 and not ocr → +0.02
        clamp [0.05, 0.50]   # never high-conf dump review without risk

else:  # DENIED paths
    conf ← PATH_CONF[reason]
    thin → −0.10
    transit7/unpaid and n_fields≤6 → −0.04
    flags_dq/text_dq/multi_review and risk → +0.02
    text_dq and ocr and n_fields≤5 → −0.04
    clamp [0.05, 0.99]
```

| reason | base conf |
|--------|----------:|
| finding_approved / finding_denied | 0.98 |
| finding_review | 0.96 |
| text_dq | 0.96 |
| flags_dq | 0.94 |
| extra_revoked | 0.95 |
| revoked | 0.92 |
| unpaid / transit7 | 0.88 |
| multi_review | 0.62 |
| short_text | 0.12 / 0.10 |
| default_review | feature formula (~0.08–0.67) |

Path rates from full-train OCR (`artifacts/modal_full_ocr`, n=1000), with modest haircuts on transit/unpaid for stamp-OCR noise.

**Rule:** high confidence only when evidence is strong **and** decision is Finding-backed or clear structured deny; low when thin / OCR-only / default review.

## Residual A/B (seg-v1, n=100, official scorer)

| system | total | extraction | classification | calibration | mean Brier | cat |
|--------|------:|-----------:|---------------:|------------:|-----------:|----:|
| modal_residual_ocr | 98.05 | 27.46 | 56.00 | 14.59 | 0.1352 | 0 |
| exp-calib (prior) | 99.06 | 27.46 | 56.00 | 15.60 | 0.1099 | 0 |
| **exp-stamp-ocr** | **100.90** | **30.84** | 55.20 | 14.86 | 0.1286 | **0** |
| **exp-uncertainty** | **102.07** | **30.84** | **55.20** | **16.02** | **0.0995** | **0** |
| **Δ vs stamp-ocr** | **+1.17** | 0 | 0 | **+1.17** | −0.0291 | 0 |

Confusion **unchanged** vs stamp-ocr (decisions only):

```
APPROVED→APPROVED 11 | APPROVED→NEEDS_REVIEW 17
DENIED→DENIED 30     | DENIED→NEEDS_REVIEW 22
NEEDS_REVIEW→DENIED 2 | NEEDS_REVIEW→NEEDS_REVIEW 18
```

### Score breakdown

| section | stamp-ocr | exp-uncertainty | Δ |
|---------|----------:|----------------:|--:|
| extraction | 30.84 | 30.84 | 0 |
| classification | 55.20 | 55.20 | 0 |
| calibration | 14.86 | **16.02** | **+1.17** |
| **total** | 100.90 | **102.07** | **+1.17** |
| catastrophic | 0 | **0** | 0 |

### Per-class after uncertainty calib (residual)

| pred | n | acc | mean_conf | mean_brier |
|------|--:|----:|----------:|-----------:|
| APPROVED | 11 | 1.00 | 0.98 | 0.0007 |
| DENIED | 32 | 0.94 | 0.92 | 0.0475 |
| NEEDS_REVIEW | 57 | 0.32 | 0.34 | 0.1477 |

## Decision: **promote-candidate (cal only)**

- Residual total **102.07 > 100.90** with **cat == 0**.
- Pure calibration lift on stamp-OCR base; extraction/classification flat; no decision change.
- Safe to merge `calibrate.py` + thin `pipeline`/`adjudicate` reason tags into `solution/` **after** stamp-OCR promote (merge owner). Do **not** rewrite residual.json.
- No case-id tables; no per-id confidence hardcoding.

## Risks

- Path rates fit full-train promote_ocr behavior under stamp-OCR residual; if adjudication rules change, recalibrate PATH_CONF.
- Residual default_review accuracy (~0.22) is lower than full-train (~0.36); feature formula keeps no-risk conf modest.
- Risk-present boost uses full-train rate (~0.83) shrunk to ~0.58 base — residual risk cells are small-n.
- DENIED residual accuracy 0.94 (2 false denials from stamp OCR noise); conf slightly high on those errors.

## Artifacts

- `artifacts/exp-uncertainty/{eval,meta,predictions,case_scores,truth}.json*`
- Code: `worktrees/exp-uncertainty/src/mib_solution/calibrate.py`  
  (+ reason tags in `adjudicate.py`, wire in `pipeline.py`; OCR unchanged from stamp-ocr)
