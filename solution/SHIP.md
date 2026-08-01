# Ship: Paddle FT

**Full report:** [`artifacts/paddle-ft-v2/ship/SHIP_REPORT.md`](../artifacts/paddle-ft-v2/ship/SHIP_REPORT.md)

## Status (submit path)

| Gate | Result |
|------|--------|
| Residual (seg-v1 n=100) | **108.77** /150 · cat **0** |
| Full train (n=1000) | **118.91** /150 · cat **0** |
| Docker lat40 @2w CLAHE=0 | **5.71 s/PDF** · PASS ≤6 |
| Image | `mib-submission:paddle-ft` · **0.60 GiB** · under 4 GiB |

Vs history: ship tesseract Docker **116.07** · tesseract P1 **118.77** · integrate **119.27**.

## Product defaults

- OCR: **Paddle** FT rec (`best_ep5`) + stock det/cls + geometry region crops  
  (`src/mib_solution/ocr_paddle.py`; default via `ocr.py`)
- Models: `models/paddle/{rec,det,cls}` (~14 MiB)
- P1 `should_ocr` retained (skip only with Finding/DQ + solid structure)
- Docker/runtime: **workers=2**, **CLAHE=0**, DPI=150, max_pages=4, OMP=1
- Ban list in OCR path: no typo banks / SPN denylists / residual case specials

## Build & run

```bash
docker build -t mib-submission:paddle-ft .
docker run --rm --network none --cpus 4 --memory 8g \
  --read-only --tmpfs /tmp:rw,nosuid,nodev,size=2g \
  -v /path/to/pdfs:/input:ro -v /path/to/out:/output \
  mib-submission:paddle-ft /input /output/predictions.jsonl
```

Measured eval artifacts: `artifacts/paddle-ft-v2/ship/{residual_clahe0,train}/eval.json`.

## Not done

- Validation 5k Docker score
- Docker full-train n=1000 confirm (host train 118.91 + Docker lat40 stand in)
- Synth retrain v2 unfinished; ship uses best_ep5
