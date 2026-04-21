"""Unit tests for the declarative product registry + date parser.

These exercise the helpers directly via the `_products` and `_parsing`
modules. No HTTP, no mocks -- the validators raise ValueError before
any network call.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from noaa_coops._parsing import parse_known_date_formats
from noaa_coops._products import validate_params


# ---------------------------------------------------------------------------
# validate_params: product validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "product",
    [
        "water_level",
        "air_temperature",
        "water_temperature",
        "wind",
        "air_pressure",
        "predictions",
        "datums",
        "high_low",
        "hourly_height",
        "daily_mean",
        "monthly_mean",
        "one_minute_water_level",
    ],
)
def test_valid_products_accepted(product: str) -> None:
    """Every documented product passes validation (with appropriate datum)."""
    # Products that require a datum get MLLW; others get None.
    datum_required = {
        "water_level",
        "hourly_height",
        "high_low",
        "daily_mean",
        "monthly_mean",
        "one_minute_water_level",
        "predictions",
    }
    datum = "MLLW" if product in datum_required else None
    validate_params(
        product=product,
        datum=datum,
        bin_num=None,
        interval=None,
        units="metric",
        time_zone="gmt",
    )


def test_unknown_product_rejected() -> None:
    with pytest.raises(ValueError, match="Invalid product"):
        validate_params(
            product="not_a_real_product",
            datum=None,
            bin_num=None,
            interval=None,
            units="metric",
            time_zone="gmt",
        )


# ---------------------------------------------------------------------------
# validate_params: datum
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "datum", ["MHHW", "MHW", "MTL", "MSL", "MLW", "MLLW", "NAVD", "STND", "IGLD", "LWD"]
)
def test_valid_datums_accepted(datum: str) -> None:
    validate_params(
        product="water_level",
        datum=datum,
        bin_num=None,
        interval=None,
        units="metric",
        time_zone="gmt",
    )


def test_missing_datum_for_water_level_rejected() -> None:
    with pytest.raises(ValueError, match="No datum"):
        validate_params(
            product="water_level",
            datum=None,
            bin_num=None,
            interval=None,
            units="metric",
            time_zone="gmt",
        )


def test_lowercase_datum_accepted() -> None:
    """Datums are normalized to uppercase before validation, so `mllw` is valid."""
    validate_params(
        product="water_level",
        datum="mllw",
        bin_num=None,
        interval=None,
        units="metric",
        time_zone="gmt",
    )


def test_unknown_datum_rejected() -> None:
    with pytest.raises(ValueError, match="Invalid datum"):
        validate_params(
            product="water_level",
            datum="nope",
            bin_num=None,
            interval=None,
            units="metric",
            time_zone="gmt",
        )


# ---------------------------------------------------------------------------
# validate_params: units + time_zone
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("units", ["metric", "english"])
def test_valid_units_accepted(units: str) -> None:
    validate_params(
        product="water_temperature",
        datum=None,
        bin_num=None,
        interval=None,
        units=units,
        time_zone="gmt",
    )


def test_invalid_units_rejected() -> None:
    with pytest.raises(ValueError, match="[Uu]nit"):
        validate_params(
            product="water_temperature",
            datum=None,
            bin_num=None,
            interval=None,
            units="furlongs",
            time_zone="gmt",
        )


@pytest.mark.parametrize("time_zone", ["gmt", "lst", "lst_ldt"])
def test_valid_time_zones_accepted(time_zone: str) -> None:
    validate_params(
        product="water_temperature",
        datum=None,
        bin_num=None,
        interval=None,
        units="metric",
        time_zone=time_zone,
    )


def test_invalid_time_zone_rejected() -> None:
    with pytest.raises(ValueError, match="[Tt]ime [Zz]one"):
        validate_params(
            product="water_temperature",
            datum=None,
            bin_num=None,
            interval=None,
            units="metric",
            time_zone="utc",
        )


# ---------------------------------------------------------------------------
# parse_known_date_formats
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "input_str,expected_dt",
    [
        ("20150101", datetime(2015, 1, 1, 0, 0)),
        ("20150101 12:34", datetime(2015, 1, 1, 12, 34)),
        ("01/15/2015", datetime(2015, 1, 15, 0, 0)),
        ("01/15/2015 23:59", datetime(2015, 1, 15, 23, 59)),
    ],
)
def test_parse_known_date_formats_accepts_all_documented_formats(
    input_str: str, expected_dt: datetime
) -> None:
    dt, fmt_str = parse_known_date_formats(input_str)
    assert dt == expected_dt
    # Second return value is always the canonical "%Y%m%d %H:%M" form
    assert fmt_str == expected_dt.strftime("%Y%m%d %H:%M")


@pytest.mark.parametrize(
    "bad_input",
    [
        "not-a-date",
        "2015-01-01",  # ISO dashes not supported
        "15/01/2015",  # day-first not supported
        "",  # empty string -- covers the historical UnboundLocalError path
    ],
)
def test_parse_known_date_formats_rejects_invalid(bad_input: str) -> None:
    """Invalid dates raise ValueError, never UnboundLocalError.

    The empty-string case is a regression guard: before the Tier 4
    rewrite, a `match = False` flag set only in the `except` branch
    could leave the flag unbound if the loop never hit the except --
    which could raise UnboundLocalError on certain edge cases.
    """
    with pytest.raises(ValueError):
        parse_known_date_formats(bad_input)
