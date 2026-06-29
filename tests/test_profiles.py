"""Tests for survey_cleaner.profiles."""

from __future__ import annotations

import pandas as pd
import pytest

from survey_cleaner.loaders import LoadResult
from survey_cleaner.profiles import detect_google_forms, detect_profile


def _load(df: pd.DataFrame) -> LoadResult:
    return LoadResult(df=df, source_path="memory", kind="csv")


def test_detect_google_forms_from_timestamp_signature(google_forms_df):
    lr = _load(google_forms_df)
    assert detect_google_forms(lr) is True
    profile = detect_profile(lr)
    assert profile.name == "google_forms"
    assert profile.timestamp_column == "Timestamp"


def test_generic_fallback_when_no_timestamp():
    df = pd.DataFrame({"name": ["a"], "age": ["1"]})
    lr = _load(df)
    assert detect_google_forms(lr) is False
    assert detect_profile(lr).name == "generic"


def test_timestamp_not_first_is_not_google_forms():
    df = pd.DataFrame({"email": ["a@x.com"], "Timestamp": ["2024-01-01"]})
    assert detect_google_forms(_load(df)) is False


def test_override_forces_profile(google_forms_df):
    lr = _load(google_forms_df)
    assert detect_profile(lr, override="generic").name == "generic"

    plain = _load(pd.DataFrame({"a": ["1"]}))
    assert detect_profile(plain, override="google_forms").name == "google_forms"


def test_auto_override_behaves_like_detection(google_forms_df):
    assert detect_profile(_load(google_forms_df), override="auto").name == "google_forms"


def test_invalid_override_raises():
    with pytest.raises(ValueError, match="Unknown profile"):
        detect_profile(_load(pd.DataFrame({"a": ["1"]})), override="surveymonkey")
