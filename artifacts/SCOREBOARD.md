# Scoreboard

Merge owner appends only. Residual row before full-data row for the same change name.

| date | name | stage | slice | primary | catastrophic | notes | artifacts | git |
|------|------|-------|-------|---------|--------------|-------|-----------|-----|
| 2026-07-30 | process-drill | Setup | dummy residual | n/a | n/a | process drill skeleton; not a product score | worktrees/drill/experiments/drill/FINDINGS.md | 38ce888 |
| 2026-07-30 | baseline | Baseline | train_full | 98.88 | 0 | pypdf+label regex; deny-only; no auto-approve | artifacts/baseline/ | 1b4ff44 |
| 2026-07-30 | residual_baseline | Segment | residual_seg-v1 | 62.21 | 0 | baseline system on frozen residual n=100 | artifacts/residual_baseline/ | 283876d |
| 2026-07-30 | exp-extract | Explore | residual_seg-v1 | 64.24 | 0 | extract multi-source labels; residual A/B | artifacts/exp-extract/ | 283876d |
| 2026-07-30 | exp-adjudicate | Explore | residual_seg-v1 | 74.85 | 0 | finding notes + deny rules; residual A/B | artifacts/exp-adjudicate/ | 283876d |
| 2026-07-30 | exp-risk | Explore | residual_seg-v1 | 71.60 | 0 | registry/risk signals; residual A/B | artifacts/exp-risk/ | 283876d |
| 2026-07-30 | promote_seg1 | Integrate | residual_seg-v1 | 75.37 | 0 | merged extract+adjudicate; no auto-APPROVED; residual+full | artifacts/promote_seg1/ | 283876d |
| 2026-07-30 | promote_seg1_full | Integrate | train_full | 106.95 | 0 | after residual promote; Finding APPROVED only for approve | artifacts/promote_seg1/train_eval.json | 283876d |
