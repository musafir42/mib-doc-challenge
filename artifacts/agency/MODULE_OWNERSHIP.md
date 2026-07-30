# Explore module ownership (seg-v1 fan-out)

| experiment | may edit | must not edit |
|------------|----------|---------------|
| exp-extract | worktrees/exp-extract/src/mib_solution/extract.py (and tiny pipeline glue if needed) | adjudicate.py primary logic; residual.json; solution/ |
| exp-adjudicate | worktrees/exp-adjudicate/src/mib_solution/adjudicate.py | extract.py; residual.json; solution/ |
| exp-risk | worktrees/exp-risk/src/mib_solution/extract.py (risk/registry only) + adjudicate.py if needed for mapped flags | residual.json; solution/; do not fight exp-extract on name/purpose parsers — focus risk |

Merge only on orchestrator after residual A/B.
