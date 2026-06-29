"""End-to-end CLI tests for survey_cleaner.cli."""

from __future__ import annotations

import pandas as pd

from survey_cleaner.cli import main


def test_cli_end_to_end_csv_is_non_destructive(write_csv, google_forms_df, tmp_path):
    path = write_csv(google_forms_df, name="responses.csv")
    before = path.read_bytes()
    out = tmp_path / "outputs"

    code = main([str(path), "--out", str(out), "--split-multiselect"])

    assert code == 0
    assert (out / "cleaned.csv").exists()
    assert (out / "quality_report.md").exists()
    # The input file must be byte-for-byte unchanged.
    assert path.read_bytes() == before


def test_cli_end_to_end_xlsx_with_sheet(write_xlsx, google_forms_df, tmp_path):
    sheets = {
        "Form Responses 1": google_forms_df,
        "Pivot": pd.DataFrame({"junk": ["1"]}),
    }
    path = write_xlsx(sheets, name="responses.xlsx")
    out = tmp_path / "outputs"

    code = main([str(path), "--out", str(out), "--sheet", "Form Responses 1"])

    assert code == 0
    cleaned = pd.read_csv(out / "cleaned.csv")
    assert "what_is_your_age" in cleaned.columns


def test_cli_report_only(write_csv, google_forms_df, tmp_path):
    path = write_csv(google_forms_df, name="responses.csv")
    out = tmp_path / "outputs"

    code = main([str(path), "--out", str(out), "--report-only"])

    assert code == 0
    assert not (out / "cleaned.csv").exists()
    assert (out / "data_dictionary.csv").exists()


def test_cli_with_rules(write_csv, google_forms_df, tmp_path):
    path = write_csv(google_forms_df, name="responses.csv")
    rules = tmp_path / "rules.yaml"
    rules.write_text(
        'rename:\n  "What is your age?": age_years\n'
        'drop_columns:\n  - "Optional comments"\n',
        encoding="utf-8",
    )
    out = tmp_path / "outputs"

    code = main([str(path), "--out", str(out), "--rules", str(rules)])

    assert code == 0
    cleaned = pd.read_csv(out / "cleaned.csv")
    assert "age_years" in cleaned.columns
    assert "optional_comments" not in cleaned.columns


def test_cli_missing_file_returns_nonzero(tmp_path):
    code = main([str(tmp_path / "nope.csv"), "--out", str(tmp_path / "o")])
    assert code == 2


def test_cli_refuses_overwrite_without_force(write_csv, google_forms_df, tmp_path):
    path = write_csv(google_forms_df, name="responses.csv")
    out = tmp_path / "outputs"

    assert main([str(path), "--out", str(out)]) == 0
    # Second run without --force should refuse.
    assert main([str(path), "--out", str(out)]) == 2
    # With --force it succeeds.
    assert main([str(path), "--out", str(out), "--force"]) == 0


def test_cli_drop_duplicates(write_csv, google_forms_df, tmp_path):
    path = write_csv(google_forms_df, name="responses.csv")
    out = tmp_path / "outputs"

    code = main([str(path), "--out", str(out), "--drop-duplicates"])

    assert code == 0
    cleaned = pd.read_csv(out / "cleaned.csv")
    # The fixture has 5 rows with exactly one duplicate -> 4 remain.
    assert len(cleaned) == 4
