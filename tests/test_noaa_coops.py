"""Unit tests for API wrapper."""
from __future__ import absolute_import
import numpy as np
import pytest
import noaa_coops as nc


def test_error_handling() -> None:
    """Test if script raises error when given an invalid datum for a station."""
    seattle = nc.Station(9447130)
    with pytest.raises(ValueError):
        seattle.get_data(
            begin_date="20150101",
            end_date="20150331",
            product="water_level",
            datum="navd88",  # this is an invalid datum
            units="metric",
            time_zone="gmt",
        )


def test_bbox() -> None:
    """Test bbox script."""
    bbox = [-74.4751, 40.389, -73.7432, 40.9397]
    assert np.all(
        [
            ['8516945', '8518750', '8519483', '8531680']
            == nc.stationid_from_bbox(bbox)
        ]
    )
