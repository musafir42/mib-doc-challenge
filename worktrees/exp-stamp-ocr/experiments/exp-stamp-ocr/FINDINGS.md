# exp-stamp-ocr

## Hypothesis

Full-page tesseract @ 200 DPI (modal_residual_ocr) still misses small / low-contrast DQ stamps. Rasterizing at ~275 DPI, OCR’ing stamp-prone crops (top/bottom 25%, four corners ~30%, center band) with CLAHE contrast boost and dual PSM (6 + 11), then merging unique lines, should recover more risk/finding tokens and lift residual score without catastrophic false approvals.

## Method

- Worktree: `worktrees/exp-stamp-ocr/` — only `src/mib_solution/ocr.py` changed
- Farm: Modal Volume **`mib-data`**, action `score-residual-ocr`, run-name `exp-stamp-ocr`
- Code mount: `MIB_CODE_SRC=worktrees/exp-stamp-ocr/src`
- Pipeline still merges OCR via `merge_text_layers` (unchanged)

### OCR changes (`ocr.py`)

| knob | baseline residual OCR | exp-stamp-ocr |
|------|----------------------|---------------|
| DPI | 200 | **275** (env `MIB_OCR_DPI` override) |
| full page | psm 6 only | psm **6 + 11** |
| crops | none | top/bottom 25%, 4 corners ~30%, center band |
| preprocess | none | OpenCV CLAHE (fallback PIL contrast) on crops |
| crop PSM | n/a | **6 + 11** per crop |
| merge | page concat | unique line merge (casefold) |

## Residual A/B (seg-v1, n=100, official scorer)

| system | primary | extraction | classification | calibration | catastrophic | notes |
|--------|--------:|-----------:|---------------:|------------:|-------------:|-------|
| modal_residual_text | 75.37 | 18.33 | 43.40 | 13.64 | 0 | text layer only |
| **modal_residual_ocr** | **98.05** | 27.46 | **56.00** | 14.59 | **0** | full-page psm6 @ 200 |
| **exp-stamp-ocr** | **100.90** | **30.84** | 55.20 | **14.86** | **0** | **+2.85 vs residual OCR** |

Confusion delta vs modal_residual_ocr:

| cell | baseline OCR | stamp OCR |
|------|-------------:|----------:|
| DENIED→DENIED | 29 | **30** |
| DENIED→NEEDS_REVIEW | 23 | 22 |
| APPROVED→APPROVED | 11 | 11 |
| APPROVED→NEEDS_REVIEW | 17 | 17 |
| NEEDS_REVIEW→NEEDS_REVIEW | 20 | 18 |
| NEEDS_REVIEW→DENIED | 0 | 2 |

Lift drivers: extraction raw **2471 → 2776** (+305); one additional correct DENIED (e.g. MIB-000074, MIB-000151). Classification slightly down (−0.8) from two NR→DENIED false denials + one DENIED regression (MIB-000166), still net primary up and **cat 0**.

## Decision: **promote** (residual gate)

Residual primary **100.90 > 98.05** with **0** catastrophic. Stamp-region OCR is a pure OCR-path improvement (no case-id tables). Ship path should keep higher DPI + crop merge; consider trimming crop count or pages if runtime budget tightens on full validation.

## Risks

- ~16 tesseract passes/page (2 full + 7 crops × 2 PSM) → slower than baseline OCR; residual map finished under Modal 300s timeout with 2 CPU
- Extra OCR noise can false-fire DQ phrases (2 NR→DENIED) or overwrite better field tokens (minor extraction regressions on a few cases)
- Some stamps remain non-OCR-able graphics (e.g. prior biohazard smoke misses)

## Artifacts

- `artifacts/exp-stamp-ocr/{eval.json,meta.json,predictions.jsonl,case_scores.jsonl,truth.csv}`
- Baseline compare: `artifacts/modal_residual_ocr/`
- Code: `worktrees/exp-stamp-ocr/src/mib_solution/ocr.py`
