"""Tests for survey_cleaner.rules."""

from __future__ import annotations

import pytest

from survey_cleaner.rules import RulesError, apply_rules, load_rules
from survey_cleaner.schema import build_schema


def write_rules(tmp_path, text: str):
    path = tmp_path / "rules.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_load_rules_full(tmp_path):
    path = write_rules(
        tmp_path,
        """
rename:
  "What is your age?": age_years
types:
  "Joined on": date
missing_values:
  - "n.a."
  - missing
multiselect:
  columns: ["Symptoms"]
  delimiter: ";"
drop_columns:
  - "Internal ID"
""",
    )
    rules = load_rules(path)
    assert rules.rename == {"What is your age?": "age_years"}
    assert rules.types == {"Joined on": "date"}
    assert rules.missing_tokens() == {"n.a.", "missing"}
    assert rules.multiselect_columns == ["Symptoms"]
    assert rules.multiselect_delimiter == ";"
    assert rules.drop_columns == ["Internal ID"]


def test_load_rules_empty_file(tmp_path):
    path = write_rules(tmp_path, "")
    rules = load_rules(path)
    assert rules.rename == {}
    assert rules.missing_tokens() == set()


def test_load_rules_unknown_key_raises(tmp_path):
    path = write_rules(tmp_path, "explode_everything: true\n")
    with pytest.raises(RulesError, match="Unknown rules key"):
        load_rules(path)


def test_load_rules_invalid_type_raises(tmp_path):
    path = write_rules(tmp_path, 'types:\n  "Age": integer\n')
    with pytest.raises(RulesError, match="Invalid type"):
        load_rules(path)


def test_load_rules_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_rules(tmp_path / "nope.yaml")


def test_apply_rules_mutates_schema(tmp_path):
    schema = build_schema(["What is your age?", "Joined on", "Symptoms", "Internal ID"])
    path = write_rules(
        tmp_path,
        """
rename:
  "What is your age?": age_years
types:
  "Joined on": date
multiselect:
  columns: ["Symptoms"]
drop_columns:
  - "Internal ID"
""",
    )
    apply_rules(schema, load_rules(path))

    age = schema.by_original("What is your age?")
    assert age.cleaned_name == "age_years"

    joined = schema.by_original("Joined on")
    assert joined.inferred_type == "date" and joined.forced_type is True

    symptoms = schema.by_original("Symptoms")
    assert symptoms.is_multiselect is True
    assert symptoms.force_split is True
    assert symptoms.inferred_type == "multiselect"

    internal = schema.by_original("Internal ID")
    assert internal.dropped is True
    assert [c.cleaned_name for c in schema.active()] == [
        "age_years",
        "joined_on",
        "symptoms",
    ]


def test_apply_rules_unknown_column_raises(tmp_path):
    schema = build_schema(["a", "b"])
    path = write_rules(tmp_path, 'drop_columns:\n  - "does not exist"\n')
    with pytest.raises(RulesError, match="not found"):
        apply_rules(schema, load_rules(path))


def test_apply_rules_rename_collision_raises(tmp_path):
    schema = build_schema(["First", "Second"])
    path = write_rules(tmp_path, 'rename:\n  "First": second\n')
    with pytest.raises(RulesError, match="duplicate"):
        apply_rules(schema, load_rules(path))
