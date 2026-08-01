# Paddle FT ship status (submit target)

## Product
- Default OCR: **Paddle FT** (`ocr_paddle.py`), not tesseract
- Models: `solution/models/paddle/{rec,det,cls}` (~14 MiB) — best_ep5 rec
- Image: `mib-submission:paddle-ft` **0.60 GiB** (under 4 GiB)
- Defaults: workers=**2**, CLAHE=**0**, DPI=150, max_pages=4 (8 GiB box)

## Gates

| Gate | Result |
|------|--------|
| Residual | **108.77** /150 cat **0** (CLAHE=0 same as CLAHE=1) |
| Docker lat40 @2w CLAHE=0 | **5.71 s/PDF** wall (**PASS** ≤6) |
| Docker lat40 @2w CLAHE=1 | 6.27 s (fail) → CLAHE off default |
| Docker workers=3 | OOM on 8g |
| Host lat40 @4w | 2.64 s (needs ~20 GiB; not scoring box) |
| Docker smoke 5 PDF | PASS workers 1–2 |
| Full train n=1000 | **RUNNING** (`ship/train/`, W=2 CLAHE=0) |

## Key files
- `solution/src/mib_solution/ocr_paddle.py`
- `solution/src/mib_solution/ocr.py` (default paddle)
- `solution/Dockerfile`, `solution/run.sh`
- `solution/models/paddle/`

## Running
Full train PID in `artifacts/paddle-ft-v2/ship/train/train.pid` — expect ~5–6 s/PDF × 1000 / 2 workers ≈ **45–60 min**.
