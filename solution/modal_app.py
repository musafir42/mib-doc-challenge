"""Modal experiment farm — Sandbox-first bulk scoring (not the offline product).

Shared Volume: mib-data (train/ + validation/ PDFs).
One (or few) Sandboxes process many PDFs with in-container workers, then terminate.

Official Sandbox pattern (Modal docs):
  create → exec → terminate → detach
  volumes= supported like Functions
  from_dockerfile images work with Sandboxes

Usage:
  modal run solution/modal_app.py --action smoke
  modal run solution/modal_app.py --action populate-volume
  modal run solution/modal_app.py --action score-residual-ocr --run-name promote_integrate
  modal run solution/modal_app.py --action score-full-ocr --run-name promote_integrate_full
  modal run solution/modal_app.py --action predict-validation-ocr --run-name ship_align_val
  modal run solution/modal_app.py --action score-full-docker --run-name ship_docker_full
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time
from pathlib import Path

import modal

APP_NAME = "mib-doc-experiments"
VOLUME_NAME = "mib-data"
VOL_MOUNT = "/data"

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
SOLUTION_SRC = ROOT / "src"
_code_env = os.environ.get("MIB_CODE_SRC", "").strip()
if _code_env:
    CODE_SRC = Path(_code_env)
    if not CODE_SRC.is_absolute():
        CODE_SRC = (REPO / CODE_SRC).resolve()
else:
    CODE_SRC = SOLUTION_SRC
if not CODE_SRC.exists():
    CODE_SRC = SOLUTION_SRC

DATA_ZIP_URL = (
    "https://huggingface.co/datasets/arjun-krishna1/mib-doc-challenge-data/"
    "resolve/main/mib-doc-challenge-public-data-v2026-07-07.zip"
)
DATA_ZIP_SHA256 = "a9bb8c1bbf51346ebf49c2e3e1acdb7a5d6cd0760162767b0d133c7b7200f3c4"

# Images (code baked in for sandboxes)
# add_local_* must be last image step (Modal rule); use copy=True if later steps needed.
text_image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install("pypdf>=5.0.0")
    .env({"PYTHONPATH": "/app/src"})
    .add_local_dir(str(CODE_SRC), remote_path="/app/src")
)

ocr_image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("tesseract-ocr", "poppler-utils")
    .pip_install(
        "pypdf>=5.0.0",
        "pdf2image>=1.17.0",
        "pytesseract>=0.3.13",
        "pillow>=10.0.0",
        "opencv-python-headless>=4.8.0",
        "numpy>=1.26.0",
    )
    .env({"PYTHONPATH": "/app/src", "TMPDIR": "/tmp", "HOME": "/tmp"})
    .add_local_dir(str(CODE_SRC), remote_path="/app/src")
)

# Same Dockerfile as offline submission — Sandboxes accept from_dockerfile images.
# Clear ENTRYPOINT so sb.exec("python", ...) is not swallowed by run.sh.
docker_image = (
    modal.Image.from_dockerfile(
        str(ROOT / "Dockerfile"),
        context_dir=str(ROOT),
    )
    .entrypoint([])
    .cmd([])
)

_populate_image = (
    modal.Image.debian_slim(python_version="3.12").apt_install(
        "curl", "ca-certificates", "unzip"
    )
)

app = modal.App(APP_NAME)
volume = modal.Volume.from_name(VOLUME_NAME, create_if_missing=True)


def _workers() -> int:
    return max(1, min(int(os.environ.get("MIB_SANDBOX_WORKERS", "4")), 16))


def _timeout_seconds(n_ids: int, use_ocr: bool) -> int:
    # Rough budget; OCR ~ few s/PDF with 4 workers
    per = 8 if use_ocr else 1
    est = int(n_ids * per / max(1, _workers())) + 600
    return min(24 * 3600 - 60, max(600, est))


def _run_sandbox_bulk(
    *,
    image: modal.Image,
    case_ids: list[str],
    input_subdir: str,
    run_name: str,
    use_ocr: bool,
    remote_run_dir: str | None = None,
) -> dict:
    """Create sandbox, bulk-predict, pull results, terminate.

    Official lifecycle: create → exec → terminate → detach.
    """
    remote_run_dir = remote_run_dir or f"runs/{run_name}"
    remote_base = f"{VOL_MOUNT}/{remote_run_dir}"
    # Stage ids JSON via volume put (small)
    with tempfile.TemporaryDirectory() as td:
        local_ids = Path(td) / "ids.json"
        local_ids.write_text(json.dumps(case_ids) + "\n")
        subprocess.check_call(
            [
                "modal",
                "volume",
                "put",
                VOLUME_NAME,
                str(local_ids),
                f"{remote_run_dir}/ids.json",
                "--force",
            ]
        )

    # Keep container alive for exec (empty ENTRYPOINT images exit immediately otherwise).
    timeout_s = _timeout_seconds(len(case_ids), use_ocr)
    sb = modal.Sandbox.create(
        "sleep",
        str(timeout_s + 120),
        image=image,
        volumes={VOL_MOUNT: volume},
        timeout=timeout_s + 180,
        cpu=4,
        memory=8192,
        # Unbuffered logs so dashboard + local stream show progress during OCR
        env={
            "PYTHONUNBUFFERED": "1",
            "PYTHONPATH": "/app/src:/app",
            "TMPDIR": "/tmp",
            "HOME": "/tmp",
        },
        app=app,
    )
    summary: dict = {
        "sandbox_id": getattr(sb, "object_id", None),
        "n_ids": len(case_ids),
        "input_subdir": input_subdir,
        "use_ocr": use_ocr,
        "workers": _workers(),
    }
    try:
        cmd = [
            "python",
            "-m",
            "mib_solution.modal_bulk_runner",
            "--ids-json",
            f"{remote_base}/ids.json",
            "--input-root",
            f"{VOL_MOUNT}/{input_subdir}",
            "--out-jsonl",
            f"{remote_base}/predictions.jsonl",
            "--errors-json",
            f"{remote_base}/errors.json",
            "--workers",
            str(_workers()),
        ]
        if use_ocr:
            cmd.append("--use-ocr")
        print("sandbox exec:", " ".join(cmd), flush=True)
        proc = sb.exec(*cmd, timeout=timeout_s)
        # Prefer streaming stdout while running, then wait for exit.
        stdout_chunks: list[str] = []
        try:
            for line in proc.stdout:
                print(line, end="", flush=True)
                stdout_chunks.append(line)
        except Exception as exc:  # noqa: BLE001
            print(f"stdout stream error: {exc!r}", flush=True)
        try:
            ret = proc.wait()
        except TypeError:
            proc.wait()
            ret = getattr(proc, "returncode", None)
        except Exception as exc:  # noqa: BLE001
            ret = None
            print(f"wait() error: {exc!r}", flush=True)
        try:
            err = proc.stderr.read() if proc.stderr is not None else ""
            if err:
                print("STDERR:", str(err)[-4000:], flush=True)
        except Exception:
            pass
        summary["returncode"] = ret if ret is not None else getattr(proc, "returncode", None)
        summary["stdout_tail"] = "".join(stdout_chunks)[-2000:]
        # Reload volume then pull artifacts
        try:
            volume.reload()
        except Exception:
            pass
        time.sleep(2)
    finally:
        try:
            sb.terminate(wait=True)
        except TypeError:
            try:
                sb.terminate()
            except Exception:
                pass
        try:
            sb.detach()
        except Exception:
            pass

    return summary


def _pull_run_artifacts(run_name: str, art: Path) -> dict:
    """Pull predictions/errors/summary from Volume into local artifacts/."""
    art.mkdir(parents=True, exist_ok=True)
    remote_run = f"runs/{run_name}"
    pulled = {}
    for name in ("predictions.jsonl", "errors.json", "predictions.summary.json", "ids.json"):
        # summary may be predictions.summary.json from with_suffix
        remote = f"{remote_run}/{name}"
        if name == "predictions.summary.json":
            remote = f"{remote_run}/predictions.summary.json"
        local = art / name
        try:
            subprocess.check_call(
                ["modal", "volume", "get", VOLUME_NAME, remote, str(local), "--force"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
            pulled[name] = local.exists()
        except subprocess.CalledProcessError:
            # try alternate summary path
            if "summary" in name:
                alt_remote = f"{remote_run}/predictions.summary.json"
                try:
                    subprocess.check_call(
                        [
                            "modal",
                            "volume",
                            "get",
                            VOLUME_NAME,
                            alt_remote,
                            str(art / "summary.json"),
                            "--force",
                        ],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.PIPE,
                    )
                    pulled["summary.json"] = (art / "summary.json").exists()
                except subprocess.CalledProcessError:
                    pulled[name] = False
            else:
                pulled[name] = False
    # Fix summary filename from bulk runner: out_jsonl.with_suffix('.summary.json')
    # → predictions.summary.json
    for cand in (
        art / "predictions.summary.json",
        art / "summary.json",
    ):
        if cand.exists():
            try:
                pulled["summary"] = json.loads(cand.read_text())
            except json.JSONDecodeError:
                pass
    if (art / "errors.json").exists():
        try:
            errs = json.loads((art / "errors.json").read_text())
            missing = [e.get("case_id") for e in errs if isinstance(e, dict) and e.get("case_id")]
            (art / "missing_ids.json").write_text(json.dumps(missing, indent=2) + "\n")
            pulled["n_missing"] = len(missing)
        except json.JSONDecodeError:
            pass
    n_preds = 0
    if (art / "predictions.jsonl").exists():
        n_preds = sum(1 for line in (art / "predictions.jsonl").read_text().splitlines() if line.strip())
    pulled["n_preds"] = n_preds
    return pulled


def _score_local(root: Path, art: Path, truth_csv: Path, run_name: str, action: str, extra_meta: dict) -> dict:
    preds_path = art / "predictions.jsonl"
    eval_path = art / "eval.json"
    subprocess.check_call(
        [
            "python3",
            str(root / "scripts" / "evaluate.py"),
            "--truth",
            str(truth_csv),
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
        "compute": "sandbox",
        "n_preds": extra_meta.get("n_preds"),
        "n_missing": extra_meta.get("n_missing"),
        "primary": ev["scores"]["total_score"],
        "extraction": ev["scores"]["extraction_score"],
        "classification": ev["scores"]["classification_score"],
        "calibration": ev["scores"]["calibration_score"],
        "catastrophic": ev["raw"]["catastrophic_false_approvals"],
        "scores": ev["scores"],
        "volume": VOLUME_NAME,
        "code_src": str(CODE_SRC),
        **{k: v for k, v in extra_meta.items() if k not in ("n_preds", "n_missing")},
    }
    (art / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    print(json.dumps(meta, indent=2))
    return meta


def _filter_truth(root: Path, case_ids: list[str], out_csv: Path) -> None:
    import csv

    rows = list(csv.DictReader((root / "data" / "train_labels.csv").open()))
    idset = set(case_ids)
    with out_csv.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        for r in rows:
            if r["case_id"] in idset:
                w.writerow(r)


@app.local_entrypoint()
def main(action: str = "smoke", run_name: str = "modal_smoke"):
    root = REPO
    art = root / "artifacts" / run_name
    art.mkdir(parents=True, exist_ok=True)

    if action == "smoke":
        # Tiny sandbox: list volume + import package
        sb = modal.Sandbox.create(
            image=ocr_image,
            volumes={VOL_MOUNT: volume},
            timeout=120,
            app=app,
        )
        try:
            p = sb.exec(
                "python",
                "-c",
                "from pathlib import Path; "
                "import mib_solution; "
                f"t=list(Path('{VOL_MOUNT}/train').glob('*.pdf')); "
                f"v=list(Path('{VOL_MOUNT}/validation').glob('*.pdf')); "
                "print({'ok': True, 'version': getattr(mib_solution,'__version__', '?'), "
                "'train_pdfs': len(t), 'validation_pdfs': len(v), "
                f"'sample_train': (Path('{VOL_MOUNT}/train')/'MIB-000001.pdf').exists()}});",
                timeout=60,
            )
            out = p.stdout.read()
            print(out)
            (art / "smoke.json").write_text(out if out.strip().startswith("{") else json.dumps({"raw": out}) + "\n")
        finally:
            try:
                sb.terminate(wait=True)
            except TypeError:
                sb.terminate()
            sb.detach()
        return

    if action == "populate-volume":
        splits_env = os.environ.get("MIB_VOLUME_SPLITS", "validation")
        want = [s.strip() for s in splits_env.split(",") if s.strip()]
        sb = modal.Sandbox.create(
            image=_populate_image,
            volumes={VOL_MOUNT: volume},
            timeout=90 * 60,
            memory=8192,
            cpu=2,
            app=app,
        )
        result: dict = {"ok": False, "splits": want}
        try:
            script = f"""
import hashlib, shutil, subprocess, tempfile
from pathlib import Path
want = {want!r}
url = {DATA_ZIP_URL!r}
expect = {DATA_ZIP_SHA256!r}
mount = Path({VOL_MOUNT!r})
with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    z = td / 'data.zip'
    subprocess.check_call(['curl','-L','--fail','--retry','5','-o',str(z),url])
    h = hashlib.sha256()
    with z.open('rb') as f:
        for chunk in iter(lambda: f.read(1<<20), b''):
            h.update(chunk)
    digest = h.hexdigest()
    assert digest == expect, (digest, expect)
    ext = td / 'extract'
    ext.mkdir()
    subprocess.check_call(['unzip','-q','-o',str(z),'data/*/*','-d',str(ext)])
    counts = {{}}
    for split in want:
        src = ext / 'data' / split
        dst = mount / split
        dst.mkdir(parents=True, exist_ok=True)
        n = 0
        for pdf in src.glob('*.pdf'):
            shutil.copy2(pdf, dst / pdf.name)
            n += 1
        counts[split] = n
    print({{'ok': True, 'sha256': digest, 'counts': counts}})
"""
            p = sb.exec("python", "-c", script, timeout=90 * 60)
            out = p.stdout.read()
            print(out)
            try:
                # last line JSON
                for line in reversed(out.strip().splitlines()):
                    if line.strip().startswith("{"):
                        result = json.loads(line.strip().replace("'", '"'))
                        break
            except json.JSONDecodeError:
                result = {"ok": True, "raw": out[-2000:]}
            volume.commit()
        finally:
            try:
                sb.terminate(wait=True)
            except TypeError:
                sb.terminate()
            sb.detach()
        (art / "populate_volume.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result, indent=2))
        return

    if action == "docker-smoke":
        # One PDF through submission Dockerfile image in a Sandbox
        sb = modal.Sandbox.create(
            image=docker_image,
            volumes={VOL_MOUNT: volume},
            timeout=300,
            app=app,
        )
        try:
            p = sb.exec(
                "python",
                "-c",
                "import sys; sys.path[:0]=['/app/src','/app']; "
                "from pathlib import Path; "
                "from mib_solution.pipeline import predict_pdf; "
                f"pdf=Path('{VOL_MOUNT}/train/MIB-000001.pdf'); "
                "pred=predict_pdf(pdf, use_ocr=True); "
                "print({'ok': True, 'case_id': pred.get('case_id'), "
                "'adjudication': pred.get('adjudication'), 'image': 'dockerfile'});",
                timeout=240,
            )
            out = p.stdout.read()
            print(out)
            (art / "docker_smoke.json").write_text(
                out if "{" in out else json.dumps({"raw": out}) + "\n"
            )
        finally:
            try:
                sb.terminate(wait=True)
            except TypeError:
                sb.terminate()
            sb.detach()
        return

    # ---- bulk actions via sandbox ----
    if action in {
        "score-residual",
        "score-residual-ocr",
        "score-full",
        "score-full-ocr",
        "score-full-docker",
        "predict-validation-ocr",
        "predict-validation-docker",
        "retry-missing-ocr",
    }:
        use_ocr = action in {
            "score-residual-ocr",
            "score-full-ocr",
            "score-full-docker",
            "predict-validation-ocr",
            "predict-validation-docker",
            "retry-missing-ocr",
        }
        # Docker submission image in Sandbox (same Dockerfile as offline ship)
        use_docker_image = action in {
            "score-full-docker",
            "predict-validation-docker",
        } or os.environ.get("MIB_USE_DOCKER_IMAGE", "").strip() in {"1", "true", "yes"}
        if use_docker_image:
            image = docker_image
        elif use_ocr:
            image = ocr_image
        else:
            image = text_image

        if action == "retry-missing-ocr":
            missing_path = art / "missing_ids.json"
            if not missing_path.exists():
                raise SystemExit(f"no {missing_path}")
            case_ids = json.loads(missing_path.read_text())
            input_subdir = os.environ.get("MIB_INPUT_SUBDIR", "validation")
        elif action in {"predict-validation-ocr", "predict-validation-docker"}:
            import csv

            case_ids = [
                row["case_id"].strip()
                for row in csv.DictReader((root / "data" / "validation_manifest.csv").open())
                if row.get("case_id")
            ]
            input_subdir = "validation"
        elif action in {"score-full", "score-full-ocr", "score-full-docker"}:
            case_ids = sorted(p.stem for p in (root / "data" / "train").glob("*.pdf"))
            input_subdir = "train"
        else:
            residual = json.loads((root / "artifacts" / "residual.json").read_text())
            case_ids = residual["case_ids"]
            input_subdir = "train"

        print(
            f"SANDBOX bulk action={action} n={len(case_ids)} "
            f"subdir={input_subdir} ocr={use_ocr} workers={_workers()}"
        )
        sb_meta = _run_sandbox_bulk(
            image=image,
            case_ids=case_ids,
            input_subdir=input_subdir,
            run_name=run_name,
            use_ocr=use_ocr,
        )
        pulled = _pull_run_artifacts(run_name, art)
        extra = {**sb_meta, **pulled}

        if action in {"predict-validation-ocr", "predict-validation-docker"} or (
            action == "retry-missing-ocr" and input_subdir == "validation"
        ):
            # Stage submission package
            sub_user = os.environ.get("MIB_SUBMIT_USER", "musafir42")
            sub_dir = root / "submissions" / sub_user
            sub_dir.mkdir(parents=True, exist_ok=True)
            if (art / "predictions.jsonl").exists():
                (sub_dir / "predictions.jsonl").write_text((art / "predictions.jsonl").read_text())
            n_exp = len(case_ids) if action != "retry-missing-ocr" else None
            if action in {"predict-validation-ocr", "predict-validation-docker"}:
                import csv

                n_exp = sum(1 for _ in csv.DictReader((root / "data" / "validation_manifest.csv").open()))
            n_preds = pulled.get("n_preds", 0)
            n_missing = pulled.get("n_missing", 0)
            meta = {
                "run_name": run_name,
                "action": action,
                "compute": "sandbox",
                "n_preds": n_preds,
                "n_expected": n_exp,
                "n_missing": n_missing,
                "complete": n_missing == 0 and (n_exp is None or n_preds == n_exp),
                "submission_path": str(sub_dir / "predictions.jsonl"),
                "volume": VOLUME_NAME,
                **{k: v for k, v in extra.items() if k not in ("n_preds", "n_missing")},
            }
            (art / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")
            print(json.dumps(meta, indent=2))
            if not meta["complete"] and action in {
                "predict-validation-ocr",
                "predict-validation-docker",
            }:
                raise SystemExit(
                    f"INCOMPLETE val preds {n_preds}/{n_exp}; "
                    f"re-run --action retry-missing-ocr --run-name {run_name}"
                )
            return

        # Train / residual: official evaluate
        if not (art / "predictions.jsonl").exists():
            raise SystemExit(f"no predictions pulled for {run_name}: {pulled}")
        if action.startswith("score-residual"):
            truth = art / "truth.csv"
            residual = json.loads((root / "artifacts" / "residual.json").read_text())
            _filter_truth(root, residual["case_ids"], truth)
        else:
            truth = root / "data" / "train_labels.csv"
        _score_local(root, art, truth, run_name, action, extra)
        return

    raise SystemExit(f"unknown action: {action}")
