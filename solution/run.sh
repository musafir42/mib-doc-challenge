#!/usr/bin/env bash
set -euo pipefail

input_dir="${1:?usage: run.sh <input_pdf_dir> <output_path>}"
output_path="${2:?usage: run.sh <input_pdf_dir> <output_path>}"

# Challenge runtime mounts root FS read-only with tmpfs on /tmp only.
# Force all temp/OCR/pdf2image scratch into /tmp (not /app or $HOME).
export TMPDIR="${TMPDIR:-/tmp}"
export TEMP="${TEMP:-/tmp}"
export TMP="${TMP:-/tmp}"
export HOME="${HOME:-/tmp}"
export XDG_CACHE_HOME="${XDG_CACHE_HOME:-/tmp/.cache}"
export TESSDATA_PREFIX="${TESSDATA_PREFIX:-/usr/share/tesseract-ocr/5/tessdata}"
mkdir -p "$TMPDIR" "$XDG_CACHE_HOME" 2>/dev/null || true

# Scoring gives 4 vCPU. One process per vCPU; one OpenMP/tesseract thread each.
# Without OMP=1, multi-thread tesseract thrash makes OCR wall-time explode.
export OMP_THREAD_LIMIT="${OMP_THREAD_LIMIT:-1}"
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-1}"
export OPENBLAS_NUM_THREADS="${OPENBLAS_NUM_THREADS:-1}"
export MKL_NUM_THREADS="${MKL_NUM_THREADS:-1}"
export MIB_WORKERS="${MIB_WORKERS:-4}"

# Prefer installed package; fall back to src layout inside the image.
if command -v mib-solution >/dev/null 2>&1; then
  mib-solution "$input_dir" "$output_path"
else
  export PYTHONPATH="/app/src:${PYTHONPATH:-}"
  python3 -m mib_solution.cli "$input_dir" "$output_path"
fi
