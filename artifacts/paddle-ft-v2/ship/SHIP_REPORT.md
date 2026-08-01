# Paddle FT Ship Report

**Submit path:** PaddleOCR fine-tuned recognition (best_ep5) + stock det/cls + geometry region crops  
**Product default:** `MIB_OCR_ENGINE=paddle` in `solution/`  
**Date:** 2026-08-01  
**Score scale:** /150 · residual = frozen hard subset seg-v1 n=100 · full train n=1000  
**Artifacts root:** `artifacts/paddle-ft-v2/ship/`

---

## 1. Executive summary

Paddle fine-tuned OCR is the **ship / submit path**. Perception is non-brittle: stock Paddle detection and angle classification, fine-tuned recognition (`best_ep5`), and fixed geometry region crops only—no OCR typo banks or SPN denylists in the OCR path. The P1 `should_ocr` gate (skip OCR only when the text layer already has a trusted Finding/DQ signal with solid structure) is retained.

| Gate | Result |
|------|--------|
| Residual (seg-v1 n=100) | **108.77** /150 · cat **0** |
| Full train (n=1000) | **118.91** /150 · cat **0** |
| Docker lat40 @2w CLAHE=0 | **5.71 s/PDF** wall · **PASS** (≤6 s) |
| Docker image | `mib-submission:paddle-ft` · **0.60 GiB** uncompressed · **under 4 GiB** |
| Models | ~14 MiB vendored under `solution/models/paddle/` |

CLAHE off (`MIB_OCR_CLAHE=0`) and `MIB_WORKERS=2` are required on the 8 GiB scoring box: CLAHE=1 fails lat40 (~6.27 s), and three Paddle workers OOM. Residual quality is identical at CLAHE=0 and CLAHE=1 (**108.77**). Full-train host wall with the same CLAHE=0 / W=2 config is ~4.06 s/PDF and scores **118.91**, above tesseract P1 full train (**118.77**) and ship-lean tesseract Docker (**116.07**), slightly below historical always-OCR integrate (**119.27**).

---

## 2. Goals

1. **Submit paddle FT** as the product default OCR engine (not tesseract).
2. Keep OCR **non-brittle**: put hard reading in the model and geometry crops; ban typo forests / SPN denylists / residual case_id specials from the FT OCR path.
3. **Beat or match tesseract** under challenge constraints—especially residual ≥ ~108 and full train near historical P1 (~118.77) / integrate (~119.27)—while staying inside latency, memory, and offline Docker limits.
4. Preserve catastrophic safety: **0** catastrophic false APPROVED.

---

## 3. Constraints

From `EVALUATION.md` and `DOCKER_SUBMISSION.md`:

| Constraint | Limit |
|------------|--------|
| Runtime box | **4 vCPU**, **8 GiB RAM**, CPU only, no GPU |
| Network | **`--network none`** (offline; no package downloads or APIs at runtime) |
| Filesystem | Read-only root FS; writable `/tmp` tmpfs; bind input (ro) and output |
| Latency | **≤6 s/PDF average**; hard wall 30,000 s on 5k validation |
| Image size | **≤4 GiB** uncompressed (`docker image inspect`) |
| Model artifacts | ≤250 MiB each; **≤1 GiB** total |
| Models allowed | Offline OCR, classical CV, rules, small task-specific / candidate-trained models |
| **Forbidden** | LLMs, VLMs, multimodal foundation models, cloud OCR/document APIs |
| Docker contract | Image entrypoint: `<input_pdf_dir> <output_predictions_path>` |

Scoring box flags used for ship-align:

```bash
docker run --rm --network none --cpus 4 --memory 8g --pids-limit 512 \
  --read-only --tmpfs /tmp:rw,nosuid,nodev,size=2g \
  -v <pdfs>:/input:ro -v <out>:/output \
  mib-submission:paddle-ft /input /output/predictions.jsonl
```

---

## 4. Approach

### 4.1 Selective OCR (P1 gate retained)

`should_ocr` in `solution/src/mib_solution/ocr.py` still decides when heavy OCR runs:

- Always OCR thin / incomplete text layers.
- **Skip OCR only** when the embedded text layer already carries a trusted adjudication signal (**Finding** line and/or **DQ** tokens) with solid structure (SPN/visa and enough structural signals).
- Ultra-rich forms **without** Finding/DQ still OCR (P1 recovery of stamp DENIED/APPROVED and fee/risk). Legacy ultra-rich skips are off unless `MIB_OCR_ULTRARICH_SKIP=1`.

This gate is independent of the OCR engine and was already validated on tesseract (promote_p1 residual **108.44** / full train **118.77**).

### 4.2 Perception stack

| Piece | Choice |
|-------|--------|
| Detection | Stock PP-OCRv4 mobile det (vendored) |
| Classification | Stock angle cls (vendored) |
| Recognition | **Fine-tuned** `best_ep5` export (val acc ≈ **0.8452** @ epoch 5) |
| Engine | `paddleocr==2.10.0` + `paddlepaddle==3.0.0` CPU |
| Rasterize | pdf2image / poppler · default **DPI=150** · **max_pages=4** |

Implementation: `solution/src/mib_solution/ocr_paddle.py`. Default wiring: `ocr.py` routes `ocr_pdf_text` to paddle unless `MIB_OCR_ENGINE=tesseract` (A/B only).

### 4.3 Geometry region crops

Fixed page-fraction crops only (no content/SPN-guided boxes):

| Region | Fractions (x0,y0,x1,y1) |
|--------|-------------------------|
| `top_band` | 0–100% × 0–20% |
| `bottom_band` | 0–100% × 80–100% |
| `tl_corner` / `tr_corner` | 30% corners top |
| `bl_corner` / `br_corner` | 30% corners bottom |
| `center_band` | 15–85% × 30–70% (stamp / fee band) |

Per page: full-page det+rec, then region crops det+rec; merge unique lines. Optional mild CLAHE is available but **default off** for Docker latency.

### 4.4 Ban list (OCR path)

Must **not** appear in the paddle FT OCR path:

- OCR typo banks (`Fouing`, `DEMED`, embamen, …) as a substitute for model accuracy
- Hardcoded SPN denylists in the FT path
- Train-precision residual `case_id` specials
- Multi-PSM tesseract ensemble inside the FT path

**Allowed / retained at policy layer:** visa/fee/risk enums and schema formats; catastrophic-safe adjudicate (strict Finding APPROVED; prefer NEEDS_REVIEW over false approve); geometry fractions; canonical extract regexes. Product `adjudicate.py` still has legacy OCR-tolerant Finding regexes for stamp variants—those are policy tolerance, not a new FT-path typo forest.

### 4.5 8 GiB runtime knobs

| Knob | Ship default | Why |
|------|--------------|-----|
| `MIB_WORKERS` | **2** | W=3+ OOM on 8g with Paddle processes |
| `MIB_OCR_CLAHE` | **0** | lat40 CLAHE=1 ≈ **6.27 s** (fail); CLAHE=0 ≈ **5.71 s** (pass); residual score unchanged |
| `OMP_*` / `MKL_*` / `OPENBLAS_*` | **1** | Avoid thread thrash under process pool |
| `FLAGS_use_mkldnn` | **0** | Stable CPU path |
| DPI / max_pages | 150 / 4 | Latency budget with region crops |

---

## 5. What was done (timeline)

Scores are official scorer totals /150 unless noted. Catastrophic false approvals are 0 on every listed promote.

| Stage | Config | Residual | Full train | Notes |
|-------|--------|----------|------------|--------|
| Historical integrate | Always-OCR-class path | **108.78** | **119.27** | `promote_integrate` · quality ceiling reference |
| Tesseract ship-lean Docker | select-ocr + dpi lean | — | **116.07** | `ship_train_docker` · ~2.7 s/PDF · under budget but quality drop |
| Tesseract **P1** | Finding/DQ skip only | **108.44** | **118.77** | `promote_p1` · lat40 ~5.09 s host |
| Base paddle (dpi150, full-page) | stock rec | **97.70** | — | Misses stamp-heavy residual |
| Old paddle FT mid | ep3 full-page only | **105.42** | — | Better than base; still below P1 |
| Regions + **best_ep5** | geometry + FT rec | **108.77** | — | Phase A `baseline_region` · residual gate pass |
| **Integrate into solution/** | default OCR = paddle | **108.77** (CLAHE 0/1) | **118.91** | Vendored models · product code |
| Docker image + lat40 | W=2 CLAHE=0 | — | lat **5.71 s/PDF** | Image **0.60 GiB** · pass ≤6 |
| Host full train ship config | W=2 CLAHE=0 | — | **118.91** | wall ~4.06 s/PDF · cat 0 |

Narrative path in short:

1. Tesseract latency ship Docker scored **116.07** (select-ocr + lean DPI tradeoff).
2. P1 `should_ocr` recovered full train to **118.77** (residual **108.44**).
3. Stock paddle residual only **97.7** — not competitive.
4. Mid FT export full-page ~**105**.
5. Geometry regions + **best_ep5** rec reached residual **108.77** (cat 0).
6. Promoted into `solution/`, vendored models, Dockerfile/`run.sh` defaults, Docker lat40 pass at **5.71 s/PDF**.
7. Full train with ship defaults: **118.91** cat 0.

---

## 6. How

### 6.1 Product files

| Path | Role |
|------|------|
| `solution/src/mib_solution/ocr_paddle.py` | Paddle FT + geometry OCR (ship default) |
| `solution/src/mib_solution/ocr.py` | Engine switch; P1 `should_ocr`; tesseract A/B |
| `solution/src/mib_solution/pipeline.py` | End-to-end predict |
| `solution/src/mib_solution/{extract,evidence,adjudicate,calibrate}.py` | Fields / policy / confidence |
| `solution/src/mib_solution/cli.py` | CLI entry |
| `solution/models/paddle/{det,cls,rec}/` | Vendored offline models (~14 MiB total) |
| `solution/Dockerfile` | Offline image build |
| `solution/run.sh` | Entrypoint · env defaults for 8g box |
| `solution/pyproject.toml` | Deps: paddlepaddle 3.0.0, paddleocr 2.10.0, opencv, pdf2image, … |

### 6.2 Model vendoring

- **rec:** FT export from `artifacts/paddle-ft/train/best_ep5/inference` (not mid_export / latest).
- **det / cls:** stock PP-OCRv4 mobile inference trees.
- Runtime path: `MIB_PADDLE_MODELS=/app/models/paddle` in Docker; package-relative `solution/models/paddle` on host.
- Approximate sizes: rec ~7.6 MiB, det ~3.9 MiB, cls ~2.1 MiB (**~14 MiB** total ≪ 1 GiB cap).

### 6.3 Dockerfile highlights

- Base: `python:3.11-slim`
- System: `poppler-utils`, `libgomp1`, `libgl1`, `libglib2.0-0`
- Pip: pinned paddle stack + vision deps; package install with `--no-deps` after deps
- Bake models under `/app/models`
- ENV: `MIB_OCR_ENGINE=paddle`, `MIB_WORKERS=2`, `MIB_OCR_CLAHE=0`, OMP=1, `HOME`/`XDG_CACHE_HOME`/`TMPDIR` under `/tmp`
- `ENTRYPOINT ["/app/run.sh"]`

### 6.4 Measurement

| Measurement | Location / method |
|-------------|-------------------|
| Residual | n=100 from `artifacts/residual.json` · `scripts/evaluate.py` → `ship/residual/` and `ship/residual_clahe0/` |
| Full train | n=1000 · host W=2 CLAHE=0 → `ship/train/eval.json` |
| Host lat40 | `ship/latency40.json` · W=4 · **2.64 s/PDF** (high RAM host; not scoring box) |
| Docker lat40 | Challenge-like `--cpus 4 --memory 8g` · W=2 CLAHE=0 · **5.71 s/PDF**; CLAHE=1 · **6.27 s** |
| Image size | `docker image inspect mib-submission:paddle-ft` · **0.60 GiB** |

Residual breakdown (CLAHE=0 == CLAHE=1 on total):

| Component | Score |
|-----------|------:|
| Extraction /50 | 35.20 |
| Classification /80 | 58.30 |
| Calibration /20 | 15.27 |
| Missing penalty | 0.00 |
| **Total** | **108.77** |
| Catastrophic FA | **0** |

Full train breakdown (`ship/train/eval.json`):

| Component | Score |
|-----------|------:|
| Extraction /50 | 43.48 |
| Classification /80 | 60.74 |
| Calibration /20 | 14.68 |
| Missing penalty | 0.00 |
| **Total** | **118.91** |
| Catastrophic FA | **0** |
| Timing | wall **4059 s** · **4.06 s/PDF** · W=2 · CLAHE=0 |

---

## 7. Scores table

| System | Residual | Full train | Cat | Latency (notes) |
|--------|---------:|-----------:|----:|-----------------|
| Historical integrate (tesseract always-OCR-class) | 108.78 | **119.27** | 0 | quality ceiling |
| Tesseract ship-lean Docker | — | **116.07** | 0 | ~2.7 s/PDF Docker 4c/8g |
| Tesseract P1 | **108.44** | **118.77** | 0 | lat40 ~5.09 s host @4w |
| Base paddle dpi150 | **97.70** | — | 0 | full-page stock |
| Old paddle FT mid (ep3) | **105.42** | — | 0 | full-page FT |
| **Paddle FT ship (this)** | **108.77** | **118.91** | **0** | Docker lat40 **5.71 s** @2w CLAHE=0 · host lat40 2.64 s @4w · host train 4.06 s @2w |

**Deltas (paddle FT ship vs):**

| Comparator | Δ residual | Δ full train |
|------------|----------:|-------------:|
| vs hist integrate 119.27 | −0.01 | **−0.36** |
| vs tesseract ship Docker 116.07 | — | **+2.84** |
| vs tesseract P1 118.77 | **+0.33** | **+0.14** |
| vs base paddle 97.70 | **+11.07** | — |
| vs old FT mid 105.42 | **+3.35** | — |

Host vs Docker latency (paddle FT ship):

| Setting | s/PDF wall | Gate ≤6 |
|---------|----------:|:-------:|
| Host lat40 · W=4 · high RAM | 2.64 | PASS (not 8g box) |
| Host full train · W=2 CLAHE=0 | 4.06 | PASS |
| **Docker lat40 · W=2 CLAHE=0 · 4c/8g** | **5.71** | **PASS** |
| Docker lat40 · W=2 CLAHE=1 | 6.27 | FAIL |
| Docker W=3 | OOM | — |

---

## 8. Knowledge from non-FT trials

These lessons shaped the ship config; they come from tesseract ship-align, P1 recovery, base paddle, and latency explores—not only from FT training.

1. **Residual ≠ train.** Residual is a frozen hard subset (seg-v1). Lean select-ocr could look fine on residual (**108.20** promote_lat_ship) while full train Docker fell to **116.07**. Always residual A/B before full-train claims; then re-check train.
2. **P1 gate matters.** Skipping OCR on ultra-rich text without Finding/DQ loses stamp DENIED/APPROVED and fee/risk on train. P1 (OCR unless trusted Finding/DQ + structure) recovered **+2.70** full-train points vs ship-lean (**116.07 → 118.77**).
3. **OMP thrash.** Process-pool workers × multi-thread OpenMP/MKL made single OCR calls take minutes. Ship sets `OMP_THREAD_LIMIT=1`, `OMP_NUM_THREADS=1`, `MKL_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1`.
4. **Cat-safe adjudication.** Never promote OCR garbage to APPROVED; strict Finding APPROVED path; prefer NEEDS_REVIEW. All promote rows above keep cat **0**.
5. **Anti-overfit / non-brittle OCR.** Typo banks and SPN denylists score residual but do not generalize. FT rec + geometry is the maintainable substitute; ban list is documented in `ocr_paddle.py`.
6. **Docker 8g ≠ host memory.** Host lat40 @4 workers can look fast (**2.64 s**) while needing ~20 GiB RSS aggregate. Scoring box is **8 GiB**: cap workers at **2** for Paddle; W=3 OOM.
7. **CLAHE is not free.** Residual total identical with CLAHE on/off for this stack, but Docker lat40 fails with CLAHE on. Default **CLAHE=0**.
8. **Stock paddle is not enough.** Base residual **97.7** — full-page mobile rec misses stamp bands that geometry crops + FT rec recover.
9. **OpenCV/numpy must ship.** Host residual reconfirm without opencv in pyproject dropped OCR preprocess and residual collapsed (~104). Dockerfile and `pyproject.toml` must include vision deps.
10. **Image size budget is comfortable** for this stack: **0.60 GiB** image, **~14 MiB** models—well under 4 GiB / 1 GiB model caps.
11. **DPI lean vs quality.** dpi 200/4 helped tesseract latency ship but cost train points vs richer integrate; paddle ship uses dpi **150** with region crops and still beats P1 residual/train under the 6 s Docker budget at W=2.

---

## 9. Packaging / submit

### Build

```bash
cd /root/dev-workspace/mib-doc-challenge
docker build -t mib-submission:paddle-ft solution/
docker image inspect mib-submission:paddle-ft --format '{{.Size}}'  # expect ~0.60 GiB < 4 GiB
```

### Run (challenge-like)

```bash
mkdir -p /tmp/mib-out
docker run --rm --network none \
  --cpus 4 --memory 8g --pids-limit 512 \
  --read-only --tmpfs /tmp:rw,nosuid,nodev,size=2g \
  -v "$PWD/data/train:/input:ro" \
  -v /tmp/mib-out:/output \
  mib-submission:paddle-ft /input /output/predictions.jsonl
```

### What’s in the image

- Python 3.11 slim + poppler + minimal OpenGL/GLib for OpenCV/Paddle
- `paddlepaddle==3.0.0`, `paddleocr==2.10.0`, opencv-headless, pdf2image, pillow, pypdf, numpy
- Vendored `models/paddle/{det,cls,rec}` (FT rec + stock det/cls)
- Application under `/app/src` (`mib_solution`)
- `run.sh` defaults: engine=paddle, models path, DPI=150, max_pages=4, CLAHE=0, workers=2, OMP=1, caches in `/tmp`

### Overrides (optional A/B)

```bash
# tesseract A/B (image must still contain tess if used; ship default is paddle)
-e MIB_OCR_ENGINE=tesseract

# force CLAHE on (fails lat40 on 8g)
-e MIB_OCR_CLAHE=1

# single worker (safer memory, slower wall)
-e MIB_WORKERS=1
```

### Score locally after Docker

```bash
python3 scripts/evaluate.py \
  --truth data/train_labels.csv \
  --submission /tmp/mib-out/predictions.jsonl \
  --output-json /tmp/mib-out/eval.json \
  --case-scores-jsonl /tmp/mib-out/case_scores.jsonl
```

---

## 10. Not done / optional

| Item | Status |
|------|--------|
| Validation set **n=5k** full Docker score | **Not run** (latency gate measured on lat40; hard wall budget not exercised on 5k) |
| **Docker full train** n=1000 under 4c/8g | **Not confirmed** as a single Docker end-to-end score; host full train **118.91** + Docker lat40 **5.71 s** stand in. Recommend one Docker full-train confirm before final contest upload if time allows. |
| Synth retrain (paddle-ft-v2 train epoch path) | **Unfinished** / not promoted. Ship uses prior **best_ep5**, not a completed v2 mixed-data retrain export. |
| Region crop pruning (skip empty bands) | Optional latency win; not required after CLAHE=0 / W=2 pass |
| Soft ultra-rich / mid-DPI recovery hybrids | Explored under tesseract worktrees; not needed for paddle FT ship defaults |

---

## 11. Reproduce commands

All paths from monorepo root: `/root/dev-workspace/mib-doc-challenge`.

### Host residual (CLAHE=0, ship models)

```bash
export CUDA_VISIBLE_DEVICES=
export MIB_OCR_ENGINE=paddle
export MIB_PADDLE_MODELS="$PWD/solution/models/paddle"
export MIB_OCR_CLAHE=0 MIB_OCR_DPI=150 MIB_OCR_MAX_PAGES=4
export MIB_WORKERS=2
export OMP_THREAD_LIMIT=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
export PYTHONPATH="$PWD/solution/src"

# predictions on residual ids → then official evaluate
# (see solution/experiments/RESIDUAL.md for full harness)
python3 scripts/evaluate.py \
  --truth artifacts/residual_truth.csv \
  --submission artifacts/paddle-ft-v2/ship/residual_clahe0/predictions.jsonl \
  --output-json /tmp/residual_eval.json \
  --case-scores-jsonl /tmp/residual_case_scores.jsonl
# expected total ≈ 108.77 cat 0
```

### Host full train (recorded ship run)

```bash
export CUDA_VISIBLE_DEVICES=
export MIB_OCR_ENGINE=paddle MIB_PADDLE_MODELS="$PWD/solution/models/paddle"
export MIB_OCR_CLAHE=0 MIB_WORKERS=2
export OMP_THREAD_LIMIT=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
export PYTHONPATH="$PWD/solution/src"

# e.g. mib-solution or python -m mib_solution.cli
# recorded artifacts:
#   artifacts/paddle-ft-v2/ship/train/{predictions.jsonl,eval.json,timing.json}
# total_score 118.906… → 118.91 cat 0 · ~4.06 s/PDF wall
```

### Docker build, smoke, lat40-class run

```bash
docker build -t mib-submission:paddle-ft solution/

# smoke handful of PDFs
mkdir -p /tmp/mib-smoke
docker run --rm --network none --cpus 4 --memory 8g \
  --read-only --tmpfs /tmp:rw,nosuid,nodev,size=2g \
  -v "$PWD/data/train:/input:ro" -v /tmp/mib-smoke:/output \
  mib-submission:paddle-ft /input /output/predictions.jsonl
# restrict input mount to a small PDF dir for true smoke if needed

# lat40: mount a 40-PDF subset; wall_s/n ≤ 6
```

### Official eval of recorded ship artifacts

```bash
python3 scripts/evaluate.py \
  --truth artifacts/residual_truth.csv \
  --submission artifacts/paddle-ft-v2/ship/residual_clahe0/predictions.jsonl \
  --output-json /tmp/ship_residual_eval.json

python3 scripts/evaluate.py \
  --truth data/train_labels.csv \
  --submission artifacts/paddle-ft-v2/ship/train/predictions.jsonl \
  --output-json /tmp/ship_train_eval.json
```

### Tesseract A/B (not ship default)

```bash
export MIB_OCR_ENGINE=tesseract
# requires tesseract binary + pytesseract; residual reference promote_p1 108.44 / 118.77
```

---

## Artifact index

| Path | Contents |
|------|----------|
| `artifacts/paddle-ft-v2/ship/SHIP_STATUS.md` | Live ship gates summary |
| `artifacts/paddle-ft-v2/ship/SHIP_REPORT.md` | This report |
| `artifacts/paddle-ft-v2/ship/residual/` | Residual eval (CLAHE on path; same score) |
| `artifacts/paddle-ft-v2/ship/residual_clahe0/` | Residual eval CLAHE=0 · **108.77** |
| `artifacts/paddle-ft-v2/ship/train/` | Full train · **118.91** · timing · READY |
| `artifacts/paddle-ft-v2/ship/latency40.json` | Host lat40 @4w · 2.64 s/PDF |
| `artifacts/SCOREBOARD.md` | Rows `paddle_ft_ship` / `paddle_ft_ship_full` |
| `solution/SHIP.md` | Pointer / ship summary for submit tree |
| `solution/Dockerfile`, `solution/run.sh` | Offline submit contract |

---

## Bottom line

**Ship paddle FT:** residual **108.77** · full train **118.91** · cat **0** · Docker **5.71 s/PDF** @2w CLAHE=0 · image **0.60 GiB**. Beats tesseract P1 on residual and full train, clears the 6 s Docker budget on the 8 GiB box, and stays non-brittle in the OCR stack. Optional follow-ups are validation-5k and a Docker full-train confirm—not blockers for the measured ship path.
