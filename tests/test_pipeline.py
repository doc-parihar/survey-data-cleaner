"""End-to-end pipeline behavior that is awkward to assert via the CLI alone."""

from __future__ import annotations

import pandas as pd

from survey_cleaner.pipeline import Config, process


def test_column_stats_reflect_rows_after_dropping_duplicates(write_csv):
    df = pd.DataFrame(
        {
            "Timestamp": [
                "2024-01-01 09:00:00",
                "2024-01-01 09:00:00",
                "2024-01-02 09:00:00",
            ],
            "Age": ["N/A", "N/A", "30"],
        }
    )
    path = write_csv(df)

    result = process(path, Config(drop_duplicates=True))

    age = result.schema.by_cleaned("age")
    assert result.n_rows_out == 2
    assert age.n_missing == 1
    assert age.pct_missing == 0.5
