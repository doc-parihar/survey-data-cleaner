"""Shared synthetic fixtures. No real survey data is ever used."""

from __future__ import annotations

import pandas as pd
import pytest


@pytest.fixture
def google_forms_df() -> pd.DataFrame:
    """A small, deliberately-messy Google Forms-style export.

    Includes: a Timestamp first column, mixed missing tokens, a numeric column,
    a yes/no column, a comma-separated checkbox (multi-select) column, a
    duplicate row, and a mostly-empty column.
    """
    return pd.DataFrame(
        {
            "Timestamp": [
                "2024-01-02 10:15:30",
                "2024-01-02 11:00:00",
                "2024-01-03 09:30:00",
                "2024-01-02 11:00:00",  # duplicate of row index 1
                "2024-01-04 14:20:00",
            ],
            "Email Address": [
                "a@example.com",
                "b@example.com",
                "NA",
                "b@example.com",
                "c@example.com",
            ],
            "What is your age?": ["34", "29", "41", "29", "N/A"],
            "Do you consent to participate?": ["Yes", "No", "yes", "No", "YES"],
            "Which symptoms apply? (select all)": [
                "Fever, Cough",
                "Cough",
                "Fever, Headache, Cough",
                "Cough",
                "-",
            ],
            "Optional comments": ["", "", "n/a", "", "All good"],
        }
    )


@pytest.fixture
def write_csv(tmp_path):
    def _write(df: pd.DataFrame, name: str = "data.csv", encoding: str = "utf-8", sep: str = ","):
        path = tmp_path / name
        df.to_csv(path, index=False, encoding=encoding, sep=sep)
        return path

    return _write


@pytest.fixture
def write_xlsx(tmp_path):
    def _write(sheets, name: str = "data.xlsx"):
        path = tmp_path / name
        with pd.ExcelWriter(path, engine="openpyxl") as xl:
            if isinstance(sheets, dict):
                for sheet_name, df in sheets.items():
                    df.to_excel(xl, sheet_name=sheet_name, index=False)
            else:
                sheets.to_excel(xl, sheet_name="Sheet1", index=False)
        return path

    return _write
