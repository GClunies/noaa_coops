"""Unit tests for interval-specific request limits and interval defaults.

Pins the two behaviors introduced in PR #110:
- 1-minute predictions cap the per-request window at 30 days
  (``INTERVAL_LIMIT_OVERRIDES`` in ``noaa_coops._products``).
- ``daily_max_min`` defaults ``interval`` to ``"h"`` when omitted in
  ``Station.get_data``.

No live network calls -- HTTP is mocked with `responses`.
"""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import pytest
import responses

from noaa_coops._products import get_max_days
from noaa_coops.station import Station

DATA_GETTER_URL_RE = __import__("re").compile(
    r"https://api\.tidesandcurrents\.noaa\.gov/api/prod/datagetter\?.*"
)


# ---------------------------------------------------------------------------
# get_max_days: interval-specific overrides
# ---------------------------------------------------------------------------


def test_predictions_one_minute_interval_capped_at_30_days() -> None:
    """1-minute predictions are much denser, so the window drops to 30 days."""
    assert get_max_days("predictions", "1") == 30


def test_predictions_hourly_interval_uses_product_limit() -> None:
    """Non-overridden intervals fall back to PRODUCT_LIMITS (365 days)."""
    assert get_max_days("predictions", "h") == 365


@pytest.mark.parametrize("interval", [None, "hilo", "6", "60"])
def test_predictions_other_intervals_use_product_limit(
    interval: str | None,
) -> None:
    assert get_max_days("predictions", interval) == 365


def test_predictions_integer_interval_matches_string_override() -> None:
    """Integer intervals are normalized to strings before the override lookup."""
    assert get_max_days("predictions", 1) == 30


# ---------------------------------------------------------------------------
# Station.get_data: daily_max_min interval default
# ---------------------------------------------------------------------------


def _bare_station(station_id: str = "9447130") -> Station:
    s = Station.__new__(Station)
    s.id = station_id
    s.units = "metric"
    return s


def _daily_max_min_body() -> dict:
    """Minimal datagetter success payload for a daily_max_min request."""
    return {
        "data": [
            {
                "dailyMax": [
                    {
                        "dateHourly": "2015-01-01",
                        "timeHourly": "12:00",
                        "valueHourly": "2.50",
                        "pcCompleteHourly": "100",
                        "flagHourly": "0,0",
                    }
                ],
            }
        ],
    }


@responses.activate
def test_daily_max_min_defaults_interval_to_hourly() -> None:
    """Omitting `interval` for daily_max_min requests hourly data."""
    responses.add(
        responses.GET,
        DATA_GETTER_URL_RE,
        json=_daily_max_min_body(),
        status=200,
    )

    station = _bare_station()
    station.get_data(
        begin_date="20150101",
        end_date="20150105",
        product="daily_max_min",
        datum="STND",
        units="metric",
        time_zone="gmt",
    )

    assert len(responses.calls) == 1
    query = parse_qs(urlparse(responses.calls[0].request.url).query)
    assert query["interval"] == ["h"]


@responses.activate
def test_daily_max_min_explicit_interval_not_overridden() -> None:
    """An explicit interval passes through unchanged."""
    responses.add(
        responses.GET,
        DATA_GETTER_URL_RE,
        json=_daily_max_min_body(),
        status=200,
    )

    station = _bare_station()
    station.get_data(
        begin_date="20150101",
        end_date="20150105",
        product="daily_max_min",
        datum="STND",
        interval="6",
        units="metric",
        time_zone="gmt",
    )

    assert len(responses.calls) == 1
    query = parse_qs(urlparse(responses.calls[0].request.url).query)
    assert query["interval"] == ["6"]
