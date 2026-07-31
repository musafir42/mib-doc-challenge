# exp-psm-grid

## Hypothesis

exp-stamp-ocr (full-page psm 6+11 + stamp crops @ 275 DPI) still leaves residual extraction headroom. Running a multi-PSM tesseract ensemble over full-page modes **{3, 4, 6, 11, 12}** plus sparse-leaning crop modes **{6, 11, 12}**, then merging unique lines (casefold), should recover complementary layout/stamp tokens and lift residual primary above **100.90** with **cat 0**.

## Method

- Worktree: `worktrees/exp-psm-grid/` — **only** `src/mib_solution/ocr.py` changed
- Farm: Modal Volume **`mib-data`**, action `score-residual-ocr`, run-name `exp-psm-grid`
- Code mount: `MIB_CODE_SRC=worktrees/exp-psm-grid/src`
- Command:
  ```bash
  PATH=$HOME/.local/bin:$PATH MIB_CODE_SRC=worktrees/exp-psm-grid/src \
    modal run solution/modal_app.py --action score-residual-ocr --run-name exp-psm-grid
  ```
- No case-id tables / runtime label lookup

### OCR changes (`ocr.py`)

| knob | exp-stamp-ocr (bar) | exp-psm-grid |
|------|---------------------|--------------|
| DPI | 275 | **275** (env `MIB_OCR_DPI`) |
| full-page PSM | 6, 11 | **3, 4, 6, 11, 12** |
| crops | top/bottom 25%, 4 corners ~30%, center | same |
| crop preprocess | CLAHE / PIL contrast | same |
| crop PSM | 6, 11 | **6, 11, 12** |
| merge | unique lines (casefold) | unique lines (casefold) |
| tesseract | default | `--oem 3 --psm N` |
| env overrides | `MIB_OCR_DPI` | + `MIB_OCR_PSMS`, `MIB_OCR_CROP_PSMS` |

Passes/page ≈ 5 full + 7×3 crop = **26** (vs stamp-ocr **16**). Modal `predict_ocr` timeout 300s; residual map completed with **0** errors.

## Residual A/B (seg-v1, n=100, official scorer)

| system | primary | extraction | classification | calibration | catastrophic | notes |
|--------|--------:|-----------:|---------------:|------------:|-------------:|-------|
| modal_residual_ocr | 98.05 | 27.46 | 56.00 | 14.59 | 0 | full-page psm6 @ 200 |
| **exp-stamp-ocr** | **100.90** | 30.84 | 55.20 | 14.86 | **0** | stamp crops + psm 6/11 |
| **exp-psm-grid** | **101.90** | **31.84** | 55.20 | 14.86 | **0** | **+1.00 vs stamp bar** |

Confusion (psm-grid): identical class counts to stamp-ocr —

| cell | count |
|------|------:|
| APPROVED→APPROVED | 11 |
| APPROVED→NEEDS_REVIEW | 17 |
| DENIED→DENIED | 30 |
| DENIED→NEEDS_REVIEW | 22 |
| NEEDS_REVIEW→DENIED | 2 |
| NEEDS_REVIEW→NEEDS_REVIEW | 18 |

Lift driver: **extraction** 30.84 → **31.84** (+1.0 points / raw field recovery from extra PSM modes). Classification and calibration unchanged; **catastrophic 0**.

## Decision: **promote** (residual gate)

Residual primary **101.90 > 100.90** with **0** catastrophic. Pure OCR-path improvement (unique-line multi-PSM ensemble). Safe to promote into `solution/` OCR after merge-owner residual re-score; classification unchanged so no new deny/approve policy risk from this change alone.

## Risks

- ~26 tesseract passes/page → slower than stamp-ocr; residual finished under 300s, but full validation 5k may need worker budget check
- Extra OCR noise can still false-fire DQ phrases (same 2 NR→DENIED as stamp-ocr); multi-PSM did not worsen classification here
- PSM 12 (OSD) occasionally empty on crops — swallowed; full-page 3/4 add most unique form lines
- Some stamps remain non-OCR-able graphics

## Artifacts

- `artifacts/exp-psm-grid/{eval.json,meta.json,predictions.jsonl,case_scores.jsonl,truth.csv}`
- Baseline compare: `artifacts/exp-stamp-ocr/`, `artifacts/modal_residual_ocr/`
- Code: `worktrees/exp-psm-grid/src/mib_solution/ocr.py`
