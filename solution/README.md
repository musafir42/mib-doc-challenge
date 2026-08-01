# MIB solution — Paddle FT ship

Offline PDF intake pipeline for the MIB Doc Challenge.

**Product OCR:** PaddleOCR with fine-tuned rec + geometry region crops  
(`ocr_paddle.py`; default `MIB_OCR_ENGINE=paddle`).

**Current measured (official scorer, cat 0):**

| Split | Total /150 | Artifact |
|-------|------------|----------|
| Residual (seg-v1, n=100) | **108.77** | `artifacts/paddle-ft-v2/ship/residual_clahe0/` |
| Full train (n=1000) | **118.91** | `artifacts/paddle-ft-v2/ship/train/` |

Ship report: [`artifacts/paddle-ft-v2/ship/SHIP_REPORT.md`](../artifacts/paddle-ft-v2/ship/SHIP_REPORT.md)  
Ship notes: [`SHIP.md`](SHIP.md) · packaging checklist: [`PACKAGING.md`](PACKAGING.md)

> Historical tesseract integrate (residual ~108.78 / train ~119.27) is **not** the current product.  
> Tesseract remains as A/B only: `MIB_OCR_ENGINE=tesseract`.

## Local run

```bash
uv sync
# directory of PDFs → predictions.jsonl
export MIB_OCR_ENGINE=paddle
export MIB_PADDLE_MODELS="$PWD/models/paddle"
export MIB_OCR_CLAHE=0
export MIB_WORKERS=2
uv run mib-solution ../data/train ../artifacts/local_train/predictions.jsonl
```

Residual A/B (preferred before any full-train claim): see `experiments/RESIDUAL.md`.

## Docker (submission path)

Matches challenge evaluation (`EVALUATION.md` / `DOCKER_SUBMISSION.md` / `scripts/run_docker_submission.py`):

- **4 vCPU**, **8 GiB** RAM, **`--network none`**, read-only root, tmpfs `/tmp`
- Vendored models at `/app/models/paddle` (no runtime downloads)
- Defaults: `MIB_WORKERS=2`, `MIB_OCR_CLAHE=0`, `MIB_PADDLE_MODELS=/app/models/paddle`

```bash
cd solution
docker build --pull=false -t mib-submission:paddle-ft .

mkdir -p /tmp/mib-out
docker run --rm \
  --network none \
  --cpus 4 \
  --memory 8g \
  --pids-limit 512 \
  --read-only \
  --tmpfs /tmp:rw,nosuid,nodev,size=2g \
  --mount type=bind,src=/path/to/pdfs,dst=/input,readonly \
  --mount type=bind,src=/tmp/mib-out,dst=/output \
  mib-submission:paddle-ft /input /output/predictions.jsonl
```

Or via the challenge runner (same flags):

```bash
python3 scripts/run_docker_submission.py \
  --repo solution \
  --input-dir data/train \
  --output /tmp/mib-out/predictions.jsonl \
  --image-tag mib-submission:paddle-ft
```

### Ship env (baked into image / `run.sh`)

| Variable | Default | Notes |
|----------|---------|--------|
| `MIB_OCR_ENGINE` | `paddle` | `tesseract` for A/B only |
| `MIB_PADDLE_MODELS` | `/app/models/paddle` | `{rec,det,cls}` dirs |
| `MIB_WORKERS` | `2` | 3+ OOM on 8 GiB box |
| `MIB_OCR_CLAHE` | `0` | CLAHE=1 fails lat40 ≤6 s/PDF |
| `MIB_OCR_DPI` | `150` | |
| `MIB_OCR_MAX_PAGES` | `4` | |
| `OMP_THREAD_LIMIT` | `1` | avoid OpenMP oversubscription |

Measured: Docker lat40 ~**5.71 s/PDF** @2w CLAHE=0 (PASS ≤6); image ~**0.60 GiB** (limit 4 GiB).

## Modules

| File | Role |
|------|------|
| `pipeline.py` | end-to-end predict |
| `ocr_paddle.py` | **ship OCR** — Paddle FT + geometry regions |
| `ocr.py` | engine dispatch; tesseract fallback for A/B |
| `extract.py` | fields |
| `evidence.py` | page/precedence helpers |
| `adjudicate.py` | APPROVED / DENIED / NEEDS_REVIEW |
| `calibrate.py` | confidence only |
| `models/paddle/{rec,det,cls}/` | vendored offline models (~14 MiB) |

## Modal

Optional/legacy only (`modal_app.py`). Default compute is local multi-process or Docker on a high-CPU box.
