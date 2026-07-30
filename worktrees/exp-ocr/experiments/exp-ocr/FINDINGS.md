# exp-ocr

## Hypothesis

Because residual missed DENIED often have DQ stamps invisible to the PDF text layer, OCR (poppler rasterize + tesseract) on residual cases should recover risk/finding tokens and improve residual score without catastrophic false approvals.

## Method

- Worktree: `worktrees/exp-ocr/` with `ocr.py` + OCR-aware `pipeline.predict_pdf(use_ocr=…)`
- Farm: Modal Volume **`mib-data`** (1000 train PDFs preloaded)
- Functions: `predict_text.map` vs `predict_ocr.map` (parallel, not idle sandboxes)
- Image: debian + tesseract-ocr + poppler-utils + pdf2image/pytesseract/pillow

## Residual A/B (seg-v1, n=100, official scorer)

| system | primary | extraction | classification | calibration | catastrophic | notes |
|--------|--------:|-----------:|---------------:|------------:|-------------:|-------|
| residual_baseline (Segment) | 62.21 | 16.62 | 33.00 | 12.59 | 0 | early baseline |
| promote_seg1 text (local) | 75.37 | 18.33 | 43.40 | 13.64 | 0 | pre-OCR promote |
| **modal_residual_text** | **75.37** | 18.33 | 43.40 | 13.64 | **0** | Modal map = local |
| **modal_residual_ocr** | **98.05** | **27.46** | **56.00** | **14.59** | **0** | **+22.68 vs text** |

Confusion (OCR residual): DENIED→DENIED 12→**29**; APPROVED→APPROVED 7→**11**; cat **0**.

## Decision: **promote** (residual gate)

OCR residual beats promote_seg1 residual by **+22.7** with **0** catastrophic.  
Full-train OCR Modal score required before ship; Docker must bake tesseract/poppler within image limits (Ship-align).

## Risks

- OCR may hallucinate tokens → mitigated by existing trusted-text filters + no multi-field auto-APPROVED
- Runtime: ~seconds/PDF; validation 5k PDFs need parallel workers under 6s/PDF budget
- Image size: tesseract+poppler increase Docker weight — measure before ship claim
- Some DQ stamps remain non-OCR-able graphics (MIB-000033 biohazard still missed in OCR smoke)

## Artifacts

- `artifacts/modal_residual_text/`
- `artifacts/modal_residual_ocr/`
- `artifacts/modal_smoke/`, `artifacts/modal_ocr_smoke/`
