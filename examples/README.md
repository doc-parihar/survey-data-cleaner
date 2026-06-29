# Example: messy Google Forms export → clean table + report

This folder lets you see what `survey-data-cleaner` produces **without running
anything**. It uses the same dataset as the before/after in the project README.

## Files

- [`responses.csv`](responses.csv) — a synthetic, deliberately-messy Google
  Forms export (6 rows, including one duplicate submission, mixed missing
  markers like `NA` / `N/A` / `-` / `nil`, a comma-separated checkbox column,
  and a mostly-empty column).
- [`sample_output/`](sample_output/) — the files produced by the command below.
- [`rules.yaml`](rules.yaml) — an optional overrides file you can try.

## How `sample_output/` was generated

```bash
survey-clean examples/responses.csv --out examples/sample_output --split-multiselect
```

That single command produced:

| Output | What it is |
| --- | --- |
| [`cleaned.csv`](sample_output/cleaned.csv) | Analysis-ready table: `snake_case` headers, real types, standardised blanks, and one 0/1 indicator column per checkbox option. |
| [`data_dictionary.csv`](sample_output/data_dictionary.csv) | Every column with its original question text, inferred type, and missing/unique stats. |
| [`quality_report.md`](sample_output/quality_report.md) | Human-readable summary of what was detected and changed. |
| [`cleaning_log.json`](sample_output/cleaning_log.json) | Machine-readable audit trail (tool version, thresholds, per-column decisions). |

## Try the rules file

```bash
survey-clean examples/responses.csv --out out/ --rules examples/rules.yaml
```

This renames `What is your age?` → `age_years`, forces the temperature column
to a number, drops `Internal notes`, and splits the symptoms checkbox column —
all driven by [`rules.yaml`](rules.yaml).
