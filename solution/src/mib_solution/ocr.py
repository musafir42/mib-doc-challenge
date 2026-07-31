"""OCR fallback with stronger deskew + selective binarize (exp-deskew-v2).

Builds on exp-deskew (residual 101.70 cat 0) and exp-stamp-ocr (100.90):
- Rasterize at ~275 DPI
- Stronger deskew: finer projection search (0.25°) + Hough consensus; apply ≥0.55°
- Full page: deskewed psm 6/11/4 (natural image first — never replace with binary)
- Stamp crops: CLAHE (psm 6+11) then additive Otsu / adaptive binarize (psm 6)
- Unique-line merge preserves earlier natural OCR for first-match extract
- No unconditional red-boost (hurt residual in deskew v1 A/B)
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

# Optional heavy deps — fail soft if missing (text-layer path still works).
try:
    from pdf2image import convert_from_path
    import pytesseract
except Exception:  # pragma: no cover
    convert_from_path = None  # type: ignore
    pytesseract = None  # type: ignore

try:
    from PIL import Image, ImageEnhance, ImageOps
except Exception:  # pragma: no cover
    Image = None  # type: ignore
    ImageEnhance = None  # type: ignore
    ImageOps = None  # type: ignore

try:
    import cv2
    import numpy as np
except Exception:  # pragma: no cover
    cv2 = None  # type: ignore
    np = None  # type: ignore


def ocr_available() -> bool:
    if convert_from_path is None or pytesseract is None:
        return False
    from shutil import which

    return which("tesseract") is not None


# ---------------------------------------------------------------------------
# Deskew (stronger than exp-deskew: finer grid + lower apply threshold)
# ---------------------------------------------------------------------------


def _pil_to_rgb_np(im: Any) -> Any:
    return np.array(im.convert("RGB"))


def _np_to_pil(arr: Any) -> Any:
    if arr.ndim == 2:
        return Image.fromarray(arr)
    return Image.fromarray(arr)


def _estimate_skew_projection(
    gray: Any, search: float = 12.0, step: float = 0.25
) -> float:
    """Angle (degrees, CCW) maximizing horizontal projection variance."""
    thr = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
    scale = 700.0 / max(thr.shape)
    if scale < 1.0:
        thr_s = cv2.resize(thr, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    else:
        thr_s = thr
    h, w = thr_s.shape
    cx, cy = w / 2.0, h / 2.0
    best_a, best_s = 0.0, -1.0
    a = -search
    while a <= search + 1e-9:
        M = cv2.getRotationMatrix2D((cx, cy), float(a), 1.0)
        rot = cv2.warpAffine(
            thr_s,
            M,
            (w, h),
            flags=cv2.INTER_NEAREST,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=0,
        )
        s = float(rot.sum(axis=1).astype(np.float64).var())
        if s > best_s:
            best_s, best_a = s, float(a)
        a += step
    # Local refine at half-step around best
    half = step / 2.0
    for a2 in (best_a - half, best_a + half, best_a - step * 0.75, best_a + step * 0.75):
        if abs(a2) > search:
            continue
        M = cv2.getRotationMatrix2D((cx, cy), float(a2), 1.0)
        rot = cv2.warpAffine(
            thr_s,
            M,
            (w, h),
            flags=cv2.INTER_NEAREST,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=0,
        )
        s = float(rot.sum(axis=1).astype(np.float64).var())
        if s > best_s:
            best_s, best_a = s, float(a2)
    return best_a


def _estimate_skew_hough(gray: Any) -> float | None:
    """Median near-horizontal Hough line angle, or None if weak signal."""
    blur = cv2.GaussianBlur(gray, (3, 3), 0)
    edges = cv2.Canny(blur, 50, 150, apertureSize=3)
    min_len = max(40, gray.shape[1] // 5)
    lines = cv2.HoughLinesP(
        edges,
        1,
        np.pi / 180.0,
        threshold=80,
        minLineLength=min_len,
        maxLineGap=25,
    )
    if lines is None or len(lines) == 0:
        return None
    angles: list[float] = []
    for line in lines:
        x1, y1, x2, y2 = [float(v) for v in line.ravel()[:4]]
        ang = float(np.degrees(np.arctan2(y2 - y1, x2 - x1)))
        if abs(ang) <= 25.0:
            angles.append(ang)
    if len(angles) < 5:
        return None
    return float(np.median(np.asarray(angles, dtype=np.float64)))


def _consensus_skew_angle(gray: Any) -> float:
    """Combine projection + Hough; clamp; ignore micro-rotations."""
    proj = _estimate_skew_projection(gray, search=12.0, step=0.25)
    hough = _estimate_skew_hough(gray)
    if hough is not None and abs(proj - hough) <= 2.5:
        angle = 0.55 * proj + 0.45 * hough
    elif hough is not None and abs(hough) >= 1.25 and abs(proj) < 0.6:
        angle = hough
    elif hough is not None and abs(proj) >= 1.0 and abs(hough) >= 1.0:
        # Both agree on "skewed" but diverge slightly — prefer projection (form lines)
        angle = proj if abs(proj) <= abs(hough) + 1.5 else 0.7 * proj + 0.3 * hough
    else:
        angle = proj
    # Stronger than v1 (0.75°): catch milder skew without micro-noise
    if abs(angle) < 0.55:
        return 0.0
    return float(max(-15.0, min(15.0, angle)))


def _rotate_bound(im: Any, angle: float) -> Any:
    """Rotate PIL image by angle degrees (CCW), expanding canvas with white fill."""
    if abs(angle) < 1e-3:
        return im
    if cv2 is None or np is None:
        return im.rotate(angle, expand=True, fillcolor=(255, 255, 255))
    arr = _pil_to_rgb_np(im)
    h, w = arr.shape[:2]
    M = cv2.getRotationMatrix2D((w / 2.0, h / 2.0), angle, 1.0)
    cos = abs(float(M[0, 0]))
    sin = abs(float(M[0, 1]))
    nw = int(h * sin + w * cos)
    nh = int(h * cos + w * sin)
    M[0, 2] += (nw / 2.0) - w / 2.0
    M[1, 2] += (nh / 2.0) - h / 2.0
    rotated = cv2.warpAffine(
        arr,
        M,
        (nw, nh),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(255, 255, 255),
    )
    return _np_to_pil(rotated)


def deskew_image(im: Any) -> tuple[Any, float]:
    """Deskew a PIL page image. Returns (image, angle_applied)."""
    if cv2 is None or np is None or Image is None:
        return im, 0.0
    try:
        arr = _pil_to_rgb_np(im)
        gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
        angle = _consensus_skew_angle(gray)
        if abs(angle) < 0.55:
            return im, 0.0
        return _rotate_bound(im, angle), angle
    except Exception:
        return im, 0.0


# ---------------------------------------------------------------------------
# Contrast / binarize / stamp cleanup
# ---------------------------------------------------------------------------


def _enhance_contrast(im: Any) -> Any:
    """Boost contrast for faded stamp ink. Prefer OpenCV CLAHE; fall back to PIL."""
    if cv2 is not None and np is not None and Image is not None:
        try:
            arr = np.array(im.convert("RGB"))
            gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
            clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
            enhanced = clahe.apply(gray)
            return Image.fromarray(enhanced)
        except Exception:
            pass
    if ImageEnhance is not None and ImageOps is not None:
        try:
            gray = ImageOps.grayscale(im)
            return ImageEnhance.Contrast(gray).enhance(1.8)
        except Exception:
            pass
    return im


def _to_gray_u8(im: Any) -> Any:
    arr = np.array(im.convert("RGB"))
    return cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)


def _ensure_dark_on_light(bw: Any) -> Any:
    """Force dark text on light background for tesseract."""
    if float(bw.mean()) < 127.0:
        return 255 - bw
    return bw


def _binarize_otsu(im: Any) -> Any:
    """CLAHE → light denoise → Otsu binary (crop-oriented)."""
    if cv2 is None or np is None or Image is None:
        return im
    try:
        gray = _to_gray_u8(im)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        g = clahe.apply(gray)
        g = cv2.GaussianBlur(g, (3, 3), 0)
        _, bw = cv2.threshold(g, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        bw = _ensure_dark_on_light(bw)
        # Tiny close to reconnect broken stamp strokes
        kernel = np.ones((2, 2), np.uint8)
        bw = cv2.morphologyEx(bw, cv2.MORPH_CLOSE, kernel, iterations=1)
        return Image.fromarray(bw)
    except Exception:
        return im


def _binarize_adaptive(im: Any) -> Any:
    """CLAHE → adaptive Gaussian threshold (handles uneven scan lighting)."""
    if cv2 is None or np is None or Image is None:
        return im
    try:
        gray = _to_gray_u8(im)
        clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
        g = clahe.apply(gray)
        # Block size odd, scaled mildly with image size
        h, w = g.shape
        block = max(15, min(51, (min(h, w) // 20) | 1))
        if block % 2 == 0:
            block += 1
        bw = cv2.adaptiveThreshold(
            g, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, block, 11
        )
        bw = _ensure_dark_on_light(bw)
        return Image.fromarray(bw)
    except Exception:
        return im


def _mild_sharpen_gray_pil(im: Any) -> Any:
    """Very light unsharp on deskewed full page to restore rotation blur."""
    if cv2 is None or np is None or Image is None:
        return im
    try:
        arr = np.array(im.convert("RGB"))
        gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
        blur = cv2.GaussianBlur(gray, (0, 0), 1.0)
        sharp = cv2.addWeighted(gray, 1.45, blur, -0.45, 0)
        return Image.fromarray(sharp)
    except Exception:
        return im


def _maybe_upscale(im: Any, min_side: int = 180, scale: float = 1.5) -> Any:
    """Upscale small stamp crops so thin ink is tesseract-readable."""
    w, h = im.size
    if min(w, h) >= min_side:
        return im
    if cv2 is not None and np is not None:
        try:
            arr = np.array(im.convert("RGB") if im.mode != "L" else im)
            out = cv2.resize(
                arr,
                None,
                fx=scale,
                fy=scale,
                interpolation=cv2.INTER_CUBIC,
            )
            return Image.fromarray(out)
        except Exception:
            pass
    nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
    return im.resize((nw, nh), Image.Resampling.LANCZOS if hasattr(Image, "Resampling") else Image.LANCZOS)


def _stamp_crops(im: Any) -> list[tuple[str, Any]]:
    """Crop stamp-prone regions: top/bottom 25%, four corners ~30%, center band."""
    w, h = im.size
    cw = max(1, int(w * 0.30))
    ch = max(1, int(h * 0.30))
    top_h = max(1, int(h * 0.25))
    bot_y = h - top_h
    mid_y0 = max(0, int(h * 0.30))
    mid_y1 = min(h, int(h * 0.70))
    mid_x0 = max(0, int(w * 0.15))
    mid_x1 = min(w, int(w * 0.85))

    regions: list[tuple[str, tuple[int, int, int, int]]] = [
        ("top_band", (0, 0, w, top_h)),
        ("bottom_band", (0, bot_y, w, h)),
        ("tl_corner", (0, 0, cw, ch)),
        ("tr_corner", (w - cw, 0, w, ch)),
        ("bl_corner", (0, h - ch, cw, h)),
        ("br_corner", (w - cw, h - ch, w, h)),
        ("center_band", (mid_x0, mid_y0, mid_x1, mid_y1)),
    ]
    out: list[tuple[str, Any]] = []
    for name, box in regions:
        try:
            crop = im.crop(box)
            if crop.size[0] >= 8 and crop.size[1] >= 8:
                out.append((name, crop))
        except Exception:
            continue
    return out


def _ocr_image(im: Any, psm: int) -> str:
    try:
        return pytesseract.image_to_string(im, config=f"--psm {psm}") or ""
    except Exception:
        return ""


def _merge_unique_texts(chunks: list[str]) -> str:
    """Merge OCR chunks preserving order; drop exact-duplicate lines (casefold)."""
    seen: set[str] = set()
    kept: list[str] = []
    for chunk in chunks:
        for raw in (chunk or "").splitlines():
            line = " ".join(raw.split()).strip()
            if not line:
                continue
            key = line.casefold()
            if key in seen:
                continue
            seen.add(key)
            kept.append(line)
    return "\n".join(kept)


def ocr_pdf_text(pdf_path: Path, dpi: int = 275, max_pages: int = 6) -> str:
    """Rasterize, stronger-deskew, OCR full page + CLAHE/binary stamp crops."""
    if not ocr_available():
        return ""
    path = Path(pdf_path)
    if not path.exists():
        return ""
    try:
        dpi = int(os.environ.get("MIB_OCR_DPI", str(dpi)))
    except ValueError:
        pass
    # Optional: skip binary crop passes for A/B (default on)
    use_binary = os.environ.get("MIB_OCR_BINARIZE", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }
    try:
        images = convert_from_path(str(path), dpi=dpi, first_page=1, last_page=max_pages)
    except Exception:
        return ""

    page_parts: list[str] = []
    for page_idx, im in enumerate(images):
        chunks: list[str] = []

        deskewed, angle = deskew_image(im)
        did_deskew = abs(angle) >= 0.55
        full = _mild_sharpen_gray_pil(deskewed) if did_deskew else deskewed

        # 1) Full-page natural (deskewed) first — first-match extract prefers these
        for psm in (6, 11, 4):
            text = _ocr_image(full, psm=psm)
            if text.strip():
                chunks.append(text)

        # 2) Full-page mild CLAHE only (not binary) — helps low-contrast form ink
        full_clahe = _enhance_contrast(deskewed)
        text = _ocr_image(full_clahe, psm=6)
        if text.strip():
            chunks.append(text)

        # 3) Stamp crops: CLAHE first, then additive binarize (gap-fill only)
        for name, crop in _stamp_crops(deskewed):
            crop_u = _maybe_upscale(crop)
            enhanced = _enhance_contrast(crop_u)
            for psm in (6, 11):
                text = _ocr_image(enhanced, psm=psm)
                if text.strip():
                    chunks.append(text)
            if use_binary:
                # Otsu on every crop (psm 6 only — cost control)
                otsu = _binarize_otsu(crop_u)
                text = _ocr_image(otsu, psm=6)
                if text.strip():
                    chunks.append(text)
                # Adaptive only on edge bands / corners (uneven lighting stamps)
                if name in {
                    "top_band",
                    "bottom_band",
                    "tl_corner",
                    "tr_corner",
                    "bl_corner",
                    "br_corner",
                }:
                    adapt = _binarize_adaptive(crop_u)
                    text = _ocr_image(adapt, psm=6)
                    if text.strip():
                        chunks.append(text)

        merged = _merge_unique_texts(chunks)
        if merged:
            page_parts.append(f"--- PAGE {page_idx + 1} ---\n{merged}")

    return "\n".join(page_parts)


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
    """Append OCR under a marker so adjudicate can use both."""
    base = text_layer or ""
    ocr = (ocr_text or "").strip()
    if not ocr:
        return base
    if ocr.casefold() in base.casefold():
        return base
    return base + "\n\n--- OCR_FALLBACK ---\n" + ocr
