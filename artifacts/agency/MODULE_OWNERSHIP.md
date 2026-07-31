# Module ownership (latency ship Explore)

Non-overlapping edit scopes for concurrent worktrees.

| name | primary paths | may touch | do not touch |
|------|---------------|-----------|--------------|
| lat-dpi | `ocr.py` defaults DPI/max_pages only | env docs | adjudicate, extract, run.sh |
| lat-psm-lite | `ocr.py` PSM loops only | — | should_ocr, crops list, packaging |
| lat-crops-lite | `ocr.py` `_stamp_crops` + binarize branches | — | full-page PSM list, packaging |
| lat-select-ocr | `ocr.py` `should_ocr` + light `pipeline.py` hooks | — | stamp crop geometry, packaging |
| lat-tiered | `ocr.py` new lite path + `pipeline.py` routing | calibrate flags | adjudicate rules |
| lat-parallel-ship | `run.sh`, `cli.py`, `pipeline.predict_dir`/`run` | Dockerfile notes | OCR algorithm quality |

## Residual bar

- Prefer residual ≥ **104.45** cat 0 (no-cv2 floor) after cuts.
- Stretch: approach **108.78** with OpenCV present **and** 4CPU ≤6 s/PDF.
- Latency gate is hard for Ship-align even if residual dips slightly — document tradeoff.

## Compute

Local multi-process only. `MIB_WORKERS≤2` per Explore residual run. No Modal.
