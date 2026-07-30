"""Modal experiment farm: residual / full-data scoring (not the offline product).

Usage (after `modal setup` / token):
  modal run solution/modal_app.py --action smoke
  modal run solution/modal_app.py --action score-residual --run-name residual_baseline

Layout:
  - Shared Volume for train/validation PDFs (upload once)
  - Functions for bulk score (not idle sandboxes)
  - Artifacts written back to local artifacts/<run_name>/
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

import modal

APP_NAME = "mib-doc-experiments"
VOLUME_NAME = "mib-doc-data"
VOL_MOUNT = "/data"

image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install("pypdf>=5.0.0")
    .add_local_dir(
        str(Path(__file__).resolve().parent / "src"),
        remote_path="/app/src",
    )
)

app = modal.App(APP_NAME)
volume = modal.Volume.from_name(VOLUME_NAME, create_if_missing=True)


@app.function(image=image, volumes={VOL_MOUNT: volume}, timeout=120)
def smoke() -> dict:
    """Prove Modal can import solution code and see the Volume mount."""
    import sys

    sys.path.insert(0, "/app/src")
    from mib_solution import __version__

    data = Path(VOL_MOUNT)
    train = data / "train"
    n_pdfs = len(list(train.glob("*.pdf"))) if train.exists() else 0
    return {
        "ok": True,
        "version": __version__,
        "volume_train_pdfs": n_pdfs,
        "mount": VOL_MOUNT,
    }


@app.function(image=image, volumes={VOL_MOUNT: volume}, timeout=60 * 30, cpu=2, memory=4096)
def score_residual(case_ids: list[str], run_name: str) -> dict:
    """Predict residual case_ids from Volume train/ and return predictions JSONL text."""
    import sys

    sys.path.insert(0, "/app/src")
    from mib_solution.pipeline import predict_pdf, write_jsonl

    train = Path(VOL_MOUNT) / "train"
    preds = []
    missing = []
    for cid in case_ids:
        pdf = train / f"{cid}.pdf"
        if not pdf.exists():
            missing.append(cid)
            continue
        preds.append(predict_pdf(pdf))

    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "predictions.jsonl"
        write_jsonl(out, preds)
        body = out.read_text()
    return {
        "run_name": run_name,
        "n_preds": len(preds),
        "missing_pdfs": missing,
        "predictions_jsonl": body,
    }


@app.local_entrypoint()
def main(action: str = "smoke", run_name: str = "modal_smoke"):
    """Orchestrator-side entry: pull artifacts locally; merge only on orchestrator."""
    root = Path(__file__).resolve().parents[1]
    art = root / "artifacts" / run_name
    art.mkdir(parents=True, exist_ok=True)

    if action == "smoke":
        result = smoke.remote()
        (art / "smoke.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result, indent=2))
        return

    if action == "score-residual":
        residual_path = root / "artifacts" / "residual.json"
        residual = json.loads(residual_path.read_text())
        case_ids = residual["case_ids"]
        result = score_residual.remote(case_ids, run_name)
        preds_path = art / "predictions.jsonl"
        preds_path.write_text(result["predictions_jsonl"])
        # Build residual truth and score locally with challenge scorer
        import csv

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
        meta = {
            "run_name": run_name,
            "action": action,
            "git": sha,
            "residual_version": residual.get("version"),
            "n_case_ids": len(case_ids),
            "n_preds": result["n_preds"],
            "missing_pdfs": result["missing_pdfs"],
            "command": f"modal run solution/modal_app.py --action score-residual --run-name {run_name}",
        }
        (art / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")
        print(json.dumps(meta, indent=2))
        print(eval_path.read_text()[:500])
        return

    raise SystemExit(f"unknown action: {action}")
