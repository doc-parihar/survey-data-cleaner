"""End-to-end orchestration: load -> profile -> schema -> clean -> validate.

``process`` returns an in-memory :class:`ProcessResult`; it writes no files.
:mod:`survey_cleaner.reports` turns a result into output files, and
:mod:`survey_cleaner.cli` wires user arguments to a :class:`Config`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

import pandas as pd

from survey_cleaner.cleaning import (
    DEFAULT_MISSING_TOKENS,
    coerce_column,
    split_multiselect,
    standardize_missing,
)
from survey_cleaner.loaders import LoadResult, load_table
from survey_cleaner.profiles import Profile, detect_profile
from survey_cleaner.rules import Rules, apply_rules, load_rules
from survey_cleaner.schema import Column, Schema, build_schema, populate_stats
from survey_cleaner.types_infer import infer_type
from survey_cleaner.validators import Validation, validate


@dataclass
class Config:
    profile: str = "auto"  # auto | google_forms | generic
    sheet: Optional[str] = None
    encoding: Optional[str] = None
    split_multiselect: bool = False
    dayfirst: bool = True
    drop_duplicates: bool = False
    drop_empty_cols: bool = False
    missing_threshold: float = 0.9
    rules_path: Optional[str] = None
    write_xlsx: bool = False
    report_only: bool = False


@dataclass
class ProcessResult:
    load_result: LoadResult
    profile: Profile
    schema: Schema
    cleaned_df: pd.DataFrame
    validation: Validation
    config: Config
    rules: Optional[Rules] = None
    missing_tokens: List[str] = field(default_factory=list)
    n_rows_in: int = 0
    n_rows_out: int = 0
    dropped_duplicate_rows: int = 0
    dropped_empty_columns: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


def process(input_path, config: Config) -> ProcessResult:
    load_result = load_table(input_path, sheet=config.sheet, encoding=config.encoding)
    profile = detect_profile(load_result, override=config.profile)
    schema = build_schema(list(load_result.df.columns), profile=profile.name)

    rules = load_rules(config.rules_path) if config.rules_path else None

    # Missing-value tokens are needed before inference, so resolve them now.
    tokens = set(DEFAULT_MISSING_TOKENS)
    if rules:
        tokens |= rules.missing_tokens()

    # Rules override auto-detection; applying them up front lets us skip
    # inference on forced columns while still letting rules win.
    if rules:
        apply_rules(schema, rules)

    # Working frame: active columns only, in original order, with cleaned names.
    keep = [i for i, c in enumerate(schema.columns) if not c.dropped]
    df = load_result.df.iloc[:, keep].copy()
    df.columns = [schema.columns[i].cleaned_name for i in keep]
    active = schema.active()

    # 1. Standardise missing values, then infer + coerce per column.
    rules_delim = rules.multiselect_delimiter if rules else None
    for col in active:
        series, n_std = standardize_missing(df[col.cleaned_name], tokens)
        col.n_missing_standardised = n_std

        if not col.forced_type:
            inferred, meta = infer_type(series, dayfirst=config.dayfirst)
            col.inferred_type = inferred
            col.type_meta = meta
            col.is_multiselect = inferred == "multiselect"

        coerced, n_failed = coerce_column(series, col.inferred_type, dayfirst=config.dayfirst)
        col.n_coercion_failed = n_failed
        if n_failed:
            col.add_note(f"{n_failed} value(s) could not be parsed as {col.inferred_type}")
        df[col.cleaned_name] = coerced

    # 2. Split multi-select columns (children inserted right after their parent).
    df = _split_multiselect_columns(df, schema, config, profile, rules_delim)

    # 3. Validate, then optionally act on the findings (non-destructive default).
    validation = validate(df, empty_threshold=config.missing_threshold)
    n_rows_in = load_result.n_rows

    dropped_dupes = 0
    if config.drop_duplicates and validation.n_duplicate_rows:
        df = df.drop(index=validation.duplicate_row_indices).reset_index(drop=True)
        dropped_dupes = validation.n_duplicate_rows

    dropped_empty: List[str] = []
    if config.drop_empty_cols and validation.empty_columns:
        dropped_empty = [name for name, _ in validation.empty_columns]
        df = df.drop(columns=dropped_empty)
        for col in schema.columns:
            if col.cleaned_name in dropped_empty:
                col.dropped = True
                col.add_note("dropped as mostly-empty (--drop-empty-cols)")

    # 4. Per-column statistics on the final cleaned table.
    present = set(df.columns)
    for col in schema.columns:
        if col.cleaned_name in present:
            populate_stats(col, df[col.cleaned_name])

    warnings = list(load_result.warnings) + list(schema.warnings)

    return ProcessResult(
        load_result=load_result,
        profile=profile,
        schema=schema,
        cleaned_df=df,
        validation=validation,
        config=config,
        rules=rules,
        missing_tokens=sorted(tokens),
        n_rows_in=n_rows_in,
        n_rows_out=len(df),
        dropped_duplicate_rows=dropped_dupes,
        dropped_empty_columns=dropped_empty,
        warnings=warnings,
    )


def _split_multiselect_columns(
    df: pd.DataFrame,
    schema: Schema,
    config: Config,
    profile: Profile,
    rules_delim: Optional[str],
) -> pd.DataFrame:
    new_order: List[str] = []
    additions = {}
    inserted: List[tuple] = []  # (parent_column, child_column)

    for col in schema.active():
        new_order.append(col.cleaned_name)
        should_split = col.is_multiselect and (config.split_multiselect or col.force_split)
        if not should_split:
            continue

        delimiter = (
            col.type_meta.get("delimiter") or rules_delim or profile.multiselect_delimiter
        )
        existing = list(df.columns) + list(additions.keys())
        indicators, children = split_multiselect(
            df[col.cleaned_name], col.cleaned_name, delimiter, existing_names=existing
        )
        for option, name in children:
            additions[name] = indicators[name]
            new_order.append(name)
            child = Column(
                original_name=f"{col.original_name} [{option}]",
                cleaned_name=name,
                inferred_type="indicator",
            )
            child.add_note(
                f"multi-select indicator for option '{option}' from "
                f"'{col.cleaned_name}'"
            )
            inserted.append((col, child))
        col.split_children = children
        col.add_note(f"split into {len(children)} indicator column(s)")

    if not additions:
        return df

    for name, series in additions.items():
        df[name] = series
    df = df[new_order]

    # Weave the new child Column objects into the schema, after each parent.
    children_by_parent = {}
    for parent, child in inserted:
        children_by_parent.setdefault(id(parent), []).append(child)
    woven: List[Column] = []
    for col in schema.columns:
        woven.append(col)
        woven.extend(children_by_parent.get(id(col), []))
    schema.columns = woven
    return df
