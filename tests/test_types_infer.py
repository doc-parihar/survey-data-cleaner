"""Tests for survey_cleaner.types_infer."""

from __future__ import annotations

import numpy as np
import pandas as pd

from survey_cleaner.types_infer import (
    detect_multiselect,
    infer_type,
    parse_number,
)


def s(values):
    return pd.Series(values, dtype="object")


def test_parse_number_variants():
    assert parse_number("1,234") == (1234.0, False)
    assert parse_number("  42 ") == (42.0, False)
    assert parse_number("$19.99") == (19.99, False)
    assert parse_number("45%") == (45.0, True)
    assert parse_number("₹500") == (500.0, False)
    assert parse_number("abc") is None
    assert parse_number("") is None


def test_infer_boolean():
    t, _ = infer_type(s(["Yes", "No", "yes", "NO", np.nan]))
    assert t == "boolean"
    t2, _ = infer_type(s(["true", "false", "true"]))
    assert t2 == "boolean"


def test_infer_number_integer_vs_float():
    t_int, meta_int = infer_type(s(["1", "2", "3", "10"]))
    assert t_int == "number"
    assert meta_int["integer"] is True

    t_float, meta_float = infer_type(s(["1.5", "2.0", "3.25"]))
    assert t_float == "number"
    assert meta_float["integer"] is False


def test_infer_percent_flag():
    t, meta = infer_type(s(["10%", "20%", "30%"]))
    assert t == "number"
    assert meta["percent"] is True


def test_infer_date_vs_datetime():
    t_date, _ = infer_type(s(["2024-01-01", "2024-02-15", "2024-03-30"]))
    assert t_date == "date"

    t_dt, _ = infer_type(
        s(["2024-01-01 10:15:00", "2024-02-15 09:00:00", "2024-03-30 23:59:59"])
    )
    assert t_dt == "datetime"


def test_year_like_numbers_stay_number_not_date():
    # Numbers win before datetime, so a year column is numeric, not a date.
    t, _ = infer_type(s(["2019", "2020", "2021", "2022"]))
    assert t == "number"


def test_infer_multiselect():
    t, meta = infer_type(
        s(
            [
                "Fever, Cough",
                "Cough",
                "Fever, Headache, Cough",
                "Headache",
                "Fever, Cough",
            ]
        )
    )
    assert t == "multiselect"
    assert meta["delimiter"] == ","


def test_free_text_with_commas_is_not_multiselect():
    # Many distinct comma phrases -> too many options -> stays text.
    values = [f"unique sentence number {i}, with detail {i}" for i in range(40)]
    assert detect_multiselect(pd.Series(values)) is None
    t, _ = infer_type(s(values))
    assert t == "text"


def test_infer_categorical():
    values = (["Male"] * 10) + (["Female"] * 10) + (["Other"] * 5)
    t, meta = infer_type(s(values))
    assert t == "categorical"
    assert meta["n_unique"] == 3


def test_near_miss_number_stays_text():
    # 8/10 parse as numbers -> below the 0.9 threshold -> not number.
    values = ["1", "2", "3", "4", "5", "6", "7", "8", "apple", "banana"]
    t, _ = infer_type(s(values))
    assert t != "number"


def test_all_missing_is_text():
    t, meta = infer_type(s([np.nan, np.nan]))
    assert t == "text"
    assert "missing" in meta["reason"]
