# Binding stage

Date: 2026-07-30  
Baseline train: **98.88 / 150** (ext 37.39, cls 49.67, cal 11.83, cat 0)

## Diagnostics (full train, official scorer)

| Check | total | extraction | classification | calibration | cat |
|-------|------:|-----------:|---------------:|------------:|----:|
| Oracle labels (gold fields + gold adj, conf=1) | 150.00 | 50.00 | 80.00 | 20.00 | 0 |
| Label-only + **current** adjudicate rules | 117.63 | 50.00 | 55.64 | 11.99 | 0 |
| Cheap defaults (filename id, all NEEDS_REVIEW) | 50.77 | 4.95 | 36.80 | 9.02 | 0 |
| Baseline extract + **oracle** adjudication | **136.99** | 37.39 | 80.00 | 19.60 | 0 |
| Oracle extract + always NEEDS_REVIEW | 98.54 | 50.00 | 36.80 | 11.74 | 0 |
| **Baseline (measured)** | **98.88** | 37.39 | 49.67 | 11.83 | 0 |

Artifacts: `artifacts/ceiling/*_eval.json`, `summary.json`.

## Error taxonomy (baseline × labels)

- **Classification:** 498 correct; 487 conservative_review (mostly APPROVED→NEEDS_REVIEW and DENIED→NEEDS_REVIEW); 0 catastrophic.
- **Missed DENIED:** 204. Of those, 99 have `risk_flags=none` (deny reasons not captured by DQ-flag path). 68 have DQ flags in labels that never appear in the text layer (stamp/image only); some registry text says `EMBARGO REVIEW` without `planetary_embargo` token.
- **Extraction miss rates (worst):** purpose 46%, fee 36%, home_world 33%, name 29%, risk 21%, sponsor 20%, visa 20%.
- **Extract-poor cases:** 97 (ext_frac < 0.35); empty/image-first pages common.

## Label-only decision

With **perfect structured inputs**, current deny-only adjudicate scores **55.64 / 80** classification (total 117.63).  
→ Policy rules are **incomplete** even with gold fields: missing non-flag deny reasons and any safe APPROVED path.

## Cheap path

Minimal reading (defaults + NEEDS_REVIEW): **50.77 / 150**. Baseline’s text-layer extract is already worth ~+48 points over pure defaults.

## Conclusion: binding stage

**Primary binding: adjudication / decision policy** under trusted fields  
(baseline extract + oracle adj → **137**, +38 vs baseline; gold fields + current rules only reach cls 55.6/80).

**Secondary binding: field extraction / trusted signal recovery**  
(ext 37/50; many risk and identity signals only in images or non-label phrasing like `EMBARGO REVIEW`).

**Not binding yet:** calibration alone (moves with adjudication correctness).

## Therefore we invest next in

1. **Adjudication expansion (safe):** map secondary trusted signals → DENIED / NEEDS_REVIEW; learn APPROVED only when multi-field clean; never increase catastrophic false approvals.
2. **Extraction quality:** robust Label\\nValue parsing, multi-page merge, fee/purpose/home/name; registry status → risk_flags.
3. **OCR / vision path (stretch):** only if residual A/B shows text-layer ceiling on risk stamps.

Residual freeze: `artifacts/residual.json` version **seg-v1** (n=100 hard failures).
