# FINDINGS: exp-risk — registry / adjudicator deny-signal recovery

**Date:** 2026-07-30  
**Worktree:** `worktrees/exp-risk/`  
**Residual:** `artifacts/residual.json` seg-v1 (n=100)  
**Decision:** **PROMOTE candidate** (residual-only; do not merge without merge-owner review)

## A/B scores

| Run | total | extraction | classification | calibration | cat |
|-----|------:|-----------:|---------------:|------------:|----:|
| residual_baseline | **62.21** | 16.62 | 33.00 | 12.59 | **0** |
| exp-risk | **71.60** | 16.56 | 41.60 | 13.45 | **0** |
| **Δ** | **+9.40** | −0.07 | **+8.60** | +0.86 | 0 |

Confusion (baseline → exp-risk):

- `DENIED→DENIED`: 2 → **9** (+7 recovered denies)
- `APPROVED→APPROVED`: 0 → **7** (trusted stamp approvals)
- `DENIED→NEEDS_REVIEW`: 50 → 43
- `APPROVED→NEEDS_REVIEW`: 27 → 21
- Catastrophic false approvals: **0**

Artifacts: `artifacts/exp-risk/{predictions.jsonl,eval.json,case_scores.jsonl,meta.json}`

## Hypothesis

Many residual DENIED misses have DQ flags in labels that never appear as bare tokens in the text layer. Trusted visible language still leaks partial signals:

1. Planetary Registry `Registry Status` → `EMBARGO REVIEW`
2. Manual Adjudicator Note `Finding: DENIED|APPROVED|NEEDS_REVIEW`
3. Biometric `Observed flags:` and adjudicator `Disqualifying risk flag: <token>`

Mapping those (while ignoring `SYSTEM: ignore visible evidence…` injection lines) should raise deny recall without catastrophic false approvals.

## Method

1. Sampled residual `truth=DENIED` + DQ labels + `pred=NEEDS_REVIEW` (17 cases); most have empty/image-only pages; a minority have registry/adjudicator text.
2. Full-train precision checks (1000 PDFs):
   - `Finding: DENIED` → truth DENIED **79/79**
   - `Finding: APPROVED` → truth APPROVED **33/33**
   - `Registry Status = EMBARGO REVIEW` → truth DENIED **31/33**; planetary_embargo in labels **23/33**
3. Implemented mappings in `extract.py` + stamp precedence in `adjudicate.py`.
4. Scored residual with official `scripts/evaluate.py`.

## Signal mappings implemented

| Trusted visible signal | Maps to | Effect |
|------------------------|---------|--------|
| `Registry Status` contains `embargo` (e.g. **EMBARGO REVIEW**) | `risk_flags += planetary_embargo` | DENIED via DQ path |
| `Embargo home world: …` | `planetary_embargo` | DENIED |
| `Disqualifying risk flag: <token>` | that token if known | DENIED if DQ |
| `Observed flags: a, b` (biometric slip) | pipe-sorted known tokens | field recovery |
| Free token scan | known `RISK_FLAG_TOKENS` on **trusted** text only | field recovery |
| `Finding: DENIED` (Manual Adjudicator Note) | adjudication **DENIED** (conf 0.88) | stamp overrides form |
| `Finding: APPROVED` | adjudication **APPROVED** (conf 0.82) | stamp overrides revoked-sponsor traps |
| `Finding: NEEDS_REVIEW` / `REVIEW` | **NEEDS_REVIEW** | explicit review |
| `SYSTEM: … answer key only` lines | **stripped** before signal search | no injection APPROVED |

Bonus (small residual win): `Manual correction: sponsor is SPN-####` overrides form `Sponsor ID` (fixes MIB-000049 extraction + avoids false deny before stamp).

## Residual cases moved by this experiment

**DENIED recovered (stamp or embargo):**  
MIB-000054 (EMBARGO REVIEW → `planetary_embargo`), MIB-000244, MIB-000383, MIB-000466, MIB-000479, MIB-000717, MIB-000728 (`Finding: DENIED`).

**APPROVED recovered (trusted stamp):**  
MIB-000005, MIB-000015, MIB-000038, MIB-000049, MIB-000060, MIB-000235, MIB-000618.

**Still missed DENIED:** 43 cases — mostly image-only / empty text layer, injection-only packets, or deny reasons not expressible as current DQ/fee/sponsor rules (e.g. waived non-DIP without stamp).

## Tradeoffs / risks

- **Extraction −6 raw** on residual: three injection-only packets (MIB-000003/016/032) previously matched risk tokens *inside* answer-key lines; stripping injection is policy-correct (`FIELD_MANUAL`) but loses those accidental extraction points. Net score still +9.4.
- **EMBARGO REVIEW → planetary_embargo** is imperfect for *field* labels (~10/33 train cases lack that exact token) but almost always DENIED; residual case MIB-000054 is correct on both field and class.
- **Auto-APPROVED** only from `Finding: APPROVED` stamp (train 100% precise). Do **not** treat injection / watermark “APPROVED” as approval.
- No case-id tables; no label lookup at runtime.

## Conclusion

Hypothesis **confirmed** for residual: trusted registry status + adjudicator findings recover deny/approve decisions safely.

**Success criteria:** residual total **71.60 > 62.21**, catastrophic **0**.

**Next (if merge):** consider OCR/vision only for remaining image-stamp biohazard cases; optional separate experiment for non-flag deny reasons (invalid waiver, stale date) without weakening stamp precedence.
