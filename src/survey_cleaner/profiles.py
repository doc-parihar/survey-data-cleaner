"""Survey-platform profiles.

A profile records light, platform-specific conventions and how it is detected
from the header row. v1 ships a strong Google Forms profile and a generic
fallback that always matches. Profiles never reshape the table; they only
provide hints (e.g. the default multi-select delimiter and which column is the
submission timestamp).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from survey_cleaner.loaders import LoadResult

VALID_PROFILE_NAMES = ("auto", "google_forms", "generic")


@dataclass
class Profile:
    name: str
    multiselect_delimiter: str = ","
    timestamp_column: Optional[str] = None
    description: str = ""


GENERIC = Profile(
    name="generic",
    multiselect_delimiter=",",
    description="Generic rectangular survey table (one row per response).",
)


def _headers(load_result: LoadResult) -> List[str]:
    return [str(c).strip() for c in load_result.df.columns]


def detect_google_forms(load_result: LoadResult) -> bool:
    """Google Forms exports a ``Timestamp`` column as the first column."""
    headers = _headers(load_result)
    return bool(headers) and headers[0].lower() == "timestamp"


def _google_forms_profile(load_result: LoadResult) -> Profile:
    headers = _headers(load_result)
    return Profile(
        name="google_forms",
        multiselect_delimiter=",",
        timestamp_column=headers[0] if headers else None,
        description=(
            "Google Forms response export: first column is the submission "
            "Timestamp; checkbox answers are comma-separated in a single cell."
        ),
    )


def detect_profile(
    load_result: LoadResult, override: Optional[str] = None
) -> Profile:
    """Return the profile to use, honouring an explicit ``override``.

    ``override`` may be ``None``/``"auto"`` (detect), ``"google_forms"`` or
    ``"generic"``. An unknown override raises ``ValueError``.
    """
    if override and override != "auto":
        if override == "google_forms":
            return _google_forms_profile(load_result)
        if override == "generic":
            return GENERIC
        raise ValueError(
            f"Unknown profile '{override}'. Choose from: {VALID_PROFILE_NAMES}"
        )

    if detect_google_forms(load_result):
        return _google_forms_profile(load_result)
    return GENERIC
