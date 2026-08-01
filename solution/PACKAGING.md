# Packaging checklist — Paddle FT ship

Short pre-submit checklist for the offline Docker submission.

## Required files (in `solution/`)

- [ ] `Dockerfile` — builds offline-capable image; `ENTRYPOINT` → `run.sh`
- [ ] `run.sh` — accepts `<input_pdf_dir> <output_predictions_path>`
- [ ] `pyproject.toml` + `src/mib_solution/` — pipeline package
- [ ] `README.md` — scores, Docker flags, env
- [ ] `SHIP.md` — ship notes / pointer to report
- [ ] `models/paddle/rec/` — FT rec (`inference.pdmodel`, `inference.pdiparams`, `en_dict.txt`, …)
- [ ] `models/paddle/det/` — detection inference
- [ ] `models/paddle/cls/` — angle cls inference

Do **not** remove tesseract fallback in `ocr.py` (A/B via `MIB_OCR_ENGINE=tesseract`).

## Model dirs

```text
solution/models/paddle/
  rec/   # fine-tuned PP-OCRv4 rec (best_ep5)
  det/   # stock det
  cls/   # stock cls
```

- Individual model artifact ≤ **250 MiB** (largest rec params ~7.3 MiB)
- Total models ≤ **1 GiB** (tree ~**14 MiB**)
- Image must `COPY models /app/models` and set `MIB_PADDLE_MODELS=/app/models/paddle`
- No hub/download at runtime — network is `none`

## Offline build

```bash
cd solution
docker build --pull=false -t mib-submission:paddle-ft .
```

Build may use network for base image + `pip install`. Runtime must not.

## Size limits (EVALUATION / DOCKER_SUBMISSION)

| Limit | Budget | Ship |
|-------|--------|------|
| Uncompressed image | ≤ 4 GiB | ~0.60 GiB (`mib-submission:paddle-ft`) |
| Per model file | ≤ 250 MiB | OK |
| Total models | ≤ 1 GiB | ~14 MiB |
| Latency | ≤ 6 s/PDF avg @ 4 vCPU / 8 GiB | ~5.71 s (lat40, W=2, CLAHE=0) |

## Eval runtime flags (must match)

```bash
docker run --rm \
  --network none \
  --cpus 4 \
  --memory 8g \
  --pids-limit 512 \
  --read-only \
  --tmpfs /tmp:rw,nosuid,nodev,size=2g \
  --mount type=bind,src=…/pdfs,dst=/input,readonly \
  --mount type=bind,src=…/out,dst=/output \
  mib-submission:paddle-ft /input /output/predictions.jsonl
```

Env (image defaults): `MIB_WORKERS=2`, `MIB_OCR_CLAHE=0`, `MIB_PADDLE_MODELS=/app/models/paddle`.

## Smoke test

```bash
# 1) Models present
test -f models/paddle/rec/inference.pdiparams
test -f models/paddle/det/inference.pdmodel
test -f models/paddle/cls/inference.pdmodel

# 2) Build
docker build --pull=false -t mib-submission:paddle-ft .

# 3) Offline smoke (few PDFs)
mkdir -p /tmp/mib-smoke-out
docker run --rm --network none --cpus 4 --memory 8g --pids-limit 512 \
  --read-only --tmpfs /tmp:rw,nosuid,nodev,size=2g \
  --mount type=bind,src="$(pwd)/../data/train",dst=/input,readonly \
  --mount type=bind,src=/tmp/mib-smoke-out,dst=/output \
  mib-submission:paddle-ft /input /output/predictions.jsonl
# Prefer a small PDF subset bind-mount for speed; full train is the score gate.

# 4) Validate + score (repo root)
python3 scripts/validate_submission.py --submission /tmp/mib-smoke-out/predictions.jsonl
python3 scripts/evaluate.py \
  --truth data/train_labels.csv \
  --submission /tmp/mib-smoke-out/predictions.jsonl \
  --output-json /tmp/mib-smoke-out/eval.json
```

## Ship scores (gates)

| Gate | Score | Cat |
|------|-------|-----|
| Residual CLAHE=0 | **108.77** | 0 |
| Full train n=1000 | **118.91** | 0 |

Details: `../artifacts/paddle-ft-v2/ship/SHIP_REPORT.md` · `../artifacts/paddle-ft-v2/ship/MANIFEST.txt`
