# Finding recovery analysis (residual D→NR / A→NR)

Date: 2026-08-01  
Baseline: trusted_fix residual cat0 **104.22**, full train **114.01**

## Residual failure inventory

| Bucket | n | Root cause |
|--------|---|------------|
| DENIED→NR | 24 | |
| · missing structured deny | 16 | Truth has DQ / unpaid / multi-review; extract risk=none / fee≠unpaid |
| · no Finding OCR | 7 | OCR never produces a Finding-like stamp |
| · Finding regex miss | 1 | `FindingDENED` / `Finding:DENED` (MIB-000747) |
| APPROVED→NR | 18 | All risk=none; need clean Finding APPROVED |

## Probe conclusions (product path, trusted_corpus)

1. **should_ocr is already True** on sampled DNR/ANR — gate is not the issue.
2. **Strict `Finding:\s*(APPROVED|DENIED|…)` hits zero** on residual hard slice.
3. **Trusted path is not dropping recoverable Findings** — when OCR has no stamp, trusted has none; when OCR has `FindingDENED`, trusted keeps it (regex then fails).
4. **Decoy noise**: SAMPLE DENIAL / barcode “force adjudication=APPROVED” appear often; trusted_corpus already strips answer-key decoys but not all scan tab headers.
5. **Recoverable near-misses (clean, not typo forests)**:
   - DNR `MIB-000747`: `FindingDENED`, `Finding:DENED`
   - DNR `MIB-000151` (intermittent OCR): `FindngDENED` + garbled `plonetary_embsrgo` (garble not fixed)
   - ANR `MIB-000071`: `Findng APPROVED`
6. **Most DQ/unpaid DNR**: stamps are image-only or OCR garbage — not fixable with maintainable text rules. Needs OCR quality / geometry, not adjudicate forests.

## Chosen fix (anti-overfit)

Structural Finding flex only:

- Label: `Finding` | `Findng` | `Findin` (drop of one letter i or g)
- Separator: optional `[:.\-]?` and whitespace (covers `FindingDENIED`, `Finding: DENIED`)
- Decision: full tokens + `DENED`→DENIED **only** when labeled as Finding
- APPROVED decision stays exact `APPROVED` (no APPROV)

Aligned in `adjudicate.py`, `evidence.py` page type, `ocr.py` structure probe.

**Not done (brittle / low ROI):** OCR garble maps for embargo/biohazard, EXTRA SPNs, free-text DENIED without Finding label.

## Residual re-score (after fix)

| | total | class | cat0 | D→NR | A→A | D→D |
|--|------:|------:|-----:|-----:|----:|----:|
| trusted_fix baseline | 104.22 | 54.1 | 0 | 24 | 10 | 28 |
| **finding_recover** | **106.26** | **55.9** | **0** | **22** | **11** | **30** |
| delta | **+2.05** | **+1.8** | 0 | −2 | +1 | +2 |

Flips (all correct):
- `MIB-000747` NR→DENIED (`FindingDENED`)
- `MIB-000151` NR→DENIED (`FindngDENED`)
- `MIB-000071` NR→APPROVED (`Findng APPROVED`)

No catastrophic false approvals.

## Full train re-score

| | total | class | cat0 | A→A | D→D | D→NR | A→NR |
|--|------:|------:|-----:|----:|----:|-----:|-----:|
| trusted_fix baseline | 114.01 | 57.85 | 0 | 58 | 309 | 122 | 228 |
| **finding_recover** | **114.80** | **58.45** | **0** | **62** | **315** | **116** | **224** |
| delta | **+0.79** | **+0.60** | 0 | +4 | +6 | −6 | −4 |

Extract unchanged (40.77). Calibration +0.19. Runtime ~36 min @ MIB_WORKERS=4.
