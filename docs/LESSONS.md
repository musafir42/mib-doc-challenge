# Lessons — campaign knowledge for future paddle FT work

This is **not** the ship recipe (see `docs/APPROACH.md`). It captures what we learned from tesseract Explore, latency ship, residual recovery, OCR bakeoffs, and early paddle FT—so future changes improve the **paddle FT bet** instead of replaying dead ends.

---

## 1. Measurement discipline

1. **Residual ≠ full train.** Residual (seg-v1 n=100) is a frozen hard slice. Lean OCR skip looked fine on residual (~108.2) while full train Docker fell to **116.07**. Always residual A/B **and** train (or ≥200 proxy) before claiming a win.
2. **Latency must use the scoring shape.** Host ProcessPool @4 workers can show **2.6 s/PDF** while using ~20 GiB. Scoring is **4 vCPU / 8 GiB**. For paddle, **W=2** is the real gate; W=3+ OOMs.
3. **Catastrophic false APPROVED = hard fail.** Prefer NEEDS_REVIEW. Strict Finding APPROVED; never promote OCR garbage to APPROVED.
4. **Decompose scores.** Class vs extract vs calib tells you where to spend (P1 was mostly class; regions helped extract on residual).
5. **Promote caps.** Do not stack every residual +0.2 Explore. Prefer **1–2 general** changes per integrate (anti-overfit).

---

## 2. Selective OCR (still true under paddle)

1. **Ultra-rich skip without Finding/DQ bleeds class.** Forms with rich text layers but stamp-only Finding never enter OCR → DENIED/APPROVED → NEEDS_REVIEW. That was the −3.2 train drop vs hist.
2. **P1 gate recovered ~+2.7 full-train points** (116.07 → 118.77 on tesseract): skip OCR only when Finding/DQ already in text + structure. **Keep P1** under paddle.
3. **Train OCR rate ~43% → ~83%** under P1; still under 6 s if the engine is efficient enough (paddle Docker ~5.7 s @2w).

---

## 3. Latency / systems

1. **OMP thrash:** ProcessPool × multi-thread tesseract/OpenMP made OCR wall explode. Always `OMP_THREAD_LIMIT=1` and single-thread BLAS per worker.
2. **CLAHE is not free.** Residual total can be identical with CLAHE on/off; Docker lat40 failed with CLAHE on (~6.27 s). Ship **CLAHE=0**.
3. **DPI/pages knobs trade quality for speed.** Tess lean dpi200/max_pages4 hurt train vs always-OCR hist. Paddle dpi150 + regions still hit residual/train targets.
4. **OpenCV/numpy must be declared.** Missing deps silently disabled deskew/CLAHE and residual collapsed (~104 vs ~108).

---

## 4. Brittleness vs maintainability

1. **Typo forests score residual, overfit texture.** `Fouing` / `DEMED` / train P≥0.97 risk maps / SPN denylists are campaign residue—not a good long-term OCR strategy.
2. **Geometry + trained rec** is the maintainable substitute for multi-PSM stamp ensembles.
3. **Keep policy enums in code** (visa, fee, risk names, schema formats). Move **reading** into the model.
4. **Pseudo-label FT (~73% self-OCR labels)** lifts stock paddle but caps quality; synth + GT-heavy labels are the right next data path (attempted; ship still uses best_ep5).

---

## 5. Engine bakeoffs (what not to reopen first)

| Engine | Residual-ish / note | Latency |
|--------|---------------------|---------|
| Tesseract multi-pass (integrate) | residual ~108.8 · train 119.27 | heavy; hist not 6s-measured |
| Tesseract P1 | 108.44 · train 118.77 | ~5–6 s host @4w |
| Base paddle full-page | **97.7** | very fast |
| Paddle FT mid full-page | ~105 | fast |
| **Paddle FT + regions (ship)** | **108.77 · train 118.91** | **~5.7 s Docker @2w** |
| LFM / Florence / GOT / SmolDocling | slow or risky | not shippable under 6s / bans |

VLMs/foundation models are **banned** in submitted runtime even if accurate.

---

## 6. Paddle-specific ops

1. **Vendored models only** at runtime (`MIB_PADDLE_MODELS`); network none.
2. **best_ep5** beat mid_export and `latest`; salvage best val checkpoint rather than finishing all epochs on CPU.
3. **Memory:** each paddle process is multi-GB; 8g box → **2 workers max** for this stack.
4. **Image size** is comfortable (~0.6 GiB); model size is tiny (~14 MiB).

---

## 7. Dead ends / low priority

- Stacking all residual Explore winners into one integrate  
- Always-on 275 DPI / 6 pages multi-PSM on 100% of PDFs under 6 s @4c  
- Residual-only micro-tunes without train evidence  
- Case-id lookup tables as “OCR”  
- Chasing Modal 119.27 with unlimited latency  

---

## 8. Suggested future work (ordered)

1. **Val 5k** under Docker 4c/8g (true ship-align).  
2. **Docker full train** confirm ≈ 118.91.  
3. **Synth + RecAug retrain** on clean labels (no residual leak); re-score residual + train + lat40.  
4. Slim **adjudicate** OCR-tolerant regexes once rec is strong enough (measure cat 0).  
5. Optional: hybrid full-page paddle + fewer regions if lat headroom tightens.  
6. Do **not** re-open VLM bakeoffs for submit runtime.

---

## 9. Scoreboard memory (high-water marks)

| Name | Stage | Score |
|------|-------|------:|
| hist promote_integrate residual | residual | 108.78 |
| hist promote_integrate full | train | **119.27** |
| ship_train_docker lean tess | train | 116.07 |
| promote_p1 residual / full | residual / train | 108.44 / **118.77** |
| **paddle FT ship residual / full** | residual / train | **108.77 / 118.91** |

Use these as regression baselines when changing the ship path.
