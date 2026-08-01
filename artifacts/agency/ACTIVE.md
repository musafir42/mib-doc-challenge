# Active agents

## Ship: paddle FT (submit path)
- Product default OCR: paddle (`solution/src/mib_solution/ocr_paddle.py`)
- Scores: residual **108.77** / full train **118.91** cat 0
- Docker: `mib-submission:paddle-ft` · lat40 ~5.71 s/PDF @2w · CLAHE=0
- Report: `artifacts/paddle-ft-v2/ship/SHIP_REPORT.md` · `solution/SHIP.md`
- Branch: `ship/paddle-ft` (commit/pack)

## Retired as submit target
- tesseract promote_p1 (still in tree as `MIB_OCR_ENGINE=tesseract` A/B)
