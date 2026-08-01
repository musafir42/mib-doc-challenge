# Approach — Paddle FT ship

**Submit product:** offline PaddleOCR with fine-tuned recognition + geometry region crops  
**Branch:** `ship/paddle-ft` · **Default engine:** `MIB_OCR_ENGINE=paddle`  
**Score scale:** /150 · residual = frozen hard subset (seg-v1 n=100) · full train n=1000  

---

## 1. What we ship

| Gate | Result |
|------|--------|
| Residual (anti-overfit clean policy) | **107.21** /150 · cat **0** |
| Residual (prior brittle policy, reference) | 108.77 /150 · cat 0 |
| Full train (prior brittle policy) | **118.91** /150 · cat **0** |
| Full train (anti-overfit clean) | *re-score in progress* → `artifacts/ship/anti_overfit/` |
| Docker latency (lat40 @2w, CLAHE=0, 4c/8g) | **~5.71 s/PDF** · **PASS** (≤6 s) |
| Image | `mib-submission:paddle-ft` · **~0.60 GiB** (≤4 GiB) |
| Models | ~**14 MiB** under `solution/models/paddle/` |

**Comparators:** tesseract P1 full train **118.77** · lean docker tess **116.07** · historical integrate **119.27**.

Policy was cleaned for generalization (see `docs/LESSONS.md` and `artifacts/ship/OVERFIT_CRITIQUE.md`): drop train-mined EXTRA SPNs, OCR garble risk maps, and Finding typo banks. Residual dropped **−1.56** (mostly class) with **cat still 0** — intentional trade for maintainability.

---

## 2. Why this approach

1. **Challenge forbids LLMs/VLMs** at runtime; offline OCR + candidate-trained models are allowed (`EVALUATION.md`).
2. **Tesseract multi-PSM + stamp crops** scored well but is brittle (typo regexes, many passes) and latency-heavy; lean skips for speed hurt full train (116.07).
3. **Paddle stock** was fast but weak on residual (**97.7**); **fine-tuned rec + fixed geometry crops** recovered residual **108.77** without a typo-bank OCR path.
4. **Policy stays in code** (enums, Finding strict APPROVED, cat-safe rules, P1 `should_ocr`); **perception stays in the model** + geometry—not residual case-id tables.

---

## 3. Constraints (non-negotiable)

| Constraint | Limit |
|------------|--------|
| Box | **4 vCPU / 8 GiB**, CPU only |
| Network | **`--network none`** at score time |
| Latency | **≤6 s/PDF** average; hard cap 30k s on 5k val |
| Image | **≤4 GiB** uncompressed |
| Models | ≤250 MiB each · **≤1 GiB** total |
| Allowed | Offline OCR, CV, rules, small task-specific / candidate-trained |
| Forbidden | LLMs, VLMs, foundation multimodal, cloud OCR APIs |

---

## 4. Architecture

```
PDF → text layer → should_ocr (P1)
                 → if OCR: paddle full-page + geometry crops
                 → extract → adjudicate → calibrate → prediction
```

### Selective OCR (P1)

Skip heavy OCR **only** when the text layer already has **Finding and/or DQ** plus solid structure.  
Ultra-rich forms **without** Finding/DQ still OCR (recovers stamp class losses from the lean ship).

### Perception

| Piece | Choice |
|-------|--------|
| Det / angle cls | Stock PP-OCR mobile (vendored) |
| Rec | **Fine-tuned** `best_ep5` (val acc ~0.845 @ epoch 5) |
| Geometry | Fixed fractions: top/bottom bands, 4 corners, center stamp band |
| DPI / pages | **150** / **4** |
| CLAHE | **Off** by default (latency; residual unchanged) |

### OCR ban list (keep non-brittle)

Do **not** add to the paddle OCR path: typo banks (`Fouing`, `DEMED`, …), SPN denylists, residual case_id specials, multi-PSM tesseract ensembles.

### Runtime knobs (8 GiB box)

| Knob | Default | Why |
|------|---------|-----|
| `MIB_WORKERS` | **2** | W=3+ OOM with Paddle on 8g |
| `MIB_OCR_CLAHE` | **0** | CLAHE=1 → ~6.27 s/PDF (fail lat) |
| OMP / MKL / OpenBLAS | **1** | Avoid OpenMP thrash under process pool |

Host @4 workers can look faster (~2.6 s/PDF) but needs ~20 GiB aggregate RSS—not the scoring box.

---

## 5. Product layout

```text
solution/
  Dockerfile          # offline paddle image
  run.sh              # entrypoint + env defaults
  pyproject.toml
  models/paddle/{rec,det,cls}/
  src/mib_solution/
    ocr_paddle.py     # ship OCR
    ocr.py            # P1 gate + engine switch (tesseract A/B only)
    pipeline.py extract.py adjudicate.py calibrate.py evidence.py cli.py
```

Evidence snapshots (metrics only): `artifacts/ship/{residual_eval,train_eval,train_timing,docker_lat40}.json`.

---

## 6. Score breakdown

**Residual (CLAHE=0):** extract 35.20 · class 58.30 · calib 15.27 · total **108.77** · cat 0  

**Full train:** extract 43.48 · class 60.74 · calib 14.68 · total **118.91** · cat 0 · wall ~4.06 s/PDF @ W=2  

---

## 7. Build & run

```bash
cd solution
docker build -t mib-submission:paddle-ft .

docker run --rm --network none \
  --cpus 4 --memory 8g --pids-limit 512 \
  --read-only --tmpfs /tmp:rw,nosuid,nodev,size=2g \
  -v /path/to/pdfs:/input:ro -v /path/to/out:/output \
  mib-submission:paddle-ft /input /output/predictions.jsonl
```

Host (dev):

```bash
export PYTHONPATH=solution/src
export MIB_PADDLE_MODELS=$PWD/solution/models/paddle
export MIB_WORKERS=2 MIB_OCR_CLAHE=0
# venv with paddlepaddle + paddleocr
python -m mib_solution.cli data/train /tmp/preds.jsonl
```

Optional A/B: `MIB_OCR_ENGINE=tesseract` (legacy path only).

---

## 8. Not in this ship

- Private validation 5k package (not scored here)
- Docker full-train n=1000 confirm (host full train + Docker lat40 stand in)
- Unfinished synth RecAug retrain; **ship weights = best_ep5**

---

## 9. Future improvements (use LESSONS.md)

Read **`docs/LESSONS.md`** before changing gates, OCR density, or adjudicate rules. Measure residual + full train + Docker lat40 under 4c/8g every time.
