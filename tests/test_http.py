"""Mock-based tests for HTTP hardening in noaa_coops.station.

These tests verify:
- All `requests.get` calls pass a `timeout=` kwarg
- `get_data_inventory` catches narrow exceptions (not bare `except:`)
- `KeyboardInterrupt` / `SystemExit` are NOT swallowed
- HTTP non-200 raises `COOPSAPIError` (already implemented; regression test)

No network access required.
"""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

import pytest
import requests
import zeep

import noaa_coops as nc
from noaa_coops._http import DEFAULT_TIMEOUT
from noaa_coops.station import COOPSAPIError, Station


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _bare_station(station_id: str = "9447130", units: str = "metric") -> Station:
    """Construct a Station without calling __init__ (no network).

    Used by tests that exercise specific methods in isolation without paying
    the cost of a full construction round-trip.

    NOTE: keep in sync with Station.__init__ if new instance attributes are
    added that the exercised method relies on.
    """
    s = Station.__new__(Station)
    s.id = station_id
    s.units = units
    return s


@pytest.fixture
def metadata_response() -> MagicMock:
    """Fake mdapi response shaped like a Seattle water-level station."""
    resp = MagicMock(spec=requests.Response)
    resp.status_code = 200
    resp.json.return_value = {
        "stations": [
            {
                "id": "9447130",
                "name": "Seattle",
                "state": "WA",
                "lat": 47.6026,
                "lng": -122.3393,
                "affiliations": "",
                "benchmarks": {},
                "datums": [],
                "details": {},
                "disclaimers": {},
                "floodlevels": {},
                "greatlakes": False,
                "harmonicConstituents": [],
                "nearby": [],
                "notices": [],
                "observedst": True,
                "portscode": None,
                "products": [],
                "sensors": [],
                "shefcode": "STLW1",
                "stormsurge": False,
                "tidal": True,
                "tideType": "Mixed",
                "timezone": "LST/LDT",
                "timezonecorr": -8,
            }
        ]
    }
    return resp


@pytest.fixture
def bbox_response() -> MagicMock:
    """Fake mdapi station-list response with two stations."""
    resp = MagicMock(spec=requests.Response)
    resp.status_code = 200
    resp.json.return_value = {
        "stations": [
            {"id": "A", "lat": 40.5, "lng": -74.0},
            {"id": "B", "lat": 41.0, "lng": -74.2},
        ]
    }
    return resp


def _assert_timeout(mock_get: MagicMock) -> None:
    """Common assertion: the first call to requests.get received DEFAULT_TIMEOUT.

    Inspects `call_args_list[0]` rather than `call_args` (which returns the
    last call) so future code that makes multiple calls cannot hide a missing
    timeout on an earlier call.
    """
    assert mock_get.call_args_list, "requests.get was never called"
    call = mock_get.call_args_list[0]
    assert "timeout" in call.kwargs, "requests.get called without timeout="
    assert call.kwargs["timeout"] == DEFAULT_TIMEOUT


# ---------------------------------------------------------------------------
# Timeout tests
# ---------------------------------------------------------------------------


def test_default_timeout_constant_exists() -> None:
    """DEFAULT_TIMEOUT is a (connect, read) tuple of positive floats."""
    assert isinstance(DEFAULT_TIMEOUT, tuple)
    assert len(DEFAULT_TIMEOUT) == 2
    connect, read = DEFAULT_TIMEOUT
    assert connect > 0
    assert read > 0


def test_get_stations_from_bbox_passes_timeout(bbox_response: MagicMock) -> None:
    """get_stations_from_bbox must pass timeout= to requests.get."""
    with patch("noaa_coops.station._SESSION.get") as mock_get:
        mock_get.return_value = bbox_response
        nc.get_stations_from_bbox(lat_coords=[40.0, 41.5], lon_coords=[-74.5, -73.5])
    _assert_timeout(mock_get)


def test_get_metadata_passes_timeout(metadata_response: MagicMock) -> None:
    """Station.__init__ -> get_metadata must pass timeout= to requests.get."""
    with (
        patch("noaa_coops.station._SESSION.get") as mock_get,
        patch("noaa_coops.station.zeep.Client") as mock_zeep,
    ):
        mock_get.return_value = metadata_response
        # Force get_data_inventory to fail fast; verified separately below.
        mock_zeep.side_effect = zeep.exceptions.Fault("test")
        nc.Station(id="9447130")

    _assert_timeout(mock_get)


def test_make_api_request_passes_timeout() -> None:
    """_make_api_request must pass timeout= to requests.get."""
    station = _bare_station()

    mock_resp = MagicMock(spec=requests.Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"data": [{"t": "2015-01-01 00:00", "v": "1.5"}]}

    with patch("noaa_coops.station._SESSION.get") as mock_get:
        mock_get.return_value = mock_resp
        station._make_api_request("https://example.com/data", "water_level")

    _assert_timeout(mock_get)


# ---------------------------------------------------------------------------
# Narrow-exception tests (no more bare `except:`)
# ---------------------------------------------------------------------------


def test_inventory_handles_missing_parameter_key(
    metadata_response: MagicMock,
) -> None:
    """SOAP responses without a 'parameter' key must not crash Station construction.

    Guards against `KeyError` raised by the `response["parameter"]` subscript
    inside `get_data_inventory`. The previous narrow catch in `__init__` did
    not cover `KeyError`.
    """
    mock_service = MagicMock()
    mock_service.getDataInventory.return_value = {}  # no "parameter" key
    mock_client = MagicMock()
    mock_client.service = mock_service

    with (
        patch("noaa_coops.station._SESSION.get") as mock_get,
        patch("noaa_coops.station.zeep.Client", return_value=mock_client),
    ):
        mock_get.return_value = metadata_response
        station = nc.Station(id="9447130")

    assert station.data_inventory == {}


@pytest.mark.parametrize(
    "zeep_error",
    [
        pytest.param(
            zeep.exceptions.TransportError("network down"), id="transport-error"
        ),
        pytest.param(zeep.exceptions.Fault("soap-fault"), id="soap-fault"),
        pytest.param(zeep.exceptions.XMLParseError("bad xml"), id="xml-parse-error"),
    ],
)
def test_inventory_swallows_zeep_errors_gracefully(
    metadata_response: MagicMock, zeep_error: Exception
) -> None:
    """Zeep errors (transport, fault, parse) degrade to an empty dict sentinel."""
    with (
        patch("noaa_coops.station._SESSION.get") as mock_get,
        patch("noaa_coops.station.zeep.Client") as mock_zeep,
    ):
        mock_get.return_value = metadata_response
        mock_zeep.side_effect = zeep_error

        station = nc.Station(id="9447130")

    assert station.data_inventory == {}


def test_inventory_swallows_requests_errors_gracefully(
    metadata_response: MagicMock,
) -> None:
    """If the underlying requests layer raises, inventory fetch degrades."""
    with (
        patch("noaa_coops.station._SESSION.get") as mock_get,
        patch("noaa_coops.station.zeep.Client") as mock_zeep,
    ):
        mock_get.return_value = metadata_response
        mock_zeep.side_effect = requests.ConnectionError("boom")

        station = nc.Station(id="9447130")

    assert station.data_inventory == {}


@pytest.mark.parametrize(
    "system_exc",
    [
        pytest.param(KeyboardInterrupt(), id="keyboard-interrupt"),
        pytest.param(SystemExit(1), id="system-exit"),
    ],
)
def test_inventory_does_not_swallow_system_exceptions(
    metadata_response: MagicMock, system_exc: BaseException
) -> None:
    """KeyboardInterrupt / SystemExit must propagate, not be absorbed."""
    expected_type = type(system_exc)
    with (
        patch("noaa_coops.station._SESSION.get") as mock_get,
        patch("noaa_coops.station.zeep.Client") as mock_zeep,
    ):
        mock_get.return_value = metadata_response
        mock_zeep.side_effect = system_exc

        with pytest.raises(expected_type):
            nc.Station(id="9447130")


def test_inventory_logs_warning_on_failure(
    metadata_response: MagicMock, caplog: pytest.LogCaptureFixture
) -> None:
    """Inventory fetch failures emit a WARNING (not DEBUG, not silent)."""
    with (
        patch("noaa_coops.station._SESSION.get") as mock_get,
        patch("noaa_coops.station.zeep.Client") as mock_zeep,
        caplog.at_level(logging.WARNING, logger="noaa_coops.station"),
    ):
        mock_get.return_value = metadata_response
        mock_zeep.side_effect = zeep.exceptions.TransportError("nope")
        nc.Station(id="9447130")

    warnings = [r for r in caplog.records if r.name == "noaa_coops.station"]
    assert warnings, "No warning emitted on inventory fetch failure"


@pytest.mark.parametrize(
    "station_id",
    [
        pytest.param("s09010", id="alphanumeric-currents"),
        pytest.param("PUG1515", id="alphanumeric-ports"),
        pytest.param("123456", id="six-digit-numeric"),
        pytest.param("12345678", id="eight-digit-numeric"),
    ],
)
def test_inventory_skipped_for_non_7digit_ids(
    station_id: str, caplog: pytest.LogCaptureFixture
) -> None:
    """Non-7-digit IDs skip the SOAP call -- no network, no WARNING, one INFO.

    NOAA's SOAP DataInventory service only accepts 7-digit numeric IDs and
    rejects everything else with a deterministic "Wrong Station ID" fault.
    Constructing a Station with such an ID must not call zeep and must not
    emit a WARNING (avoids noise for every currents/PORTS station), but
    should emit a single INFO-level message so users who raise their log
    level can see why data_inventory is empty.
    """
    with (
        patch("noaa_coops.station.populate_metadata"),
        patch("noaa_coops.station.zeep.Client") as mock_zeep,
        caplog.at_level(logging.INFO, logger="noaa_coops.station"),
    ):
        station = nc.Station(id=station_id)

    assert station.data_inventory == {}
    assert not mock_zeep.called, "SOAP client must not be instantiated"

    records = [r for r in caplog.records if r.name == "noaa_coops.station"]
    assert not any(r.levelno >= logging.WARNING for r in records), (
        "Skip path must not emit WARNING or higher"
    )
    info_records = [r for r in records if r.levelno == logging.INFO]
    assert len(info_records) == 1, "Expected exactly one INFO message on skip"
    assert station_id in info_records[0].getMessage()


# ---------------------------------------------------------------------------
# COOPSAPIError on HTTP non-200 (regression)
# ---------------------------------------------------------------------------


def test_bbox_raises_on_http_error() -> None:
    """get_stations_from_bbox raises COOPSAPIError for non-200 responses."""
    bad_resp = MagicMock(spec=requests.Response)
    bad_resp.status_code = 503
    bad_resp.reason = "Service Unavailable"

    with patch("noaa_coops.station._SESSION.get") as mock_get:
        mock_get.return_value = bad_resp
        with pytest.raises(COOPSAPIError):
            nc.get_stations_from_bbox(
                lat_coords=[40.0, 41.5], lon_coords=[-74.5, -73.5]
            )


def test_make_api_request_raises_on_http_error() -> None:
    """_make_api_request raises COOPSAPIError for non-200 responses."""
    station = _bare_station()

    bad_resp = MagicMock(spec=requests.Response)
    bad_resp.status_code = 500
    bad_resp.reason = "Internal Server Error"

    with patch("noaa_coops.station._SESSION.get") as mock_get:
        mock_get.return_value = bad_resp
        with pytest.raises(COOPSAPIError):
            station._make_api_request("https://example.com/data", "water_level")
