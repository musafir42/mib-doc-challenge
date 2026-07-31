# MIB solution

Offline PDF intake pipeline for the MIB Doc Challenge.

**Current measured (official scorer):** residual ~**108.78** / train ~**119.27** /150, cat **0**  
(`artifacts/promote_integrate/`, `artifacts/promote_integrate_full/`).  
See repo `GROK_BUILD.md` and `artifacts/HANDOFF.md` for handoff to a high-CPU machine.

## Local run

```bash
uv sync
# directory of PDFs → predictions.jsonl
uv run mib-solution ../data/train ../artifacts/local_train/predictions.jsonl
```

Residual A/B (preferred before any full-train claim):

```bash
# from repo root
export MIB_WORKERS=$(nproc 2>/dev/null || echo 8)
# see experiments/RESIDUAL.md
```

## Docker (submission path)

```bash
docker build -t mib-submission .
docker run --rm --network none \
  --read-only --tmpfs /tmp:rw,nosuid,nodev,size=4g \
  --mount type=bind,src=/path/to/pdfs,dst=/input,readonly \
  --mount type=bind,src=/path/to/out,dst=/output \
  mib-submission /input /output/predictions.jsonl
```

`run.sh` forces temp/cache into `/tmp` so OCR works under challenge read-only root FS.

## Modules

| File | Role |
|------|------|
| `pipeline.py` | end-to-end predict |
| `ocr.py` | tesseract/poppler |
| `extract.py` | fields |
| `evidence.py` | page/precedence helpers |
| `adjudicate.py` | APPROVED / DENIED / NEEDS_REVIEW |
| `calibrate.py` | confidence only |

## Modal

Optional/legacy only (`modal_app.py`). Default compute is local multi-process or Docker on a high-CPU box.
