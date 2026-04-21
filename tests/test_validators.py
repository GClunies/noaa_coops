"""Unit tests for `_check_product_params` and `_parse_known_date_formats`.

Both methods raise ValueError before any HTTP call, so these tests run
fully offline with no mocking — just construct a bare Station and
exercise the methods directly.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from noaa_coops.station import Station


def _bare_station() -> Station:
    """Build a Station without running __init__ (no HTTP)."""
    s = Station.__new__(Station)
    s.id = "9447130"
    s.units = "metric"
    return s


# ---------------------------------------------------------------------------
# _check_product_params: product validation
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
    station = _bare_station()
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
    station._check_product_params(
        product=product,
        datum=datum,
        bin_num=None,
        interval=None,
        units="metric",
        time_zone="gmt",
    )


def test_unknown_product_rejected() -> None:
    station = _bare_station()
    with pytest.raises(ValueError, match="Invalid product"):
        station._check_product_params(
            product="not_a_real_product",
            datum=None,
            bin_num=None,
            interval=None,
            units="metric",
            time_zone="gmt",
        )


# ---------------------------------------------------------------------------
# _check_product_params: datum
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "datum", ["MHHW", "MHW", "MTL", "MSL", "MLW", "MLLW", "NAVD", "STND", "IGLD", "LWD"]
)
def test_valid_datums_accepted(datum: str) -> None:
    station = _bare_station()
    station._check_product_params(
        product="water_level",
        datum=datum,
        bin_num=None,
        interval=None,
        units="metric",
        time_zone="gmt",
    )


def test_missing_datum_for_water_level_rejected() -> None:
    station = _bare_station()
    with pytest.raises(ValueError, match="No datum"):
        station._check_product_params(
            product="water_level",
            datum=None,
            bin_num=None,
            interval=None,
            units="metric",
            time_zone="gmt",
        )


def test_lowercase_datum_accepted() -> None:
    """Datums are normalized to uppercase before validation, so `mllw` is valid."""
    station = _bare_station()
    # No raise
    station._check_product_params(
        product="water_level",
        datum="mllw",
        bin_num=None,
        interval=None,
        units="metric",
        time_zone="gmt",
    )


def test_unknown_datum_rejected() -> None:
    station = _bare_station()
    with pytest.raises(ValueError, match="Invalid datum"):
        station._check_product_params(
            product="water_level",
            datum="nope",  # not in the allowlist
            bin_num=None,
            interval=None,
            units="metric",
            time_zone="gmt",
        )


# ---------------------------------------------------------------------------
# _check_product_params: units + time_zone
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("units", ["metric", "english"])
def test_valid_units_accepted(units: str) -> None:
    station = _bare_station()
    station._check_product_params(
        product="water_temperature",
        datum=None,
        bin_num=None,
        interval=None,
        units=units,
        time_zone="gmt",
    )


def test_invalid_units_rejected() -> None:
    station = _bare_station()
    with pytest.raises(ValueError, match="[Uu]nit"):
        station._check_product_params(
            product="water_temperature",
            datum=None,
            bin_num=None,
            interval=None,
            units="furlongs",
            time_zone="gmt",
        )


@pytest.mark.parametrize("time_zone", ["gmt", "lst", "lst_ldt"])
def test_valid_time_zones_accepted(time_zone: str) -> None:
    station = _bare_station()
    station._check_product_params(
        product="water_temperature",
        datum=None,
        bin_num=None,
        interval=None,
        units="metric",
        time_zone=time_zone,
    )


def test_invalid_time_zone_rejected() -> None:
    station = _bare_station()
    with pytest.raises(ValueError, match="[Tt]ime [Zz]one"):
        station._check_product_params(
            product="water_temperature",
            datum=None,
            bin_num=None,
            interval=None,
            units="metric",
            time_zone="utc",  # must be gmt, lst, or lst_ldt
        )


# ---------------------------------------------------------------------------
# _parse_known_date_formats
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
    station = _bare_station()
    dt, fmt_str = station._parse_known_date_formats(input_str)
    assert dt == expected_dt
    # Second return value is always the canonical "%Y%m%d %H:%M" form
    assert fmt_str == expected_dt.strftime("%Y%m%d %H:%M")


@pytest.mark.parametrize(
    "bad_input",
    [
        "not-a-date",
        "2015-01-01",  # ISO dashes not supported
        "15/01/2015",  # day-first not supported
        "",  # empty string — covers the latent UnboundLocalError path
    ],
)
def test_parse_known_date_formats_rejects_invalid(bad_input: str) -> None:
    """Invalid dates raise ValueError, never UnboundLocalError.

    The empty-string case exercises the historical ``match`` flag bug:
    before the fix, a string that fails on the first format iteration
    without ever reaching the flag assignment would raise UnboundLocalError
    instead of a proper ValueError.
    """
    station = _bare_station()
    with pytest.raises(ValueError):
        station._parse_known_date_formats(bad_input)
