"""End-to-end prediction pipeline for a directory of PDFs."""

from __future__ import annotations

import json
from pathlib import Path

from mib_solution.adjudicate import adjudicate
from mib_solution.extract import extract_fields, extract_pdf_text

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


def predict_pdf(pdf_path: Path) -> dict:
    text = extract_pdf_text(pdf_path)
    fields = extract_fields(pdf_path, text=text)
    adjudication, confidence = adjudicate(fields)
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


def predict_dir(input_dir: Path) -> list[dict]:
    pdfs = sorted(Path(input_dir).glob("*.pdf"))
    return [predict_pdf(pdf) for pdf in pdfs]


def write_jsonl(path: Path, predictions: list[dict]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for pred in predictions:
            row = {k: pred[k] for k in OUTPUT_KEYS}
            f.write(json.dumps(row, sort_keys=True) + "\n")


def run(input_dir: str | Path, output_path: str | Path) -> int:
    predictions = predict_dir(Path(input_dir))
    write_jsonl(Path(output_path), predictions)
    return len(predictions)
