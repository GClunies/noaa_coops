from __future__ import absolute_import

import pytest

import noaa_coops as nc


def test_error_handling():
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
