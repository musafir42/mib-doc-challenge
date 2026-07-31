# Module ownership (Explore)

When fanning out experiments, assign non-overlapping edit scopes.

| Area | Paths | Notes |
|------|-------|--------|
| OCR preprocess | `solution/src/mib_solution/ocr.py` | deskew, stamp crops, PSM, red channel |
| Extract / evidence | `extract.py`, `evidence.py` | labeled fields, page roles, trusted text |
| Adjudicate | `adjudicate.py` | deny/approve/review policy only |
| Calibrate | `calibrate.py`, thin `pipeline.py` hooks | conf only; do not change labels |
| Packaging | `Dockerfile`, `run.sh`, `.dockerignore` | Ship-align only |

## Residual bar (current)

Beat **`promote_integrate` residual ~108.78 cat 0** (or document why a lower residual is acceptable for private robustness).

Score residual with local multi-process (see `solution/experiments/RESIDUAL.md`).  
Modal is **not** required.

Merge owner integrates after residual A/B on main.
