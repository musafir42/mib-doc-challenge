"""End-to-end prediction pipeline for a directory of PDFs."""

from __future__ import annotations

import json
import os
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from mib_solution.adjudicate import adjudicate
from mib_solution.calibrate import calibrate
from mib_solution.extract import extract_fields, extract_pdf_text
from mib_solution.ocr import merge_text_layers, ocr_pdf_text, should_ocr

OUTPUT_KEYS = [
    "case_id",
    "applicant_name",
    "species_code",
    "home_world",
    "visa_class",
    "sponsor_id",
    "arrival_date",
    "declared_purpose",
    "risk_flags",
    "fee_status",
    "adjudication",
    "confidence",
]


def default_workers() -> int:
    """Ship default: min(4, cpu_count). Challenge scoring gives 4 vCPU.

    Override with MIB_WORKERS. Pair with OMP_THREAD_LIMIT=1 so each worker
    uses one core without OpenMP oversubscription inside tesseract/opencv.
    """
    env = os.environ.get("MIB_WORKERS")
    if env is not None and str(env).strip() != "":
        try:
            return max(1, int(env))
        except ValueError:
            pass
    return min(4, os.cpu_count() or 1)


def _page_count(pdf_path: Path) -> int:
    try:
        from pypdf import PdfReader

        n = len(PdfReader(str(pdf_path)).pages)
        return max(1, int(n))
    except Exception:
        return 1


def predict_pdf(pdf_path: Path, use_ocr: bool | None = None) -> dict:
    """Predict one PDF. OCR runs when use_ocr=True or should_ocr(text_layer)."""
    text_layer = extract_pdf_text(pdf_path)
    do_ocr = bool(use_ocr) if use_ocr is not None else should_ocr(text_layer)
    if do_ocr:
        ocr_text = ocr_pdf_text(pdf_path)
        text = merge_text_layers(text_layer, ocr_text)
    else:
        text = text_layer
    fields = extract_fields(pdf_path, text=text)
    fields["_ocr_used"] = do_ocr
    fields["_page_count"] = _page_count(pdf_path)
    # Ensure text length proxy is available for calibrate
    if fields.get("_text_len") is None:
        fields["_text_len"] = len(fields.get("_text") or text or "")
    adjudication, _legacy_conf, adj_reason = adjudicate(fields)
    fields["_adj_reason"] = adj_reason
    # Feature/path-based confidence (Brier); does not change adjudication
    confidence = calibrate(fields, adjudication, reason=adj_reason)
    pred = {k: fields.get(k, "unknown") for k in OUTPUT_KEYS if k not in {"adjudication", "confidence"}}
    pred["adjudication"] = adjudication
    pred["confidence"] = float(confidence)
    # Normalize fee_status enum
    fee = str(pred.get("fee_status", "unknown")).casefold()
    if fee not in {"paid", "waived", "unpaid", "unknown"}:
        fee = "unknown"
    pred["fee_status"] = fee
    # risk_flags empty → none
    rf = str(pred.get("risk_flags") or "none").strip()
    pred["risk_flags"] = rf if rf else "none"
    return pred


def predict_dir(input_dir: Path, workers: int | None = None) -> list[dict]:
    """Predict all PDFs in a directory.

    Uses ProcessPoolExecutor when workers > 1 (default min(4, cpu_count)).
    Output order is deterministic: sorted by case_id.
    """
    pdfs = sorted(Path(input_dir).glob("*.pdf"))
    if not pdfs:
        return []
    n_workers = default_workers() if workers is None else max(1, int(workers))
    if n_workers <= 1 or len(pdfs) == 1:
        preds = [predict_pdf(pdf) for pdf in pdfs]
    else:
        # map preserves input order; we re-sort by case_id below for determinism
        with ProcessPoolExecutor(max_workers=n_workers) as ex:
            preds = list(ex.map(predict_pdf, pdfs))
    preds.sort(key=lambda p: str(p.get("case_id") or ""))
    return preds


def write_jsonl(path: Path, predictions: list[dict]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Deterministic write order even if caller passed unsorted preds
    ordered = sorted(predictions, key=lambda p: str(p.get("case_id") or ""))
    with path.open("w", encoding="utf-8") as f:
        for pred in ordered:
            row = {k: pred[k] for k in OUTPUT_KEYS}
            f.write(json.dumps(row, sort_keys=True) + "\n")


def run(input_dir: str | Path, output_path: str | Path, workers: int | None = None) -> int:
    predictions = predict_dir(Path(input_dir), workers=workers)
    write_jsonl(Path(output_path), predictions)
    return len(predictions)
