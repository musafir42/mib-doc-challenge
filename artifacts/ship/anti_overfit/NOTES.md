# Anti-overfit policy cleanup

**Date:** 2026-08-01  
**Goal:** Prefer generalization / maintainable rules over train-texture points.

## Code changes
- No `EXTRA_REVOKED_SPONSORS` (manual SPN-0007/0139/4040 only)
- No OCR garble risk pattern bank
- Clean Finding regex only
- Fuzzy extract max_dist 1
- Adjudicate returns reason for calibrate
- CLAHE default 0 in ocr_paddle

## Residual (n=100, W=2, CLAHE=0)

| | Total | Class | Extract | Calib | Cat |
|--|------:|------:|--------:|------:|----:|
| Before (brittle) | 108.77 | 58.30 | 35.20 | 15.27 | 0 |
| **After (clean)** | **107.21** | 55.90 | 35.06 | 16.25 | **0** |

Full train re-score: see `train_eval.json` when `TRAIN_READY` exists.
