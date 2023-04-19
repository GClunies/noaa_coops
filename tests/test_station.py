from __future__ import absolute_import

import pandas as pd
import pytest

import noaa_coops as nc


def test_station_metadata():
    """Test that the station object is created."""
    seattle = nc.Station(id="9447130")

    assert seattle.metadata["id"] == "9447130"
    assert seattle.id == "9447130"
    assert seattle.metadata["name"] == "Seattle"
    assert seattle.name == "Seattle"
    assert seattle.metadata["state"] == "WA"
    assert seattle.state == "WA"


def test_station_inventory():
    """Test that the station inventory is returned."""
    seattle = nc.Station(id="9447130")

    assert seattle.data_inventory["Wind"]["start_date"] == "1991-11-09 00:00"


def test_station_data():
    """Test that the station data is returned."""
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
    assert sample["v"][0] == 1.799
    assert sample["s"][0] == 0.023
    assert sample["f"][0] == "0,0,0,0"
    assert sample["q"][0] == "v"


def test_invalid_datum():
    """Test error handling."""
    seattle = nc.Station(id="9447130")

    with pytest.raises(ValueError):
        seattle.get_data(
            begin_date="20150101",
            end_date="20150331",
            product="water_level",
            datum="navd88",  # Invalid datum (should be navd or NAVD)
            units="metric",
            time_zone="gmt",
        )


def test_stations_from_bbox():
    """Test that stations from a bounding box are returned."""

    stations = nc.get_stations_from_bbox(
        lat_coords=[40.389, 40.9397],
        lon_coords=[-74.4751, -73.7432],
    )
    assert stations == ["8516945", "8518750", "8519483", "8531680"]


def test_stations_from_bbox_invalid_coorsds():
    """Test error is raised when invalid lat_coords passed.""" ""

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


def test_stations_from_bbox_invalid_lon():
    """Test error is raised when invalid lon_coords passed.""" ""

    with pytest.raises(ValueError):
        nc.get_stations_from_bbox(
            lat_coords=[40.389, 40.9397],
            lon_coords=[-74.4751, -73.7432, 100.0],
        )
