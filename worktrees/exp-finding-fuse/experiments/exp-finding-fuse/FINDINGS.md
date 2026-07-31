# exp-finding-fuse

Date: 2026-07-30  
Worktree: `worktrees/exp-finding-fuse/`  
Owns: `src/mib_solution/adjudicate.py` (Finding fuse only)  
Residual: `artifacts/residual.json` version **seg-v1** (n=100)  
Bar: beat **exp-stamp-ocr 100.90** with **cat 0**

## Hypothesis

Adjudicator Finding notes are highest-trust evidence (FIELD_MANUAL stamp / signed note). Baseline takes the first strict `Finding:\s*(APPROVED|DENIED|NEEDS_REVIEW)` match on the merged text+OCR blob. That misses OCR-only notes with:

- missing/odd punctuation (`Finding DENIED`, `Finding. DENIED`)
- OCR typos (`DENED`, `DEMED`)
- garbled “Finding” near `Manual Adjudicator Note` with a visible stamp word

Fusing Findings **per layer** (text vs `--- OCR_FALLBACK ---`) with OCR-tolerant parsing and stamp-over-form precedence should recover more correct DENIED/APPROVED without catastrophic false approvals.

## Method

Changed only `adjudicate.py`:

1. **Layer split** on `--- OCR_FALLBACK ---` (from `merge_text_layers`).
2. **OCR-tolerant Finding regex** — optional `:` / `.` / `-`, common `Finding` misspellings.
3. **Token normalize** — `DENED`/`DEMED`/short `DEN*` → DENIED; APPROVED variants; REVIEW → NEEDS_REVIEW.
4. **Manual Adjudicator fallback** — if no Finding line, recover stamp word inside a Manual Adjudicator window.
5. **Fuse policy**
   - text-only or OCR-only Finding → use it (stamp-class)
   - both agree → that decision
   - APPROVED vs DENIED across layers → **NEEDS_REVIEW** (never sole false APPROVED)
6. Finding path still runs **before** form deny/approve rules (stamp precedence over form fields).
7. No multi-field auto-APPROVED; no case-id tables.

## Residual A/B (seg-v1, Modal OCR map)

| system | primary | extraction | classification | calibration | catastrophic |
|--------|--------:|-----------:|---------------:|------------:|-------------:|
| modal_residual_ocr | 98.05 | 27.46 | 56.00 | 14.59 | **0** |
| exp-stamp-ocr | **100.90** | 30.84 | 55.20 | 14.86 | **0** |
| **exp-finding-fuse** | **102.98** | 30.84 | **57.00** | **15.13** | **0** |

Δ vs stamp-ocr: **+2.08** primary, **+1.80** classification, cat **0**.

### Confusion delta (vs stamp-ocr)

| cell | stamp-ocr | finding-fuse |
|------|----------:|-------------:|
| DENIED→DENIED | 30 | **32** |
| DENIED→NEEDS_REVIEW | 22 | **20** |
| APPROVED→APPROVED | 11 | **12** |
| APPROVED→NEEDS_REVIEW | 17 | **16** |
| NEEDS_REVIEW→DENIED | 2 | 2 |
| cat false approvals | 0 | **0** |

### Residual adjudication deltas (all gains, no losses)

| case_id | truth | stamp-ocr → fuse | driver |
|---------|-------|------------------|--------|
| MIB-000283 | DENIED | NR → DENIED | OCR `Finding DEMED` / `Finding DENIED` |
| MIB-000747 | DENIED | NR → DENIED | OCR `Finding: DENED` |
| MIB-000047 | APPROVED | NR → APPROVED | OCR/text Finding fuse recovery |

## Decision: **promote candidate**

- Residual **102.98 > 100.90**, catastrophic **0**
- Pure adjudicate Finding path; extraction/OCR unchanged
- Safe conflict policy (APPROVED∩DENIED → NEEDS_REVIEW)

## Risks / residual headroom

- Fuzzy DEN* tokens could theoretically fire on noise; mitigated by requiring Finding-like prefix or Manual Adjudicator window, and conflict→NR
- Still ~20 DENIED→NR (image-only DQ stamps without recoverable Finding text) and ~16 APPROVED→NR (no Finding stamp; needs separate safe-approve path)
- Full-train regression not scored in this experiment

## Artifacts

- `artifacts/exp-finding-fuse/{eval.json,meta.json,predictions.jsonl,case_scores.jsonl,truth.csv}`
- Code: `worktrees/exp-finding-fuse/src/mib_solution/adjudicate.py`

## Command

```bash
PATH=$HOME/.local/bin:$PATH
MIB_CODE_SRC=worktrees/exp-finding-fuse/src \
  modal run solution/modal_app.py --action score-residual-ocr --run-name exp-finding-fuse
```
