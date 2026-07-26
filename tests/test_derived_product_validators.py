"""Unit tests for the Derived Product API's parameter validator.

These exercise `_derived.validate_params` directly. No HTTP, no mocks --
the validator raises ValueError before any network call. See
`test_validators.py` for the equivalent tests against `_products.validate_params`
(the non-derived Data API).
"""

from __future__ import annotations

import pytest
from noaa_coops._derived import validate_params

BASE = {
    "product": "extrfa",
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
                "product": "extrfa",
                "start_date": "20240201",
                "end_date": "20240101",
            },
            "must not be after",
        ),
        ({"product": "extrfa", "units": "furlongs"}, "Invalid units"),
        ({"product": "sea_level_trends", "datum": "MLLW"}, "does not accept"),
        ({"product": "top_ten_water_levels", "datum": "NOTREAL"}, "Invalid datum"),
        (
            {"product": "extrfa", "detail": "monthly_means"},
            "only supported for sea_level_trends",
        ),
        ({"product": "sea_level_trends", "detail": "bogus"}, "Invalid detail"),
        (
            {"product": "extrfa", "level_type": "low"},
            "only supported for extreme_water_levels",
        ),
        (
            {"product": "extreme_water_levels", "level_type": "bogus"},
            "Invalid level_type",
        ),
        (
            {"product": "extrfa", "scenario": "low"},
            "only supported for slr_projections",
        ),
        (
            {"product": "slr_projections", "scenario": "bogus"},
            "Invalid scenario",
        ),
        ({"product": "htf_annual", "year": 1750}, "Invalid year"),
        ({"product": "htf_annual", "year": 3000}, "Invalid year"),
        ({"product": "htf_annual", "year": "2020"}, "must be an int"),
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
        {"product": "extrfa"},
        {"product": "extrfa", "datum": "MLLW"},
        {"product": "top_ten_water_levels", "datum": "MLLW"},
        {"product": "extreme_water_levels"},
        {"product": "extreme_water_levels", "level_type": "high"},
        {"product": "extreme_water_levels", "level_type": "low"},
        {"product": "htf_annual", "year": 2001},
        {"product": "htf_annual", "year": 1800},
    ],
)
def test_valid_derived_params_accepted(overrides):
    """Every documented product, plus its detail/level_type/datum variants
    where applicable, passes validation with no error."""
    kwargs = {**BASE, **overrides}
    validate_params(**kwargs)  # should not raise
