# Ship overfit critique — inference / runtime pipeline

**Scope:** `solution/` product path only (paddle FT ship).  
**Scores under review:** residual **108.77** (`artifacts/ship/residual_eval.json`), full train **118.91** (`artifacts/ship/train_eval.json`).  
**Method:** static review of pipeline, OCR gate, paddle stack, extract, adjudicate, calibrate, evidence, docs. No full retrain / re-score.

---

## 1. Executive verdict

**Overfit level: mixed (medium policy / medium–high measurement, low–medium perception stack).**

The ship is **not** a case-id answer table and deliberately moved stamp reading into geometry + FT rec rather than a pure multi-PSM typo forest. That is a real generalization improvement vs historical tesseract integrate. However, **decision and calibration layers still carry train-mined texture**: OCR-tolerant Finding typo banks, train-precision OCR risk maps, extra SPN denylists beyond the public manual, path-confidence priors fit on full train, and a P1 `should_ocr` gate whose thresholds and comments are residual/train-sliced. Residual is a **subset of train** (100/100 overlap), FT rec was largely **pseudo-labeled from self-OCR on the same corpus**, and **private val 5k has never been scored** under the Docker 4c/8g box. Residual 108.77 and train 118.91 therefore measure **in-distribution hardness + conservative class dump**, not out-of-distribution private validation.

---

## 2. Findings table

| Component | Risk | Severity | Evidence (file / symbol) | Why it matters for private val |
|-----------|------|----------|--------------------------|--------------------------------|
| Residual ⊆ train | Measurement illusion | **High** | `artifacts/residual_truth.csv` case_ids all in `data/train_labels.csv` (100/100); docs call residual “frozen hard subset” | Residual wins can be train-hard-slice tuning; private val can differ in texture without looking like residual |
| Paddle rec FT data | Pseudo-label / residual leak | **High** | `docs/LESSONS.md` §4–5, §8: “~73% self-OCR labels”; “synth + GT-heavy… no residual leak”; ship = `best_ep5` | Rec errors on val stamp/ink styles not in train self-OCR will tank Finding + extract; residual score overstates true OCR lift |
| No private val run | Measurement illusion | **High** | `docs/APPROACH.md` §8: “Private validation 5k package (not scored here)”; Docker full-train not confirmed | Only gate that matters for leaderboard is unscored; host train ≠ Docker 5k |
| `EXTRA_REVOKED_SPONSORS` | Train-mined denylist | **High** | `adjudicate.py` `EXTRA_REVOKED_SPONSORS` = `{SPN-9090, SPN-2718, SPN-7331}`; comment “almost always disqualifying”; train non-DIP: 38/38 DENIED | Val may use other revoked IDs (manual: “Other revoked sponsors may appear”) or different SPNs → miss DENIED; false DENY if IDs reused without revoke |
| `OCR_RISK_PATTERNS` | Train-precision garble bank | **Medium–High** | `adjudicate.py` lines ~98–165; comment “P(DENIED\|hit) ≥ 0.97”; patterns for `ntonetary enkgenn`, `risk fap/flap`, `embamen`, etc. | Engine-specific OCR typos change with paddle FT vs tesseract; false DENY from over-broad emb* patterns or miss on new garble |
| Finding OCR variants | Engine-texture typo bank | **Medium** | `adjudicate.FINDING_RE`, `ocr._FINDING_RE`: `Fouing`, `Frdirg`, `Finis`, `DEMED`, `DENED`, …; LESSONS §4 flags as campaign residue | Gate + class depend on *this* engine’s typo distribution; paddle may emit different corruptions → skip OCR wrongly or miss Finding |
| `should_ocr` P1 thresholds | Residual / train-slice policy | **Medium** | `ocr.should_ocr`: `_OCR_MIN_CHARS=400` (“residual median ~390”), struct≥5/6/7, n≥450/500, core_miss≥3; ultra-rich skip off after full-train bleed | Char/struct floors may not match val text-layer density; wrong skip → stamp class loss (as lean ship −3.2 train) |
| Closed vocab extract lists | Closed-set normalize | **Medium** | `extract.KNOWN_HOME_WORLDS` (13), `KNOWN_SPECIES` (12), `KNOWN_PURPOSES` (10) — **exact train support** | Val OOV world/species/purpose → unknown or wrong fuzzy pull; extract score gap |
| Fuzzy normalize (dist≤2–3) | OCR over-correction | **Medium** | `_fuzzy_token`, `_normalize_home_world` max_dist=3, `_normalize_species` max_dist=3, purpose dist=2 | Near-miss maps can snap to wrong closed token under noisy OCR |
| Path calib priors | Train residual conf map | **Medium** (partly dead) | `calibrate.PATH_CONF` “from full-train OCR path accuracy”; residual dump notes; **but** `adjudicate` never sets `_adj_reason` | Coarse fallback (APPROVED→finding_approved 0.98, DENIED→flags_dq 0.94, NR→feature dump) still train-tuned; Brier can move on val class mix |
| `DAMAGED_PACKET_RE` | Train phrase memorization | **Low–Medium** | `adjudicate`: “Train text-layer: 8/8 NEEDS_REVIEW” | Phrase may not appear on val; if similar damage wording differs, OCR “unpaid” false DENY returns |
| `PACKET_RECEIPT_DATE = 2026-07-07` | Dataset-cut constant | **Low–Medium** | `adjudicate.PACKET_RECEIPT_DATE`, `STALE_DAYS=180` | Stale rule is policy-aligned if receipt date is shared; wrong cut date flips stale DENIED boundary |
| Geometry region fractions | Inductive bias, mild layout fit | **Low–Medium** | `ocr_paddle._REGION_FRACS` fixed top/bottom/corners/center | Layout shift on val (stamp not in bands) → miss Finding/fee; not case-id overfit but form-layout assumption |
| Host vs Docker latency / workers | Measurement mismatch | **Medium** (ops) | LESSONS: host ~2.6 s @4w ~20 GiB; ship W=2, lat40 5.71 s; full train host wall ~4.06 s | Val 5k hard cap / mean 6 s may fail or quality change under memory pressure; train score not Docker-scored |
| REVOKED_SPONSORS (manual 3) | Policy, OK | **Low** | Manual SPN-0007/0139/4040; `FIELD_MANUAL.md` | Legitimate public policy |
| TRANSIT-7 hard DENY | Policy | **Low** | Manual “usually denied”; code always DENY | Slight over-hard vs “usually”; rare val exceptions → wrong DENY |
| Strict Finding APPROVED | Cat-safe policy | **Low** (healthy) | `FINDING_APPROVED_STRICT_RE`; train conf: 58 A→A, 0 cat FP, 227 A→NR | Under-APPROVE burns class points but protects cat; good for challenge rules |
| No case_id lookup tables | Anti-memorization | **— (healthy)** | grep: no `MIB-######` specials in `solution/src`; extract comment “No case-id answer tables” | Fair; perception not replaced by ID tables |
| Evidence page router | Schema / manual precedence | **Low** | `evidence.PAGE_CLASSIFIERS`, `FIELD_PAGE_PREF` | Generalizes if doc headers stable; synthetic filler regex is train-flavored but low risk |
| CLAHE default vs run.sh | Config footgun | **Low** | `ocr_paddle` default CLAHE env `"1"`; `run.sh` forces `0` | Non-entrypoint runs differ; not overfit, ship path is consistent |

---

## 3. Ranked top 5 risks for val drop

1. **Pseudo-labeled FT rec + residual⊂train measurement**  
   Perception lift on residual/train may not transfer to val scan styles, stamp fonts, or ink. Stock paddle residual was **97.7**; ship recovery to **108.77** is largely FT+regions on the **same** hard train slice. Val drop first shows up as missing Finding / DQ stamps → class collapses into NEEDS_REVIEW (already 227 A→NR, 70 D→NR on train).

2. **`EXTRA_REVOKED_SPONSORS` train mining**  
   Three IDs beyond the public manual, 100% non-DIP DENIED on train. Val either (a) uses *other* revoked SPNs → miss DENIED, or (b) reuses IDs without revoke semantics → false DENY. High leverage on classification (80 pts).

3. **OCR risk map + Finding typo banks tied to train OCR texture**  
   Patterns explicitly validated at train P≥0.97; Finding variants (`Fouing`/`DEMED`/…) also feed `should_ocr` “has finding”. New OCR error modes → false DENY (over-broad emb*) or silent miss (under-broad Finding) and wrong OCR skip.

4. **P1 `should_ocr` char/struct floors**  
   Tuned after ultra-rich skip bled full train (−3.2). Val packets with rich text layers but stamp-only Finding and different length distributions can re-open the lean-ship failure mode (skip OCR → dump NR / wrong class).

5. **Closed vocab + fuzzy extract on train support only**  
   Species/worlds/purposes lists are the full train closed set. Val OOV or harder OCR → extract points drop (train extract 43.5/50 vs residual 35.2/50 already shows hard-slice extract fragility). Fuzzy dist=3 can also wrong-snap.

**Honorable mention:** calibration is feature/path-based and train-commented; class mix shift (more true APPROVED recoverability or different NR rate) moves the 20-pt Brier term even if adjudication rules hold.

---

## 4. Ranked things that look healthy / general

1. **No case-id lookup / residual specials in runtime code** — ban list in `ocr_paddle` docstring is respected for IDs; pipeline is PDF→text→OCR→extract→rules.

2. **Policy enums and manual-backed deny structure** — TRANSIT-7, unpaid fee, public revoked trio, DQ flag set, multi review-only flags, stale 180-day rule align with `FIELD_MANUAL.md` (with noted EXTRA SPN exception).

3. **Catastrophic-FP discipline** — strict `Finding: APPROVED` only; no multi-field auto-APPROVED; cat **0** on residual and train. Correct challenge prior.

4. **Geometry crops as inductive bias** — fixed fractional bands for stamps/headers are form-layout priors, not residual case lists; maintainable substitute for multi-PSM stamp ensembles (LESSONS §4).

5. **Evidence precedence / decoy stripping** — page-type ranks and untrusted-line filters match the challenge’s adversarial design (answer keys, hidden text) rather than memorizing labels.

6. **P1 gate intent** — “skip OCR only if Finding/DQ + structure” is a general latency policy; failure mode is known and partially measured on full train, not residual-only.

7. **Conservative default NEEDS_REVIEW** — when uncertain, dump-bin review; hurts APPROVED recall but is the right score-shape under heavy cat penalty.

8. **Vendored offline models + Docker knobs** — network-none, W=2, CLAHE=0, OMP=1 are environment-honest; latency gate was measured (lat40 5.71 s).

---

## 5. Concrete recommendations

### Ablate (cheap, high information)

| Ablation | How | What it tells you |
|----------|-----|-------------------|
| Drop `EXTRA_REVOKED_SPONSORS` | Empty set; re-score train + residual | Class points pure from train-mined SPNs |
| Drop `OCR_RISK_PATTERNS` (keep clean text DQ regexes) | Comment out map; re-score | How much DENIED depends on garble bank |
| Strict Finding only (drop typo bank) | `FINDING_RE` → clean `Finding:` + DENIED/NR variants only | Class + OCR-skip sensitivity to typo forest |
| Always OCR (force) | `MIB_FORCE_OCR=1` on residual + train sample | Upper bound if P1 mis-skips |
| Regions off | `MIB_OCR_REGIONS=0` | Extract/class lift from geometry vs full-page FT |
| Fuzzy off / exact known lists only | Temporarily disable `_fuzzy_token` in normalize | Extract over-correction rate |

### Measure next (priority order)

1. **Private val 5k under Docker 4c/8g, W=2, CLAHE=0** — only score that refutes overfit.  
2. **Docker full train n=1000** — confirm host **118.91** is not host-only.  
3. **Per-path class decomposition** — Finding-backed vs TRANSIT vs unpaid vs revoked vs OCR-risk vs default NR; compare residual vs train (residual already has weak APPROVED: 10 A→A, 18 A→NR).  
4. **OCR hit rate of Finding tokens** under paddle FT on a held-out train slice (e.g. 200 IDs never used in FT labels) — approximate “new texture”.  
5. **If FT data pipeline is reopened:** retrain rec on **synth + GT**, **exclude residual IDs from pseudo-labels**, then residual becomes a cleaner OCR generalization check.

### Do *not* do (anti-overfit)

- Stack more residual Explore regexes / SPN IDs / Finding typos without train **and** val evidence.  
- Case-id tables.  
- Raise APPROVED via multi-field auto-approve (cat risk).  
- Treat residual +0.2 as a ship gate (LESSONS promote caps).

### Small cleanups (optional, not rewrites)

- Set `_adj_reason` in `adjudicate` **or** delete unused `PATH_CONF` keys — current pipeline always falls back to coarse class priors (`pipeline` reads `fields["_adj_reason"]` but adjudicate never writes it).  
- Align `ocr_paddle` CLAHE default with ship (`0`) so non-`run.sh` runs match lat40.  
- Document that residual ⊂ train in APPROACH scoreboard so residual is never sold as independent val.

---

## 6. Scoreboard caveat

| Snapshot | Total | Class | Extract | Calib | Cat | n |
|----------|------:|------:|--------:|------:|----:|--:|
| Residual | **108.77** | 58.30 | 35.20 | 15.27 | 0 | 100 |
| Full train | **118.91** | 60.74 | 43.48 | 14.68 | 0 | 1000 |

**These numbers do not prove generalization.**

- Residual is a **hard subset of the labeled train set**, not a holdout. Improving residual after inspecting residual failures is classic train-texture fit.  
- Full train **118.91** is **in-sample** relative to every rule mined from `train_labels.csv`, SPN frequency tables, and (for FT) pseudo-OCR labels drawn from the same PDFs.  
- Train confusion is **heavily conservative** (227 true APPROVED → NEEDS_REVIEW; only 58 correct APPROVED). High score can coexist with weak APPROVED recovery that a different val mix punishes.  
- Latency/quality reported on **host** full train + **Docker lat40**, not Docker full train or Docker val 5k.  
- Paddle FT is credited for residual recovery vs stock **97.7**, but LESSONS admit pseudo-label FT and residual leak risk — residual score is **not** an independent OCR generalization proof.  
- Historical tesseract integrate **119.27** under a different latency regime shows the train ceiling is nearby; **+0.14** vs P1 train is within noise/regime, not a large inductive win.

**Bottom line:** ship inference is a **mixed** system — solid anti-ID-table architecture and cat-safe policy, with **medium** rule/OCR-texture overfit and **high** measurement risk until private val is scored under the real box. Treat 108.77 / 118.91 as **regression baselines for the train distribution**, not as evidence the pipeline will hold on private validation.

---

*Reviewer stance: skeptical but fair. No product code changed for this critique.*
