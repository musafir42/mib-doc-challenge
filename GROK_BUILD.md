# Grok Build Playbook — MIB Doc Challenge

**What this is:** How to **think, measure, and improve** a constrained offline evaluation challenge.  
**What this is not:** A product recipe. Challenge manuals, scorer, and data in this repo always win on conflict.

### Hard process constraints

| Constraint | Rule |
|------------|------|
| **Python packaging** | **`uv` only** (`uv init` / `uv add` / `uv sync` / `uv run`). No pip/poetry/conda as primary. |
| **Experiment compute** | Prefer a **single high-CPU cloud VM** (or local multi-core) + **Docker** for residual / full train / val. Product submission is offline Docker. |
| **Modal** | **Optional / legacy only.** Not the default path. Do not reintroduce serverless farms unless the human asks. |
| **Generalization** | No case-id answer tables / runtime label lookup in product code. |
| **You are the merge owner** | Unless the human names someone else, **you** integrate worktrees, write the scoreboard, enforce kills, and re-score residual on main. |

### Named stages

```text
Setup → Baseline → Segment → Explore → Integrate → Ship-align → Stretch
```

| Stage | You are here when… | You may leave when… |
|-------|--------------------|---------------------|
| **Setup** | Clean forked repo open | Prereqs OK; layout dirs present; scorer produced a **number** |
| **Baseline** | Building first real system | Tagged system + official eval on scoreboard |
| **Segment** | Slicing errors | Residual frozen **and** residual harness documented **and** ceiling note written |
| **Explore** | Parallel worktrees | Segment exit only. Each run has FINDINGS + residual A/B |
| **Integrate** | Merge owner promoting | Residual re-scored on **main**; scoreboard row; tag if improved |
| **Ship-align** | Matching ship to measured config | Offline Docker smoke + full train/val with same lockfile/flags |
| **Stretch** | High-EV residuals only | Catastrophic metric still safe |

---

## Campaign handoff (read this first on a new machine)

**Status (2026-07-30):** Integrate candidate is in `solution/`. Ship-align **not** complete (no full Docker train+val package yet). Modal farm is **retired** as the default path — continue on a high-CPU box.

### Best measured scores (official scorer, /150, cat = catastrophic false approvals)

| System | Slice | Primary | Cat | Artifacts |
|--------|-------|--------:|----:|-----------|
| **promote_integrate** (current `solution/`) | residual seg-v1 n=100 | **108.78** | 0 | `artifacts/promote_integrate/` |
| **promote_integrate** | train full n=1000 | **119.27** | 0 | `artifacts/promote_integrate_full/` |
| promote_ocr (Modal OCR, earlier) | train full | 114.20 | 0 | `artifacts/modal_full_ocr/` |
| Best single residual Explore | deny-recall | 104.87 | 0 | `artifacts/exp-deny-recall/` |
| residual baseline (Segment freeze) | residual | 62.21 | 0 | `artifacts/residual_baseline/` |
| Docker smoke (10 PDFs) | smoke | 132.13* | 0 | `artifacts/docker_ship/` (*not comparable to full train*) |

Residual identity: `artifacts/residual.json` version **seg-v1** (n=100). Only merge owner rewrites it.

### What is in `solution/` (product)

| Module | Role |
|--------|------|
| `pipeline.py` | PDF → text/OCR merge → extract → adjudicate → calibrate |
| `ocr.py` | poppler + tesseract; deskew/stamp crops; TMPDIR-safe under Docker `--read-only` |
| `extract.py` | multi-source labeled fields + trusted-text filters |
| `evidence.py` | page roles / precedence helpers (integrated where used) |
| `adjudicate.py` | Finding notes, deny recall, review-safe APPROVED only |
| `calibrate.py` | path/feature confidence (Brier); does not change labels |
| `cli.py` / `run.sh` | offline entrypoints |
| `Dockerfile` | tesseract + poppler + pip install; image ~0.1 GiB |

**Do not** put Modal, cloud OCR APIs, or LLMs in the submission runtime (challenge rules).

### What was removed / frozen (do not resurrect by default)

- Modal sandbox bulk ship scripts (`ship_docker_*`, `ship_align_*`, `modal_bulk_runner`)
- Stale multi-agent ACTIVE rows (cleared)
- Modal as default experiment farm

Historical Modal residual/full scores remain on the scoreboard as audit trail only.

### Next work on the high-CPU machine (priority order)

1. **Bootstrap box** — see [New machine bootstrap](#new-machine-bootstrap) below.
2. **Re-score residual on main** with local parallel workers → confirm ~108.78.
3. **Full train Docker score** (1000 PDFs) with challenge-like flags → must land near **119.27**.
4. **Validation preds** (5000 PDFs, no labels) → package for submission.
5. **Ship-align** checklist in scoreboard; `validate_submission.py`.
6. **Segment-2 / Stretch** only after ship path is honest: slice integrate failures, residual-first Explore.

### Known landmines

| Issue | Mitigation |
|-------|------------|
| Challenge root FS read-only; only `/tmp` writable | `run.sh` forces `TMPDIR`/`HOME`/`XDG_CACHE` to `/tmp`; OCR uses `output_folder=/tmp` |
| Catastrophic = APPROVED when truth DENIED | Never auto-APPROVED from multi-field heuristics alone; need trusted Finding APPROVED |
| Residual scale ≠ full train | Both are /150 max; residual is a hard subset — expect lower absolute residual scores |
| Injection / SYSTEM answer-key lines | Prefer trusted labeled blocks + OCR of visible stamps over free-form full-text harvest |
| Image-only DQ / biohazard stamps | OCR path is required; text-only collapses residual |

Authoritative longer trail: `artifacts/AUDIT.md`, `artifacts/HANDOFF.md`, `artifacts/SCOREBOARD.md`.

---

## New machine bootstrap

Target: **one high-CPU VM** (≈16–32 vCPU, 32–64 GB RAM, ≥40 GB free disk). No Modal required.

```bash
# 1) Clone (or rsync) the fork — you need git history + solution + artifacts + data layout
git clone https://github.com/musafir42/mib-doc-challenge.git
cd mib-doc-challenge

# 2) System packages (Debian/Ubuntu family)
sudo apt-get update
sudo apt-get install -y git python3 python3-venv docker.io \
  tesseract-ocr tesseract-ocr-eng poppler-utils

# 3) uv
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"

# 4) Data — train/validation PDFs are gitignored; restore from the challenge zip or your laptop:
#    data/train/*.pdf (1000), data/validation/*.pdf (5000), data/train_labels.csv
#    See data/README.md / DATASET_CARD.md. Do NOT commit PDFs.

# 5) Product env
cd solution && uv sync && cd ..

# 6) Scorer smoke (must produce a number)
python3 scripts/evaluate.py --help >/dev/null
# residual path: see solution/experiments/RESIDUAL.md

# 7) Docker smoke (10 PDFs)
docker build -t mib-submission:latest solution/
# then bind-mount 10 train PDFs as in artifacts/docker_ship/READY.md
```

**Parallel residual / train locally** (prefer this over any cloud map API):

```bash
# Example: residual with N workers (GNU parallel or a small Python pool)
# See solution/experiments/RESIDUAL.md for the canonical residual harness.
uv run --project solution python -c "
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
import json, os
from mib_solution.pipeline import predict_pdf, write_jsonl
root = Path('.')
ids = json.loads((root/'artifacts/residual.json').read_text())['case_ids']
workers = int(os.environ.get('MIB_WORKERS', os.cpu_count() or 4))
def one(cid):
    return predict_pdf(root/'data/train'/f'{cid}.pdf')
preds = []
with ProcessPoolExecutor(max_workers=workers) as ex:
    futs = [ex.submit(one, c) for c in ids]
    for f in as_completed(futs):
        preds.append(f.result())
out = root/'artifacts/residual_local'
out.mkdir(parents=True, exist_ok=True)
write_jsonl(out/'predictions.jsonl', preds)
print(len(preds), 'workers=', workers)
"
python3 scripts/evaluate.py \
  --truth artifacts/residual_truth.csv \
  --submission artifacts/residual_local/predictions.jsonl \
  --output-json artifacts/residual_local/eval.json \
  --case-scores-jsonl artifacts/residual_local/case_scores.jsonl
```

For full train / validation, same pattern over all PDFs in `data/train` or `data/validation`, or:

```bash
docker run --rm --network none --cpus $(nproc) --memory 32g \
  --read-only --tmpfs /tmp:rw,nosuid,nodev,size=8g \
  -v "$PWD/data/train:/input:ro" -v "$PWD/artifacts/ship_train:/output" \
  mib-submission:latest /input /output/predictions.jsonl
```

---

## Glossary

| Term | Meaning |
|------|---------|
| **Repo root** | Forked challenge repo cwd. Rules, data, scorer live here; product in `solution/`. |
| **`solution/`** | Product code (pipeline, Docker, uv project). |
| **`artifacts/`** | Preds, evals, residual freeze, scoreboard, agency, handoff. |
| **`worktrees/`** | Isolated copies of `solution/` for parallel experiments. Prefer FINDINGS + `artifacts/<name>/` over committing full trees. |
| **Official score** | Challenge `scripts/evaluate.py` output only. Max **150**. |
| **Catastrophic** | Scorer: false APPROVED when truth DENIED. |
| **Residual** | Frozen hard subset `artifacts/residual.json` (seg-v1, n=100). |
| **Ship-align** | Docker offline path matches measured config (`uv.lock`, flags, OCR deps). |
| **uv** | Required Python package manager. |

---

## Setup

### Prerequisites

| Need | Check |
|------|--------|
| git | `git --version` |
| Python 3.12+ | `python3 --version` |
| **uv** | `uv --version` |
| Docker | `docker info` |
| tesseract + poppler | system or Docker image |
| git-lfs | if README requires |
| **CPU box** | Prefer ≥16 cores for full train/val |

### Layout

```text
.                           ← repo root
  manuals, data/, scripts/
  solution/                 ← product (uv + Docker)
  artifacts/                ← SCOREBOARD, residual, runs, HANDOFF
  worktrees/                ← experiments (optional isolation)
  GROK_BUILD.md             ← this playbook
```

### Setup done when

- [ ] Repo root with data present  
- [ ] `uv sync` in `solution/`  
- [ ] Numeric scorer smoke  
- [ ] Residual harness once (`solution/experiments/RESIDUAL.md`)  
- [ ] Docker image builds  

---

## The game

| Axis | Question |
|------|----------|
| Objective | Maximize official total score (/150) |
| Constraints | Offline Docker; size; latency; no cloud LLMs/OCR APIs in runtime |
| Risk | Catastrophic false approvals |
| Uncertainty | Private test; injection/hidden fields |

**Win:** residual-first → promote → **Ship-align** (Docker full train + val preds).  
**Lose:** full-data thrash without residual; id memorization; “win” without Docker honesty.

---

## The loop

```text
Baseline → Segment (residual + harness + ceiling)
  → Explore → Residual A/B
  → Integrate → Ship-align → (Stretch)
```

### Baseline

Runnable pipeline, schema-valid preds, eval under `artifacts/baseline/`, scoreboard row.

### Segment (hard gate)

- `artifacts/residual.json` frozen (merge owner only)
- `solution/experiments/RESIDUAL.md` command path
- residual baseline scored once
- `artifacts/ceiling/BINDING.md`

### Explore

- Worktree or branch per hypothesis; `experiments/<name>/FINDINGS.md` required
- Residual A/B before promote claims
- Register in `artifacts/agency/ACTIVE.md`; kill stale rows
- Multi-agent optional; one high-EV slice is fine

### Integrate

1. Port minimal patch into `solution/`  
2. Re-score residual on main  
3. Scoreboard row  
4. Full train only after residual promote criteria  
5. Tag if improved  

### Ship-align (required before calling a win)

- [ ] Same `solution/uv.lock` in Docker image  
- [ ] Same OCR/env flags as measured  
- [ ] Docker smoke (`artifacts/docker_ship/`) green  
- [ ] Full train Docker score ≈ measured integrate  
- [ ] Validation preds written + `validate_submission.py`  
- [ ] Scoreboard notes Ship-align OK  

### Stretch

High-EV residual slices only; catastrophic must stay safe.

---

## Complexity and compute

| Work | Where |
|------|--------|
| Edit / tiny debug | Local `uv run` in `solution/` |
| Residual A/B | **Same machine**, multi-process / Docker |
| Full train / validation | **High-CPU VM** + Docker or ProcessPool |
| Submission | Offline Docker only |

Pay for OCR cost when residual A/B pays. Cheap text path first when debugging extract rules.

---

## Scoreboard

**Only** `artifacts/SCOREBOARD.md`. Merge owner appends.

| date | name | stage | slice | primary | catastrophic | notes | artifacts | git |
|------|------|-------|-------|---------|--------------|-------|-----------|-----|

Residual row before full-data row for the same change. Keep losers.

---

## Anti-patterns

Explore before Segment · full-data every tweak · case-id tables · “win” without Ship-align · pip-first · treating Modal as required · committing PDFs or secrets · resurrecting abandoned ship_docker Modal scripts · shared mutable `solution/` across parallel writers without merge discipline.

---

## Paste prompt (new machine / new session)

```text
You are Grok Build. Continue the MIB Doc Challenge on this machine.

PROCESS: GROK_BUILD.md (handoff section first)
TRUTH: manuals, scorer, data, submission contract in this repo (override playbook on conflict).
STATE: artifacts/HANDOFF.md + artifacts/SCOREBOARD.md + artifacts/AUDIT.md

You are the merge owner unless the human names someone else.

DEFAULT COMPUTE: high-CPU local/VM + Docker. Residual-first. Modal is legacy — do not use unless asked.

CURRENT PRODUCT: solution/ (integrate candidate ~108.78 residual / ~119.27 full train, cat 0).
NEXT: bootstrap if needed → residual reconfirm → Docker full train → validation preds → Ship-align.
THEN: Segment-2 / Stretch on integrate failures only.

LAW: uv only; no case-id answer tables; catastrophic types from scorer only;
  artifacts/SCOREBOARD.md merge-owner append only; ship config = measured config.
```

---

## One-page summary

```text
High-CPU box + Docker is the farm. Residual (seg-v1 n=100) gates every promote.
solution/ is the product; scoreboard + HANDOFF carry memory across machines.
Ship-align = offline Docker train score + val preds, same lockfile as measured.
No Modal by default. No LLM/cloud OCR in submission. No id memorization.
```
