"""OCR fallback for stamp / image-only signals (experiment path)."""

from __future__ import annotations

import os
from pathlib import Path

# Optional heavy deps — fail soft if missing (text-layer path still works).
try:
    from pdf2image import convert_from_path
    import pytesseract
except Exception:  # pragma: no cover
    convert_from_path = None  # type: ignore
    pytesseract = None  # type: ignore


def ocr_available() -> bool:
    if convert_from_path is None or pytesseract is None:
        return False
    # tesseract binary must exist on PATH (baked into Modal image / host brew)
    from shutil import which

    return which("tesseract") is not None


def ocr_pdf_text(pdf_path: Path, dpi: int = 200, max_pages: int = 6) -> str:
    """Rasterize PDF pages and OCR. Returns concatenated text or empty string."""
    if not ocr_available():
        return ""
    path = Path(pdf_path)
    if not path.exists():
        return ""
    try:
        images = convert_from_path(str(path), dpi=dpi, first_page=1, last_page=max_pages)
    except Exception:
        return ""
    parts: list[str] = []
    for im in images:
        try:
            # psm 6: assume block of text; good for form pages + stamps
            text = pytesseract.image_to_string(im, config="--psm 6")
        except Exception:
            text = ""
        if text:
            parts.append(text)
    return "\n".join(parts)


def should_ocr(text_layer: str, force: bool = False) -> bool:
    """Decide whether OCR is worth the cost."""
    if force:
        return True
    if os.environ.get("MIB_FORCE_OCR", "").strip() in {"1", "true", "yes"}:
        return True
    t = text_layer or ""
    if len(t.strip()) < 120:
        return True
    lower = t.casefold()
    # Missing structured risk language but packet may have stamp-only DQ
    risk_tokens = (
        "biohazard",
        "embargo",
        "warrant",
        "tamper",
        "finding:",
        "risk flag",
        "observed flags",
    )
    if not any(tok in lower for tok in risk_tokens):
        return True
    return False


def merge_text_layers(text_layer: str, ocr_text: str) -> str:
    """Append OCR under a marker so adjudicate can use both; prefer longer unique content."""
    base = text_layer or ""
    ocr = (ocr_text or "").strip()
    if not ocr:
        return base
    # Avoid huge duplication when OCR ≈ text layer
    if ocr.casefold() in base.casefold():
        return base
    return base + "\n\n--- OCR_FALLBACK ---\n" + ocr
