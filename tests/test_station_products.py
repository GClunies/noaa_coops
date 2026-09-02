"""Per-product integration coverage for Station.get_data.

Until now only ``water_level`` had cassette-backed end-to-end tests; the other
products in ``ALL_PRODUCTS`` flowed through ``_make_api_request`` unverified.
This module exercises the product matrix so the response-envelope dispatch in
``_make_api_request`` is actually covered.

Cassettes are recorded once against the live NOAA CO-OPS API and replayed
offline (see tests/conftest.py vcr_config, record_mode="once"). Re-record with:
    uv run pytest tests/test_station_products.py --record-mode=rewrite

Station IDs per product (documented so cassettes can be re-recorded):
  - water_level / air_temperature / wind / predictions: 9447130 (Seattle).
    NOTE: Seattle's met sensors (air_temperature, wind) were retired
    2019-01-02, so those products use a pre-2019 date window.
  - currents: bh0101 (Castle Island, Boston Harbor PORTS, deployed 2025-11).
    NOTE: observed currents age out of the Data API (only a recent rolling
    window is served). If re-recording, pick a date within ~30-60 days of an
    active currents station and update the param below.
  - currents_predictions: cb0102 (Cape Henry LB 2CH), valid bins 4/9/14.
"""

from __future__ import annotations

import pandas as pd
import pytest

import noaa_coops as nc

# (product, station_id, get_data kwargs, expected column subset)
# Every product here uses the standard "t" timestamp field + a flat
# {"data": [...]} or {"predictions": [...]} envelope.
DATA_PRODUCT_MATRIX = [
    pytest.param(
        "water_level",
        "9447130",
        {"begin_date": "20150101", "end_date": "20150102", "datum": "MLLW"},
        {"v", "s", "f", "q"},
        id="water_level",
    ),
    pytest.param(
        "air_temperature",
        "9447130",
        {"begin_date": "20150101", "end_date": "20150102"},
        {"v", "f"},
        id="air_temperature",
    ),
    pytest.param(
        "wind",
        "9447130",
        {"begin_date": "20150101", "end_date": "20150102"},
        {"s", "d", "dr", "g", "f"},
        id="wind",
    ),
    pytest.param(
        "currents",
        "bh0101",
        {"begin_date": "20260525", "end_date": "20260526", "bin_num": 1},
        {"s", "d", "b"},
        id="currents",
    ),
    pytest.param(
        "predictions",
        "9447130",
        {
            "begin_date": "20150101",
            "end_date": "20150103",
            "datum": "MLLW",
            "interval": "hilo",
        },
        {"v", "type"},
        id="predictions",
    ),
    pytest.param(
        "daily_max_min",
        "9447130",
        {
            "begin_date": "20150101",
            "end_date": "20150131",
            "interval": "6",
            "datum": "MLLW",
        },
        {"record_type", "value", "pcComplete", "flag"},
        id="daily_max_min",
    ),
]


@pytest.mark.vcr
@pytest.mark.parametrize(
    ("product", "station_id", "kwargs", "expected_cols"), DATA_PRODUCT_MATRIX
)
def test_data_products(
    product: str,
    station_id: str,
    kwargs: dict,
    expected_cols: set[str],
) -> None:
    """Each product returns a non-empty, datetime-indexed DataFrame whose
    columns include the product-specific fields."""
    station = nc.Station(id=station_id)
    df = station.get_data(product=product, **kwargs)

    assert not df.empty, f"{product} returned an empty DataFrame"
    assert isinstance(df.index, pd.DatetimeIndex)
    missing = expected_cols - set(df.columns)
    assert not missing, f"{product} missing expected columns: {missing}"


@pytest.mark.vcr
def test_currents_predictions_envelope() -> None:
    """currents_predictions nests its records under current_predictions.cp
    rather than the flat {"data": [...]} envelope, so it exercises a
    separate branch of _make_api_request's dispatch. This test verifies
    that branch surfaces the prediction records, and that the "Time"
    timestamp field is normalized to a DatetimeIndex.
    """
    station = nc.Station(id="cb0102")
    df = station.get_data(
        begin_date="20240101",
        end_date="20240102",
        product="currents_predictions",
        bin_num=4,
    )
    assert not df.empty
    assert isinstance(df.index, pd.DatetimeIndex)
    # Velocity_Major is the defining currents_predictions field.
    assert "Velocity_Major" in df.columns


def test_datums_rejected_by_get_data() -> None:
    """`datums` is a Metadata API concept (station.datums), not a Data API
    product, so it's not in ALL_PRODUCTS. get_data should reject it with a
    ValueError rather than attempting a request.
    """
    station = nc.Station(id="9447130")
    with pytest.raises(ValueError, match="Invalid product"):
        station.get_data(
            begin_date="20150101",
            end_date="20150102",
            product="datums",
            datum="MLLW",
        )


def test_daily_max_min_rejects_unexpected_record_key(monkeypatch) -> None:
    """The daily_max_min flattener maps 'dailyMax'/'dailyMin' keys to
    record_type 'max'/'min'. Any other key must raise a clear KeyError
    instead of silently defaulting to 'max'.
    """
    from noaa_coops import station as station_mod

    class FakeResponse:
        status_code = 200

        @staticmethod
        def json() -> dict:
            return {
                "data": [
                    {
                        "dailyWeird": [
                            {
                                "dateHourly": "2015-01-01",
                                "timeHourly": "09:00",
                                "valueHourly": 1.0,
                                "pcCompleteHourly": 100,
                                "flagHourly": 0,
                            }
                        ]
                    }
                ]
            }

    monkeypatch.setattr(
        station_mod._SESSION, "get", lambda url, timeout: FakeResponse()
    )
    station = nc.Station.__new__(nc.Station)  # skip metadata fetch in __init__
    with pytest.raises(KeyError, match="Unexpected record key 'dailyWeird'"):
        station._make_api_request("http://fake", product="daily_max_min")
