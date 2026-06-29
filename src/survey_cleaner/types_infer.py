"""Deterministic, threshold-based column type inference.

Given a *cleaned* series (missing values already converted to NaN), guess one
of: ``boolean``, ``number``, ``date``, ``datetime``, ``multiselect``,
``categorical`` or ``text``. Inference only ever decides the *type*; the actual
value conversion happens in :mod:`survey_cleaner.cleaning`.

The thresholds below are module constants so they are easy to find, document,
and report in the cleaning log.
"""

from __future__ import annotations

import re
import warnings
from typing import Dict, Optional, Tuple

import pandas as pd

# Fraction of non-missing values that must match a type for it to win.
TYPE_THRESHOLD = 0.9

# A column is categorical when its distinct count is at most this bound and it
# is not perfectly unique (which would make it an identifier / free text).
CATEGORICAL_MAX_UNIQUE = 20
CATEGORICAL_MAX_FRACTION = 0.05

# Multi-select heuristics: the delimiter must appear in at least this fraction
# of cells, and the resulting option vocabulary must stay small.
MULTISELECT_MIN_DELIM_FRACTION = 0.30
MULTISELECT_MAX_OPTIONS = 30
MULTISELECT_DELIMITERS = (",", ";")

BOOL_TRUE = {"true", "yes", "y", "t", "1"}
BOOL_FALSE = {"false", "no", "n", "f", "0"}
BOOL_VOCAB = BOOL_TRUE | BOOL_FALSE

_CURRENCY = "$€£₹¥"


def _clean_non_null(series: pd.Series) -> pd.Series:
    s = series.dropna().astype(str).str.strip()
    return s[s != ""]


def parse_number(value: str) -> Optional[Tuple[float, bool]]:
    """Parse a single value into ``(number, is_percent)`` or ``None``.

    Strips a single leading currency symbol, thousands separators, surrounding
    whitespace and a trailing percent sign. Percent values keep their face
    value (``"45%"`` -> ``45.0``); the percent flag is recorded, not applied.
    """
    s = value.strip()
    if not s:
        return None
    is_percent = s.endswith("%")
    if is_percent:
        s = s[:-1].strip()
    if s and s[0] in _CURRENCY:
        s = s[1:].strip()
    s = s.replace(",", "")
    if s in ("", "+", "-", "."):
        return None
    try:
        return float(s), is_percent
    except ValueError:
        return None


def _fraction_boolean(values: pd.Series) -> float:
    lowered = values.str.lower()
    return float(lowered.isin(BOOL_VOCAB).mean())


def _fraction_number(values: pd.Series) -> Tuple[float, bool, bool]:
    parsed = [parse_number(v) for v in values]
    ok = [p for p in parsed if p is not None]
    if not values.size:
        return 0.0, False, False
    fraction = len(ok) / len(values)
    all_integer = bool(ok) and all(num.is_integer() for num, _ in ok)
    any_percent = any(is_pct for _, is_pct in ok)
    return fraction, all_integer, any_percent


def _fraction_datetime(values: pd.Series, dayfirst: bool) -> Tuple[float, bool]:
    parsed = _to_datetime(values, dayfirst)
    valid = parsed.dropna()
    if not values.size:
        return 0.0, False
    fraction = len(valid) / len(values)
    has_time = bool(
        valid.size
        and (
            (valid.dt.hour != 0)
            | (valid.dt.minute != 0)
            | (valid.dt.second != 0)
        ).any()
    )
    return fraction, has_time


def _to_datetime(values: pd.Series, dayfirst: bool) -> pd.Series:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            return pd.to_datetime(
                values, errors="coerce", dayfirst=dayfirst, format="mixed"
            )
        except (ValueError, TypeError):
            return pd.to_datetime(values, errors="coerce", dayfirst=dayfirst)


def detect_multiselect(values: pd.Series) -> Optional[Tuple[str, int]]:
    """Return ``(delimiter, n_options)`` if the column looks multi-select."""
    for delim in MULTISELECT_DELIMITERS:
        frac_with = float(values.str.contains(re.escape(delim)).mean())
        if frac_with < MULTISELECT_MIN_DELIM_FRACTION:
            continue
        options = set()
        for v in values:
            for part in v.split(delim):
                p = part.strip()
                if p:
                    options.add(p)
        if 0 < len(options) <= MULTISELECT_MAX_OPTIONS:
            return delim, len(options)
    return None


def infer_type(series: pd.Series, dayfirst: bool = True) -> Tuple[str, Dict]:
    """Infer a column type and return ``(type_name, meta)``.

    Evaluation order (first to clear the threshold wins): boolean, number,
    date/datetime, multi-select, categorical, then text as the fallback.
    """
    values = _clean_non_null(series)
    n = len(values)
    if n == 0:
        return "text", {"reason": "all values missing"}

    if _fraction_boolean(values) >= TYPE_THRESHOLD:
        return "boolean", {}

    frac_num, all_integer, any_percent = _fraction_number(values)
    if frac_num >= TYPE_THRESHOLD:
        return "number", {"integer": all_integer, "percent": any_percent}

    frac_dt, has_time = _fraction_datetime(values, dayfirst)
    if frac_dt >= TYPE_THRESHOLD:
        return ("datetime" if has_time else "date"), {}

    multiselect = detect_multiselect(values)
    if multiselect is not None:
        delim, n_options = multiselect
        return "multiselect", {"delimiter": delim, "n_options": n_options}

    n_unique = int(values.nunique())
    cat_bound = max(CATEGORICAL_MAX_UNIQUE, int(CATEGORICAL_MAX_FRACTION * n))
    if n_unique <= cat_bound and n_unique < n:
        return "categorical", {"n_unique": n_unique}

    return "text", {}
