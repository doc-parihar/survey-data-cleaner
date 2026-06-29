"""Tests for survey_cleaner.validators."""

from __future__ import annotations

import numpy as np
import pandas as pd

from survey_cleaner.validators import (
    find_constant_columns,
    find_duplicate_rows,
    find_empty_columns,
    validate,
)


def test_find_duplicate_rows_full_row():
    df = pd.DataFrame(
        {
            "a": [1, 2, 1, 3],
            "b": ["x", "y", "x", "z"],
        }
    )
    n, idx = find_duplicate_rows(df)
    assert n == 1
    assert idx == [2]  # row 2 duplicates row 0 (keep-first)


def test_find_duplicate_rows_ignoring_a_column():
    df = pd.DataFrame(
        {
            "timestamp": ["t1", "t2", "t3"],
            "answer": ["yes", "no", "yes"],
        }
    )
    # All distinct as full rows.
    assert find_duplicate_rows(df)[0] == 0
    # Ignoring the timestamp, rows 0 and 2 are duplicate answers.
    n, idx = find_duplicate_rows(df, ignore=["timestamp"])
    assert n == 1
    assert idx == [2]


def test_find_empty_columns():
    df = pd.DataFrame(
        {
            "full": [1, 2, 3, 4],
            "mostly_empty": [np.nan, np.nan, np.nan, "x"],
            "all_empty": [np.nan, np.nan, np.nan, np.nan],
        }
    )
    empty = dict(find_empty_columns(df, threshold=0.9))
    assert "full" not in empty
    # 0.75 missing is below the 0.9 threshold, so it is not flagged.
    assert "mostly_empty" not in empty
    assert "all_empty" in empty
    assert empty["all_empty"] == 1.0


def test_find_empty_columns_threshold_boundary():
    df = pd.DataFrame({"c": [np.nan, np.nan, np.nan, "x"]})  # 0.75 missing
    assert find_empty_columns(df, threshold=0.75) == [("c", 0.75)]
    assert find_empty_columns(df, threshold=0.8) == []


def test_find_constant_columns():
    df = pd.DataFrame(
        {
            "const": ["x", "x", "x"],
            "varies": ["x", "y", "x"],
            "const_with_na": ["a", np.nan, "a"],
        }
    )
    constants = find_constant_columns(df)
    assert "const" in constants
    assert "const_with_na" in constants
    assert "varies" not in constants


def test_validate_aggregates_everything():
    df = pd.DataFrame(
        {
            "a": [1, 1, 1],
            "b": ["p", "p", "p"],
            "empty": [np.nan, np.nan, np.nan],
        }
    )
    result = validate(df, empty_threshold=0.9)
    assert result.n_rows == 3
    assert result.n_duplicate_rows == 2
    assert ("empty", 1.0) in result.empty_columns
    assert "a" in result.constant_columns
