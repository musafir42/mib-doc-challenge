# MIB solution — Paddle FT ship

Offline PDF intake for the MIB Doc Challenge. **Submit path = PaddleOCR FT.**

| Gate | Score |
|------|------:|
| Residual n=100 (clean policy) | **107.21**+ /150 cat 0 — see `docs/APPROACH.md` |
| Full train n=1000 | re-score after trusted-text fix — see `artifacts/ship/` |
| Docker lat40 (4c/8g, W=2) | **~5.71 s/PDF** (≤6) |

## Docs (repo knowledge)

| Doc | Contents |
|-----|----------|
| [`docs/APPROACH.md`](../docs/APPROACH.md) | Current ship approach, constraints, architecture, scores, run |
| [`docs/LESSONS.md`](../docs/LESSONS.md) | Campaign knowledge for future paddle improvements |

Challenge contracts: root `EVALUATION.md`, `DOCKER_SUBMISSION.md`.

## Docker

```bash
docker build -t mib-submission:paddle-ft .
docker run --rm --network none --cpus 4 --memory 8g --pids-limit 512 \
  --read-only --tmpfs /tmp:rw,nosuid,nodev,size=2g \
  -v /path/to/pdfs:/input:ro -v /path/to/out:/output \
  mib-submission:paddle-ft /input /output/predictions.jsonl
```

Defaults: `MIB_WORKERS=2`, `MIB_OCR_CLAHE=0`, models at `/app/models/paddle`.

## Layout

- `src/mib_solution/` — pipeline (OCR default: `ocr_paddle.py`)
- `models/paddle/{rec,det,cls}/` — offline weights (~14 MiB)
- `Dockerfile`, `run.sh` — submission entrypoint
