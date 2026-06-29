"""Tests for survey_cleaner.reports (uses the real pipeline end-to-end)."""

from __future__ import annotations

import json

import pandas as pd
import pytest

from survey_cleaner.pipeline import Config, process
from survey_cleaner.reports import DATA_DICTIONARY_COLUMNS, write_outputs


def test_write_outputs_creates_all_files(write_csv, google_forms_df, tmp_path):
    path = write_csv(google_forms_df, name="gf.csv")
    result = process(path, Config(split_multiselect=True, write_xlsx=True))
    out = tmp_path / "out"

    write_outputs(result, out)

    for name in (
        "cleaned.csv",
        "cleaned.xlsx",
        "data_dictionary.csv",
        "quality_report.md",
        "cleaning_log.json",
    ):
        assert (out / name).exists(), f"missing {name}"


def test_data_dictionary_preserves_question_text(write_csv, google_forms_df, tmp_path):
    path = write_csv(google_forms_df, name="gf.csv")
    result = process(path, Config(split_multiselect=True))
    out = tmp_path / "out"
    write_outputs(result, out)

    dd = pd.read_csv(out / "data_dictionary.csv")
    assert list(dd.columns) == DATA_DICTIONARY_COLUMNS
    # Original question text is preserved verbatim.
    assert "What is your age?" in set(dd["original_column"])
    assert "what_is_your_age" in set(dd["cleaned_column"])


def test_cleaned_csv_has_multiselect_indicators(write_csv, google_forms_df, tmp_path):
    path = write_csv(google_forms_df, name="gf.csv")
    result = process(path, Config(split_multiselect=True))
    out = tmp_path / "out"
    write_outputs(result, out)

    cleaned = pd.read_csv(out / "cleaned.csv")
    indicator_cols = [
        c
        for c in cleaned.columns
        if c.startswith("which_symptoms_apply") and "__" in c
    ]
    assert indicator_cols, "expected split indicator columns in cleaned.csv"


def test_cleaning_log_is_valid_json_with_expected_keys(
    write_csv, google_forms_df, tmp_path
):
    path = write_csv(google_forms_df, name="gf.csv")
    result = process(path, Config())
    out = tmp_path / "out"
    write_outputs(result, out)

    log = json.loads((out / "cleaning_log.json").read_text(encoding="utf-8"))
    for key in ("tool", "version", "input", "profile", "columns", "duplicates", "missing_tokens"):
        assert key in log
    assert log["tool"] == "survey-data-cleaner"
    assert log["profile"] == "google_forms"
    # The fixture contains one duplicate response row.
    assert log["duplicates"]["found"] == 1


def test_report_only_skips_cleaned_data(write_csv, google_forms_df, tmp_path):
    path = write_csv(google_forms_df, name="gf.csv")
    result = process(path, Config(report_only=True))
    out = tmp_path / "ro"
    write_outputs(result, out)

    assert not (out / "cleaned.csv").exists()
    assert not (out / "cleaned.xlsx").exists()
    assert (out / "quality_report.md").exists()
    assert (out / "data_dictionary.csv").exists()


def test_overwrite_requires_force(write_csv, google_forms_df, tmp_path):
    path = write_csv(google_forms_df, name="gf.csv")
    result = process(path, Config())
    out = tmp_path / "ow"

    write_outputs(result, out)
    with pytest.raises(FileExistsError, match="force"):
        write_outputs(result, out)
    # With force it succeeds.
    written = write_outputs(result, out, force=True)
    assert any(p.name == "cleaned.csv" for p in written)
