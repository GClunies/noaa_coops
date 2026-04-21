"""Integration tests for the public Station API.

These use VCR cassettes recorded against the live NOAA CO-OPS API. Replay
is offline and deterministic. Re-record with:
    uv run pytest tests/test_station.py --record-mode=rewrite

The one test still gated on live network is ``test_station_inventory``
-- the SOAP ``DataInventory`` endpoint is awkward to cassette reliably
(zeep caches WSDL out-of-band from VCR), so it runs nightly instead of
on every PR. See ``.github/workflows/nightly.yml``.
"""

from __future__ import annotations

import pandas as pd
import pytest

import noaa_coops as nc


@pytest.mark.vcr
def test_station_metadata() -> None:
    """Station construction populates metadata fields from NOAA mdapi."""
    seattle = nc.Station(id="9447130")

    assert seattle.metadata["id"] == "9447130"
    assert seattle.id == "9447130"
    assert seattle.metadata["name"] == "Seattle"
    assert seattle.name == "Seattle"
    assert seattle.metadata["state"] == "WA"
    assert seattle.state == "WA"


@pytest.mark.live
def test_station_inventory() -> None:
    """Data inventory populated from the SOAP endpoint -- live only."""
    seattle = nc.Station(id="9447130")

    assert "Wind" in seattle.data_inventory
    assert "start_date" in seattle.data_inventory["Wind"]


@pytest.mark.vcr
def test_station_data() -> None:
    """Station.get_data returns a DataFrame with the expected shape."""
    seattle = nc.Station(id="9447130")
    df = seattle.get_data(
        begin_date="20150101",
        end_date="20150131",
        product="water_level",
        datum="MLLW",
        units="metric",
        time_zone="gmt",
    )
    sample = df.head(1)

    assert sample.index[0] == pd.to_datetime("2015-01-01 00:00:00")
    # Columns returned by the datagetter for water_level
    for col in ("v", "s", "f", "q"):
        assert col in df.columns


@pytest.mark.vcr
def test_invalid_datum() -> None:
    """Invalid datum raises ValueError before any datagetter call."""
    seattle = nc.Station(id="9447130")

    with pytest.raises(ValueError):
        seattle.get_data(
            begin_date="20150101",
            end_date="20150331",
            product="water_level",
            datum="navd88",  # lowercase -- valid value would be "NAVD"
            units="metric",
            time_zone="gmt",
        )


@pytest.mark.vcr
def test_stations_from_bbox() -> None:
    """Bounding-box query returns stations in the given lat/lon window."""
    stations = nc.get_stations_from_bbox(
        lat_coords=[40.389, 40.9397],
        lon_coords=[-74.4751, -73.7432],
    )
    # NY Harbor / Sandy Hook region has historically had 4 stations here.
    # The exact ID set drifts occasionally as NOAA commissions/decommissions
    # instruments, so we assert shape rather than a hardcoded list.
    assert len(stations) >= 3
    assert all(isinstance(s, str) and s.isdigit() for s in stations)


@pytest.mark.vcr
def test_stations_from_bbox_invalid_coords() -> None:
    """Error is raised when lat_coords or lon_coords are not of length 2."""
    with pytest.raises(ValueError):
        nc.get_stations_from_bbox(
            lat_coords=[40.389, 40.9397, 99.0],
            lon_coords=[-74.4751, -73.7432],
        )

    with pytest.raises(ValueError):
        nc.get_stations_from_bbox(
            lat_coords=[40.389, 40.9397],
            lon_coords=[-74.4751, -73.7432, -76.1234],
        )
