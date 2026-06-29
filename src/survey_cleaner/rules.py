"""Optional YAML rules: a small, documented set of overrides.

All keys are optional and reference columns by their **original header text**.
Rules are applied *after* automatic detection, so they always win.

```yaml
rename:            { "What is your age?": age_years }
types:             { "Joined on": date }            # number|date|datetime|boolean|categorical|multiselect|text
missing_values:    [ "n.a.", "missing" ]            # extra tokens, merged with the defaults
multiselect:       { columns: ["Which symptoms apply? (select all)"], delimiter: "," }
drop_columns:      [ "Internal ID" ]
```
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import yaml

from survey_cleaner.schema import Schema

ALLOWED_KEYS = {"rename", "types", "missing_values", "multiselect", "drop_columns"}
ALLOWED_TYPES = {
    "number",
    "date",
    "datetime",
    "boolean",
    "categorical",
    "multiselect",
    "text",
}


class RulesError(ValueError):
    """Raised for malformed rules files or rules that reference unknown columns."""


@dataclass
class Rules:
    rename: Dict[str, str] = field(default_factory=dict)
    types: Dict[str, str] = field(default_factory=dict)
    missing_values: List[str] = field(default_factory=list)
    multiselect_columns: List[str] = field(default_factory=list)
    multiselect_delimiter: Optional[str] = None
    drop_columns: List[str] = field(default_factory=list)

    def missing_tokens(self) -> set:
        return {str(t).strip().lower() for t in self.missing_values}


def load_rules(path) -> Rules:
    """Load and validate a rules YAML file. Raises ``RulesError`` on problems."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Rules file not found: {p}")

    with p.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise RulesError("Rules file must be a YAML mapping at the top level.")

    unknown = set(data) - ALLOWED_KEYS
    if unknown:
        raise RulesError(
            f"Unknown rules key(s): {sorted(unknown)}. "
            f"Allowed: {sorted(ALLOWED_KEYS)}"
        )

    rename = data.get("rename") or {}
    if not isinstance(rename, dict):
        raise RulesError("'rename' must be a mapping of original header -> new name.")

    types = data.get("types") or {}
    if not isinstance(types, dict):
        raise RulesError("'types' must be a mapping of column -> type.")
    for col, type_name in types.items():
        if type_name not in ALLOWED_TYPES:
            raise RulesError(
                f"Invalid type '{type_name}' for column '{col}'. "
                f"Allowed: {sorted(ALLOWED_TYPES)}"
            )

    missing_values = data.get("missing_values") or []
    if not isinstance(missing_values, list):
        raise RulesError("'missing_values' must be a list of strings.")

    drop_columns = data.get("drop_columns") or []
    if not isinstance(drop_columns, list):
        raise RulesError("'drop_columns' must be a list of column headers.")

    multiselect = data.get("multiselect") or {}
    if not isinstance(multiselect, dict):
        raise RulesError(
            "'multiselect' must be a mapping with 'columns' and optional 'delimiter'."
        )
    ms_columns = multiselect.get("columns") or []
    if not isinstance(ms_columns, list):
        raise RulesError("'multiselect.columns' must be a list of column headers.")
    ms_delimiter = multiselect.get("delimiter")

    return Rules(
        rename={str(k): str(v) for k, v in rename.items()},
        types={str(k): str(v) for k, v in types.items()},
        missing_values=[str(v) for v in missing_values],
        multiselect_columns=[str(v) for v in ms_columns],
        multiselect_delimiter=ms_delimiter,
        drop_columns=[str(v) for v in drop_columns],
    )


def _require_column(schema: Schema, original: str, context: str):
    col = schema.by_original(original)
    if col is None:
        raise RulesError(
            f"{context}: column '{original}' was not found in the input headers."
        )
    return col


def _ensure_unique_names(schema: Schema) -> None:
    seen: Dict[str, List[str]] = {}
    for col in schema.columns:
        if col.dropped:
            continue
        seen.setdefault(col.cleaned_name, []).append(col.original_name)
    collisions = {k: v for k, v in seen.items() if len(v) > 1}
    if collisions:
        raise RulesError(
            f"rules.rename produced duplicate cleaned column names: {collisions}"
        )


def apply_rules(schema: Schema, rules: Rules) -> None:
    """Mutate ``schema`` in place to reflect the rules. Apply after inference.

    Note: ``rules.missing_values`` is intentionally *not* handled here -- those
    extra tokens are needed at the earlier missing-standardisation step and are
    pulled directly from :meth:`Rules.missing_tokens` by the pipeline.
    """
    for original, new_name in rules.rename.items():
        col = _require_column(schema, original, "rules.rename")
        col.cleaned_name = str(new_name)
        col.add_note(f"name forced via rules -> '{new_name}'")
    _ensure_unique_names(schema)

    for original in rules.drop_columns:
        col = _require_column(schema, original, "rules.drop_columns")
        col.dropped = True
        col.add_note("dropped via rules")

    for original, type_name in rules.types.items():
        col = _require_column(schema, original, "rules.types")
        col.inferred_type = type_name
        col.forced_type = True
        col.add_note(f"type forced via rules -> {type_name}")
        if type_name == "multiselect":
            col.is_multiselect = True
            col.force_split = True

    for original in rules.multiselect_columns:
        col = _require_column(schema, original, "rules.multiselect")
        col.is_multiselect = True
        col.inferred_type = "multiselect"
        col.forced_type = True
        col.force_split = True
        col.add_note("declared multi-select via rules")
