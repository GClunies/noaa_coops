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
        end_date="20150331",
        product="water_level",
        datum="MLLW",
        units="metric",
        time_zone="gmt",
    )
    sample = df.head(1)

    assert sample.index[0] == pd.to_datetime("2015-01-01 00:00:00")
    assert sample["water_level"][0] == 1.799
    assert sample["sigma"][0] == 0.023
    assert sample["flags"][0] == "0,0,0,0"
    assert sample["QC"][0] == "v"


def test_invalid_datum():
    """Test error handling."""
    seattle = nc.Station(id="9447130")

    with pytest.raises(ValueError):
        seattle.get_data(
            begin_date="20150101",
            end_date="20150331",
            product="water_level",
            datum="navd88",  # Invalid datum
            units="metric",
            time_zone="gmt",
        )
