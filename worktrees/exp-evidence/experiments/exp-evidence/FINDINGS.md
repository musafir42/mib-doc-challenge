# exp-evidence — cross-page evidence resolution

## Hypothesis

Multi-page residual packets mix intake forms, biometric slips, sponsor letters,
registry extracts, fee receipts, adjudicator notes, OCR noise, and SYSTEM
answer-key decoys. Resolving each field by **FIELD_MANUAL trusted-evidence
order** (plus active `case_id` filtering and multi-applicant rules) should lift
extraction vs stamp-OCR residual without catastrophic false approvals.

## Method

- Worktree: `worktrees/exp-evidence/`
- New: `src/mib_solution/evidence.py` (page typing + candidate rank + pick)
- Own: `src/mib_solution/extract.py` (wired through evidence resolution)
- OCR path unchanged (inherits stamp-region OCR from worktree base)
- Farm: `MIB_CODE_SRC=worktrees/exp-evidence/src` + Modal `score-residual-ocr`

### Resolution rules

| Rank | Source | Notes |
|-----:|--------|-------|
| 0 | Manual correction (applicant/sponsor) | Highest — signed note |
| 1 | Adjudicator note page | Finding / stamp page |
| 2 | Intake FORM I-8090 | Labeled fields preferred |
| 3 | Biometric FORM B-13 | Species Match preferred for species |
| 4 | Sponsor attestation | Narrative name/purpose/visa/sponsor |
| 5 | Registry extract | Name/world/species/date/status |
| 6 | Fee receipt | Authoritative for fee_status / waiver |
| 7 | Untyped / machine text | Free-form fallback |
| 90 | SYSTEM answer-key decoy | **Last resort only** — never overrides visible |

Additional rules:

1. **Active case_id** = PDF filename stem; pages that only mention other MIB ids are dropped.
2. **Multi-applicant / identity conflict:** when form name ≠ biometric/registry name and there is **no** manual correction, prefer biometric/registry name; emit `identity_conflict` only for explicit tokens or clean text-layer form-vs-bio conflict (not OCR name noise).
3. **Decoy filter:** SYSTEM answer-key lines are not used as high-trust evidence; parsed only as rank-90 fill when no visible candidate exists.
4. **OCR pollution:** reject `OCR_FALLBACK`, `NEEDS_REVIEW`, etc. as species; strip `PASSPORT IMAGE` / `COPY ARTIFACT` from names; complete OCR fragments onto known species/home-world vocab when confident.
5. **Dates:** reject implausible years/days; prefer labeled form/registry over free OCR (fixes 2028/2008 OCR year glitches).
6. **Risk:** union of labeled Observed flags / Registry Status / free tokens on trusted pages; decoy risk only if nothing else found.

## Residual A/B (seg-v1, n=100, official scorer, Modal OCR)

| system | primary | extraction | classification | calibration | catastrophic |
|--------|--------:|-----------:|---------------:|------------:|-------------:|
| modal_residual_ocr | 98.05 | 27.46 | 56.00 | 14.59 | **0** |
| **exp-stamp-ocr** (prior best) | **100.90** | 30.84 | 55.20 | 14.86 | **0** |
| **exp-evidence** | **102.81** | **32.76** | 55.20 | 14.86 | **0** |
| Δ vs stamp-ocr | **+1.91** | **+1.91** | 0.00 | 0.00 | 0 |

- extraction raw: **2776 → 2948** (+172)
- classification raw: 552 unchanged (same confusion matrix as stamp-ocr)
- catastrophic false approvals: **0**

Confusion (identical to stamp-ocr):

| cell | count |
|------|------:|
| APPROVED→APPROVED | 11 |
| APPROVED→NEEDS_REVIEW | 17 |
| DENIED→DENIED | 30 |
| DENIED→NEEDS_REVIEW | 22 |
| NEEDS_REVIEW→DENIED | 2 |
| NEEDS_REVIEW→NEEDS_REVIEW | 18 |

### Field-level deltas vs stamp-ocr

| field | gains | losses |
|-------|------:|-------:|
| home_world | 15 | 1 |
| species_code | 13 | 5 |
| applicant_name | 8 | 1 |
| declared_purpose | 4 | 1 |
| arrival_date | 3 | 1 |
| risk_flags | 1 | 0 |
| fee_status | 1 | 0 |
| sponsor_id | 0 | 2 |

Lift drivers: species completion (`OCR_FALLBACK`/`AQL`/`ONIAN` → known codes), home-world cleanup/vocab, name scrub + multi-applicant preference, date plausibility, decoy-as-last-resort filling empty OCR packets without overriding visible form/registry.

## Decision: **promote** (residual gate)

Residual primary **102.81 > 100.90** with **cat 0**. Pure extraction improvement on top of stamp-OCR; adjudication confusion unchanged.

## Artifacts

- `artifacts/exp-evidence/{eval.json,meta.json,predictions.jsonl,case_scores.jsonl,truth.csv}`
- Code: `worktrees/exp-evidence/src/mib_solution/{evidence.py,extract.py}`
- Compare: `artifacts/exp-stamp-ocr/`

## Risks / follow-ups

- Answer-key last-resort can still inject wrong visa/risk when OCR finds nothing (e.g. image-only biohazard + wrong key visa); policy-correct alternative is leaving fields unknown (lower residual extract).
- Species/home-world vocab completion can over-correct rare novel codes (not seen on residual).
- Classification headroom still large (APPROVED→NR 17, DENIED→NR 22) — not owned by this experiment.
