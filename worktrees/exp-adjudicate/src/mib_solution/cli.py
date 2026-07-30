"""CLI entrypoint: mib-solution <input_pdf_dir> <output_predictions_path>."""

from __future__ import annotations

import sys

from mib_solution.pipeline import run


def main(argv: list[str] | None = None) -> None:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 2:
        raise SystemExit("usage: mib-solution <input_pdf_dir> <output_predictions_path>")
    n = run(args[0], args[1])
    print(f"wrote {n} predictions to {args[1]}", file=sys.stderr)


if __name__ == "__main__":
    main()
