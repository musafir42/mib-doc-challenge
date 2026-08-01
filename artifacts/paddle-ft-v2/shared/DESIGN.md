# Paddle FT v2 — synth + non-brittle inference

## Goal
Replace brittle OCR typo forests with a **candidate-trained rec model** + **geometry-only region OCR** + **canonical policy enums**.  
Ship default remains tesseract P1 until residual/train gates pass.

## Checkpoint (killed train)
- **Primary:** `artifacts/paddle-ft/train/best_ep5/` — best_epoch **5**, val acc **0.8452**
- Inference export: `artifacts/paddle-ft/train/best_ep5/inference/`
- **Do not use:** mid_export epoch 3, `latest`, `iter_epoch_5` as primary

## Architecture (maintainable)

```
PDF → should_ocr (P1 or always if budget) 
    → region crops (fixed geometry ONLY — no SPN lists / no typo tables)
    → FT rec model
    → full-page paddle det+rec (optional first pass)
    → merge text
    → extract with CANONICAL regex only
    → adjudicate POLICY only (enums, Finding strict APPROVED, cat-safe)
    → calibrate (simple)
```

### Code keeps (non-brittle)
- Visa/fee/risk **enums** and schema formats (`SPN-\d{4}`, `MIB-\d{6}`, dates)
- Catastrophic safety: never promote OCR garbage to APPROVED; prefer NEEDS_REVIEW
- Finding: strict `Finding:\s*APPROVED`; DENIED/NR from clear tokens only
- Fee/visa policy rules that match labeled MIB policy (unpaid, TRANSIT-7, etc.) — **not** sponsor denylists of train IDs
- Geometry region boxes as fractions of page (top band, corners, fee band)

### Code must NOT add (brittle — ban list for v2 path)
- OCR typo banks (`Fouing`, `Frdirg`, `DEMED`, embamen, …) — **model learns damage**
- Hardcoded SPN denylists (`SPN-9090`, …) in the FT path
- Train-precision regex maps (P≥0.97 on train text)
- Residual case_id special cases
- Multi-PSM tesseract ensemble inside FT path

### Model owns (perception)
- Reading Finding / risk / fee / form lines under blur, red ink, rotation, partial crop
- General English rec on MIB-like fonts

## Synthetic data requirements
**Agent: paddle-ft-synth** → `artifacts/paddle-ft-v2/synth/`

1. **Classes (minimum):**
   - Finding lines: `Finding: APPROVED|DENIED|NEEDS_REVIEW` (+ occasional colon-less)
   - Risk stamps: `planetary_embargo`, `biohazard_red`, warrant/tamper-like **canonical** phrases
   - Fee: `Fee Status: paid|waived|unpaid`
   - Form: applicant names, `SPN-####`, visa enums, species, home world, dates, purpose
2. **Damage aug:** rotate ±15°, blur, contrast, red ink overlay, jpeg, partial crop, noise
3. **Labels:** exact ground truth strings (no self-pseudo from base paddle)
4. **Anti-leak:** **exclude residual case_ids** from any real crop mix; no case-id-only labels
5. **Volume:** target ≥8k synth lines; mix later with real GT-corrected crops (not 73% pseudo)
6. **Outputs:** `images/`, `train_list.txt`, `val_list.txt`, `manifest.jsonl`, `STATS.md`, `READY`
7. **Format:** Paddle rec `img_path\tlabel` relative to data_dir

## Mixed data + retrain
**Agent: paddle-ft-v2-train** → waits on synth READY + infer harness READY

1. Build `artifacts/paddle-ft-v2/mixed_data/`:
   - All synth train
   - Real crops from `artifacts/paddle-ft/data` **filtered:** drop residual case_ids; prefer GT/fee/finding corrections over `ocr_pseudo` (cap pseudo ≤20% or drop entirely if enough synth)
2. Train config: RecAug **ON**, epoch ≤10 CPU first cut, warm-start from **best_ep5** or official pretrain
3. Export inference to `artifacts/paddle-ft-v2/train/inference/`
4. Write READY + meta.json

## Non-brittle inference harness
**Agent: paddle-ft-infer** → `worktrees/paddle-ft-infer/` + `artifacts/paddle-ft-v2/infer/`

1. `ocr_ft_v2.py`: region crops + FT rec + optional full-page
2. Env: `MIB_OCR_ENGINE=paddle_ft_v2`, `MIB_PADDLE_REC_MODEL_DIR=...`
3. Monkeypatch only — **no permanent solution/ edit** unless residual≥108 and human says promote
4. `canonical_decode.py` (optional helpers): only enum/schema regexes
5. Document ban list in module docstring

## Score
**Agent: paddle-ft-v2-score**

1. Baseline residual with **best_ep5** + new region pipeline (even before retrain)
2. After v2 train READY: residual again; if ≥108 cat0 → full train optional
3. FINDINGS vs tesseract P1 108.44 / 118.77 and old paddle FT 105.42

## Gates
| Gate | Threshold |
|------|-----------|
| Residual | ≥ 108.0 cat 0 to consider promote |
| Full train | ≥ 116 ship; aim ≥ 118 |
| Latency40 @4w | ≤ 6 s/PDF |
| Cat | 0 |
| Brittleness | no new typo/SPN denylist in FT path |

## Product default
Keep **tesseract promote_p1** as ship until gates pass. FT v2 is harness/env opt-in.
