# noaa_coops

[![Build Status](https://travis-ci.org/GClunies/noaa_coops.svg?branch=master)](https://travis-ci.org/GClunies/noaa_coops)
[![PyPI](https://img.shields.io/pypi/v/noaa_coops.svg)](https://pypi.python.org/pypi/noaa-coops)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/noaa_coops.svg)](https://pypi.python.org/pypi/noaa-coops)

A Python wrapper for the NOAA CO-OPS Tides &amp; Currents [Data](https://tidesandcurrents.noaa.gov/api/)
and [Metadata](https://tidesandcurrents.noaa.gov/mdapi/latest/) APIs.

## Use
---
### Stations
All data is accessed via a `Station` class object with methods for retrieving metadata, observed data, and predicted data. Stations are identified by a unique `stationid` which can be found using this [mapping interface](https://tidesandcurrents.noaa.gov/). You can initialize a `Station` object by passing the `stationid` as an argument:

```python
>>> import noaa_coops as nc
>>> seattle = nc.Station(9447130)
```

### Get Metadata
Station metadata is stored as a dictionary in the `.metadata` attribute of a `Station` object. Additionally, the keys of the metadata attribute dictionary are also assigned as attributes of the station object itself.

```python
>>> from pprint import pprint as print  # For pretty printing
>>> import noaa_coops as nc
>>> seattle = nc.Station(9447130)
>>> print(seattle.lat_lon['lat'])
47.601944
>>> print(seattle.lat_lon['lon'])
-122.339167
```

### Get Data Inventory
A description of a Station's data products and available dates can be accessed via the `.data_inventory` attribute of a `Station` object.

```python
>>> import noaa_coops as nc
>>> from pprint import pprint as print
>>> seattle = nc.Station(9447130)
>>> print(seattle.data_inventory)
{'Air Temperature': {'end_date': '2019-01-02 18:36',
                     'start_date': '1991-11-09 01:00'},
 'Barometric Pressure': {'end_date': '2019-01-02 18:36',
                         'start_date': '1991-11-09 00:00'},
 'Preliminary 6-Minute Water Level': {'end_date': '2023-02-05 19:54',
                                      'start_date': '2001-01-01 00:00'},
 'Verified 6-Minute Water Level': {'end_date': '2022-12-31 23:54',
                                   'start_date': '1995-06-01 00:00'},
 'Verified High/Low Water Level': {'end_date': '2022-12-31 23:54',
                                   'start_date': '1977-10-18 02:18'},
 'Verified Hourly Height Water Level': {'end_date': '2022-12-31 23:00',
                                        'start_date': '1899-01-01 00:00'},
 'Verified Monthly Mean Water Level': {'end_date': '2022-12-31 23:54',
                                       'start_date': '1898-12-01 00:00'},
 'Water Temperature': {'end_date': '2019-01-02 18:36',
                       'start_date': '1991-11-09 00:00'},
 'Wind': {'end_date': '2019-01-02 18:36', 'start_date': '1991-11-09 00:00'}}
```

### Get Data
Station data can be fetched using the `.get_data` method on a `Station` object. Data is returned as Pandas DataFrames for ease of use and analysis. Available data products can be found in [NOAA CO-OPS Data API](https://tidesandcurrents.noaa.gov/api/#products) docs.

`noaa_coops` currently supports the following data products:
- Currents
- Observed water levels
- Observed daily high and low water levels (use `product="high_low"`)
- Predicted water levels
- Predicted high and low water levels
- Winds
- Air pressure
- Air temperature
- Water temperature

The example below fetches water level data from the Seattle station (`stationid`=9447130) for a 3 month period.

```python
>>> import noaa_coops as nc
>>> seattle = nc.Station(9447130)
>>> df_water_levels = seattle.get_data(
...     begin_date="20150101",
...     end_date="20150331",
...     product="water_level",
...     datum="MLLW",
...     units="metric",
...     time_zone="gmt")
>>> df_water_levels.head()
                     water_level  sigma    flags QC
date_time
2015-01-01 00:00:00        1.799  0.023  0,0,0,0  v
2015-01-01 00:06:00        1.718  0.018  0,0,0,0  v
2015-01-01 00:12:00        1.639  0.013  0,0,0,0  v
2015-01-01 00:18:00        1.557  0.012  0,0,0,0  v
2015-01-01 00:24:00        1.473  0.014  0,0,0,0  v

```

## Development

### Requirements
This package and its dependencies are managed using [poetry](https://python-poetry.org/). To install the development environment for `noaa_coops`, first install poetry, then run (inside the repo):

```bash
poetry install
```

### TODO
Click [here](https://github.com/GClunies/py_noaa/issues) for a list of existing issues and to submit a new one.

### Contribution
Contributions are welcome, feel free to submit a pull request.
