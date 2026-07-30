#!/usr/bin/env bash
set -euo pipefail

input_dir="${1:?usage: run.sh <input_pdf_dir> <output_path>}"
output_path="${2:?usage: run.sh <input_pdf_dir> <output_path>}"

# Prefer installed package; fall back to src layout inside the image.
if command -v mib-solution >/dev/null 2>&1; then
  mib-solution "$input_dir" "$output_path"
else
  export PYTHONPATH="/app/src:${PYTHONPATH:-}"
  python3 -m mib_solution.cli "$input_dir" "$output_path"
fi
