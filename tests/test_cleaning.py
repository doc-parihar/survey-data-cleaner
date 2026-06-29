"""Tests for survey_cleaner.cleaning."""

from __future__ import annotations

import pandas as pd

from survey_cleaner.cleaning import (
    DEFAULT_MISSING_TOKENS,
    coerce_boolean,
    coerce_column,
    coerce_datetime,
    coerce_number,
    split_multiselect,
    standardize_missing,
)


def test_standardize_missing_all_default_tokens():
    raw = pd.Series(["", "NA", "N/A", "nil", "None", "null", "-", "--", " 42 "])
    cleaned, n = standardize_missing(raw, DEFAULT_MISSING_TOKENS)
    assert n == 8
    # Only the real value survives, trimmed.
    assert cleaned.dropna().tolist() == ["42"]


def test_standardize_missing_is_case_insensitive_and_trims():
    raw = pd.Series(["  na  ", "Na", "nA", "yes"])
    cleaned, n = standardize_missing(raw)
    assert n == 3
    assert cleaned.iloc[3] == "yes"


def test_coerce_number_integer_downcast_and_failures():
    raw = pd.Series(["1", "2", "bad", None])
    out, n_failed = coerce_number(raw)
    assert n_failed == 1
    assert str(out.dtype) == "Int64"
    assert out.iloc[0] == 1 and out.iloc[1] == 2
    assert pd.isna(out.iloc[2])


def test_coerce_number_keeps_float():
    out, _ = coerce_number(pd.Series(["1.5", "2.25"]))
    assert str(out.dtype) == "float64"


def test_coerce_boolean():
    out, n_failed = coerce_boolean(pd.Series(["Yes", "no", "TRUE", "maybe", None]))
    assert n_failed == 1
    assert out.iloc[0] is True or out.iloc[0] == True  # noqa: E712
    assert out.iloc[1] == False  # noqa: E712
    assert pd.isna(out.iloc[3])


def test_coerce_datetime_date_only():
    out, n_failed = coerce_datetime(
        pd.Series(["2024-01-02", "03/15/2024", "not a date"]),
        dayfirst=False,
        with_time=False,
    )
    assert n_failed == 1
    assert out.iloc[0] == "2024-01-02"
    assert out.iloc[1] == "2024-03-15"


def test_coerce_column_dispatch_passthrough_for_text():
    raw = pd.Series(["alpha", "beta"])
    out, n_failed = coerce_column(raw, "text")
    assert n_failed == 0
    assert out.tolist() == ["alpha", "beta"]


def test_split_multiselect_creates_indicator_columns():
    raw = pd.Series(["Fever, Cough", "Cough", "Fever, Headache", None])
    indicators, children = split_multiselect(raw, "symptoms", ",", existing_names=["symptoms"])

    # Options discovered in first-appearance order.
    assert [opt for opt, _ in children] == ["Fever", "Cough", "Headache"]
    col_names = [name for _, name in children]
    assert col_names == ["symptoms__fever", "symptoms__cough", "symptoms__headache"]

    fever = indicators["symptoms__fever"]
    assert fever.iloc[0] == 1
    assert fever.iloc[1] == 0
    assert fever.iloc[2] == 1
    assert pd.isna(fever.iloc[3])  # missing parent -> missing indicator
    assert str(fever.dtype) == "Int64"


def test_split_multiselect_avoids_name_collisions():
    raw = pd.Series(["A, B"])
    indicators, children = split_multiselect(
        raw, "q", ",", existing_names=["q", "q__a"]
    )
    names = [name for _, name in children]
    assert "q__a_2" in names  # collided with the pre-existing q__a
