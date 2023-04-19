# noaa_coops

[![PyPI](https://img.shields.io/pypi/v/noaa_coops.svg)](https://pypi.python.org/pypi/noaa-coops)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/noaa_coops.svg)](https://pypi.python.org/pypi/noaa-coops)

A Python wrapper for the NOAA CO-OPS Tides &amp; Currents [Data](https://tidesandcurrents.noaa.gov/api/)
and [Metadata](https://tidesandcurrents.noaa.gov/mdapi/latest/) APIs.

## Installation
This package is distributed via [PyPi](https://pypi.org/project/noaa-coops/) and can be installed using , `pip`, `poetry`, etc.
```bash
# Install with pip
❯ pip install noaa_coops

# Install with poetry
❯ poetry add noaa_coops
```

## Getting Started

### Stations
Data is accessed via `Station` class objects. Each station is uniquely identified by an `id`. To initialize a `Station` object, run:

```python
>>> from noaa_coops import Station
>>> seattle = Station(id="9447130")  # Create Station object for Seattle (ID = 9447130)
```

Stations and their IDs can be found using the Tides & Currents [mapping interface](https://tidesandcurrents.noaa.gov/). Alternatively, you can search for stations in a bounding box using the `get_stations_from_bbox` function, which will return a list of stations found in the box (if any).
```python
>>> from pprint import pprint
>>> from noaa_coops import Station, get_stations_from_bbox
>>> stations = get_stations_from_bbox(lat_coords=[40.389, 40.9397], lon_coords=[-74.4751, -73.7432])
>>> pprint(stations)
['8516945', '8518750', '8519483', '8531680']
>>> station_one = Station(id="8516945")
>>> pprint(station_one.name)
'Kings Point'
```

### Metadata
Station metadata is stored in the `.metadata` attribute of a `Station` object. Additionally, the keys of the metadata attribute dictionary are also assigned as attributes of the station object itself.

```python
>>> from pprint import pprint
>>> from noaa_coops import Station
>>> seattle = Station(id="9447130")
>>> pprint(list(seattle.metadata.items())[:5])                   # Print first 3 items in metadata
[('tidal', True), ('greatlakes', False), ('shefcode', 'EBSW1')]  # Metadata dictionary can be very long
>>> pprint(seattle.lat_lon['lat'])                               # Print latitude
47.601944
>>> pprint(seattle.lat_lon['lon'])                               # Print longitude
-122.339167
```

### Data Inventory
A description of a Station's data products and available dates can be accessed via the `.data_inventory` attribute of a `Station` object.

```python
>>> from noaa_coops import Station
>>> from pprint import pprint
>>> seattle = Station(id="9447130")
>>> pprint(seattle.data_inventory)
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

### Data Retrieval
Available data products can be found in NOAA CO-OPS Data API docs.

Station data can be fetched using the `.get_data` method on a `Station` object. Data is returned as a Pandas [DataFrame](https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.html) for ease of use and analysis. DataFrame columns are named according to the NOAA CO-OPS API [docs](https://api.tidesandcurrents.noaa.gov/api/prod/responseHelp.html), with the `t` column (timestamp) set as the DataFrame index.

The example below fetches water level data from the Seattle station (id=9447130) for a 1 month period. The corresponding [web output](https://tidesandcurrents.noaa.gov/waterlevels.html?id=9447130&units=metric&bdate=20150101&edate=20150131&timezone=GMT&datum=MLLW) is shown below the code as a reference.

```python
>>> from noaa_coops import Station
>>> seattle = Station(id="9447130")
>>> df_water_levels = seattle.get_data(
...     begin_date="20150101",
...     end_date="20150131",
...     product="water_level",
...     datum="MLLW",
...     units="metric",
...     time_zone="gmt")
>>> df_water_levels.head()
                         v      s        f  q
t
2015-01-01 00:00:00  1.799  0.023  0,0,0,0  v
2015-01-01 00:06:00  1.718  0.018  0,0,0,0  v
2015-01-01 00:12:00  1.639  0.013  0,0,0,0  v
2015-01-01 00:18:00  1.557  0.012  0,0,0,0  v
2015-01-01 00:24:00  1.473  0.014  0,0,0,0  v

```

![image](https://user-images.githubusercontent.com/28986302/233147224-765fbe05-372c-40f3-8bbe-4102536e7ff3.png)


## Development

### Requirements
This package and its dependencies are managed using [poetry](https://python-poetry.org/). To install the development environment for `noaa_coops`, first install poetry, then run (inside the repo):

```bash
poetry install
```

### TODO
Click [here](https://github.com/GClunies/noaa_coops/issues) for a list of existing issues and to submit a new one.

### Contribution
Contributions are welcome, feel free to submit a pull request.
