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
        ({"product": "extrfa", "start_date": "20240201", "end_date": "20240101"}, "must not be after"),
        ({"product": "extrfa", "units": "furlongs"}, "Invalid units"),
        ({"product": "sealvltrends", "datum": "MLLW"}, "does not accept"),
        ({"product": "toptenwaterlevels", "datum": "NOTREAL"}, "Invalid datum"),
        ({"product": "extrfa", "detail": "monthly_means"}, "only supported for sealvltrends"),
        ({"product": "sealvltrends", "detail": "bogus"}, "Invalid detail"),
        ({"product": "extrfa", "level_type": "low"}, "only supported for extremewaterlevels"),
        ({"product": "extremewaterlevels", "level_type": "bogus"}, "Invalid level_type"),
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
        {"product": "htf_daily", "start_date": "20240101", "end_date": "20240201", "datum": "MLLW"},
        {"product": "htf_monthly"},
        {"product": "htf_seasonal"},
        {"product": "htf_annual"},
        {"product": "sealvltrends"},
        {"product": "sealvltrends", "detail": "monthly_means"},
        {"product": "sealvltrends", "detail": "events"},
        {"product": "sealvltrends", "detail": "seasonal_cycle"},
        {"product": "slr_projections"},
        {"product": "slr_projectionOffsets"},
        {"product": "extrfa"},
        {"product": "extrfa", "datum": "MLLW"},
        {"product": "toptenwaterlevels", "datum": "MLLW"},
        {"product": "extremewaterlevels"},
        {"product": "extremewaterlevels", "level_type": "high"},
        {"product": "extremewaterlevels", "level_type": "low"},
    ],
)
def test_valid_derived_params_accepted(overrides):
    """Every documented product, plus its detail/level_type/datum variants
    where applicable, passes validation with no error."""
    kwargs = {**BASE, **overrides}
    validate_params(**kwargs)  # should not raise