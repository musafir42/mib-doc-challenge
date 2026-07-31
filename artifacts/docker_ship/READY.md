# Docker Ship-align readiness

**Status: READY** (smoke only — not a full train/validation Ship-align win)

## Image

| Field | Value |
|-------|--------|
| Tag | `mib-submission:latest` |
| Image ID | `sha256:8ace24e366badc9c5392cfac2b7fbb5b9f557cfeaf344817adcd3b52c14e3563` |
| Uncompressed size (`docker image inspect .Size`) | **106,338,655 bytes ≈ 0.099 GiB** |
| Human (`docker images`) | ~435 MB (compressed/display) |
| Limit | 4 GiB uncompressed |
| Limit check | **PASS** (~40× under budget) |

Built from:

```bash
docker build -t mib-submission:latest solution/
```

Contents: `python:3.12-slim` + `tesseract-ocr` + `poppler-utils` + `pip install .` from `solution/pyproject.toml` (deps: pypdf, pdf2image, pillow, pytesseract). Offline-capable; no runtime network.

## Entrypoint contract

```text
<input_pdf_dir> <output_predictions_path>
```

`solution/run.sh` → `mib-solution` CLI.

## Smoke run (challenge flags)

**10 train PDFs** (`MIB-000001` … `MIB-000010`).

```bash
mkdir -p /tmp/mib-in /tmp/mib-out
# copy 10 pdfs from data/train into /tmp/mib-in
docker run --rm --network none --cpus 4 --memory 8g --pids-limit 512 \
  --read-only --tmpfs /tmp:rw,nosuid,nodev,size=2g \
  -v /tmp/mib-in:/input:ro -v /tmp/mib-out:/output \
  mib-submission:latest /input /output/predictions.jsonl
```

| Metric | Value |
|--------|--------|
| Exit | 0 |
| Predictions written | 10 |
| Wall time | **51.76 s** for 10 PDFs |
| ≈ s/PDF | **~5.18 s** (under 6 s/PDF budget) |
| Network | none |
| Root FS | read-only + tmpfs `/tmp` 2g |

## Validate + score

```bash
python3 scripts/validate_submission.py \
  --submission /tmp/mib-out/predictions.jsonl \
  --pdf-dir /tmp/mib-in \
  --require-complete
# → Valid submission records: 10; Missing expected case ids: 0

python3 scripts/evaluate.py \
  --truth artifacts/docker_ship/truth10.csv \
  --submission /tmp/mib-out/predictions.jsonl \
  --output-json artifacts/docker_ship/eval_smoke10.json \
  --case-scores-jsonl artifacts/docker_ship/case_scores_smoke10.jsonl
```

### Smoke score (10 cases, filtered train truth)

| Component | Score |
|-----------|--------|
| Extraction | **45.33 / 50** |
| Classification | **74.00 / 80** |
| Calibration | **12.79 / 20** |
| Missing penalty | 0.00 |
| **Total** | **132.13 / 150** |
| Catastrophic false approvals | 0 |

Confusion:

- `APPROVED→APPROVED`: 1
- `APPROVED→NEEDS_REVIEW`: 1
- `DENIED→DENIED`: 3
- `NEEDS_REVIEW→NEEDS_REVIEW`: 5

Artifacts:

- `artifacts/docker_ship/predictions_smoke10.jsonl`
- `artifacts/docker_ship/truth10.csv`
- `artifacts/docker_ship/eval_smoke10.json`
- `artifacts/docker_ship/case_scores_smoke10.jsonl`

## /tmp OCR under `--read-only` (fixed)

Challenge mounts root read-only and only allows writable **`/tmp`** (tmpfs). Packaging fixes applied:

1. **`solution/run.sh`** — force temp/cache into `/tmp`:
   - `TMPDIR` / `TEMP` / `TMP` = `/tmp`
   - `HOME` = `/tmp`
   - `XDG_CACHE_HOME` = `/tmp/.cache`
   - `TESSDATA_PREFIX` defaulted for system tessdata
2. **`solution/src/mib_solution/ocr.py`** — `pdf2image.convert_from_path(..., output_folder=TMPDIR or "/tmp")` so raster intermediates never hit a non-writable `/app`.
3. **`solution/.dockerignore`** — exclude `.venv`, `__pycache__`, `modal_app.py`, experiments from build context (keeps image lean; does not change product logic).

Smoke with `--read-only --tmpfs /tmp` completed without write errors → OCR/temp path is good.

## Not claimed here

- Full 1,000-PDF train Docker eval (Ship-align full win)
- Validation / private test
- Explore promote merges

When Explore lands, rebuild tag and re-smoke; this packaging contract should stay green.

## Rebuild checklist for Ship-align

```bash
docker build -t mib-submission:latest solution/
docker image inspect mib-submission:latest --format '{{.Size}}'  # must be < 4 GiB
# then full train bind as in DOCKER_SUBMISSION.md / scripts/run_docker_submission.py
```
