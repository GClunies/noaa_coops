"""Unit tests for the Derived Product API's parameter validator.

These exercise `_derived.validate_params` directly (no HTTP, no mocks --
the validator raises ValueError before any network call), plus one
public-boundary regression test that proves `get_derived_product` forwards
to the validator before touching the network. See `test_validators.py` for
the equivalent tests against `_products.validate_params`
(the non-derived Data API).
"""

from __future__ import annotations

import pytest
import noaa_coops._derived as _derived
from noaa_coops._derived import validate_params

BASE = {
    "product": "rfa_extreme_water_levels",
    "start_date": None,
    "end_date": None,
    "units": None,
    "datum": None,
}


@pytest.mark.parametrize(
    ("overrides", "match"),
    [
        ({"product": "not_a_real_product"}, "Invalid product"),
        ({"product": "htf_daily", "start_date": None, "end_date": None}, "required"),
        (
            {
                "product": "rfa_extreme_water_levels",
                "start_date": "20240201",
                "end_date": "20240101",
            },
            "must not be after",
        ),
        ({"product": "rfa_extreme_water_levels", "units": "furlongs"}, "Invalid units"),
        ({"product": "sea_level_trends", "datum": "MLLW"}, "does not accept"),
        ({"product": "top_ten_water_levels", "datum": "NOTREAL"}, "Invalid datum"),
        (
            {"product": "rfa_extreme_water_levels", "detail": "monthly_means"},
            "only supported for sea_level_trends",
        ),
        ({"product": "sea_level_trends", "detail": "bogus"}, "Invalid detail"),
        (
            {"product": "rfa_extreme_water_levels", "level_type": "low"},
            "only supported for extreme_water_levels",
        ),
        (
            {"product": "extreme_water_levels", "level_type": "bogus"},
            "Invalid level_type",
        ),
        (
            {"product": "rfa_extreme_water_levels", "scenario": "low"},
            "only supported for slr_projections",
        ),
        (
            {"product": "slr_projections", "scenario": "bogus"},
            "Invalid scenario",
        ),
        ({"product": "htf_annual", "year": 1750}, "Invalid year"),
        ({"product": "htf_annual", "year": 3000}, "Invalid year"),
        ({"product": "htf_annual", "year": "2020"}, "must be an int"),
        ({"product": "sea_level_trends", "year": 2020}, "only supported for HTF"),
        ({"product": "slr_projections", "year": 2020}, "only supported for HTF"),
        ({"product": "sea_level_trends", "affil": "us"}, r"Invalid affil.*Global.*US"),
        (
            {"product": "slr_projections", "affil": "bogus"},
            r"Invalid affil.*Global.*US",
        ),
        (
            {"product": "htf_annual", "affil": "US"},
            "`affil` is only supported",
        ),
        (
            {"product": "sea_level_trends", "projection_year": 2050},
            "`projection_year` is only supported for slr_projections",
        ),
        (
            {"product": "slr_projections", "projection_year": "2050"},
            "`projection_year` must be an int",
        ),
        (
            {"product": "sea_level_trends", "report_year": 2022},
            "`report_year` is only supported",
        ),
        (
            {"product": "slr_projections", "report_year": "2022"},
            "`report_year` must be an int",
        ),
        (
            {"product": "slr_projections", "projection_year": True},
            "`projection_year` must be an int",
        ),
        (
            {"product": "slr_projections", "report_year": True},
            "`report_year` must be an int",
        ),
    ],
)
def test_validate_params_rejects_bad_input(overrides, match):
    """Each bad input maps to a specific, distinguishable ValueError message."""
    kwargs = {**BASE, **overrides}
    with pytest.raises(ValueError, match=match):
        validate_params(**kwargs)


@pytest.mark.parametrize(
    "overrides",
    [
        {"product": "htf_daily", "start_date": "20240101", "end_date": "20240201"},
        {
            "product": "htf_daily",
            "start_date": "20240101",
            "end_date": "20240201",
            "datum": "MLLW",
        },
        {"product": "htf_monthly"},
        {"product": "htf_seasonal"},
        {"product": "htf_annual"},
        {"product": "sea_level_trends"},
        {"product": "sea_level_trends", "detail": "monthly_means"},
        {"product": "sea_level_trends", "detail": "events"},
        {"product": "sea_level_trends", "detail": "seasonal_cycle"},
        {"product": "slr_projections"},
        {"product": "slr_projections", "scenario": "all"},
        {"product": "slr_projections", "scenario": "low"},
        {"product": "slr_projections", "scenario": "intermediate-high"},
        {"product": "slr_projection_offsets"},
        {"product": "rfa_extreme_water_levels"},
        {"product": "rfa_extreme_water_levels", "datum": "MLLW"},
        {"product": "top_ten_water_levels", "datum": "MLLW"},
        {"product": "extreme_water_levels"},
        {"product": "extreme_water_levels", "level_type": "high"},
        {"product": "extreme_water_levels", "level_type": "low"},
        {"product": "htf_annual", "year": 2001},
        {"product": "htf_annual", "year": 1800},
        {"product": "sea_level_trends", "affil": "US"},
        {"product": "slr_projections", "affil": "Global"},
        {"product": "slr_projection_offsets", "affil": "US"},
        {"product": "slr_projections", "projection_year": 2050},
        {"product": "slr_projections", "report_year": 2022},
        {"product": "slr_projection_offsets", "report_year": 2022},
    ],
)
def test_valid_derived_params_accepted(overrides):
    """Every documented product, plus its detail/level_type/datum variants
    where applicable, passes validation with no error."""
    kwargs = {**BASE, **overrides}
    validate_params(**kwargs)  # should not raise


class _ExplodingSession:
    """Fails the test if any HTTP request is attempted."""

    def get(self, *args, **kwargs):
        raise AssertionError("HTTP request was made before validation failed")


class _FakeStation:
    id = "9447130"


def test_get_derived_product_validates_before_http(monkeypatch):
    """Public-boundary regression: get_derived_product must forward params to
    validate_params and raise before any HTTP request. Removing the validator
    forwarding in _derived.get_derived_product must fail this test."""
    monkeypatch.setattr(_derived, "_SESSION", _ExplodingSession())
    with pytest.raises(ValueError, match=r"Invalid affil.*Global.*US"):
        _derived.get_derived_product(
            station=_FakeStation(),
            product="sea_level_trends",
            affil="bogus",
        )
