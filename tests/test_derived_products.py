"""Integration tests for the public Station Derived Product API.

These use VCR cassettes recorded against the live NOAA CO-OPS API. Replay
is offline and deterministic. Re-record with:
    uv run pytest tests/test_station.py --record-mode=rewrite

The one test still gated on live network is ``test_station_inventory``
-- the SOAP ``DataInventory`` endpoint is awkward to cassette reliably
(zeep caches WSDL out-of-band from VCR), so it runs nightly instead of
on every PR. See ``.github/workflows/nightly.yml``.
"""

from __future__ import annotations

import pytest

import noaa_coops as nc
from noaa_coops._derived import build_dpapi_url

DERIVED_PRODUCT_MATRIX = [
    pytest.param(
        "top_ten_water_levels",
        "9447130",
        {"datum": "MLLW"},
        {
            "stationId",
            "stationName",
            "peakDate",
            "peakTime",
            "height",
            "datum",
            "category",
            "event",
            "source",
        },
        id="top_ten_wls",
    ),
    pytest.param(
        "rfa_extreme_water_levels",
        "1611347",
        {},
        {
            "rl",
            "value",
            "ci_low",
            "ci_high",
            "stationId",
            "name",
            "lat",
            "lon",
            "tidalEpoch",
            "gridNum",
            "gridLat",
            "gridLong",
            "region",
            "startDate",
            "endDate",
            "validDays",
            "totalDays",
            "percentValidDays",
            "probabilitiesUnit",
            "long_term_flag",
            "short_term_flag",
            "localUIndex_value",
            "localUIndex_unit",
            "localUTrend_value",
            "localUTrend_unit",
        },
        id="rfa_extreme_water_levels",
    ),
    pytest.param(
        "sea_level_trends",
        "1611400",
        {"detail": "seasonal_cycle"},
        {
            "month",
            "seasonalVar",
            "seasonalErr",
            "stationId",
            "stationName",
            "affil",
            "trendUnits",
            "seasonalUnits",
            "seasonalAverage",
            "latitude",
            "longitude",
            "trendType",
            "autoregressive",
            "autoregressiveError",
            "trend",
            "trendError",
            "y2000_offset",
            "startDate",
            "endDate",
        },
        id="sea_level_trends_seasonal",
    ),
    pytest.param(
        "htf_annual",
        "1611400",
        {"year": 2001},
        {
            "stnId",
            "stnName",
            "lat",
            "lon",
            "year",
            "majCount",
            "modCount",
            "minCount",
            "nanCount",
            "percent_completeness",
        },
        id="htf_annual",
    ),
]


@pytest.mark.vcr
@pytest.mark.parametrize(
    ("product", "station_id", "kwargs", "expected_cols"), DERIVED_PRODUCT_MATRIX
)
def test_derived_products(
    product: str,
    station_id: str,
    kwargs: dict,
    expected_cols: set[str],
) -> None:
    """Each product returns a non-empty, number-indexed DataFrame whose
    columns include the product-specific fields."""
    station = nc.Station(id=station_id)
    df = station.get_derived_product(product=product, **kwargs)

    assert not df.empty, f"{product} returned an empty DataFrame"
    missing = expected_cols - set(df.columns)
    assert not missing, f"{product} missing expected columns: {missing}"


def test_sea_level_trends_monthly_means_requests_single_trend_type():
    """monthly_means always requests trendType=SINGLE (see _derived.build_dpapi_url) --
    all 510 stations report a single trend type as of the check documented there.
    `trendType` is a request param for this detail"""

    url = build_dpapi_url(
        product="sea_level_trends",
        station_id="1611400",
        detail="monthly_means",
    )
    assert "trendType=SINGLE" in url


@pytest.mark.vcr
def test_sea_level_trends_monthly_means() -> None:
    """Unlike test_derived_products, this checks for an exact column set (`==`),
    not just presence of the expected ones."""
    station = nc.Station(id="1611400")
    df = station.get_derived_product(product="sea_level_trends", detail="monthly_means")

    expected_cols = {
        "year",
        "month",
        "meanDate",
        "mslDeseasonalized",
        "msl",
        "trendLine",
        "upperConfidence",
        "lowerConfidence",
    }
    assert not df.empty
    assert set(df.columns) == expected_cols
