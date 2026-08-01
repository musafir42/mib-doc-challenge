# Trusted-text adversarial fix

## Changes
- Adjudicate uses `_trusted_text` (no decoy pages)
- Extract free-form fallbacks use `trusted_corpus` only
- No decoy page last-resort in `iter_pages_for_field`
- `should_ocr` strips answer-key lines before Finding probe
- Fee bare paid/waived only on fee/form/finding pages

## Residual after fix (vs anti-overfit clean 107.21)
| | Total | Class | Extract | Calib | Cat |
|--|------:|------:|--------:|------:|----:|
| Anti-overfit only | 107.21 | 55.90 | 35.06 | 16.25 | 0 |
| **+ trusted text** | **104.22** | 54.10 | 33.83 | 16.28 | **0** |

## Full train (n=1000, CLAHE=0, W=2)
| | Total | Class | Extract | Calib | Cat | s/PDF |
|--|------:|------:|--------:|------:|----:|------:|
| Prior brittle policy | **118.91** | 60.74 | 43.48 | 14.68 | 0 | ~4.06 |
| **+ anti-overfit + trusted text** | **114.01** | 57.85 | 40.77 | 15.40 | **0** | ~4.17 |

Delta vs prior full train **−4.90** (class −2.89 · extract −2.72 · calib +0.72).  
Delta residual vs anti-overfit-only **−2.99** (104.22 vs 107.21).

Trade: lower proxy score, stronger anti-injection / EVAL alignment. Cat still **0**.

Artifacts: `train_eval.json`, `train_timing.json`, `TRAIN_READY`, `train_run.log` (FULL_TRAIN).
