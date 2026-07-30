# MIB solution

Offline PDF intake pipeline for the MIB Doc Challenge.

## Local run

```bash
uv sync
uv run mib-solution data/train artifacts/baseline/predictions.jsonl
```

## Docker

```bash
docker build -t mib-submission .
docker run --rm --network none \
  --mount type=bind,src=/path/to/pdfs,dst=/input,readonly \
  --mount type=bind,src=/path/to/out,dst=/output \
  mib-submission /input /output/predictions.jsonl
```
