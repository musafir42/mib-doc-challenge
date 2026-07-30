# Grok Build Playbook — Attack a Hard Evaluation Challenge

**What this is:** How to **think, measure, and parallelize** on a constrained competition so an agent can **build and iteratively improve** a solution.  
**What this is not:** A product recipe. No prior-team scores, stacks, or field lists. Discover those from the **challenge repo** (always wins on conflict).

### Hard process constraints

| Constraint | Rule |
|------------|------|
| **Python packaging** | **`uv` only** (`uv init` / `uv add` / `uv sync` / `uv run`). No pip/poetry/conda as primary. |
| **Experiment compute** | Prefer **Modal** as the batch farm for residual and full-data scoring. Product submission still follows the challenge (often offline Docker). |
| **Generalization** | No case-id answer tables / runtime label lookup in product code. |
| **You are the merge owner** | Unless the human names someone else, **you** integrate worktrees, write the scoreboard, enforce kills, and re-score residual on main. |

### Named stages (not numbered phases)

```text
Setup → Baseline → Segment → Explore → Integrate → Ship-align → Stretch
```

| Stage | You are here when… | You may leave when… |
|-------|--------------------|---------------------|
| **Setup** | Clean forked repo open | Prereqs OK; layout dirs present; scorer produced a **number** |
| **Baseline** | Building first real system | Tagged system + official eval on scoreboard |
| **Segment** | Slicing errors | **Hard exit:** residual frozen **and** residual harness documented **and** ceiling note written |
| **Explore** | Parallel worktrees | **Hard entry:** Segment exit only. Default: multi-agent. Each run has FINDINGS + residual A/B |
| **Integrate** | Merge owner promoting | Residual re-scored on **main**; scoreboard row; tag if improved |
| **Ship-align** | Matching ship to measured config | Offline/Docker smoke OK with same lockfile/flags — **required before calling a win** |
| **Stretch** | High-EV residuals only | Catastrophic metric still safe |

**Serial until residual is frozen; multi-agent Explore is the default after that.**  
Do not invent a separate “solo lifestyle.” One worktree during Explore is fine when only one high-EV slice exists — that is still Explore.

---

## Glossary

| Term | Meaning |
|------|---------|
| **Repo root** | You are already in a **clean forked** challenge repo (cwd = that root). Rules, data, scorer live here; add `solution/` for product code. |
| **`solution/`** | Product code (pipeline, Docker, uv project). |
| **`artifacts/`** | Preds, evals, residual freeze, scoreboard, agency registry. |
| **`worktrees/`** | Isolated copies of `solution/` for parallel experiments. |
| **Baseline** | Runnable system + official score + note + git tag. Also a stage name. |
| **Official score** | Challenge evaluation script output only. |
| **Catastrophic error** | Heavily penalized error types from scorer docs — do not invent the list. |
| **Ceiling check** | Diagnostic: perfect inputs to a stage → score? Finds the bottleneck. |
| **Label-only decision check** | Decision rules on gold labels only (skip reading inputs). Not a submission. |
| **Failure slice** | Cases sharing an error pattern (analysis only). |
| **Residual** | Frozen hard failure subset for cheap A/B (`artifacts/residual.json`). |
| **Residual A/B** | Same residual file, two systems; compare official metrics. |
| **Promote / Kill** | Accept into `solution/` / stop experiment. |
| **Merge owner** | Integrates worktrees, scoreboard, kills — **default: the orchestrating agent**. |
| **Scoreboard** | `artifacts/SCOREBOARD.md` only; merge owner appends. |
| **EV** | `#cases × points_if_fixed × P(generalizes) − catastrophe_risk`. |
| **Modal** | Default cloud batch farm for experiments. Not the offline product. |
| **uv** | Required Python package/env manager. |

**Assumption:** you are already in a **clean forked** challenge repo (cwd = repo root). Do **not** re-fork or re-clone. Paths are relative to that root.

---

## Setup

You are in the clean forked repo. Confirm tools, create layout dirs, prove the scorer.

### Prerequisites

| Need | Check |
|------|--------|
| git | `git --version` |
| Python 3.x | `python3 --version` |
| **uv** | `uv --version` — https://docs.astral.sh/uv/ |
| Docker | `docker info` if submission is Docker |
| git-lfs | if challenge README says so |
| **Modal** | CLI + login before large jobs |

Data should already be present per the challenge README; if not, fetch it **in this repo only** (e.g. `git lfs pull`) — still no new clone.

### Layout (under this repo root)

```bash
# cwd = clean forked challenge repo
mkdir -p solution artifacts/agency worktrees
git rev-parse HEAD > artifacts/challenge_sha.txt
```

```text
.                           ← repo root (you are here)
  manuals, data/, scripts/
  solution/                 ← product (uv)
  artifacts/                ← SCOREBOARD.md, residual.json, runs, agency/
  worktrees/                ← parallel experiments
```

```bash
cd solution && uv init   # if empty; then uv add / uv sync / uv run
git -C .. add solution && git -C .. commit -m "scaffold solution/"
```

Scaffold early. **Do not** tag a baseline until the scorer has produced a real number.

### Prove the scorer

Tiny schema-valid preds → official evaluate → **numeric** artifact under `artifacts/scorer_smoke/`.  
`--help` is not proof.

### Modal (experiment compute)

| Role | Where |
|------|--------|
| Product / submission | Challenge path (often offline Docker) |
| Experiments | Modal: residual, full-data after promote, A/B |

- Cached image + Volume for data; Functions not idle sandboxes; cap concurrency.  
- Residual before full; pull `artifacts/<run>/` every time; same `solution/uv.lock` as ship.  
- Budget; never bake tokens into images.

```bash
modal setup && modal app list
# solution/modal_app.py — smoke / score-residual / score-full
```

### Modal layout: shared data + parallel workers

Conceptually many workers share **one** input store and keep **isolated** code:

```text
shared read-only data (Modal Volume)   e.g. /data/train/*.pdf
        │
   ┌────┼────┐
   ▼    ▼    ▼
 worker worker worker   ← each has its own code tree/branch
   │    │    │
   └────┼────┘
        ▼
 artifacts → artifacts/<run_name>/ on the orchestrator
```

| Piece | Do | Don’t |
|-------|-----|--------|
| **Inputs** | Upload corpus **once** to a Volume; mount read-only | Copy full data into every worker or rebuild into the image each run |
| **Code isolation** | One branch / copy / image per experiment | Shared mutable `solution/` across parallel writers |
| **Bulk score** | Prefer **Functions** + shard map; bill while working | Long-lived idle **Sandboxes** “just in case” |
| **Sticky agent shell** | Short-lived **Sandbox**: create → work → **terminate** | Leave sandboxes running idle |
| **git worktree** | On the **orchestrator** fork for multi-agent isolation | Require worktree inside every remote worker — one checkout/branch is enough |
| **git clone per worker** | Prefer image bake or code Volume; avoid N full clones | Full history clone on every cold start |
| **Merge** | Only on orchestrator into `solution/` after residual gates | Merge inside remote boxes with no scoreboard |

**Rule of thumb:** measure many independent cases → **Functions** + shared Volume; interactive agent session → **short-lived Sandbox**; parallel code hypotheses → N isolated code trees + **same** data Volume. Sandboxes are not automatically cheaper — **idle time** is.

### Process drill (before product ambition)

Prove the **method** works empty-handed (~30 minutes). If this fails, do not trust multi-agent product work.

- [ ] Layout: `solution/`, `artifacts/`, `worktrees/`  
- [ ] Scorer smoke number in `artifacts/scorer_smoke/`  
- [ ] Dummy `artifacts/residual.json` (any small id list)  
- [ ] Stub `solution/experiments/RESIDUAL.md` describing how residual will be scored  
- [ ] One dummy `worktrees/drill/experiments/drill/FINDINGS.md` with residual A/B table skeleton  
- [ ] `artifacts/SCOREBOARD.md` with one row  
- [ ] `artifacts/agency/ACTIVE.md` exists  

### Setup done when

- [ ] Already in clean forked repo root  
- [ ] Prereqs (uv + Modal if farming)  
- [ ] Data present; `artifacts/challenge_sha.txt` written  
- [ ] `solution/` + uv scaffold  
- [ ] Numeric scorer smoke  
- [ ] Process drill checked  
- [ ] Modal smoke (recommended)  

---

## The game

| Axis | Question |
|------|----------|
| Objective | What does the official scorer maximize? |
| Constraints | Offline? size? latency? forbidden APIs? |
| Risk | Which mistakes are catastrophic in the docs? |
| Uncertainty | What does the public manual leave incomplete? |

**Win:** measure → parallel Explore → promote/kill → Integrate → Ship-align.  
**Lose:** full-data thrash, Explore without residual, agents with no ACTIVE row, memorizing train ids.

---

## Mental model (questions, not a stack)

Infer stages from the submission contract and manuals — do not assume libraries.

**Ceiling checks** (diagnostics):

| Check | Question |
|-------|----------|
| Label-only decision | Perfect structured inputs → decision score? |
| Cheapest legal path | Minimal input reading → score? |
| Costly path on a small sample | Extra cost worth it? |

Write the conclusion down (required in Segment).

**Trust:** if the manual describes injections/conflicts, define evidence precedence from the manual before clever parsers. Prefer abstain/review when the scorer rewards that over catastrophes.

**Score economics:** for every change, which error cell improves/worsens, net EV including catastrophes?

---

## The loop

```text
Baseline → Segment (residual + harness + ceiling)
  → Explore (multi-agent default) → Residual A/B
  → Integrate → Ship-align → (Stretch)
```

---

## Baseline

Runnable pipeline, schema-valid preds, eval under `artifacts/baseline/`, note, git tag `baseline`.  
Scoreboard row. Stop feature spam until **Segment**.

---

## Segment (hard gate before Explore)

### Taxonomy

From preds × labels: scorer-relevant confusion cells; wrong outputs; input-shape clusters **from data** (don’t import a prior team’s names).  
Slice id lists = analysis only, never product logic.

### Freeze residual

`artifacts/residual.json` — **only merge owner may rewrite**.

### Residual harness (required file)

`solution/experiments/RESIDUAL.md` must document **one** command path:

```text
Score artifacts/residual.json with current solution/ →
  artifacts/<run_name>/predictions.<ext>
  artifacts/<run_name>/eval.json
  artifacts/<run_name>/meta.json   # git sha, residual identity, command

Prefer Modal. Local uv run for tiny debug.
```

### Ceiling deliverable (required file)

`artifacts/ceiling/BINDING.md` (or `.json`):

```markdown
# Binding stage
- Label-only decision: <metric or N/A + why>
- Cheap path: <metric>
- Conclusion: binding stage = <…>
- Therefore we invest next in: <…>
```

If gold fields do not exist, write **N/A** and still state best-guess binding stage from manuals + errors.

### Segment done when (all required)

- [ ] `artifacts/residual.json` frozen  
- [ ] `solution/experiments/RESIDUAL.md` exists  
- [ ] Residual harness has been run once (baseline residual row on scoreboard)  
- [ ] `artifacts/ceiling/BINDING.md` written  

**No Explore until every box is checked.**

---

## Explore (multi-agent default)

**Entry rule (hard):** Segment done checklist complete.  
**Default after entry:** spawn **2–4** independent hypothesis agents with module ownership.  
**Degenerate case:** only one high-EV slice → one worktree still counts as Explore (not a separate solo philosophy).

**Forbidden:** multi-agent product work before Segment done.

### Agency control plane

`artifacts/agency/ACTIVE.md` — merge owner maintains:

```markdown
| name | worktree | goal | started | deadline | status |
|------|----------|------|---------|----------|--------|
| exp-a | worktrees/exp-a | … | ISO time | +15m | running/done/killed |
```

On every wake, merge owner:

- Kills rows past deadline with no FINDINGS + eval artifact  
- Appends a scoreboard note for kills  

### Worktrees

```bash
rsync -a --exclude .venv solution/ worktrees/exp-<name>/
# edit only worktrees/exp-<name>/
```

| Path | Role |
|------|------|
| `worktrees/exp-<name>/` | Code |
| `worktrees/exp-<name>/experiments/<name>/FINDINGS.md` | Required |
| `artifacts/<name>/` | predictions, eval.json, meta.json |

Before fan-out: **module ownership map** (which paths each exp may touch). Overlap → serialize.

### Subagent spawn template

```text
GOAL: <one sentence>
EDIT ONLY: worktrees/exp-<name>/
READ-ONLY: manuals, data/, scripts/, artifacts/residual.json

CONSTRAINTS: challenge rules; no case-id tables; catastrophic types from scorer;
  do not merge into solution/; do not rewrite residual.json.

DELIVERABLES:
  - code in worktree
  - experiments/<name>/FINDINGS.md
  - artifacts/<name>/{predictions,eval.json,meta.json} via residual harness

SUCCESS: residual beats scoreboard baseline residual row; catastrophes not worse
KILL IF: deadline in ACTIVE.md; no real deliverable; tool loop; worse catastrophes
OUT OF SCOPE: <list>
```

Register the agent in `ACTIVE.md` **before** spawn.

### FINDINGS.md skeleton

```markdown
# <name>
## Hypothesis
Because we observe … we believe … so changing … should improve … without …

## Method
## Residual A/B
| system | primary | catastrophic | notes |
| baseline residual | | | |
| this run | | | |

## Decision: promote | kill | continue
## Risks (generalization / cost)
```

### Writer counts

| Stage | Writers |
|-------|--------:|
| Setup / Baseline / Segment | 0–1 |
| **Explore** (after hard gate) | **2–4 default** |
| Integrate | 1 (merge owner) |

---

## Integrate (merge owner — default: you)

After any experiment finishes (same session turn if possible):

1. Read FINDINGS + residual A/B.  
2. Port minimal patch into `solution/` (cherry-pick or diff — pick one style).  
3. Re-run residual harness on **main** `solution/`. If fail → no tag; fix or revert.  
4. Append **one** scoreboard row (merge owner only).  
5. If promote: tag `promote-<shortname>`; require **Ship-align** before declaring a campaign win.  
6. Update ACTIVE.md; remove/archive worktree.

### Promote vs win

| Claim | Requires |
|-------|----------|
| **Promote** candidate | Residual pass on main; no catastrophic regression; scoreboard row |
| **Win / ship-ready** | Promote **plus Ship-align** (below) |

Full-data Modal score only after residual promote criteria.  
Scoreboard: no `full` row without a residual row for that change name.

---

## Ship-align (required before calling a win)

- [ ] Same `solution/uv.lock` (or documented equivalent) on Modal image and submission image  
- [ ] Same env flags for measured vs ship config  
- [ ] Offline/Docker (or challenge-mandated) smoke on a small case set succeeds  
- [ ] Scoreboard row notes ship-align OK  

Modal-only glory without this is **not** a win.

---

## Stretch

Only if catastrophic metric remains safe. High-EV residuals only. Still residual-first; still multi-agent Explore when multiple slices.

---

## Complexity and compute

Pay for cost when residual A/B pays: gate expensive work → cheap path first → extra tools → always-on expensive combos last.

| Work | Where |
|------|--------|
| Edit / tiny debug | Local `uv run` in `solution/` |
| Residual A/B | **Modal** (default) |
| Full labeled set | **Modal** (rare, after promote) |
| Submission fidelity | Challenge path (often offline Docker) |

---

## Scoreboard

**Only** `artifacts/SCOREBOARD.md`. Merge owner appends.

| date | name | stage | slice | primary | catastrophic | notes | artifacts | git |
|------|------|-------|-------|---------|--------------|-------|-----------|-----|

Stage names only. Residual row before full-data row. Keep losers.  
Optional: refuse to log `full` without prior residual row for same `name`.

---

## Anti-patterns

Explore before Segment hard exit · full-data every tweak · shared edit dirs · no ACTIVE.md · no kill · no residual · Modal ≠ Docker lockfile · pip-first · id memorization · “win” without Ship-align · renumbering phases · treating multi-agent as optional forever after residual exists (default is Explore with 2–4 writers) · idle Modal sandboxes · cloning full data into every worker · skipping shared Volume for inputs.

---

## Cadence

| Stage | Focus | Writers |
|-------|--------|--------:|
| **Setup** | Forked root, uv, scorer smoke, process drill | 0–1 |
| **Baseline** | First tagged system | 1 |
| **Segment** | Slices, residual, harness, ceiling | 1 |
| **Explore** | Multi-agent worktrees (default) | 2–4 |
| **Integrate** | Merge owner | 1 |
| **Ship-align** | Ship = measured | 1–2 |
| **Stretch** | High-EV residuals | 2–4 |

---

## Paste prompt

```text
You are Grok Build. Attack this evaluation challenge from scratch.

You are already in a clean forked challenge repo (cwd = repo root). Do not re-fork or re-clone.

PROCESS: <path-to>/GROK_BUILD_PLAYBOOK.md
TRUTH: manuals, scorer, data, submission contract in this repo (override playbook on conflict).

You are the merge owner unless the human names someone else.
You enforce ACTIVE.md deadlines, scoreboard writes, residual-on-main, and Ship-align before any "win."

STAGES: Setup → Baseline → Segment → Explore → Integrate → Ship-align → Stretch
Serial until residual is frozen; then multi-agent Explore is the default (2–4 writers).
One worktree only when a single high-EV slice exists — still called Explore.

SETUP:
  - Prereqs: git, Python, uv, Docker if required, git-lfs if required, Modal CLI.
  - Stay in repo root. mkdir -p solution artifacts/agency worktrees.
  - Ensure data is present per README (no new clone).
  - Product in solution/ with uv (uv init/add/sync/run).
  - Local scorer smoke → artifacts/scorer_smoke/ (numeric).
  - Process drill: dummy residual, RESIDUAL.md stub, FINDINGS skeleton, SCOREBOARD, ACTIVE.md.
  - Modal auth + smoke; Modal for residual/full experiments (not offline product).
  - Modal: shared Volume for inputs; Functions for bulk score; short-lived Sandboxes only for sticky shells; merge only on orchestrator.

HARD GATES:
  - No Explore until: artifacts/residual.json + solution/experiments/RESIDUAL.md
    + one baseline residual scoreboard row + artifacts/ceiling/BINDING.md
  - No "win" / ship-ready claim until Ship-align checklist passes.
  - No full-data Modal score without residual promote for that change.
  - Kill ACTIVE.md rows past deadline without FINDINGS+eval.

LAW:
  - uv only; no case-id answer tables; catastrophic types from scorer only.
  - Measure; do not import a prior team’s stack.
  - artifacts/SCOREBOARD.md only you (merge owner) append.
  - Ship config = measured config (solution/uv.lock + same flags).

START: Setup (incl. process drill) → Baseline only.
After Segment hard exit: fan out Explore (2–4) unless only one high-EV slice.
```

---

## One-page summary

```text
Setup: already in clean forked repo → solution/ artifacts/ worktrees/ → uv → scorer number → process drill → Modal (Volume + Functions; short sandboxes if needed).
Baseline: tag + scoreboard.
Segment (hard): residual.json + RESIDUAL.md + residual score once + ceiling/BINDING.md.
Explore (default multi-agent): ACTIVE.md, 2–4 worktrees, FINDINGS, residual A/B, kill stale.
Integrate: you merge → residual on main → scoreboard → promote tag.
Ship-align: required before win (Docker/offline = measured lockfile/flags).
Stretch: high-EV only if catastrophic-safe.
Never: re-clone the fork; Explore early; full-data thrash; pip-first; id memos; win without Ship-align.
```

**Self-improving process:** agent + residual gates + multi-agent Explore + merge owner + scoreboard — not a tribal product recipe.
