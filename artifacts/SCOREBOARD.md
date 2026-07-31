# Scoreboard

Merge owner appends only. Residual row before full-data row for the same change name.  
Scale is always **/150**. Residual = hard subset (seg-v1 n=100), not a different metric.

| date | name | stage | slice | primary | catastrophic | notes | artifacts | git |
|------|------|-------|-------|---------|--------------|-------|-----------|-----|
| 2026-07-30 | process-drill | Setup | dummy residual | n/a | n/a | process drill skeleton; not a product score | worktrees/drill/experiments/drill/FINDINGS.md | 38ce888 |
| 2026-07-30 | baseline | Baseline | train_full | 98.88 | 0 | pypdf+label regex; deny-only; no auto-approve | artifacts/baseline/ | 1b4ff44 |
| 2026-07-30 | residual_baseline | Segment | residual_seg-v1 | 62.21 | 0 | baseline system on frozen residual n=100 | artifacts/residual_baseline/ | 283876d |
| 2026-07-30 | exp-extract | Explore | residual_seg-v1 | 64.24 | 0 | extract multi-source labels; residual A/B | artifacts/exp-extract/ | 283876d |
| 2026-07-30 | exp-adjudicate | Explore | residual_seg-v1 | 74.85 | 0 | finding notes + deny rules; residual A/B | artifacts/exp-adjudicate/ | 283876d |
| 2026-07-30 | exp-risk | Explore | residual_seg-v1 | 71.60 | 0 | registry/risk signals; residual A/B | artifacts/exp-risk/ | 283876d |
| 2026-07-30 | promote_seg1 | Integrate | residual_seg-v1 | 75.37 | 0 | merged extract+adjudicate; no auto-APPROVED; residual+full | artifacts/promote_seg1/ | 283876d |
| 2026-07-30 | promote_seg1_full | Integrate | train_full | 106.95 | 0 | after residual promote; Finding APPROVED only for approve | artifacts/promote_seg1/train_eval.json | 283876d |
| 2026-07-30 | modal_residual_text | Explore | residual_seg-v1 | 75.37 | 0 | historical Modal text map = promote_seg1 | artifacts/modal_residual_text/ | modal-legacy |
| 2026-07-30 | modal_residual_ocr | Explore | residual_seg-v1 | 98.05 | 0 | historical Modal OCR +22.7 vs text; tesseract+poppler | artifacts/modal_residual_ocr/ | modal-legacy |
| 2026-07-30 | modal_full_ocr | Integrate | train_full | 114.20 | 0 | historical Modal full train OCR | artifacts/modal_full_ocr/ | modal-legacy |
| 2026-07-30 | promote_ocr | Integrate | residual_seg-v1 | 98.05 | 0 | OCR pipeline into solution/ | artifacts/modal_residual_ocr/ | 3497546 |
| 2026-07-30 | exp-stamp-ocr | Explore | residual_seg-v1 | 100.90 | 0 | stamp/crop OCR | artifacts/exp-stamp-ocr/ | explore |
| 2026-07-30 | exp-approve | Explore | residual_seg-v1 | 100.49 | 0 | safe Finding APPROVED path | artifacts/exp-approve/ | explore |
| 2026-07-30 | exp-calib | Explore | residual_seg-v1 | 99.06 | 0 | path confidence calibration | artifacts/exp-calib/ | explore |
| 2026-07-30 | exp-conf-isotonic | Explore | residual_seg-v1 | 101.68 | 0 | feature conf model | artifacts/exp-conf-isotonic/ | explore |
| 2026-07-30 | exp-deskew | Explore | residual_seg-v1 | 101.70 | 0 | projection deskew before stamp OCR | artifacts/exp-deskew/ | explore |
| 2026-07-30 | exp-deskew-v2 | Explore | residual_seg-v1 | 102.01 | 0 | stronger deskew + additive crop binarize | artifacts/exp-deskew-v2/ | explore |
| 2026-07-30 | exp-red-stamp | Explore | residual_seg-v1 | 101.10 | 0 | red-channel stamp OCR | artifacts/exp-red-stamp/ | explore |
| 2026-07-30 | exp-psm-grid | Explore | residual_seg-v1 | 101.90 | 0 | multi-psm OCR ensemble | artifacts/exp-psm-grid/ | explore |
| 2026-07-30 | exp-evidence | Explore | residual_seg-v1 | 102.81 | 0 | page roles / precedence extract | artifacts/exp-evidence/ | explore |
| 2026-07-30 | exp-finding-fuse | Explore | residual_seg-v1 | 102.98 | 0 | adjudicator finding fuse | artifacts/exp-finding-fuse/ | explore |
| 2026-07-30 | exp-page-router | Explore | residual_seg-v1 | 104.04 | 0 | page-type field routing | artifacts/exp-page-router/ | explore |
| 2026-07-30 | exp-deny-recall | Explore | residual_seg-v1 | 104.87 | 0 | best single residual Explore; OCR deny signals | artifacts/exp-deny-recall/ | explore |
| 2026-07-30 | exp-review-merge | Explore | residual_seg-v1 | 102.47 | 0 | conflict→NEEDS_REVIEW | artifacts/exp-review-merge/ | explore |
| 2026-07-30 | exp-uncertainty | Explore | residual_seg-v1 | 102.07 | 0 | honest conf | artifacts/exp-uncertainty/ | explore |
| 2026-07-30 | exp-sponsor-resolve | Explore | residual_seg-v1 | 101.79 | 0 | multi-applicant/sponsor | artifacts/exp-sponsor-resolve/ | explore |
| 2026-07-30 | exp-omit-thin | Explore | residual_seg-v1 | 100.90 | 0 | omit thin cases — no gain; kill | artifacts/exp-omit-thin/ | explore |
| 2026-07-30 | exp-hidden-strip | Explore | residual_seg-v1 | 100.21 | 0 | kill vs stamp bar; policy-correct strip | artifacts/exp-hidden-strip/ | explore |
| 2026-07-30 | exp-decoy-fields | Explore | residual_seg-v1 | 100.04 | 0 | kill vs stamp bar | artifacts/exp-decoy-fields/ | explore |
| 2026-07-30 | exp-injection | Explore | residual_seg-v1 | 98.75 | 0 | kill vs stamp bar; hardening reference | artifacts/exp-injection/ | explore |
| 2026-07-30 | promote_integrate | Integrate | residual_seg-v1 | **108.78** | 0 | merged Explore winners into solution/; current product | artifacts/promote_integrate/ | main |
| 2026-07-30 | promote_integrate_full | Integrate | train_full | **119.27** | 0 | full train after integrate; cat 0 | artifacts/promote_integrate_full/ | main |
| 2026-07-30 | docker_ship_smoke | Ship-align | smoke10 | 132.13* | 0 | Docker READY; *smoke only, not full-train comparable | artifacts/docker_ship/ | main |
| 2026-07-31 | residual_reconfirm | Integrate | residual_seg-v1 | **104.45** | 0 | Host n=100, MIB_WORKERS=8, OMP=1, wall ~314s; **below** promote 108.78 — cv2/numpy missing from pyproject (deskew/CLAHE/binarize no-op); tesseract 4.1.1 | artifacts/residual_reconfirm/ | 2aafd12 |
| 2026-07-31 | residual_reconfirm_cv2 | Integrate | residual_seg-v1 | **104.74** | 0 | After uv add opencv-python-headless+numpy; wall ~408s W=8 OMP=1; still ≪108.78 — host tesseract **4.1.1** vs Modal/Docker tess5 likely; latency Explore fan-out ACTIVE | artifacts/residual_reconfirm_cv2/ | 2aafd12 |
| 2026-07-31 | lat-parallel-ship | Explore | residual_seg-v1 | **104.74** | 0 | ProcessPool predict_dir + OMP=1 + MIB_WORKERS=4 in run.sh; **quality parity** with residual_cv2 — ship packaging YES | artifacts/lat-parallel-ship/ | explore |
| 2026-07-31 | lat-dpi | Explore | residual_seg-v1 | **104.14** | 0 | dpi 200 / max_pages 4 defaults; −0.60 vs cv2; microbench ~1.58× faster OCR vs 275/6; latency candidate | artifacts/lat-dpi/ | explore |
| 2026-07-31 | lat-psm-lite | Explore | residual_seg-v1 | **102.29** | 0 | full+crop psm 6 only; −29% OCR time; residual **below** 104.45 floor — NO solo promote | artifacts/lat-psm-lite/ | explore |
| 2026-07-31 | lat-tiered | Explore | residual_seg-v1 | **100.38** | 0 | auto light/heavy final; residual ≥100 cat0 but −4.4 vs cv2 — conditional only | artifacts/lat-tiered/ | explore |
| 2026-07-31 | lat-crops-lite | Explore | residual_seg-v1 | **103.96** | 0 | 3-band crops no adaptive; ~31% faster OCR; below floor — NO solo | artifacts/lat-crops-lite/ | explore |
| 2026-07-31 | lat-select-ocr | Explore | residual_seg-v1 | **108.89** | 0 | smarter should_ocr; residual OCR 86% / train skip ~58%; **best residual**; latency YES | artifacts/lat-select-ocr/ | explore |
| 2026-07-31 | promote_lat_ship | Integrate | residual_seg-v1 | **108.20** | 0 | merge select-ocr+parallel ship+dpi200/4+opencv; residual wall ~301s@8; train40 **2.67 s/PDF @4 workers** (ocr~40%) under 6s budget | artifacts/promote_lat_ship/ | 2aafd12 |

## Campaign note (2026-07-30)

- **Default compute going forward:** high-CPU cloud VM + local Docker / multi-process. Modal farm retired as default (see `artifacts/HANDOFF.md`, `GROK_BUILD.md`).
- **Next scoreboard rows expected:** residual reconfirm on new box; Docker full train; validation package.

## Campaign note (2026-07-31)

- Residual reconfirm on Vultr box: **104.45 / 150 cat 0** (not ~108.78). Root cause: `opencv-python` / `numpy` never declared in `solution/pyproject.toml`; `ocr.py` optional imports fail → weak OCR path. Docker image also lacks OpenCV. Ship path must add deps **or** accept lower score; also must meet **6 s/PDF @ 4 vCPU**.
- Prior thrash: 8 workers × multi-thread tesseract (no `OMP_THREAD_LIMIT=1`) made single OCR calls take minutes; fixed for reconfirm.
