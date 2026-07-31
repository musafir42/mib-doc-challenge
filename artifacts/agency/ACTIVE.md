# Active agents

Merge owner maintains this table. **Empty = no parallel Explore agents running.**

| name | worktree | goal | started | deadline | status |
|------|----------|------|---------|----------|--------|
| lat-dpi | worktrees/lat-dpi | DPI/max_pages lean | 2026-07-31 | — | **DONE** 104.14 cat0 — partial promote (dpi defaults) |
| lat-psm-lite | worktrees/lat-psm-lite | Fewer PSM | 2026-07-31 | — | **DONE** 102.29 — NO solo |
| lat-crops-lite | worktrees/lat-crops-lite | Fewer crops | 2026-07-31 | — | **DONE** 103.96 — NO solo |
| lat-select-ocr | worktrees/lat-select-ocr | should_ocr gate | 2026-07-31 | — | **DONE** 108.89 — **PROMOTED** |
| lat-tiered | worktrees/lat-tiered | light/heavy tiers | 2026-07-31 | — | **DONE** 100.38 — hold |
| lat-parallel-ship | worktrees/lat-parallel-ship | ProcessPool+OMP | 2026-07-31 | — | **DONE** 104.74 parity — **PROMOTED** |

## Integrate result

`promote_lat_ship` on main `solution/`: residual **108.20** cat 0; train40 **2.67 s/PDF @ 4 workers**.

## Notes

- Latency fan-out complete 2026-07-31.
- Next: Docker rebuild + full train + val under ship flags.
