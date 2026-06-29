"""Tests for survey_cleaner.schema."""

from __future__ import annotations

import numpy as np
import pandas as pd

from survey_cleaner.schema import (
    Column,
    build_schema,
    make_cleaned_names,
    populate_stats,
    to_snake_case,
)


def test_snake_case_basic():
    assert to_snake_case("What is your age?") == "what_is_your_age"
    assert to_snake_case("  Email Address  ") == "email_address"
    assert to_snake_case("Q1: Consent (yes/no)") == "q1_consent_yes_no"


def test_snake_case_collapses_punctuation_and_spaces():
    assert to_snake_case("a -- b/c") == "a_b_c"
    assert to_snake_case("already_snake") == "already_snake"
    assert to_snake_case("double  space") == "double_space"


def test_snake_case_leading_digit_is_prefixed():
    assert to_snake_case("1st dose date") == "q_1st_dose_date"
    assert to_snake_case("2024") == "q_2024"


def test_snake_case_blank_returns_empty():
    assert to_snake_case("") == ""
    assert to_snake_case("   ") == ""
    assert to_snake_case("???") == ""


def test_make_cleaned_names_handles_blanks_and_collisions():
    originals = ["Age", "Age", "", "age", "???"]
    names = make_cleaned_names(originals)
    assert names == ["age", "age_2", "column_3", "age_3", "column_5"]
    # All names are unique.
    assert len(set(names)) == len(names)


def test_build_schema_assigns_cleaned_names_in_order():
    schema = build_schema(["Timestamp", "What is your age?"], profile="google_forms")
    assert schema.profile == "google_forms"
    assert [c.cleaned_name for c in schema.columns] == ["timestamp", "what_is_your_age"]
    assert schema.by_original("Timestamp").cleaned_name == "timestamp"
    assert schema.by_cleaned("what_is_your_age").original_name == "What is your age?"


def test_active_excludes_dropped_columns():
    schema = build_schema(["a", "b"])
    schema.columns[0].dropped = True
    assert [c.cleaned_name for c in schema.active()] == ["b"]


def test_populate_stats():
    col = Column(original_name="Age", cleaned_name="age")
    series = pd.Series([34.0, np.nan, 41.0, 41.0])
    populate_stats(col, series)
    assert col.n_missing == 1
    assert col.pct_missing == 0.25
    assert col.n_unique == 2
    assert col.example_value == "34.0"
