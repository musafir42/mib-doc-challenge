"""Ship OCR: PaddleOCR + fine-tuned rec + geometry region crops.

Non-brittle path — perception in the model; no OCR typo banks / SPN denylists.

Ban list (must not appear here):
- OCR typo banks (Fouing, DEMED, embamen, …)
- Hardcoded SPN denylists
- Train-precision residual case_id specials
- Multi-PSM tesseract ensemble

Models: package-relative ``models/paddle/{rec,det,cls}`` or env overrides.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")
os.environ.setdefault("FLAGS_use_mkldnn", "0")

_ENGINE = None
_ENGINE_ERR: str | None = None
_ENGINE_META: dict = {}

# Geometry-only region boxes (fractions of page). Top/bottom + corners + center.
_REGION_FRACS: list[tuple[str, float, float, float, float]] = [
    ("top_band", 0.00, 0.00, 1.00, 0.20),
    ("bottom_band", 0.00, 0.80, 1.00, 1.00),
    ("tl_corner", 0.00, 0.00, 0.30, 0.30),
    ("tr_corner", 0.70, 0.00, 1.00, 0.30),
    ("bl_corner", 0.00, 0.70, 0.30, 1.00),
    ("br_corner", 0.70, 0.70, 1.00, 1.00),
    ("center_band", 0.15, 0.30, 0.85, 0.70),
]


def _models_root() -> Path:
    env = os.environ.get("MIB_PADDLE_MODELS", "").strip()
    if env:
        return Path(env)
    # solution/src/mib_solution/ocr_paddle.py → solution/models/paddle
    here = Path(__file__).resolve()
    candidates = [
        here.parents[2] / "models" / "paddle",  # solution/models/paddle
        Path("/app/models/paddle"),
        Path("/root/dev-workspace/mib-doc-challenge/solution/models/paddle"),
    ]
    for c in candidates:
        if c.is_dir():
            return c
    return candidates[0]


def _resolve_subdir(name: str, env_key: str) -> Path | None:
    env = os.environ.get(env_key, "").strip()
    if env and Path(env).is_dir():
        return Path(env)
    p = _models_root() / name
    return p if p.is_dir() else None


def _extract_text_from_result(result: Any) -> str:
    if result is None:
        return ""
    lines: list[str] = []
    pages = result if isinstance(result, list) else [result]
    for page in pages:
        if page is None or not isinstance(page, list):
            continue
        for item in page:
            try:
                if isinstance(item, (list, tuple)) and len(item) >= 2:
                    info = item[1]
                    if isinstance(info, (list, tuple)) and len(info) >= 1:
                        lines.append(str(info[0]))
                    elif isinstance(info, str):
                        lines.append(info)
                    elif isinstance(info, dict) and "text" in info:
                        lines.append(str(info["text"]))
            except Exception:
                continue
    return "\n".join(lines)


def _merge_unique_texts(chunks: list[str]) -> str:
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


def get_engine_meta() -> dict:
    get_engine()
    return dict(_ENGINE_META)


def get_engine():
    """Lazy per-process PaddleOCR (vendored det/cls + FT rec)."""
    global _ENGINE, _ENGINE_ERR, _ENGINE_META
    if _ENGINE is not None:
        return _ENGINE
    if _ENGINE_ERR is not None:
        return None
    try:
        from paddleocr import PaddleOCR

        rec = _resolve_subdir("rec", "MIB_PADDLE_REC_MODEL_DIR")
        det = _resolve_subdir("det", "MIB_PADDLE_DET_MODEL_DIR")
        cls = _resolve_subdir("cls", "MIB_PADDLE_CLS_MODEL_DIR")
        rec_dict = None
        if rec is not None:
            for name in ("en_dict.txt", "ppocr_keys_v1.txt", "dict.txt"):
                cand = rec / name
                if cand.is_file():
                    rec_dict = str(cand)
                    break
        kwargs: dict = {
            "use_angle_cls": True,
            "lang": "en",
            "use_gpu": False,
            "show_log": False,
            "ocr_version": "PP-OCRv4",
        }
        if rec is not None:
            kwargs["rec_model_dir"] = str(rec)
            if rec_dict:
                kwargs["rec_char_dict_path"] = rec_dict
        if det is not None:
            kwargs["det_model_dir"] = str(det)
        if cls is not None:
            kwargs["cls_model_dir"] = str(cls)

        _ENGINE = PaddleOCR(**kwargs)
        _ENGINE_META = {
            "mode": "paddle_ft_ship",
            "rec_model_dir": str(rec) if rec else None,
            "det_model_dir": str(det) if det else None,
            "cls_model_dir": str(cls) if cls else None,
            "rec_char_dict": rec_dict,
            "models_root": str(_models_root()),
        }
        return _ENGINE
    except Exception as exc:  # noqa: BLE001
        _ENGINE_ERR = f"{type(exc).__name__}: {exc}"
        _ENGINE_META = {"mode": "error", "error": _ENGINE_ERR}
        return None


def ocr_available() -> bool:
    return get_engine() is not None


def _run_ocr(engine: Any, arr: Any) -> str:
    try:
        try:
            result = engine.ocr(arr, cls=True)
        except TypeError:
            result = engine.ocr(arr)
        return _extract_text_from_result(result)
    except Exception:
        return ""


def _clahe_rgb(arr: Any) -> Any | None:
    try:
        import cv2

        if arr is None:
            return None
        if arr.ndim == 2:
            gray = arr
        else:
            gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        return cv2.cvtColor(enhanced, cv2.COLOR_GRAY2RGB)
    except Exception:
        return None


def _geometry_crops(arr: Any) -> list[tuple[str, Any]]:
    if arr is None:
        return []
    h, w = int(arr.shape[0]), int(arr.shape[1])
    out: list[tuple[str, Any]] = []
    for name, x0f, y0f, x1f, y1f in _REGION_FRACS:
        x0 = max(0, min(w - 1, int(w * x0f)))
        y0 = max(0, min(h - 1, int(h * y0f)))
        x1 = max(x0 + 1, min(w, int(w * x1f)))
        y1 = max(y0 + 1, min(h, int(h * y1f)))
        if (x1 - x0) < 8 or (y1 - y0) < 8:
            continue
        crop = arr[y0:y1, x0:x1]
        if crop.size == 0:
            continue
        out.append((name, crop))
    return out


def ocr_pdf_text(pdf_path: Path, dpi: int = 150, max_pages: int = 4) -> str:
    """Rasterize PDF; full-page + geometry region PaddleOCR; merge unique lines."""
    engine = get_engine()
    if engine is None:
        return ""
    path = Path(pdf_path)
    if not path.exists():
        return ""
    try:
        dpi = int(os.environ.get("MIB_OCR_DPI", str(dpi)))
    except ValueError:
        pass
    try:
        max_pages = int(os.environ.get("MIB_OCR_MAX_PAGES", str(max_pages)))
    except ValueError:
        pass
    use_clahe = os.environ.get("MIB_OCR_CLAHE", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }
    use_regions = os.environ.get("MIB_OCR_REGIONS", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }
    # Optional: skip region crops when full page already rich (latency A/B).
    # Default 0 = always run geometry regions (needed for stamp Finding).
    try:
        region_skip_chars = int(os.environ.get("MIB_OCR_REGION_SKIP_CHARS", "0"))
    except ValueError:
        region_skip_chars = 0

    try:
        from pdf2image import convert_from_path
    except Exception:
        return ""

    try:
        images = convert_from_path(str(path), dpi=dpi, first_page=1, last_page=max_pages)
    except Exception:
        return ""

    page_parts: list[str] = []
    for page_idx, im in enumerate(images):
        chunks: list[str] = []
        try:
            import numpy as np

            arr = np.array(im.convert("RGB"))
        except Exception:
            arr = None
        if arr is None:
            continue

        full_text = _run_ocr(engine, arr)
        if full_text.strip():
            chunks.append(full_text)

        full_len = sum(len(t) for t in chunks)
        if use_clahe and full_len < 40:
            enh = _clahe_rgb(arr)
            if enh is not None:
                t = _run_ocr(engine, enh)
                if t.strip():
                    chunks.append(t)
                    full_len = sum(len(x) for x in chunks)

        # Regions only when full page is thin — stamps often need crops;
        # if already rich, skip for latency (override with REGION_SKIP_CHARS=0).
        run_regions = use_regions and (
            region_skip_chars <= 0 or full_len < region_skip_chars
        )
        if run_regions:
            for _name, crop in _geometry_crops(arr):
                t = _run_ocr(engine, crop)
                if t.strip():
                    chunks.append(t)
                elif use_clahe:
                    enh = _clahe_rgb(crop)
                    if enh is not None:
                        t2 = _run_ocr(engine, enh)
                        if t2.strip():
                            chunks.append(t2)

        merged = _merge_unique_texts(chunks)
        if merged:
            page_parts.append(f"--- PAGE {page_idx + 1} ---\n{merged}")

    return "\n".join(page_parts)
