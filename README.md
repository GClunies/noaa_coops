# noaa_coops

[![CI](https://github.com/GClunies/noaa_coops/actions/workflows/pull_request.yml/badge.svg)](https://github.com/GClunies/noaa_coops/actions/workflows/pull_request.yml)
[![PyPI](https://img.shields.io/pypi/v/noaa-coops.svg)](https://pypi.python.org/pypi/noaa-coops)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/noaa-coops.svg)](https://pypi.python.org/pypi/noaa-coops)
[![License: Apache 2.0](https://img.shields.io/badge/license-Apache_2.0-blue.svg)](https://github.com/GClunies/noaa_coops/blob/main/LICENSE)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![pre-commit.ci status](https://results.pre-commit.ci/badge/github/GClunies/noaa_coops/main.svg)](https://results.pre-commit.ci/latest/github/GClunies/noaa_coops/main)

A Python wrapper for the NOAA CO-OPS Tides & Currents
[Data](https://tidesandcurrents.noaa.gov/api/) and
[Metadata](https://tidesandcurrents.noaa.gov/mdapi/latest/) APIs.

## Installation

Supported on Python **3.10, 3.11, 3.12, and 3.13**.

```bash
uv add noaa-coops
```

Or with pip:

```bash
pip install noaa-coops
```

## Getting started

### Stations

Data is accessed via `Station` objects identified by a NOAA station `id`:

```python
>>> from noaa_coops import Station
>>> seattle = Station(id="9447130")  # Seattle, WA
```

Find station IDs via the NOAA
[Tides & Currents mapping interface](https://tidesandcurrents.noaa.gov/) or
search by bounding box:

```python
>>> from noaa_coops import get_stations_from_bbox, Station
>>> stations = get_stations_from_bbox(
...     lat_coords=[40.389, 40.9397],
...     lon_coords=[-74.4751, -73.7432],
... )
>>> stations
['8516945', '8518750', '8531680']
>>> Station(id="8516945").name
'Kings Point'
```

### Metadata

Station metadata lives on the `.metadata` attribute, and individual fields are
also promoted to top-level attributes on the `Station` object:

```python
>>> seattle = Station(id="9447130")
>>> seattle.name
'Seattle'
>>> seattle.state
'WA'
>>> seattle.lat_lon
{'lat': 47.60264, 'lon': -122.3393}
```

### Data inventory

Per-product first/last observation dates:

```python
>>> seattle.data_inventory["Wind"]
{'start_date': '1991-11-09 00:00', 'end_date': '...'}
```

> **Note:** The data inventory comes from NOAA's legacy SOAP endpoint and is
> best-effort. If the service is unreachable, `data_inventory` is set to `{}`
> and a warning is logged — `Station()` construction still succeeds.

### Data retrieval

Data is returned as a pandas `DataFrame` indexed by timestamp. Column names
mirror NOAA's [response format](https://api.tidesandcurrents.noaa.gov/api/prod/responseHelp.html).

```python
>>> seattle = Station(id="9447130")
>>> df = seattle.get_data(
...     begin_date="20150101",
...     end_date="20150131",
...     product="water_level",
...     datum="MLLW",
...     units="metric",
...     time_zone="gmt",
... )
>>> df.head()
                         v      s        f  q
t
2015-01-01 00:00:00  1.799  0.023  0,0,0,0  v
2015-01-01 00:06:00  1.718  0.018  0,0,0,0  v
2015-01-01 00:12:00  1.639  0.013  0,0,0,0  v
2015-01-01 00:18:00  1.557  0.012  0,0,0,0  v
2015-01-01 00:24:00  1.473  0.014  0,0,0,0  v
```

![Water levels chart](https://user-images.githubusercontent.com/28986302/233147224-765fbe05-372c-40f3-8bbe-4102536e7ff3.png)

Multi-month and multi-year ranges are automatically split into 31-day (or
365-day for `hourly_height` / `high_low`) blocks and concatenated. If NOAA
fails to return data for a block, you get a partial DataFrame along with a
`RuntimeWarning` and a `df.attrs["missing_blocks"]` list describing which
ranges failed — downstream code can detect gaps instead of silently averaging
across them.

### Supported arguments

Values accepted by `Station.get_data(...)` — see
[NOAA's API docs](https://api.tidesandcurrents.noaa.gov/api/prod/#products) for
the authoritative reference.

| Argument    | Accepted values                                                                                                                                                                                     |
|-------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `product`   | `water_level`, `hourly_height`, `high_low`, `daily_mean`, `monthly_mean`, `one_minute_water_level`, `predictions`, `datums`, `air_gap`, `air_temperature`, `water_temperature`, `wind`, `air_pressure`, `conductivity`, `visibility`, `humidity`, `salinity`, `currents`, `currents_predictions`, `ofs_water_level` |
| `datum`     | `CRD`, `IGLD`, `LWD`, `MHHW`, `MHW`, `MTL`, `MSL`, `MLW`, `MLLW`, `NAVD`, `STND` (case-insensitive). **Required** for water-level products.                                                         |
| `units`     | `metric`, `english`                                                                                                                                                                                 |
| `time_zone` | `gmt`, `lst`, `lst_ldt`                                                                                                                                                                             |
| `bin_num`   | Integer. **Required** for `currents` and `currents_predictions`. Find values on each station's info page.                                                                                           |
| `interval`  | Product-specific. `predictions`: `h`, `1`, `5`, `10`, `15`, `30`, `60`, `hilo`. `currents`: `6`, `h`. `currents_predictions`: `h`, `1`, `6`, `10`, `30`, `60`, `max_slack`. Forbidden on `water_level`, `hourly_height`, `one_minute_water_level`. |

### Accepted date formats

`begin_date` and `end_date` accept any of:

- `"20150101"` — `%Y%m%d`
- `"20150101 12:34"` — `%Y%m%d %H:%M`
- `"01/15/2015"` — `%m/%d/%Y`
- `"01/15/2015 23:59"` — `%m/%d/%Y %H:%M`

## API etiquette

NOAA's CO-OPS APIs are public and free. There are no enforced rate limits but
please be reasonable — avoid tight loops against a single station and cache
results when you can. This library uses connection pooling and automatic
retries on transient failures (429 / 5xx) via a module-level
`requests.Session`.

## Contributing

Bug reports, feature requests, and PRs welcome. See
[CONTRIBUTING.md](CONTRIBUTING.md) for dev-environment setup and the release
workflow.
