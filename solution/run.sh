#!/usr/bin/env bash
set -euo pipefail

input_dir="${1:?usage: run.sh <input_pdf_dir> <output_path>}"
output_path="${2:?usage: run.sh <input_pdf_dir> <output_path>}"

# Challenge runtime: root FS read-only, tmpfs on /tmp only.
export TMPDIR="${TMPDIR:-/tmp}"
export TEMP="${TEMP:-/tmp}"
export TMP="${TMP:-/tmp}"
export HOME="${HOME:-/tmp}"
export XDG_CACHE_HOME="${XDG_CACHE_HOME:-/tmp/.cache}"
mkdir -p "$TMPDIR" "$XDG_CACHE_HOME" 2>/dev/null || true

# Paddle ship defaults (override at docker run if needed)
export MIB_OCR_ENGINE="${MIB_OCR_ENGINE:-paddle}"
export MIB_PADDLE_MODELS="${MIB_PADDLE_MODELS:-/app/models/paddle}"
export MIB_OCR_DPI="${MIB_OCR_DPI:-150}"
export MIB_OCR_MAX_PAGES="${MIB_OCR_MAX_PAGES:-4}"
# CLAHE off: Docker lat40 @2w was 5.71 s/PDF (PASS); CLAHE on was ~6.3 (fail).
export MIB_OCR_CLAHE="${MIB_OCR_CLAHE:-0}"
export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-}"
export FLAGS_use_mkldnn="${FLAGS_use_mkldnn:-0}"

# 4 vCPU scoring box is 8 GiB: 3+ paddle workers OOM; 2 workers OK.
export OMP_THREAD_LIMIT="${OMP_THREAD_LIMIT:-1}"
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-1}"
export OPENBLAS_NUM_THREADS="${OPENBLAS_NUM_THREADS:-1}"
export MKL_NUM_THREADS="${MKL_NUM_THREADS:-1}"
export MIB_WORKERS="${MIB_WORKERS:-2}"

if command -v mib-solution >/dev/null 2>&1; then
  mib-solution "$input_dir" "$output_path"
else
  export PYTHONPATH="/app/src:${PYTHONPATH:-}"
  python3 -m mib_solution.cli "$input_dir" "$output_path"
fi
