# survey-data-cleaner

[![CI](https://github.com/doc-parihar/survey-data-cleaner/actions/workflows/ci.yml/badge.svg)](https://github.com/doc-parihar/survey-data-cleaner/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/)

Clean messy survey-style CSV/XLSX exports into an **analysis-ready table** with
a **documented cleaning report** — from one command, fully offline.

v1 includes a dedicated **Google Forms** profile plus a generic survey-table
fallback for rectangular exports from tools such as Microsoft Forms,
SurveyMonkey, Typeform, Qualtrics, REDCap, Kobo, ODK, and similar platforms.

```bash
survey-clean responses.csv --out outputs/ --split-multiselect
```

It is a small, deterministic Python CLI. No cloud, no LLM, no statistics
magic — just the boring, repeatable cleaning steps you would otherwise do by
hand in a spreadsheet every time, plus a paper trail of exactly what changed.

---

## Who it is for

- **Researchers** (clinical, public-health, social science) who export survey
  responses and need a tidy table plus a data dictionary they can cite in
  methods.
- **Small businesses and analysts** who collect feedback/intake forms and want
  clean CSVs for Excel, Power BI, R, or pandas without writing the same
  cleanup script again.

## The problem it solves

Raw survey exports are messy in predictable ways: question text as column
headers, mixed missing markers (`NA`, `N/A`, `-`, `nil`, blanks), checkbox
answers crammed into one comma-separated cell, duplicate submissions, and
mostly-empty columns. `survey-data-cleaner` standardises all of that **the same
way every time** and writes a report so the cleaning is reviewable and
reproducible.

## What it does (v1)

- Reads one rectangular survey table (`.csv` or `.xlsx`), one row per response.
- Detects a **Google Forms** profile (or a generic survey-table fallback).
- Normalises headers into safe `snake_case`, preserving the original question
  text in a **data dictionary**.
- Standardises missing values: blank, `NA`, `N/A`, `nil`, `none`, `null`, `-`, `--`.
- Infers basic column types: text, number, date/datetime, categorical, boolean,
  multi-select.
- Optionally splits multi-select checkbox columns into 0/1 **indicator columns**.
- Flags **duplicate rows**, **mostly-empty columns**, and values that failed to
  parse — without deleting anything unless you ask.
- Writes `cleaned.csv` (and optional `cleaned.xlsx`), `data_dictionary.csv`,
  `quality_report.md`, and a machine-readable `cleaning_log.json`.

## Install

Requires Python 3.9+.

```bash
git clone https://github.com/doc-parihar/survey-data-cleaner.git
cd survey-data-cleaner
pip install -e .
```

This installs the `survey-clean` command. You can also run it as a module:
`python -m survey_cleaner ...`.

## Quickstart

```bash
# Basic: clean an Excel export into ./outputs
survey-clean input.xlsx --out outputs/

# Google Forms CSV, splitting checkbox answers into indicator columns
survey-clean responses.csv --profile google_forms --split-multiselect

# Pick a specific sheet and only produce the reports (no cleaned data file)
survey-clean responses.xlsx --sheet "Form Responses 1" --report-only

# Drive cleaning with an explicit rules file (renames, forced types, etc.)
survey-clean responses.csv --rules rules.yaml
```

Useful flags: `--xlsx` (also write `cleaned.xlsx`), `--drop-duplicates`,
`--drop-empty-cols`, `--missing-threshold 0.95`, `--no-dayfirst`, `--force`
(overwrite existing outputs). Full list: `survey-clean --help`.

## Example data

A runnable sample lives in [`examples/`](examples/): a messy
[`responses.csv`](examples/responses.csv) and the exact
[`sample_output/`](examples/sample_output/) it produces — so you can see the
results without running anything.

## Before / after

**Before** — a raw Google Forms export (`responses.csv`):

| Timestamp | Email Address | What is your age? | Do you consent to participate? | Which symptoms apply? (select all) | Reported temperature (C) | Internal notes |
| --- | --- | --- | --- | --- | --- | --- |
| 2024-03-01 09:14:22 | p1@example.com | 34 | Yes | Fever, Cough | 38.2 | |
| 2024-03-01 10:02:51 | p2@example.com | 29 | No | Cough | 37.0 | |
| 2024-03-02 14:33:10 | NA | 41 | yes | Fever, Headache, Cough | 39.1 | n/a |
| 2024-03-03 08:45:00 | p5@example.com | N/A | YES | - | nil | |

**After** — `cleaned.csv` (`--split-multiselect`), with safe names, real types,
standardised blanks, and one indicator column per checkbox option:

| timestamp | email_address | what_is_your_age | do_you_consent_to_participate | which_symptoms_apply_select_all | ..._fever | ..._cough | ..._headache | reported_temperature_c | internal_notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2024-03-01 09:14:22 | p1@example.com | 34 | True | Fever, Cough | 1 | 1 | 0 | 38.2 | |
| 2024-03-01 10:02:51 | p2@example.com | 29 | False | Cough | 0 | 1 | 0 | 37.0 | |
| 2024-03-02 14:33:10 | | 41 | True | Fever, Headache, Cough | 1 | 1 | 1 | 39.1 | |
| 2024-03-03 08:45:00 | p5@example.com | | True | | | | | | |

## Sample outputs

`quality_report.md` (excerpt):

```markdown
## Cleaning summary
- Missing tokens treated as blank: '', '-', '--', 'n/a', 'na', 'nil', 'none', 'null'
- Cells standardised to missing: 9
- Multi-select columns split: 1
- Duplicate rows: 1 found, 0 dropped

## Columns
| Cleaned name | Type | % missing | Unique | Example |
| --- | --- | ---: | ---: | --- |
| timestamp | datetime | 0.0% | 5 | 2024-03-01 09:14:22 |
| what_is_your_age | number | 16.7% | 4 | 34 |
| do_you_consent_to_participate | boolean | 0.0% | 2 | True |
| which_symptoms_apply_select_all | multiselect | 16.7% | 4 | Fever, Cough |
```

`data_dictionary.csv` (excerpt) keeps the original question text as the
description:

| original_column | cleaned_column | inferred_type | description | pct_missing |
| --- | --- | --- | --- | --- |
| What is your age? | what_is_your_age | number | What is your age? | 0.1667 |
| Which symptoms apply? (select all) | which_symptoms_apply_select_all | multiselect | Which symptoms apply? (select all) | 0.1667 |

`cleaning_log.json` records the tool version, input metadata, detected profile,
thresholds used, and every per-column decision — so a result can be audited and
reproduced.

## Rules file (optional)

When auto-detection needs a nudge, pass `--rules rules.yaml`. All keys are
optional and reference columns by their **original header text**:

```yaml
rename:            { "What is your age?": age_years }
types:             { "Reported temperature (C)": number }   # number|date|datetime|boolean|categorical|multiselect|text
missing_values:    [ "n.a.", "missing" ]                    # extra tokens, merged with the defaults
multiselect:       { columns: ["Which symptoms apply? (select all)"], delimiter: "," }
drop_columns:      [ "Internal notes" ]
```

## How cleaning decisions are made

Type inference is deterministic and threshold-based. For each column, the
non-missing values are tested in this order and the first to clear the
threshold wins: **boolean → number → date/datetime → multi-select →
categorical → text**.

- A type needs **≥ 90%** of non-missing values to match.
- Numbers win before dates, so a year column like `2019, 2020` stays numeric.
- A column is **categorical** when it has few distinct values; **multi-select**
  needs a delimiter in ≥ 30% of cells and a small option vocabulary.
- Nothing is dropped by default — duplicates and empty columns are *reported*;
  use `--drop-duplicates` / `--drop-empty-cols` to act on them.

These thresholds are constants in
[`types_infer.py`](src/survey_cleaner/types_infer.py) and are echoed into every
`cleaning_log.json`.

## Limitations (read these)

- **One rectangular table at a time** — one row per response, one column per
  question/metadata field. Not a universal data-cleaning engine.
- No PDF extraction; no nested/repeated ODK groups.
- No automatic statistical analysis.
- Type inference is heuristic — **always review `quality_report.md`** before
  analysis.
- Reading `.xlsx` returns the values Excel stored; whole numbers may show as
  `123` and could carry a trailing `.0` before they are coerced to a number.
- Tested with **synthetic data only**; no compliance (HIPAA/GDPR/GCP) claims are
  made.

## Privacy

`survey-data-cleaner` runs **entirely on your machine**. It makes no network
calls and uses no cloud service or LLM. Your input file is **never modified**;
all results are written to a separate output directory.

## Roadmap

- More platform profiles (Microsoft Forms, REDCap, Kobo/ODK conventions).
- An expanded rules engine (value recoding, validation constraints).
- A bundled `examples/` folder with runnable sample inputs.

## Development

```bash
pip install -e ".[dev]"
pytest
```

The test suite uses only synthetic data.

## License

[MIT](LICENSE) © doc-parihar
