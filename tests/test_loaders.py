"""Tests for survey_cleaner.loaders."""

from __future__ import annotations

import pandas as pd
import pytest

from survey_cleaner.loaders import load_table


def test_load_csv_reads_everything_as_string(write_csv):
    df = pd.DataFrame({"id": ["007", "012", "100"], "score": ["1", "2", "3"]})
    path = write_csv(df, name="ids.csv")

    result = load_table(path)

    assert result.kind == "csv"
    assert result.n_rows == 3
    assert result.n_cols == 2
    # Leading zeros must be preserved (read as string, not int).
    assert list(result.df["id"]) == ["007", "012", "100"]
    assert all(isinstance(v, str) for v in result.df["id"])


def test_load_csv_sniffs_semicolon_delimiter(tmp_path):
    path = tmp_path / "semi.csv"
    path.write_text("name;age;city\nAsha;30;Pune\nRavi;25;Delhi\n", encoding="utf-8")

    result = load_table(path)

    assert result.delimiter == ";"
    assert list(result.df.columns) == ["name", "age", "city"]
    assert list(result.df["city"]) == ["Pune", "Delhi"]


def test_load_csv_detects_non_utf8_encoding(tmp_path):
    path = tmp_path / "latin.csv"
    # 'café' encoded as latin-1/cp1252 is not valid UTF-8.
    path.write_bytes("name,note\ncafe_owner,café\n".encode("cp1252"))

    result = load_table(path)

    assert result.encoding in ("cp1252", "latin-1")
    assert result.df["note"].iloc[0] == "café"


def test_load_xlsx_single_sheet(write_xlsx):
    df = pd.DataFrame({"q1": ["a", "b"], "q2": ["1", "2"]})
    path = write_xlsx(df, name="single.xlsx")

    result = load_table(path)

    assert result.kind == "xlsx"
    assert result.sheet == "Sheet1"
    assert list(result.df.columns) == ["q1", "q2"]


def test_load_xlsx_multi_sheet_defaults_to_first_with_warning(write_xlsx):
    sheets = {
        "Form Responses 1": pd.DataFrame({"a": ["1"]}),
        "Other": pd.DataFrame({"b": ["2"]}),
    }
    path = write_xlsx(sheets, name="multi.xlsx")

    result = load_table(path)

    assert result.sheet == "Form Responses 1"
    assert result.available_sheets == ["Form Responses 1", "Other"]
    assert any("sheets" in w.lower() for w in result.warnings)


def test_load_xlsx_named_sheet(write_xlsx):
    sheets = {
        "Form Responses 1": pd.DataFrame({"a": ["1"]}),
        "Other": pd.DataFrame({"b": ["2"]}),
    }
    path = write_xlsx(sheets, name="multi2.xlsx")

    result = load_table(path, sheet="Other")

    assert result.sheet == "Other"
    assert list(result.df.columns) == ["b"]


def test_load_xlsx_missing_sheet_raises(write_xlsx):
    path = write_xlsx(pd.DataFrame({"a": ["1"]}), name="one.xlsx")
    with pytest.raises(ValueError, match="not found"):
        load_table(path, sheet="Nope")


def test_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_table(tmp_path / "does_not_exist.csv")


def test_unsupported_extension_raises(tmp_path):
    path = tmp_path / "data.txt"
    path.write_text("hello", encoding="utf-8")
    with pytest.raises(ValueError, match="Unsupported"):
        load_table(path)
