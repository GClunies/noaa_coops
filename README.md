# noaa_coops

`noaa_coops` is a Python wrapper for NOAA CO-OPS Tides &amp; Currents [Data](https://tidesandcurrents.noaa.gov/api/) and [Metadata](https://tidesandcurrents.noaa.gov/mdapi/latest/) APIs.


This package is an evolution of [py_noaa](https://github.com/GClunies/py_noaa). The main addition being the creation of a `Station` class that is central to `noaa_coops`.

## Use
---

All data and metadata is handled using a `Station` class with methods for retriving metadata, observed data, and predicted data.

### Getting Metadata

Getting Metadata for any station is as simple as initiating a `Station` class object with the desired `stationid`. Station IDs can be found using mapping interface found at https://tidesandcurrents.noaa.gov/

```python
seattle = Station(9447130)
seattle.metadata
```

### Getting Observed or Predicted Data
Retrieving data for any station can be done using the `.get_data` method on any `Station` class object.

```python
seattle = Station(9447130)
seattle.get_data()
```
