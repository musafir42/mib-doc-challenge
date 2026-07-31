# exp-deny-recall

## Hypothesis

Residual DENIED misses under stamp-region OCR still hide disqualifiers in
OCR-garbled adjudicator notes and risk stamps. An OCR-tolerant Finding parser
plus a light risk map for biohazard / embargo / warrant / tamper tokens should
raise DENIED recall without catastrophic false APPROVED.

## Method

- Worktree: `worktrees/exp-deny-recall/` — **`adjudicate.py` only** (OCR pipeline
  unchanged; inherits stamp-crop OCR from farm image + mounted code)
- Farm: Modal Volume **`mib-data`**, action `score-residual-ocr`,
  `MIB_CODE_SRC=worktrees/exp-deny-recall/src`, run-name `exp-deny-recall`
- No case-id tables; no full-train score (residual A/B only)

### Adjudication changes

| lever | what |
|-------|------|
| OCR-tolerant Finding DENIED | Accept `Finding`/`Fouing`/`Frdirg`/`Finis`/… + `DENIED`/`DEMED`/`DENED`/`Deny` |
| Strict Finding APPROVED | Only exact `Finding: APPROVED` (never promote OCR garbage to APPROVED) |
| Light OCR risk map | Fuzzy planetary_embargo / biohazard / active_warrant / memory_tampering; Embargo-home-world; disqualifying-risk-flag lines |
| Damaged-packet guard | `Packet contains damaged or contradictory…` → NEEDS_REVIEW (blocks OCR `unpaid` false deny) |
| Fee contradiction | `unpaid` + visible `waived`/`DIP-WAIVER` → review, not deny |
| Stale non-DIP arrival | arrival >180 days before 2026-07-07 for known non-DIP visas → DENIED |

## Residual A/B (seg-v1, n=100, official scorer)

| system | primary | extraction | classification | calibration | catastrophic | notes |
|--------|--------:|-----------:|---------------:|------------:|-------------:|-------|
| modal_residual_ocr | 98.05 | 27.46 | 56.00 | 14.59 | 0 | full-page psm6 @ 200 |
| exp-stamp-ocr | 100.90 | 30.84 | 55.20 | 14.86 | 0 | stamp crops; prior bar |
| **exp-deny-recall** | **104.87** | 30.84 | **58.90** | **15.12** | **0** | **+3.97 vs stamp bar** |

Confusion delta vs exp-stamp-ocr:

| cell | stamp OCR | deny-recall |
|------|----------:|------------:|
| DENIED→DENIED | 30 | **35** |
| DENIED→NEEDS_REVIEW | 22 | **17** |
| NEEDS_REVIEW→DENIED | 2 | **1** |
| APPROVED→APPROVED | 11 | 11 |
| cat false APPROVED | 0 | **0** |

Lift drivers: +5 correct DENIED (OCR Finding DEMED / Finis:Deny class + stale non-DIP arrivals); −1 false NR→DENIED via damaged-packet / unpaid guard. Extraction unchanged (adjudicate-only).

## Decision: **promote** (residual gate)

Residual primary **104.87 > 100.90** with **0** catastrophic. Deny-signal OCR map is policy-side only; safe to merge with stamp OCR path. Remaining ~17 DENIED misses are mostly non-OCR-able biohazard graphics, empty image pages, or fee/visa signals that never appear as recoverable text.

## Risks

- OCR variance (local vs Modal) can flip borderline Finding matches; patterns are intentionally multi-variant
- One residual NR→DENIED remains (OCR invents TRANSIT-7 on a rescinded packet) — classification cost small vs recall gain
- Stale-arrival rule depends on extracted arrival date quality
- Over-broad emb* fragments could false-deny if OCR hallucinates; train text-layer precision of map patterns is 1.0 for DENIED

## Artifacts

- `artifacts/exp-deny-recall/{eval.json,meta.json,predictions.jsonl,case_scores.jsonl,truth.csv}`
- Code: `worktrees/exp-deny-recall/src/mib_solution/adjudicate.py` (`ocr_risk_flags`, OCR Finding parser)
- Baselines: `artifacts/exp-stamp-ocr/`, `artifacts/modal_residual_ocr/`
