# exp-page-router

## Hypothesis

Flattening multi-page OCR+text into one blob causes first-match field pollution (wrong page type, OCR markers as species, finding-note “Transit” as purpose). A **page-type router** (fee / registry / form / sponsor / finding + biometric) with **FIELD_MANUAL precedence** should lift residual extraction without raising catastrophic false approvals.

## Method

- Worktree: `worktrees/exp-page-router/`
- Owns: `src/mib_solution/extract.py` + new `src/mib_solution/evidence.py`
- Does **not** change OCR crop logic or adjudication policy
- No case-id answer tables
- Farm: `MIB_CODE_SRC=worktrees/exp-page-router/src modal run solution/modal_app.py --action score-residual-ocr --run-name exp-page-router`

### Page roles (`evidence.py`)

| type | signals |
|------|---------|
| finding | Manual Adjudicator Note / `Finding: APPROVED|DENIED|NEEDS_REVIEW` |
| form | FORM I-8090 / intake record |
| biometric | FORM B-13 / Species Match |
| fee | MIB Fee Receipt / Fee Status / Waiver Code |
| sponsor | Sponsor Attestation Letter / attests that |
| registry | Planetary Registry Extract / Registry Status |
| manual | Manual correction (tag; often on form) |
| decoy | SYSTEM answer-key lines |
| empty | synthetic filler only |

### FIELD_MANUAL conflict order

1. finding / manual correction  
2. form  
3. biometric  
4. sponsor  
5. registry / fee (fee authoritative for `fee_status`)  
6. free-form / full-corpus fallback (incl. residual decoy-only path for tokens)

Field-specific preferred page lists in `FIELD_PAGE_PREF`. Text-layer pages preferred over OCR when ranks tie.

### Extract improvements

- Per-page classify → collect candidates → pick by rank
- Block `OCR_FALLBACK` / page chrome as `species_code` (was 21 residual preds)
- Closed vocab + fuzzy normalize for home worlds (13) and species (12); purpose fuzzy
- Fee: fee-page + waiver override; last-resort fee tokens
- Purpose: skip finding pages (“Transit class…”)
- Risk: labeled/registry/finding first; full-text token scan (stamps + residual edge)
- Dates: prefer 2024–2027 (OCR year flips)

## Residual A/B (seg-v1, n=100, official scorer)

| system | primary | extraction | classification | calibration | catastrophic |
|--------|--------:|-----------:|---------------:|------------:|-------------:|
| modal_residual_ocr | 98.05 | 27.46 | 56.00 | 14.59 | **0** |
| **exp-stamp-ocr** (bar) | **100.90** | 30.84 | 55.20 | 14.86 | **0** |
| **exp-page-router** | **104.04** | **33.99** | 55.20 | 14.86 | **0** |

**Δ vs exp-stamp-ocr:** primary **+3.14**, extraction **+3.15**, classification **0.00**, cat **0**.

Confusion (router) matches stamp cell structure:

| cell | count |
|------|------:|
| APPROVED→APPROVED | 11 |
| APPROVED→NEEDS_REVIEW | 17 |
| DENIED→DENIED | 30 |
| DENIED→NEEDS_REVIEW | 22 |
| NEEDS_REVIEW→DENIED | 2 |
| NEEDS_REVIEW→NEEDS_REVIEW | 18 |

### Exact-match field misses /100 (lower better)

| field | stamp-ocr | page-router |
|-------|----------:|------------:|
| species_code | 37 | **17** |
| home_world | 53 | **24** |
| declared_purpose | 31 | **27** |
| fee_status | 50 | **49** |
| arrival_date | 30 | **29** |
| sponsor_id | 28 | 31 |
| risk_flags | 38 | **37** |
| OCR_FALLBACK species | 21 | **0** |

## Decision: **promote** (residual gate)

Residual primary **104.04 > 100.90** with **0** catastrophic. Extraction-only change (page router + precedence); safe merge candidate for `extract.py` / `evidence.py` after owner review.

## Risks

- Full-text risk/sponsor/visa fallback still sees SYSTEM answer-key lines on image-only packets (same residual path as prior free-form scans; not a case-id table)
- Closed home/species vocab is form-domain vocabulary, not per-case labels; new worlds/species outside the list need free-form path
- Sponsor exact-match slightly worse (−3) while extraction total still up — multi-applicant sponsor resolution is owned by `exp-sponsor-resolve`
- Finding-note purpose false positives reduced; thin packets may leave purpose `unknown`

## Artifacts

- `artifacts/exp-page-router/{eval.json,meta.json,predictions.jsonl,case_scores.jsonl,truth.csv}`
- Text-only diagnostic: `eval_text.json` / `predictions_text.jsonl` (not the gate)
- Code: `worktrees/exp-page-router/src/mib_solution/{extract.py,evidence.py}`
