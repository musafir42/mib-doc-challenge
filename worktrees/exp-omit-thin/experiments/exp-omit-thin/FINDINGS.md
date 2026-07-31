# exp-omit-thin

## Hypothesis

For thin / untrusted packets, **omitting** the case from `predictions.jsonl` (pay missing-case penalty `10 * missing / N`) can beat submitting a low-value or catastrophic-risk prediction. Residual bar: **100.90 cat0** (exp-stamp-ocr / promote OCR).

## Scorer EV (why omit is hard)

Under `mib_weighted_v1` the tradeoff is **scale-invariant in N**:

| quantity | primary contribution |
|----------|---------------------|
| 1 classification raw point | `10/N` |
| missing one case | `10/N` |
| 1 extraction raw point | `≈ 50/(45N)` ≈ `(10/N)/9` |

So **1 classification raw ≡ 1 missing-case unit**; extraction is ~1/9 unit per raw point.

Implications:

1. **`NEEDS_REVIEW` never omit** — scorer floor is **2 raw** (conservative_review) for any real truth label → ≥2 missing units before extraction.
2. **Wrong hard decision (0 raw)** needs near-zero extraction *and* bad calibration before omit wins.
3. **Catastrophic false approval (−4 raw)** → omit is strongly EV+ vs keeping APPROVED.
4. **But demoting to `NEEDS_REVIEW` strictly dominates omit** for would-be catastrophic/wrong hard decisions: keep extraction, earn ≥2 class raw, avoid missing penalty.

## Method

- Worktree: `worktrees/exp-omit-thin/` — **only `pipeline.py`** owned for this experiment
- Gate: `should_omit_prediction` / `estimated_submit_value_units` in missing-case units; omit iff value **&lt; 1.0**
- Plumbing: `_omit=True` + `error=omit_untrusted_thin` so `solution/modal_app` drops the row without editing solution farm code; local `write_jsonl` also skips `_omit`
- Gate policy:
  - NR → always submit
  - DENIED (Finding / DQ flags / well-formed unpaid|transit) → submit
  - Thin weak DENIED → still submit (E[cls] ≈ 5–6 ≫ 1 on residual-like precision)
  - **APPROVED without Finding on thin packet** → omit (catastrophic-risk safety valve)
- Farm: `MIB_CODE_SRC=worktrees/exp-omit-thin/src modal run solution/modal_app.py --action score-residual-ocr --run-name exp-omit-thin`

## Residual A/B (seg-v1, n=100, official scorer)

| system | primary | extraction | classification | calibration | missing | cat | notes |
|--------|--------:|-----------:|---------------:|------------:|--------:|----:|-------|
| **exp-stamp-ocr (bar)** | **100.90** | 30.84 | 55.20 | 14.86 | 0.00 | **0** | stamp OCR baseline |
| **exp-omit-thin** | **100.90** | 30.84 | 55.20 | 14.86 | 0.00 | **0** | **0 omits fired** |

Confusion identical to stamp-ocr bar (including 2× NR→DENIED). `n_preds=100`, `n_errors=0`.

### Oracle (post-hoc, labels allowed for analysis only)

On stamp-ocr residual preds: **no case** has positive single-omit gain; greedy multi-omit stops at 0 omits. Full-train modal OCR (n=1000, cat=0) same story — even `wrong_decision` rows still carry enough extraction that omit loses.

Naive thin heuristics (unk≥k, conf≤0.35∧thin, hard∧unk≥4, …) all **drop** primary below 100.90.

## Decision: **kill**

- Residual **ties bar 100.90 cat0** but does **not lift** — omit gate correctly stays closed under current adjudicate (APPROVED only via Finding; DENIED EV ≫ missing unit).
- Pure omission **cannot beat** this residual given partial class credit + extraction; oracle confirms empty omit set is optimal among subsets of current preds.
- Prefer **`NEEDS_REVIEW` + honest confidence** over omit for fragile packets (see exp-calib / exp-uncertainty / exp-review-merge). Omit remains a narrow safety valve for untrusted APPROVED without Finding if a future rule re-introduces auto-approve.

## Risks / notes

- No case-id tables; EV uses field/text features only.
- If adjudicate regains multi-field auto-APPROVED, thin untrusted APPROVED will start omitting (or better: force NR in adjudicate).
- Do not promote omit-as-default for thin NR packets — that burns 0.2+ class units per case for a 0.1 missing unit.

## Artifacts

- `artifacts/exp-omit-thin/{eval.json,meta.json,predictions.jsonl,case_scores.jsonl,truth.csv}`
- Code: `worktrees/exp-omit-thin/src/mib_solution/pipeline.py`
