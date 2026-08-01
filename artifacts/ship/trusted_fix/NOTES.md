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

Trade: lower proxy score, stronger anti-injection / EVAL alignment.
Full train: see train_eval.json when TRAIN_READY.
