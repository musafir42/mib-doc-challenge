# exp-sponsor-resolve FINDINGS

Date: 2026-07-30  
Worktree: `worktrees/exp-sponsor-resolve/`  
Residual: `artifacts/residual.json` version **seg-v1** (n=100)  
Compare baseline: `artifacts/exp-stamp-ocr/` (**100.90**, cat **0**)

## Hypothesis

Multi-applicant / multi-source packets (FIELD_MANUAL: *use the applicant attached to the active case_id*) lose extraction points when:

1. OCR passport/intake decoys overwrite correct text-layer attestation / biometric / registry fields.
2. First-match `Applicant` / `Sponsor ID` picks a decoy person or revoked sponsor stamp.
3. Free-form purpose scan maps denial language (`Transit class cannot authorize…`) to `transit`.

Binding name / sponsor / purpose to the active case_id page, preferring structured text-layer over OCR soup, and dropping archived/decoy people should raise residual extraction without catastrophic false approvals.

## Method

1. Residual OCR field miss analysis vs `exp-stamp-ocr` (wrong person names, revoked SPN decoys, `OCR_FALLBACK` species).
2. Full-train multi-name source study (n≈50 text-layer conflicts): manual ≫ biometric/registry ≫ intake for decoy packets.
3. Change **only** `worktrees/exp-sponsor-resolve/src/mib_solution/extract.py` (OCR path unchanged = stamp-ocr).
4. Modal residual OCR:

```bash
PATH=$HOME/.local/bin:$PATH
MIB_CODE_SRC=worktrees/exp-sponsor-resolve/src \
  modal run solution/modal_app.py --action score-residual-ocr --run-name exp-sponsor-resolve
```

## Code changes (`extract.py`)

| Change | Why |
|--------|-----|
| Split `--- OCR_FALLBACK ---`; **prefer text-layer** for name/sponsor/purpose/visa/species/home/date/fee when non-missing | Stops OCR passport/sponsor soup from clobbering attestation |
| **Active case_id page bind** — chunk on form headers; drop foreign-case / “Archived adjacent applicant” blocks | FIELD_MANUAL multi-applicant rule |
| Multi-source **name resolve**: manual → biometric → registry → intake → attest | Intake passport often decoy; bio/registry track active person |
| Multi-source **sponsor**: manual → attestation → labeled → free SPN near active case | Fixes OCR `SPN-0007`/`SPN-0139` over real letter SPN |
| Name garbage filter with **word boundaries** (no `n/?a` inside `Ixonax`) | Drop `PASSPORT IMAGE`, `COPY ARTIFACT`, etc. |
| Species denylist `OCR_FALLBACK` / form chrome | OCR marker was winning free-form species |
| Purpose free-scan skips Finding / “Transit class” lines | Avoid false `transit` from denial notes |

No case-id answer tables. No adjudicate/OCR changes.

## Residual A/B (seg-v1, n=100, official scorer)

| Run | total | extraction | classification | calibration | cat |
|-----|------:|-----------:|---------------:|------------:|----:|
| modal_residual_ocr | 98.05 | 27.46 | 56.00 | 14.59 | **0** |
| **exp-stamp-ocr** (prior best) | **100.90** | 30.84 | 55.20 | 14.86 | **0** |
| **exp-sponsor-resolve** | **101.79** | **31.73** | 55.20 | 14.86 | **0** |
| Δ vs stamp-ocr | **+0.89** | **+0.89** | 0 | 0 | 0 |

- extraction raw: **2776 → 2856** (+80)
- confusion **unchanged** vs stamp-ocr (cls/cal flat; cat **0**)

Artifacts: `artifacts/exp-sponsor-resolve/{predictions.jsonl,eval.json,case_scores.jsonl,meta.json}`

### Notable field gains (vs stamp-ocr)

| case_id | field | was → now | mechanism |
|---------|-------|-----------|-----------|
| MIB-000151 | name | `Luvoss Lukesh PASSPORT IMAGE` → `Nexkesh Oriix` | text-layer attest beats OCR passport decoy |
| MIB-000717 | name | `Solvoss Qordane` → `Xanix Orimora` | same |
| MIB-000031 | sponsor | `SPN-0007` → `SPN-3187` | attest SPN beats OCR revoked decoy |
| MIB-000728 | sponsor | `SPN-0139` → `SPN-1679` | same |
| MIB-000003/016/030/383 | species | `OCR_FALLBACK` → real codes | denylist + text prefer |
| several | name | OCR typo → text-layer spelling | text-layer priority |

### Regressions (4 fields, net still +80 raw)

| case_id | field | note |
|---------|-------|------|
| MIB-000038 | sponsor | OCR digit preferred over slightly wrong text path |
| MIB-000052 | purpose | free-scan suppressed; OCR-only purpose lost |
| MIB-000404 | name | OCR name was luckier than bound text |
| MIB-000681 | fee | text-layer missing fee; fill path missed paid |

## Offline diagnostics (train text layer)

- Multi-name packets with source conflict: **46/50** correct names after resolve (priority manual > bio > registry > intake).
- Attest vs labeled sponsor conflicts: attest correct **8/8** (always prefer letter when both present).
- Full-train text-only name accuracy: **785/1000** (image-only remainder needs OCR fill).

## Decision: **promote candidate**

- Residual primary **101.79 > 100.90** with **catastrophic == 0**.
- Pure extraction lift; classification/calibration unchanged; no decision-rule risk.
- Safe merge of `extract.py` into `solution/` after owner residual re-score on main (do not rewrite `residual.json`).

## Risks

- Text-layer preference can lose when text is empty/wrong and OCR was luckier (4 residual field losses; net positive).
- Attest-vs-intake-only name conflicts remain ~50/50 without bio/registry (4 full-train misses); residual had no pure conflict of that shape.
- Purpose free-scan is more conservative (good for denial language; may leave purpose unknown without form/attest).
- No id tables; patterns are document-structure rules only.

## Follow-ups (out of scope)

- Page-level OCR segmentation (bind OCR PAGE blocks to case_id more tightly).
- Purpose fuzzy match for OCR typos (`xenchotany` → xenobotany) as separate exp.
- Merge with exp-approve multi-signal APPROVED after extract promote.
