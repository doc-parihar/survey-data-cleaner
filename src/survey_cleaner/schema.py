"""Column naming and the schema/data-dictionary model.

The schema records, for each original column, its safe cleaned name, the
inferred (or forced) type, simple statistics, and any per-column notes. It is
the backbone of both the cleaning step and the generated data dictionary.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import pandas as pd

# Runs of characters that are not word characters (letters/digits/underscore,
# unicode-aware) collapse to a single underscore.
_NON_WORD = re.compile(r"[^\w]+", re.UNICODE)
_MULTI_UNDERSCORE = re.compile(r"_+")


def to_snake_case(name: str) -> str:
    """Normalise a single header into a safe snake_case token.

    Returns an empty string when nothing usable remains (e.g. a blank header);
    callers substitute a positional ``column_<n>`` name in that case.
    """
    s = (name or "").strip().lower()
    s = _NON_WORD.sub("_", s)
    s = _MULTI_UNDERSCORE.sub("_", s)
    s = s.strip("_")
    if not s:
        return ""
    if s[0].isdigit():
        s = "q_" + s
    return s


def make_cleaned_names(originals: List[str]) -> List[str]:
    """Map original headers to unique snake_case names, preserving order.

    Blank/unusable headers become ``column_<position>``; collisions are
    disambiguated deterministically with ``_2``, ``_3``, ... suffixes.
    """
    used = set()
    out: List[str] = []
    for i, raw in enumerate(originals, start=1):
        base = to_snake_case(str(raw)) or f"column_{i}"
        name = base
        suffix = 2
        while name in used:
            name = f"{base}_{suffix}"
            suffix += 1
        used.add(name)
        out.append(name)
    return out


@dataclass
class Column:
    """One column's identity, type, and statistics."""

    original_name: str
    cleaned_name: str
    inferred_type: str = "text"
    type_meta: dict = field(default_factory=dict)
    forced_type: bool = False  # True when a rules file fixed the type
    is_multiselect: bool = False
    force_split: bool = False  # True when rules require splitting this column
    dropped: bool = False  # True when a rules file dropped the column

    # Statistics (filled in after cleaning).
    n_missing: int = 0
    pct_missing: float = 0.0
    n_unique: int = 0
    example_value: str = ""

    # Cleaning bookkeeping.
    n_missing_standardised: int = 0
    n_coercion_failed: int = 0
    # For multi-select parents: list of (option_label, indicator_column_name).
    split_children: List[Tuple[str, str]] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def add_note(self, note: str) -> None:
        if note and note not in self.notes:
            self.notes.append(note)


@dataclass
class Schema:
    """Ordered columns plus the detected profile and table-level warnings."""

    columns: List[Column]
    profile: str = "generic"
    warnings: List[str] = field(default_factory=list)

    def active(self) -> List[Column]:
        """Columns that survive into the cleaned table (not dropped)."""
        return [c for c in self.columns if not c.dropped]

    def by_cleaned(self, cleaned_name: str) -> Optional[Column]:
        for c in self.columns:
            if c.cleaned_name == cleaned_name:
                return c
        return None

    def by_original(self, original_name: str) -> Optional[Column]:
        for c in self.columns:
            if c.original_name == original_name:
                return c
        return None


def build_schema(originals: List[str], profile: str = "generic") -> Schema:
    """Create a schema with cleaned names assigned (types decided later)."""
    originals = [str(o) for o in originals]
    cleaned = make_cleaned_names(originals)
    columns = [
        Column(original_name=o, cleaned_name=c)
        for o, c in zip(originals, cleaned)
    ]
    return Schema(columns=columns, profile=profile)


def populate_stats(column: Column, series: pd.Series) -> None:
    """Fill in missing/unique/example statistics from a cleaned series."""
    n = len(series)
    n_missing = int(series.isna().sum())
    column.n_missing = n_missing
    column.pct_missing = round(n_missing / n, 4) if n else 0.0
    column.n_unique = int(series.nunique(dropna=True))
    non_null = series.dropna()
    column.example_value = "" if non_null.empty else str(non_null.iloc[0])
