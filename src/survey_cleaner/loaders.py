"""Load a single rectangular survey table from CSV or XLSX.

Everything is read as strings (``dtype=str``, ``keep_default_na=False``) so that
missing-value handling and type coercion happen later under our explicit,
reproducible control rather than pandas' implicit parsing.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import pandas as pd

# Tried in order until one decodes the file without error. ``latin-1`` always
# succeeds (it maps every byte), so it is the guaranteed final fallback.
CSV_ENCODINGS = ("utf-8-sig", "utf-8", "cp1252", "latin-1")

# Delimiters the sniffer is allowed to choose between.
CANDIDATE_DELIMITERS = ",;\t|"

# Bytes of the file used for encoding/delimiter sniffing.
_SNIFF_BYTES = 65536


@dataclass
class LoadResult:
    """The raw loaded table plus how it was loaded."""

    df: pd.DataFrame
    source_path: str
    kind: str  # "csv" or "xlsx"
    sheet: Optional[str] = None
    encoding: Optional[str] = None
    delimiter: Optional[str] = None
    available_sheets: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def n_rows(self) -> int:
        return int(self.df.shape[0])

    @property
    def n_cols(self) -> int:
        return int(self.df.shape[1])


def load_table(
    path,
    sheet: Optional[str] = None,
    encoding: Optional[str] = None,
) -> LoadResult:
    """Load ``path`` (``.csv`` or ``.xlsx``) into a string ``DataFrame``.

    Raises ``FileNotFoundError`` if the file does not exist and ``ValueError``
    for unsupported extensions or a missing sheet name.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Input file not found: {p}")

    suffix = p.suffix.lower()
    if suffix == ".csv":
        return _load_csv(p, encoding)
    if suffix in (".xlsx", ".xlsm"):
        return _load_xlsx(p, sheet)
    raise ValueError(
        f"Unsupported file type '{suffix}'. Supported: .csv, .xlsx"
    )


def _detect_encoding(path: Path, candidates=CSV_ENCODINGS) -> str:
    raw = path.read_bytes()
    sample = raw[:_SNIFF_BYTES]
    for enc in candidates:
        try:
            sample.decode(enc)
            return enc
        except UnicodeDecodeError:
            continue
    return "latin-1"


def _sniff_delimiter(sample_text: str) -> str:
    try:
        dialect = csv.Sniffer().sniff(sample_text, delimiters=CANDIDATE_DELIMITERS)
        return dialect.delimiter
    except csv.Error:
        return ","


def _load_csv(path: Path, encoding: Optional[str]) -> LoadResult:
    enc = encoding or _detect_encoding(path)
    with path.open("r", encoding=enc, newline="") as fh:
        sample_text = fh.read(_SNIFF_BYTES)
    delimiter = _sniff_delimiter(sample_text)

    df = pd.read_csv(
        path,
        dtype=str,
        keep_default_na=False,
        sep=delimiter,
        encoding=enc,
    )
    df = _normalise_strings(df)
    return LoadResult(
        df=df,
        source_path=str(path),
        kind="csv",
        encoding=enc,
        delimiter=delimiter,
    )


def _load_xlsx(path: Path, sheet: Optional[str]) -> LoadResult:
    warnings: List[str] = []
    excel = pd.ExcelFile(path, engine="openpyxl")
    available = list(excel.sheet_names)

    if sheet is None:
        chosen = available[0]
        if len(available) > 1:
            warnings.append(
                f"Workbook has {len(available)} sheets; using the first one "
                f"('{chosen}'). Pass --sheet to choose another. "
                f"Available: {available}"
            )
    else:
        if sheet not in available:
            raise ValueError(
                f"Sheet '{sheet}' not found. Available sheets: {available}"
            )
        chosen = sheet

    df = excel.parse(sheet_name=chosen, dtype=str, keep_default_na=False)
    df = _normalise_strings(df)
    return LoadResult(
        df=df,
        source_path=str(path),
        kind="xlsx",
        sheet=chosen,
        available_sheets=available,
        warnings=warnings,
    )


def _normalise_strings(df: pd.DataFrame) -> pd.DataFrame:
    """Make every cell a plain ``str`` and every header a ``str``.

    Empty XLSX cells can arrive as ``NaN`` even with ``keep_default_na=False``;
    we render them as empty strings here so the missing-value standardisation
    step is the single place that decides what counts as missing.
    """
    df = df.copy()
    df.columns = [str(c) for c in df.columns]
    for col in df.columns:
        df[col] = df[col].astype("object").where(df[col].notna(), "").map(str)
    return df
