"""Non-destructive data-quality checks run on the cleaned table.

These functions only *detect and report*; nothing is dropped here. The CLI may
optionally act on the findings when the user passes ``--drop-*`` flags.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import pandas as pd

# A column is "mostly empty" when at least this fraction of cells are missing.
DEFAULT_EMPTY_THRESHOLD = 0.9


@dataclass
class Validation:
    n_rows: int = 0
    n_duplicate_rows: int = 0
    duplicate_row_indices: List[int] = field(default_factory=list)
    empty_columns: List[Tuple[str, float]] = field(default_factory=list)
    constant_columns: List[str] = field(default_factory=list)


def find_duplicate_rows(
    df: pd.DataFrame, ignore: Optional[List[str]] = None
) -> Tuple[int, List[int]]:
    """Count fully-duplicated rows (keep-first) and return their row positions.

    ``ignore`` columns are excluded from the comparison (e.g. a timestamp that
    differs even when the answers are identical).
    """
    ignore = set(ignore or [])
    subset = [c for c in df.columns if c not in ignore]
    if not subset or df.empty:
        return 0, []
    mask = df.duplicated(subset=subset, keep="first")
    indices = [int(i) for i in df.index[mask].tolist()]
    return int(mask.sum()), indices


def find_empty_columns(
    df: pd.DataFrame, threshold: float = DEFAULT_EMPTY_THRESHOLD
) -> List[Tuple[str, float]]:
    """Return ``(column, missing_fraction)`` for columns at/over the threshold."""
    n = len(df)
    if n == 0:
        return []
    out: List[Tuple[str, float]] = []
    for col in df.columns:
        frac = float(df[col].isna().mean())
        if frac >= threshold:
            out.append((col, round(frac, 4)))
    return out


def find_constant_columns(df: pd.DataFrame) -> List[str]:
    """Columns with a single distinct non-missing value (informational)."""
    out: List[str] = []
    for col in df.columns:
        if int(df[col].nunique(dropna=True)) == 1:
            out.append(col)
    return out


def validate(
    df: pd.DataFrame,
    ignore_duplicates_on: Optional[List[str]] = None,
    empty_threshold: float = DEFAULT_EMPTY_THRESHOLD,
) -> Validation:
    """Run all checks and return a :class:`Validation` summary."""
    n_dupes, dupe_idx = find_duplicate_rows(df, ignore=ignore_duplicates_on)
    return Validation(
        n_rows=len(df),
        n_duplicate_rows=n_dupes,
        duplicate_row_indices=dupe_idx,
        empty_columns=find_empty_columns(df, empty_threshold),
        constant_columns=find_constant_columns(df),
    )
