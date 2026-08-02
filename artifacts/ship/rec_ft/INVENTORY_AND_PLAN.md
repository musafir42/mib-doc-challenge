# Rec FT inventory & plan (no day-long train kickoff)

Date: 2026-08-02  
Constraint: **do not start ~1 day CPU full retrain** until GPU or a short scoped experiment is agreed.

## Ship today

| Item | State |
|------|--------|
| Rec weights | `solution/models/paddle/rec/` = **best_ep5** export (val acc ~0.845 @ ep5) |
| Det / cls | Stock mobile, vendored |
| Product path | P1 should_ocr + regions + best_ep5 + trusted_corpus policy |
| Residual / train | **106.26 / 114.80** cat0 (`finding_recover`) |

## What existed (pruned from repo cleanup)

| Artifact | Prior location | Status now |
|----------|----------------|------------|
| best_ep5 train checkpoint notes | `artifacts/paddle-ft/train/best_ep5/` | CHECKPOINT.md in git history; **inference export still in solution/models** |
| Real crop dataset (pseudo-heavy) | `artifacts/paddle-ft/data` | **Gone** — rebuild would take hours of OCR over train PDFs |
| Synth 9k lines (Finding/risk/fee/form) | `artifacts/paddle-ft-v2/synth/` | **Gone** — generator recoverable |
| Mixed data (synth + filtered real, no residual leak, no pseudo) | `artifacts/paddle-ft-v2/mixed_data/` | **Gone** (~9.6k lines when last built) |
| v2 retrain (warm-start best_ep5, RecAug, 10 ep CPU) | `artifacts/paddle-ft-v2/train/` | **Never finished** — ETA was ~23h @ ~1.4 samp/s |
| Scripts | worktrees (pruned) | Recovered to **`tools/rec_ft/`** (uncommitted inventory only) |

## Recovered tooling (`tools/rec_ft/`)

- `build_synth_rec.py` — GT synth lines (SEED=42, default n=9000)
- `filter_real_crops.py` / `build_rec_data.py` — real crop builders
- `build_mixed_data.py` — mix synth + real, drop residual + pseudo
- `en_PP-OCRv4_rec_ft_v2.yml` — RecAug on, warm-start best_ep5
- `train_v2.sh` — full train + export (**day-scale on CPU — do not run yet**)

## Gaps blocking a *short* retrain

1. **No training images on disk** (synth + real both deleted).
2. **No best_accuracy paddle training weights** for warm-start (only inference export in `solution/models`). Warm-start may need re-export or stock pretrain.
3. **PaddleOCR training stack** may not be installed in ship venv (inference-only).
4. Full 10-epoch mixed retrain on CPU ≈ **1 day** — **out of scope until GPU or explicit go**.

## Plan when retrain *is* allowed (ordered, time-boxed)

### A. Fast path (minutes–hours, no 1-day job)
1. Regenerate **small synth** only: e.g. `PADDLE_FT_SYNTH_N=1500` Finding/fee/risk heavy (~minutes).
2. **Smoke train 1–2 epochs** on tiny set OR offline rec eval only if harness exists — **abort if wall > 2–3h**.
3. If no clear val-acc lift on Finding lines, stop; keep best_ep5.

### B. Full path (needs GPU or overnight OK)
1. Rebuild full synth 9k + optional real GT crops **excluding residual IDs**.
2. Cap or drop ocr_pseudo (last mix: 0% pseudo).
3. Warm-start best_ep5 if training checkpoint recoverable; else official rec pretrain.
4. Train ≤10 ep with RecAug; export inference; residual → train → lat40.
5. Promote only if residual class ↑ and cat0 and lat ≤6s @2w.

### C. Explicit non-goals
- Do not re-add typo forests to buy residual points while waiting on rec.
- Do not kick off day-scale CPU train as a background hope.

## Current recommendation

Stay on **best_ep5 + finding_recover**. Next *executable* work without day ETA:

1. Docker lat40 reconfirm of current code  
2. Optional: unit tests for Finding flex  
3. Optional: tiny synth smoke (minutes) **only if** someone will score a short train later  
4. Defer full rec retrain until GPU or user OK with overnight  

Scripts in `tools/rec_ft/` are recovery inventory — not a running pipeline.
