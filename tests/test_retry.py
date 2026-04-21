"""Retry-behavior tests for the module-level session in noaa_coops._http.

Uses the `responses` library to mock HTTP at the urllib3 transport layer
so we can verify the HTTPAdapter retry policy attached to `_SESSION`
actually fires on 429/5xx.
"""

from __future__ import annotations

import re

import pytest
import responses

import noaa_coops as nc
from noaa_coops._http import _SESSION
from noaa_coops.station import COOPSAPIError


DATA_GETTER_URL_RE = re.compile(
    r"https://api\.tidesandcurrents\.noaa\.gov/api/prod/datagetter\?.*"
)
STATIONS_LIST_URL = (
    "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations.json"
)


def _bare_station(station_id: str = "9447130", units: str = "metric"):
    """Construct a Station without calling __init__ (no network)."""
    from noaa_coops.station import Station

    s = Station.__new__(Station)
    s.id = station_id
    s.units = units
    return s


# ---------------------------------------------------------------------------
# Retry on 5xx
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("retryable_status", [429, 500, 502, 503, 504])
@responses.activate
def test_session_retries_on_transient_failures(retryable_status: int) -> None:
    """The session retries once on each of the standard transient status codes.

    Two registered responses: first one fails, second one succeeds. If retry
    works, _make_api_request returns the success body; if it doesn't, we'd
    see a COOPSAPIError.
    """
    responses.add(
        responses.GET,
        DATA_GETTER_URL_RE,
        status=retryable_status,
    )
    responses.add(
        responses.GET,
        DATA_GETTER_URL_RE,
        json={"data": [{"t": "2015-01-01 00:00", "v": "1.5"}]},
        status=200,
    )

    station = _bare_station()
    df = station._make_api_request(
        "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?"
        "begin_date=20150101&end_date=20150102&station=9447130&product=water_level",
        "water_level",
    )

    assert len(df) == 1
    # The failed attempt + the successful retry.
    assert len(responses.calls) == 2


@responses.activate
def test_session_gives_up_after_configured_retries() -> None:
    """Session retries a bounded number of times, then gives up (Retry.total=3).

    Four 503 responses in a row. The adapter attempts the initial request +
    3 retries = 4 total, then returns the last 503 response. _make_api_request
    treats that as COOPSAPIError.
    """
    for _ in range(5):  # more than Retry.total=3 attempts to cover the max
        responses.add(responses.GET, DATA_GETTER_URL_RE, status=503)

    station = _bare_station()
    with pytest.raises(COOPSAPIError):
        station._make_api_request(
            "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?"
            "begin_date=20150101&end_date=20150102",
            "water_level",
        )

    # 1 initial + 3 retries = 4 attempts.
    assert len(responses.calls) == 4


@responses.activate
def test_session_does_not_retry_on_non_retryable_4xx() -> None:
    """404 is not in status_forcelist — no retry, immediate COOPSAPIError."""
    responses.add(responses.GET, DATA_GETTER_URL_RE, status=404)

    station = _bare_station()
    with pytest.raises(COOPSAPIError):
        station._make_api_request(
            "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?x=1",
            "water_level",
        )

    assert len(responses.calls) == 1


# ---------------------------------------------------------------------------
# get_stations_from_bbox also benefits from the session
# ---------------------------------------------------------------------------


@responses.activate
def test_bbox_request_retries_on_transient_failure() -> None:
    """get_stations_from_bbox goes through the shared session, so it retries too."""
    responses.add(responses.GET, STATIONS_LIST_URL, status=503)
    responses.add(
        responses.GET,
        STATIONS_LIST_URL,
        json={"stations": [{"id": "A", "lat": 40.5, "lng": -74.0}]},
        status=200,
    )

    stations = nc.get_stations_from_bbox(
        lat_coords=[40.0, 41.0], lon_coords=[-74.5, -73.5]
    )

    assert stations == ["A"]
    assert len(responses.calls) == 2


# ---------------------------------------------------------------------------
# Session sanity
# ---------------------------------------------------------------------------


def test_session_has_retry_adapter_mounted() -> None:
    """The module-level session has a retry-enabled HTTPAdapter for https://."""
    adapter = _SESSION.get_adapter("https://api.tidesandcurrents.noaa.gov")
    assert adapter.max_retries.total == 3
    assert 429 in adapter.max_retries.status_forcelist
    assert 503 in adapter.max_retries.status_forcelist
