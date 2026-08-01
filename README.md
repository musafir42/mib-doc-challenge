# MIB Doc Challenge

Offline PDF intake / adjudication under strict Docker limits (4 vCPU, 8 GiB, ≤6 s/PDF, no network, no LLMs/VLMs).

## Knowledge (this campaign)

| Doc | Purpose |
|------|---------|
| **[`docs/APPROACH.md`](docs/APPROACH.md)** | What we ship (Paddle FT), why, constraints, scores, how to run |
| **[`docs/LESSONS.md`](docs/LESSONS.md)** | Prior experiments & lessons for future paddle improvements |

## Product

Submit tree: **`solution/`** (Paddle FT OCR default).

```bash
cd solution && docker build -t mib-submission:paddle-ft .
```

See `docs/APPROACH.md` for full gates and run flags.

## Challenge references

| File | Role |
|------|------|
| `EVALUATION.md` | Scoring, limits, allowed/banned models |
| `DOCKER_SUBMISSION.md` | Image contract |
| `PRD.md` / `FIELD_MANUAL.md` | Task / fields |
| `scripts/evaluate.py` | Official scorer |

## Branch

Ship work lives on **`ship/paddle-ft`** (Paddle FT product + docs).
