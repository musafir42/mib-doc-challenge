# exp-deskew-v2

## Hypothesis

exp-deskew (pure deskew before stamp-OCR) lifted residual to **101.70** via extraction only. Stronger deskew (finer projection grid, lower apply threshold) plus **additive** crop binarize (Otsu/adaptive after CLAHE, never replacing natural full-page OCR) should recover more field tokens without the residual collapse seen when full-page binary replaced the natural image (deskew v1 reject at 97.03).

## Method

- Worktree: `worktrees/exp-deskew-v2/` — only `src/mib_solution/ocr.py` changed
- Farm: Modal Volume **`mib-data`**, action `score-residual-ocr`, run-name `exp-deskew-v2`
- Code mount: `MIB_CODE_SRC=worktrees/exp-deskew-v2/src`
- No case-id tables; adjudicate/extract unchanged

### Preprocess pipeline

| step | detail |
|------|--------|
| DPI | **275** (env `MIB_OCR_DPI`) |
| deskew | projection variance max (−12…+12°, **0.25°** step + half-step refine) + Hough median; consensus; apply if \|angle\|≥**0.55°** (v1 used 0.75° / 0.5° step); clamp ±15°; white border expand |
| full page | deskewed natural first (psm **6 + 11 + 4**); mild unsharp if rotated; full-page CLAHE psm 6 (no full-page binary) |
| crops | top/bottom 25%, 4 corners ~30%, center band on deskewed page; small crops upscaled ×1.5 |
| crop preprocess | CLAHE psm **6 + 11**, then **additive** Otsu psm 6; adaptive Gaussian psm 6 on edge/corner crops only |
| merge | unique line merge (casefold); natural OCR chunks ordered before binary so first-match extract prefers clean text |
| binarize toggle | env `MIB_OCR_BINARIZE` (default on) |

### Design lesson from deskew v1

Aggressive full-page denoise + Otsu/adaptive **as the primary image** dropped residual to **97.03**. v2 keeps natural deskewed OCR first and only **appends** binary crop passes for gap-fill.

## Residual A/B (seg-v1, n=100, official scorer)

| system | primary | extraction | classification | calibration | catastrophic | notes |
|--------|--------:|-----------:|---------------:|------------:|-------------:|-------|
| modal_residual_text | 75.37 | 18.33 | 43.40 | 13.64 | 0 | text layer only |
| modal_residual_ocr | 98.05 | 27.46 | 56.00 | 14.59 | 0 | full-page psm6 @ 200 |
| **exp-stamp-ocr** | **100.90** | 30.84 | 55.20 | 14.86 | **0** | bar for this exp |
| exp-deskew (aggressive binary) | 97.03 | 29.63 | 52.80 | 14.60 | 0 | reject |
| exp-deskew (final) | 101.70 | 31.71 | 55.20 | 14.79 | 0 | deskew only |
| **exp-deskew-v2** | **102.01** | **31.96** | 55.20 | **14.86** | **0** | **+1.11 vs stamp; +0.31 vs deskew** |

Confusion vs stamp-ocr / exp-deskew: **identical** (cls raw **552**, cat **0**).

Extraction raw: stamp **2776** → deskew **2854** → **v2 2876** (+100 vs stamp, +22 vs deskew).

Field exact-match count (9 extract fields × 100): stamp **557** → deskew **570** → v2 **575**.

Example extraction lifts vs deskew: fee_status (MIB-000034/058/440), home_world (MIB-000030/213/220), visa+purpose (MIB-000971), species (MIB-000570/717). Minor binary noise regressions on a few species/date glyphs (e.g. TRIANGULAN truncations) net positive overall.

## Decision: **promote** (residual gate)

Residual primary **102.01 > 100.90** with **0** catastrophic. Stronger deskew + selective additive crop binarize is a pure OCR-path win over stamp-ocr and a small further win over exp-deskew. Prefer this over deskew-only for ship if runtime budget allows (~extra crop Otsu/adapt passes).

## Risks

- More tesseract passes/page (full psm4 + CLAHE full + crop binary) → slower than stamp-ocr; residual map finished under Modal **300s**/case, 2 CPU, **0** errors
- Additive binary can still inject wrong first-match tokens when natural OCR missed the label entirely (observed small species/date regressions)
- Classification still flat vs stamp-ocr — graphic DQ stamps (biohazard seals, illegible redaction) remain out of reach of preprocess-only OCR
- Local tesseract occasionally recovered `TRANSIT-7` on MIB-000166; Modal farm did not — version/skew variance; do not depend on that path without farm confirmation

## Artifacts

- `artifacts/exp-deskew-v2/{eval.json,meta.json,predictions.jsonl,case_scores.jsonl,truth.csv}`
- Baselines: `artifacts/exp-stamp-ocr/` (100.90), `artifacts/exp-deskew/` (101.70)
- Code: `worktrees/exp-deskew-v2/src/mib_solution/ocr.py`
