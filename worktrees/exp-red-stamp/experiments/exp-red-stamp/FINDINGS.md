# exp-red-stamp

## Hypothesis

Red ink stamps (Finding notes, red-framed seals, pink “SAMPLE DENIAL” wash, wax seals) lose contrast when OCR runs on plain grayscale / CLAHE. Isolating red ink via `(2R−G−B)` fusion + HSV red mask, CLAHE on the hybrid, Lab-a alternate path, and upscaled red connected-component crops should recover more stamp/risk tokens than exp-stamp-ocr and lift residual primary without catastrophic false approvals.

## Method

- Worktree: `worktrees/exp-red-stamp/` — **only** `src/mib_solution/ocr.py` changed
- Farm: Modal Volume **`mib-data`**, action `score-residual-ocr`, run-name `exp-red-stamp`
- Code mount: `MIB_CODE_SRC=worktrees/exp-red-stamp/src`
- Command:

```bash
export PATH=$HOME/.local/bin:$PATH
cd REPO
MIB_CODE_SRC=worktrees/exp-red-stamp/src modal run solution/modal_app.py \
  --action score-residual-ocr --run-name exp-red-stamp
```

### OCR changes (`ocr.py`)

| knob | exp-stamp-ocr (100.90) | exp-red-stamp |
|------|------------------------|---------------|
| DPI | 275 | **280** |
| full page | psm 6+11 raw | raw **+ red-boost CLAHE** (psm 6+11); Lab-a if red_frac≥0.001 |
| band/corner crops | gray CLAHE | **red-boost CLAHE** psm 6+11 |
| adaptive regions | none | **red CC crops** (≤4), upscale 2–3×, CLAHE + red-binary |
| red math | none | `red_score=clip(2R−G−B)`; hybrid = gray·(1−s)+ (255−red)·s |
| merge | unique lines | same |

No case-id tables; no adjudicate/extract policy changes.

## Residual A/B (seg-v1, n=100, official scorer)

| system | primary | extraction | classification | calibration | catastrophic | notes |
|--------|--------:|-----------:|---------------:|------------:|-------------:|-------|
| modal_residual_ocr | 98.05 | 27.46 | 56.00 | 14.59 | 0 | full-page psm6 @ 200 |
| **exp-stamp-ocr** | **100.90** | **30.84** | 55.20 | **14.86** | **0** | prior stamp crops |
| **exp-red-stamp** | **101.10** | 30.54 | **55.80** | 14.76 | **0** | **+0.20 vs stamp; cat 0** |

Confusion delta vs exp-stamp-ocr:

| cell | stamp-ocr | red-stamp |
|------|----------:|----------:|
| DENIED→DENIED | 30 | **31** |
| DENIED→NEEDS_REVIEW | 22 | **21** |
| NEEDS_REVIEW→DENIED | 2 | 2 |
| APPROVED→APPROVED | 11 | 11 |
| cat false APPROVED | 0 | **0** |

Lift driver: classification raw **552 → 558** (+6) from one additional correct DENIED (MIB-000283 NR→DENIED). Extraction raw **2776 → 2749** (−27; red paths add some field noise) but classification gain outweighs. Calibration slightly down (Brier 0.129 → 0.131).

Notable local diagnostics (not id-memorized rules): red-boost recovers `Finding: DENIED` / `Observed flags: biohazard_red` on pages where grayscale already works; graphic-only biohazard seals (no OCR-able glyphs) remain hard (e.g. residual biohazard cases without text still miss).

## Decision: **promote** (residual gate)

Residual primary **101.10 > 100.90** with **0** catastrophic. Pure OCR-path improvement (red-channel preprocess + red CC crops). Worth merging into stamp OCR stack; watch extraction noise on full-train if promoted.

## Risks

- More tesseract passes/page (full red + CC crops) → slower than stamp-ocr; residual map finished under Modal 300s / 2 CPU
- Extra red OCR noise can corrupt field tokens (net extraction −0.3 pts) or reinforce watermark “SAMPLE DENIAL” (not a Finding; policy already ignores)
- Graphic-only red seals without text still non-OCR-able — do not invent `biohazard_red` from red blobs alone

## Artifacts

- `artifacts/exp-red-stamp/{eval.json,meta.json,predictions.jsonl,case_scores.jsonl,truth.csv}`
- Baseline compare: `artifacts/exp-stamp-ocr/`, `artifacts/modal_residual_ocr/`
- Code: `worktrees/exp-red-stamp/src/mib_solution/ocr.py`
