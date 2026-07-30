"""Modal experiment farm: residual / OCR / full-data scoring (not offline product).

Shared Volume: mib-data (train/*.pdf already populated).
Functions for bulk score; orchestrator merges artifacts only.

Usage:
  modal run solution/modal_app.py --action smoke
  modal run solution/modal_app.py --action score-residual --run-name modal_residual_text
  modal run solution/modal_app.py --action score-residual-ocr --run-name modal_residual_ocr
  modal run solution/modal_app.py --action score-full --run-name modal_full_text
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import modal

APP_NAME = "mib-doc-experiments"
# Existing workspace volume with data/train/*.pdf
VOLUME_NAME = "mib-data"
VOL_MOUNT = "/data"

ROOT = Path(__file__).resolve().parent
# OCR experiment code tree (worktree) — text-only falls back to solution/src
OCR_SRC = ROOT.parent / "worktrees" / "exp-ocr" / "src"
SOLUTION_SRC = ROOT / "src"

text_image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install("pypdf>=5.0.0")
    .add_local_dir(str(SOLUTION_SRC), remote_path="/app/src")
)

ocr_image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("tesseract-ocr", "poppler-utils")
    .pip_install("pypdf>=5.0.0", "pdf2image>=1.17.0", "pytesseract>=0.3.13", "pillow>=10.0.0")
    .add_local_dir(str(OCR_SRC if OCR_SRC.exists() else SOLUTION_SRC), remote_path="/app/src")
)

app = modal.App(APP_NAME)
volume = modal.Volume.from_name(VOLUME_NAME, create_if_missing=False)


def _predict_one(case_id: str, use_ocr: bool) -> dict:
    import sys

    sys.path.insert(0, "/app/src")
    from mib_solution.pipeline import predict_pdf

    pdf = Path(VOL_MOUNT) / "train" / f"{case_id}.pdf"
    if not pdf.exists():
        return {"case_id": case_id, "error": "missing_pdf"}
    try:
        # OCR pipeline accepts use_ocr; text-only solution may not
        try:
            pred = predict_pdf(pdf, use_ocr=use_ocr)
        except TypeError:
            pred = predict_pdf(pdf)
        pred["_ocr_mode"] = use_ocr
        return pred
    except Exception as exc:  # noqa: BLE001 — return error row for farm robustness
        return {"case_id": case_id, "error": str(exc)}


@app.function(image=text_image, volumes={VOL_MOUNT: volume}, timeout=120)
def smoke() -> dict:
    import sys

    sys.path.insert(0, "/app/src")
    from mib_solution import __version__

    train = Path(VOL_MOUNT) / "train"
    n = len(list(train.glob("*.pdf"))) if train.exists() else 0
    sample_ok = (train / "MIB-000001.pdf").exists()
    return {
        "ok": True,
        "version": __version__,
        "volume": VOLUME_NAME,
        "volume_train_pdfs": n,
        "sample_MIB-000001": sample_ok,
        "mount": VOL_MOUNT,
    }


@app.function(
    image=text_image,
    volumes={VOL_MOUNT: volume},
    timeout=120,
    cpu=1,
    memory=2048,
)
def predict_text(case_id: str) -> dict:
    return _predict_one(case_id, use_ocr=False)


@app.function(
    image=ocr_image,
    volumes={VOL_MOUNT: volume},
    timeout=300,
    cpu=2,
    memory=4096,
)
def predict_ocr(case_id: str) -> dict:
    return _predict_one(case_id, use_ocr=True)


@app.function(image=ocr_image, volumes={VOL_MOUNT: volume}, timeout=180)
def ocr_smoke(case_id: str = "MIB-000033") -> dict:
    """One-case OCR diagnostic on Volume PDF."""
    import sys

    sys.path.insert(0, "/app/src")
    from mib_solution.extract import extract_pdf_text
    from mib_solution.ocr import ocr_available, ocr_pdf_text, should_ocr
    from mib_solution.pipeline import predict_pdf

    pdf = Path(VOL_MOUNT) / "train" / f"{case_id}.pdf"
    if not pdf.exists():
        return {"ok": False, "error": "missing_pdf", "case_id": case_id}
    text_layer = extract_pdf_text(pdf)
    ocr_text = ocr_pdf_text(pdf)
    pred = predict_pdf(pdf, use_ocr=True)
    return {
        "ok": True,
        "case_id": case_id,
        "ocr_available": ocr_available(),
        "text_layer_len": len(text_layer or ""),
        "ocr_text_len": len(ocr_text or ""),
        "should_ocr": should_ocr(text_layer),
        "ocr_snippet": (ocr_text or "")[:500],
        "pred_risk": pred.get("risk_flags"),
        "pred_adj": pred.get("adjudication"),
        "pred_conf": pred.get("confidence"),
    }


def _write_preds_and_score(root: Path, art: Path, preds: list[dict], case_ids: list[str], run_name: str, action: str) -> dict:
    import csv

    # Drop error rows that aren't valid predictions
    good = []
    errors = []
    for p in preds:
        if p.get("error") or "adjudication" not in p:
            errors.append(p)
            continue
        # strip internal keys
        good.append({k: v for k, v in p.items() if not str(k).startswith("_")})

    preds_path = art / "predictions.jsonl"
    with preds_path.open("w") as f:
        for row in good:
            f.write(json.dumps(row, sort_keys=True) + "\n")

    residual = json.loads((root / "artifacts" / "residual.json").read_text())
    truth_rows = list(csv.DictReader((root / "data" / "train_labels.csv").open()))
    idset = set(case_ids)
    truth_out = art / "truth.csv"
    with truth_out.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=truth_rows[0].keys())
        w.writeheader()
        for r in truth_rows:
            if r["case_id"] in idset:
                w.writerow(r)

    eval_path = art / "eval.json"
    subprocess.check_call(
        [
            "python3",
            str(root / "scripts" / "evaluate.py"),
            "--truth",
            str(truth_out),
            "--submission",
            str(preds_path),
            "--output-json",
            str(eval_path),
            "--case-scores-jsonl",
            str(art / "case_scores.jsonl"),
        ]
    )
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    ev = json.loads(eval_path.read_text())
    meta = {
        "run_name": run_name,
        "action": action,
        "git": sha,
        "residual_version": residual.get("version"),
        "n_case_ids": len(case_ids),
        "n_preds": len(good),
        "n_errors": len(errors),
        "errors_sample": errors[:5],
        "primary": ev["scores"]["total_score"],
        "extraction": ev["scores"]["extraction_score"],
        "classification": ev["scores"]["classification_score"],
        "calibration": ev["scores"]["calibration_score"],
        "catastrophic": ev["raw"]["catastrophic_false_approvals"],
        "volume": VOLUME_NAME,
        "command": f"modal run solution/modal_app.py --action {action} --run-name {run_name}",
    }
    (art / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    return meta


@app.local_entrypoint()
def main(action: str = "smoke", run_name: str = "modal_smoke"):
    root = Path(__file__).resolve().parents[1]
    art = root / "artifacts" / run_name
    art.mkdir(parents=True, exist_ok=True)

    if action == "smoke":
        result = smoke.remote()
        (art / "smoke.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result, indent=2))
        return

    if action == "ocr-smoke":
        result = ocr_smoke.remote("MIB-000033")
        (art / "ocr_smoke.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result, indent=2))
        return

    residual = json.loads((root / "artifacts" / "residual.json").read_text())
    case_ids = residual["case_ids"]

    if action == "score-residual":
        # Parallel map text-only on promote solution image
        print(f"scoring residual n={len(case_ids)} text-only via Modal…")
        preds = list(predict_text.map(case_ids, order_outputs=True, return_exceptions=False))
        meta = _write_preds_and_score(root, art, preds, case_ids, run_name, action)
        print(json.dumps(meta, indent=2))
        return

    if action == "score-residual-ocr":
        print(f"scoring residual n={len(case_ids)} WITH OCR via Modal…")
        preds = list(predict_ocr.map(case_ids, order_outputs=True, return_exceptions=False))
        meta = _write_preds_and_score(root, art, preds, case_ids, run_name, action)
        print(json.dumps(meta, indent=2))
        return

    if action in {"score-full", "score-full-ocr"}:
        use_ocr = action == "score-full-ocr"
        train_ids = sorted(p.stem for p in (root / "data" / "train").glob("*.pdf"))
        mode = "OCR" if use_ocr else "text-only"
        print(f"scoring full train n={len(train_ids)} {mode} via Modal…")
        if use_ocr:
            preds = list(predict_ocr.map(train_ids, order_outputs=True, return_exceptions=False))
        else:
            preds = list(predict_text.map(train_ids, order_outputs=True, return_exceptions=False))
        import csv

        good = [p for p in preds if "adjudication" in p and not p.get("error")]
        errors = [p for p in preds if p.get("error") or "adjudication" not in p]
        preds_path = art / "predictions.jsonl"
        with preds_path.open("w") as f:
            for row in good:
                clean = {k: v for k, v in row.items() if not str(k).startswith("_")}
                f.write(json.dumps(clean, sort_keys=True) + "\n")
        eval_path = art / "eval.json"
        subprocess.check_call(
            [
                "python3",
                str(root / "scripts" / "evaluate.py"),
                "--truth",
                str(root / "data" / "train_labels.csv"),
                "--submission",
                str(preds_path),
                "--output-json",
                str(eval_path),
                "--case-scores-jsonl",
                str(art / "case_scores.jsonl"),
            ]
        )
        ev = json.loads(eval_path.read_text())
        meta = {
            "run_name": run_name,
            "action": action,
            "n_preds": len(good),
            "n_errors": len(errors),
            "primary": ev["scores"]["total_score"],
            "extraction": ev["scores"]["extraction_score"],
            "classification": ev["scores"]["classification_score"],
            "calibration": ev["scores"]["calibration_score"],
            "catastrophic": ev["raw"]["catastrophic_false_approvals"],
            "scores": ev["scores"],
            "volume": VOLUME_NAME,
            "command": f"modal run solution/modal_app.py --action {action} --run-name {run_name}",
        }
        (art / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")
        print(json.dumps(meta, indent=2))
        return

    raise SystemExit(f"unknown action: {action}")
