# exp-deskew

## Hypothesis

Many residual packets are scanned at 2–8° skew. Deskewing (projection-profile + Hough consensus) before the stamp-OCR path should improve glyph alignment for tesseract and lift residual primary above **100.90** without catastrophic false approvals.

## Method

- Worktree: `worktrees/exp-deskew/` — primarily `src/mib_solution/ocr.py`
- Farm: Modal Volume **`mib-data`**, action `score-residual-ocr`, run-name `exp-deskew`
- Code mount: `MIB_CODE_SRC=worktrees/exp-deskew/src`
- No case-id tables / label lookup; adjudicate/extract unchanged

### Final preprocess pipeline

| step | detail |
|------|--------|
| DPI | **275** (env `MIB_OCR_DPI`) |
| deskew | projection-profile variance max (−12…+12°, 0.5° step) + near-horizontal Hough median; consensus if \|Δ\|≤2.5°; apply only if \|angle\|≥**0.75°**, clamp ±15°; white border expand |
| full page | deskewed image; mild unsharp **only if rotated**; psm **6 + 11** |
| crops | top/bottom 25%, 4 corners ~30%, center band on **deskewed** page |
| crop preprocess | OpenCV CLAHE (fallback PIL contrast) — same as stamp-ocr |
| crop PSM | **6 + 11** |
| merge | unique line merge (casefold) |
| red boost | optional via `MIB_OCR_RED=1` (off in scored run) |

Pass count ≈ stamp-ocr (~16/page) + cheap deskew estimate.

### Failed A/B (v1 — do not ship)

Aggressive cleanup on top of deskew:

- full-page denoise + CLAHE + adaptive/Otsu binary variants
- red-boost on every stamp crop

**Result:** residual **97.03** / cat **0** — extraction raw **2667** (vs stamp 2776), classification **528** (vs 552). Binary/red noise overwrote good tokens and false-fired review paths. Kept deskew only for v2.

## Residual A/B (seg-v1, n=100, official scorer)

| system | primary | extraction | classification | calibration | catastrophic | notes |
|--------|--------:|-----------:|---------------:|------------:|-------------:|-------|
| modal_residual_text | 75.37 | 18.33 | 43.40 | 13.64 | 0 | text layer only |
| modal_residual_ocr | 98.05 | 27.46 | 56.00 | 14.59 | 0 | full-page psm6 @ 200 |
| **exp-stamp-ocr** | **100.90** | 30.84 | 55.20 | 14.86 | **0** | crops + CLAHE @ 275 |
| exp-deskew v1 (aggressive) | 97.03 | 29.63 | 52.80 | 14.60 | 0 | reject |
| **exp-deskew (final)** | **101.70** | **31.71** | 55.20 | **14.79** | **0** | **+0.80 vs stamp** |

Confusion vs stamp-ocr: **identical** (cls raw 552 both).

Extraction raw: **2776 → 2854** (+78). Gains concentrated on previously skewed pages (e.g. MIB-000747, MIB-000466, MIB-000030, MIB-000166, MIB-000676). Minor regressions on a few already-upright pages (over-deskew edge cases).

## Decision: **promote** (residual gate)

Residual primary **101.70 > 100.90** with **0** catastrophic. Pure OCR-path improvement (deskew before stamp crops). Ship path should keep projection+Hough deskew + stamp-ocr crop merge; avoid full-page adaptive/Otsu and unconditional red-boost unless gated.

## Risks

- False deskew on sparse/graphic pages (mitigated by 0.75° threshold + Hough consensus)
- INTER_CUBIC + unsharp adds slight cost; residual map finished under Modal 300s/case with 2 CPU
- Classification unchanged — deskew is an extraction lever here; further DQ-stamp recall needs red-gated crops or better stamp detectors

## Artifacts

- `artifacts/exp-deskew/{eval.json,meta.json,predictions.jsonl,case_scores.jsonl,truth.csv}`
- Baseline compare: `artifacts/exp-stamp-ocr/` (100.90 cat 0)
- Code: `worktrees/exp-deskew/src/mib_solution/ocr.py`
