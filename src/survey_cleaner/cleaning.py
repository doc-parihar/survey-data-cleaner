"""Deterministic cleaning transforms: missing values, coercion, multi-select.

These are pure building blocks. The per-column orchestration that ties them to
a :class:`~survey_cleaner.schema.Schema` lives in
:mod:`survey_cleaner.pipeline`.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from survey_cleaner.schema import to_snake_case
from survey_cleaner.types_infer import (
    BOOL_FALSE,
    BOOL_TRUE,
    _to_datetime,
    parse_number,
)

# Compared case-insensitively against each stripped cell. Stored lowercase.
DEFAULT_MISSING_TOKENS = {"", "na", "n/a", "nil", "none", "null", "-", "--"}


def standardize_missing(
    series: pd.Series, tokens=DEFAULT_MISSING_TOKENS
) -> Tuple[pd.Series, int]:
    """Trim whitespace and convert recognised missing tokens to ``NaN``.

    Returns the cleaned series and the number of cells converted to missing.
    """
    filled = series.where(series.notna(), "")
    stripped = filled.astype(str).str.strip()
    mask = stripped.str.lower().isin(tokens)
    cleaned = stripped.where(~mask, np.nan)
    return cleaned, int(mask.sum())


def coerce_boolean(series: pd.Series) -> Tuple[pd.Series, int]:
    def convert(value):
        if pd.isna(value):
            return pd.NA
        key = str(value).strip().lower()
        if key in BOOL_TRUE:
            return True
        if key in BOOL_FALSE:
            return False
        return pd.NA

    out = series.map(convert)
    n_failed = int((series.notna() & out.isna()).sum())
    return out.astype("boolean"), n_failed


def coerce_number(series: pd.Series) -> Tuple[pd.Series, int]:
    def convert(value):
        if pd.isna(value):
            return np.nan
        parsed = parse_number(str(value))
        return parsed[0] if parsed is not None else np.nan

    out = series.map(convert).astype("float64")
    n_failed = int((series.notna() & out.isna()).sum())
    non_null = out.dropna()
    if not non_null.empty and bool((non_null == non_null.round()).all()):
        out = out.astype("Int64")
    return out, n_failed


def coerce_datetime(
    series: pd.Series, dayfirst: bool = True, with_time: bool = False
) -> Tuple[pd.Series, int]:
    parsed = _to_datetime(series, dayfirst)
    n_failed = int((series.notna() & parsed.isna()).sum())
    fmt = "%Y-%m-%d %H:%M:%S" if with_time else "%Y-%m-%d"
    formatted = parsed.dt.strftime(fmt)
    return formatted, n_failed


def coerce_column(
    series: pd.Series,
    inferred_type: str,
    dayfirst: bool = True,
) -> Tuple[pd.Series, int]:
    """Coerce a cleaned series to its inferred type. Returns ``(series, n_failed)``.

    Values that fail to parse become ``NaN`` and are counted. ``text``,
    ``categorical`` and ``multiselect`` are left as cleaned strings.
    """
    if inferred_type == "boolean":
        return coerce_boolean(series)
    if inferred_type == "number":
        return coerce_number(series)
    if inferred_type in ("date", "datetime"):
        return coerce_datetime(series, dayfirst, with_time=(inferred_type == "datetime"))
    return series, 0


def _indicator(value, option: str, delimiter: str):
    if pd.isna(value):
        return pd.NA
    parts = [p.strip() for p in str(value).split(delimiter)]
    return 1 if option in parts else 0


def split_multiselect(
    series: pd.Series,
    parent_name: str,
    delimiter: str,
    existing_names: Optional[List[str]] = None,
) -> Tuple[Dict[str, pd.Series], List[Tuple[str, str]]]:
    """Build 0/1 indicator columns for a multi-select column.

    Options are discovered in order of first appearance (deterministic). The
    parent column is left untouched by the caller. Returns a dict of
    ``new_column_name -> indicator series`` and a list of
    ``(option_label, new_column_name)`` for the data dictionary.
    """
    used = set(existing_names or [])
    options: List[str] = []
    seen = set()
    for value in series.dropna():
        for part in str(value).split(delimiter):
            option = part.strip()
            if option and option not in seen:
                seen.add(option)
                options.append(option)

    indicators: Dict[str, pd.Series] = {}
    children: List[Tuple[str, str]] = []
    for option in options:
        base = f"{parent_name}__{to_snake_case(option) or 'option'}"
        name = base
        suffix = 2
        while name in used:
            name = f"{base}_{suffix}"
            suffix += 1
        used.add(name)
        indicators[name] = series.map(
            lambda v, o=option: _indicator(v, o, delimiter)
        ).astype("Int64")
        children.append((option, name))
    return indicators, children
