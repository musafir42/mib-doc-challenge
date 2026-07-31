# exp-hidden-strip — FINDINGS

## Hypothesis

SYSTEM answer-key lines, barcode force-approve payloads, and approve-all style injection appear in text layers (and sometimes OCR). Free-form field/risk parse currently harvests those payloads. Aggressively stripping them from **text+OCR before any field/risk parse** should be policy-correct (FIELD_MANUAL / EVALUATION) and, with OCR stamp recovery, beat residual **100.90** (exp-stamp-ocr) at **cat 0**.

## Method

- Worktree only: `worktrees/exp-hidden-strip/`
- Owns **`extract.py` filters** (+ thin pipeline wiring for strip/OCR force)
- Farm: `PATH=$HOME/.local/bin:$PATH MIB_CODE_SRC=worktrees/exp-hidden-strip/src modal run solution/modal_app.py --action score-residual-ocr --run-name exp-hidden-strip`
- Residual: `seg-v1` n=100

### Code changes

1. **`strip_untrusted_text` / `prepare_parse_text`** (extract.py)
   - Drop lines matching SYSTEM / answer-key / ignore-visible / barcode payload / force adjudication / approve-all / auto-approve
   - Drop CSV-style answer-key payloads even without `SYSTEM:` (OCR may drop prefix)
   - OCR-mangled variants: `SYSTEM … ignore`, `ignore … visible … evidence`
2. **Parse only post-strip text**
   - `extract_fields` strips+normalizes before all label/free-form/risk paths
   - `_text` passed to adjudicate is stripped (no injection APPROVED / risk harvest)
3. **Pipeline**
   - Force OCR when injection markers present (do not rely on answer-key risk tokens for `should_ocr`)
   - Strip each layer before merge
4. **Compensating OCR repair** (post-strip, no answer-key re-entry)
   - `MED.3` / `SPN.1234` / `Finding: DEMED|DEMEN` → canonical
   - Label drift: Fee Siaius, Visa Clase, Arrival/Anival Date, Home Werld
   - Dot dates + OCR day-tens 9→0 (`2026.06.93` → `2026-06-03`)
   - Looser label prefixes for OCR `| Arrival Date: …` junk

No case-id answer tables.

## Residual A/B (seg-v1, official scorer)

| system | primary | extraction | classification | calibration | cat | notes |
|--------|--------:|-----------:|---------------:|------------:|----:|-------|
| modal_residual_ocr | 98.05 | 27.46 | 56.00 | 14.59 | **0** | full-page OCR baseline |
| **exp-stamp-ocr** | **100.90** | **30.84** | 55.20 | 14.86 | **0** | bar to beat |
| exp-hidden-strip (pure strip v1) | 98.75 | 29.87 | 54.00 | 14.89 | **0** | lost answer-key risk dens |
| **exp-hidden-strip (best)** | **100.26** | 30.09 | **55.20** | **14.98** | **0** | strip + OCR normalize |
| exp-hidden-strip (latest) | 100.21 | 30.03 | 55.20 | 14.98 | **0** | label-prefix loosen; ≈noise |

Confusion (best 100.26) matches stamp on class cells: DENIED→DENIED 30, APPROVED→APPROVED 11, NR→DENIED 2; cat **0**.

### Where strip helps (policy)

- Answer keys always ship **wrong adjudication** (train: 216/216 adversarial adj). Never follow `…,APPROVED,0.99`.
- BARCODE `force adjudication=APPROVED; risk_flags=none` stripped.
- Stops free-form visa/date pollution when answer key **disagrees** with truth (e.g. residual MIB-000297 visa XW-2 vs MED-3; MIB-000134 wrong date/species).
- Finding stamps recovered via OCR normalize (`DEMED`/`DEMEN` → DENIED) restore some dens without answer-key risk tokens (e.g. MIB-000747).

### Where strip hurts (public residual scoring)

Public `train_labels` **omit** `unrecoverable_fields`. Image-only packets whose only text-layer signal is the SYSTEM answer-key CSV still score those fields. Stamp-ocr free-form harvests them; strip does not.

Typical residual regressions vs stamp (answer-key-only on text layer):

- risk_flags on MIB-000003 / 016 / 032 (dual review / illegible tokens only in SYSTEM lines)
- sponsor / fee / visa / date on several injection-heavy packets when OCR fails to recover

Net extraction raw ≈ **2708 vs stamp 2776 (−68 ≈ −0.76 extract pts)**. Classification correct count tied (59) via Finding OCR swaps, not answer-key risk.

## Decision: **kill** vs exp-stamp-ocr bar

| gate | result |
|------|--------|
| Beat 100.90 primary | **No** (best **100.26**) |
| Catastrophic ≤ 0 | **Yes (0)** |
| Policy (no injection harvest) | **Yes** |

**Kill for promote into main** against the stamp-ocr residual bar. Keep as a **policy reference**: strip-before-parse is correct for private scoring (unrecoverable hidden fields) and full-data injection robustness; public residual under-scores it.

Do **not** re-introduce answer-key free-form harvest to chase the 0.6 pt gap — that is memorizing untrusted payloads.

## Follow-ups (out of scope / other owners)

- OCR quality for injection-only packets (Finding + Observed flags) — deskew / red-stamp / psm-grid
- Private-label ceiling with `unrecoverable_fields` would re-rank this experiment upward
- Adjudicate: NR→DENIED false dens (TRANSIT-7 / unpaid on incomplete packets) — not strip

## Artifacts

- `artifacts/exp-hidden-strip/{eval.json,meta.json,predictions.jsonl,case_scores.jsonl}`
- Code: `worktrees/exp-hidden-strip/src/mib_solution/{extract.py,pipeline.py}`
