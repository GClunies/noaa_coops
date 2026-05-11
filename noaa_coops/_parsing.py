"""Date parsing and DataFrame normalization helpers."""

from __future__ import annotations

from datetime import datetime

import pandas as pd

KNOWN_DATE_FORMATS: tuple[str, ...] = (
    "%Y%m%d",
    "%Y%m%d %H:%M",
    "%m/%d/%Y",
    "%m/%d/%Y %H:%M",
)


def parse_known_date_formats(dt_string: str) -> tuple[datetime, str]:
    """Parse a user-provided date string in any of the supported formats.

    Args:
        dt_string: The date string to parse.

    Returns:
        A ``(datetime, str)`` tuple, where the string is always in the
        canonical ``"%Y%m%d %H:%M"`` form used by the data API.

    Raises:
        ValueError: The input did not match any of ``KNOWN_DATE_FORMATS``.
    """
    for fmt in KNOWN_DATE_FORMATS:
        try:
            dt = datetime.strptime(dt_string, fmt)
        except ValueError:
            continue
        return dt, dt.strftime("%Y%m%d %H:%M")

    raise ValueError(
        f"Invalid date format {dt_string!r} provided. "
        f"Expected one of: {KNOWN_DATE_FORMATS}. "
        "See https://tidesandcurrents.noaa.gov/api/ for details."
    )


def normalize_data_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Shape the raw datagetter response into a time-indexed DataFrame.

    - Converts the ``"t"`` column to ``DatetimeIndex``.
    - Coerces numeric-looking string columns to numbers.
    - Drops duplicate timestamps (keeping the first occurrence).

    Args:
        df: Raw DataFrame from ``pd.json_normalize`` on a datagetter response.

    Returns:
        DataFrame indexed by timestamp with numeric columns where possible.
    """
    df.index = pd.to_datetime(df["t"])
    df = df.drop(columns=["t"])

    for col in df.columns:
        try:
            df[col] = pd.to_numeric(df[col])
        except ValueError:
            # Leave non-numeric columns alone (e.g., "f", "q" quality flags).
            df[col] = df[col]

    return df[~df.index.duplicated(keep="first")]
