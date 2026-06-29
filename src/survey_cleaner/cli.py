"""Command-line interface for survey-data-cleaner.

Examples::

    survey-clean input.xlsx --out outputs/
    survey-clean responses.csv --profile google_forms --split-multiselect
    survey-clean responses.xlsx --sheet "Form Responses 1" --report-only
    survey-clean responses.csv --rules rules.yaml
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from typing import List, Optional

from survey_cleaner import __version__
from survey_cleaner.pipeline import Config, ProcessResult, process
from survey_cleaner.reports import write_outputs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="survey-clean",
        description=(
            "Clean a messy survey CSV/XLSX export into an analysis-ready table "
            "with a reproducible cleaning report."
        ),
    )
    parser.add_argument("input", help="Path to the input .csv or .xlsx file.")
    parser.add_argument(
        "--out",
        default="outputs",
        help="Output directory for the cleaned data and reports (default: outputs).",
    )
    parser.add_argument(
        "--profile",
        choices=["auto", "google_forms", "generic"],
        default="auto",
        help="Survey profile (default: auto-detect).",
    )
    parser.add_argument("--sheet", default=None, help="XLSX sheet name to load.")
    parser.add_argument("--encoding", default=None, help="Force a CSV text encoding.")
    parser.add_argument(
        "--split-multiselect",
        action="store_true",
        help="Split detected multi-select columns into 0/1 indicator columns.",
    )
    parser.add_argument(
        "--xlsx",
        action="store_true",
        dest="write_xlsx",
        help="Also write cleaned.xlsx alongside cleaned.csv.",
    )
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="Write reports + data dictionary only (no cleaned data files).",
    )
    parser.add_argument(
        "--rules",
        default=None,
        dest="rules_path",
        help="Path to a rules.yaml file of overrides.",
    )
    parser.add_argument(
        "--drop-duplicates",
        action="store_true",
        help="Drop fully-duplicate rows from the cleaned table.",
    )
    parser.add_argument(
        "--drop-empty-cols",
        action="store_true",
        help="Drop mostly-empty columns from the cleaned table.",
    )
    parser.add_argument(
        "--missing-threshold",
        type=float,
        default=0.9,
        help="Missing fraction at/above which a column is 'mostly empty' (default: 0.9).",
    )
    parser.add_argument(
        "--no-dayfirst",
        action="store_false",
        dest="dayfirst",
        help="Interpret ambiguous dates as month-first (default is day-first).",
    )
    parser.set_defaults(dayfirst=True)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing files in the output directory.",
    )
    parser.add_argument(
        "--verbose", action="store_true", help="Print extra warnings to stderr."
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"survey-data-cleaner {__version__}",
    )
    return parser


def _config_from_args(args: argparse.Namespace) -> Config:
    return Config(
        profile=args.profile,
        sheet=args.sheet,
        encoding=args.encoding,
        split_multiselect=args.split_multiselect,
        dayfirst=args.dayfirst,
        drop_duplicates=args.drop_duplicates,
        drop_empty_cols=args.drop_empty_cols,
        missing_threshold=args.missing_threshold,
        rules_path=args.rules_path,
        write_xlsx=args.write_xlsx,
        report_only=args.report_only,
    )


def _print_summary(result: ProcessResult, written, verbose: bool = False) -> None:
    v = result.validation
    print(f"survey-clean: cleaned '{result.load_result.source_path}'")
    print(f"  profile : {result.profile.name}")
    print(f"  rows    : {result.n_rows_in} in -> {result.n_rows_out} out")
    print(f"  columns : {result.cleaned_df.shape[1]} in cleaned table")

    types = Counter(
        c.inferred_type for c in result.schema.columns if not c.dropped
    )
    print("  types   : " + ", ".join(f"{k}={n}" for k, n in sorted(types.items())))

    if v.n_duplicate_rows:
        if result.dropped_duplicate_rows:
            print(f"  duplicates: {v.n_duplicate_rows} found, dropped")
        else:
            print(
                f"  duplicates: {v.n_duplicate_rows} found "
                "(use --drop-duplicates to remove)"
            )
    if v.empty_columns:
        print(f"  empty cols: {[n for n, _ in v.empty_columns]}")

    print("  outputs :")
    for path in written:
        print(f"    - {path}")

    if verbose:
        for warning in result.warnings:
            print(f"  warning : {warning}", file=sys.stderr)


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    config = _config_from_args(args)

    try:
        result = process(args.input, config)
        written = write_outputs(result, args.out, force=args.force)
    except FileExistsError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    _print_summary(result, written, verbose=args.verbose)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
