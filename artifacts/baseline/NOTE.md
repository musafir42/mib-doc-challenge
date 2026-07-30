# Baseline

## System
- PDF text-layer extract via `pypdf` (no OCR)
- Label/value block regex fields from intake / fee / registry pages
- Adjudication: hard DENIED only on clear DQ risk flags, TRANSIT-7, unpaid (non-DIP), public revoked sponsors; else **NEEDS_REVIEW**
- Never auto-APPROVED (avoids catastrophic false approval)

## Official train score (1000 cases)
See `eval.json`.

## Intent
First measured system. No feature spam until Segment residual freeze + ceiling.

## Known gaps
- OCR/image-only pages missed
- Risk flags often not in text layer (stamps)
- No cross-page conflict resolution / injection resistance beyond ignoring free-text decoys somewhat
- No APPROVED path yet (classification headroom)
