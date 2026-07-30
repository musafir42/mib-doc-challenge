# exp-extract — multi-page labeled field recovery

**Decision: promote** (residual primary ↑, catastrophic not worse)

## Hypothesis

Label\\nValue parsing was incomplete for purpose / fee / home / name / sponsor across page variants. Better multi-page labeled extract (plus attestation / biometric / registry / manual-correction sources) raises extraction points on residual without increasing catastrophic false approvals.

## Method

1. Inspect residual PDFs (`pypdf` text layer) vs `artifacts/residual_truth.csv` and baseline predictions.
2. Improve `worktrees/exp-extract/src/mib_solution/extract.py` only (adjudicate rules unchanged).
3. Score residual vs frozen `artifacts/residual_baseline/`.

## Residual diagnostics (text layer)

| Packet signal | ~count / 100 |
| --- | ---: |
| Almost empty (synthetic header only) | 25 |
| Fee receipt | 34 |
| Sponsor attestation | 21 |
| Intake FORM I-8090 | 14 |
| Registry extract | 12 |
| Biometric B-13 | 10 |
| Manual correction note | 3 |
| SYSTEM answer-key decoys | 11 |

Baseline residual field miss rates were highest on purpose / home / name / species; many misses are image-only. Recoverable headroom was mostly:

- purpose + name from **sponsor attestation** narrative
- species from **Species Match** on biometric slips
- sponsor / name from **Manual correction:** notes
- risk from **Registry Status: EMBARGO REVIEW**
- fee from **Waiver Code: DIP-WAIVER** (override paid/unpaid)

## Code changes (`extract.py`)

1. **Multi-source labeled extract** — `Label\\nValue` and `Label: Value`; aliases `Species Match`, `Observed flags`, `Registry Status`, `Waiver Code`.
2. **Manual corrections** highest priority for applicant name and sponsor id.
3. **Attestation parsers** — `Sponsor SPN-#### attests that NAME is expected on Earth for PURPOSE` (newline-tolerant purpose); `class VISA`.
4. **Fee** — active waiver codes (`DIP-WAIVER`, hardship-like) → `waived`.
5. **Risk** — map `EMBARGO REVIEW` / registry status phrases → `planetary_embargo` (etc.); keep free-form token scan on full text.
6. **Trusted text filter** — drop `SYSTEM: … answer key` lines for free-form name/purpose/attestation paths (no case-id answer tables in product code).

## Residual A/B

| Run | total / 150 | extraction | classification | calibration | cat |
| --- | ---: | ---: | ---: | ---: | ---: |
| residual_baseline | **62.21** | 16.62 | 33.00 | 12.59 | **0** |
| exp-extract | **64.24** | 18.33 | 33.20 | 12.70 | **0** |
| **Δ** | **+2.03** | **+1.71** | **+0.20** | **+0.12** | **0** |

- extraction raw: 1496 → 1650 (+154)
- classification raw: 330 → 332 (+2)
- confusion: removed baseline `APPROVED→DENIED` (1); still zero catastrophic false approvals

### Notable case moves

- **Gains:** attestation purpose/name (~15 purpose, ~13 name), biometric species, manual sponsor/name, fee DIP-WAIVER, `MIB-000054` risk `EMBARGO REVIEW` → DENIED (cls 2→8).
- **Tradeoff:** `MIB-000409` fee unpaid→waived (correct extract) dropped deny-on-unpaid path (cls 8→2); net cls still positive via embargo case + fixed false deny on corrected sponsor.

## Decision

**promote** — residual primary 64.24 > 62.21 with cat 0. Safe extraction-only improve; merge candidate for solution extract path after owner review (do not merge from this agent).

## Follow-ups (out of scope here)

- Image/OCR path for ~25 empty text packets (largest remaining ext ceiling).
- Adjudication policy for deny reasons without text-layer risk flags (separate exp-adjudicate).
