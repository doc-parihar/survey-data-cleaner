"""survey_cleaner: clean messy survey CSV/XLSX exports into analysis-ready tables.

Version 1 cleans one rectangular survey table at a time (one row per response,
one column per question/metadata field) and emits a documented, reproducible
cleaning report. It is deterministic and runs fully locally -- no cloud, no LLM.
"""

__version__ = "0.1.0"
