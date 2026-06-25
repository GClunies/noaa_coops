"""Multi-block fetch behavior tests for `Station.get_data`.

Exercises the error-handling and concat path in the multi-block branch:
- No more silent data loss: failed blocks emit RuntimeWarning + log warning
- Missing blocks recorded in `df.attrs['missing_blocks']`
- Successful blocks are still returned as a concatenated DataFrame
- Single-pass `pd.concat` (O(n) memory) rather than per-iteration concat
"""

from __future__ import annotations

import logging

import pytest
import responses

from noaa_coops.station import COOPSAPIError, Station


DATA_GETTER_URL_RE = __import__("re").compile(
    r"https://api\.tidesandcurrents\.noaa\.gov/api/prod/datagetter\?.*"
)


def _bare_station(station_id: str = "9447130") -> Station:
    s = Station.__new__(Station)
    s.id = station_id
    s.units = "metric"
    return s


def _block_body(timestamp: str) -> dict:
    """Minimal datagetter success payload for a single 6-min observation."""
    return {
        "metadata": {"id": "9447130", "name": "Seattle"},
        "data": [
            {"t": timestamp, "v": "1.50", "s": "0.02", "f": "0,0,0,0", "q": "v"},
        ],
    }


@responses.activate
def test_multi_block_happy_path_concats_successfully() -> None:
    """Happy path: multiple blocks succeed -> single concatenated DataFrame."""
    # 3-month fetch => 3 blocks at 31-day granularity
    for ts in ["2015-01-15 00:00", "2015-02-15 00:00", "2015-03-15 00:00"]:
        responses.add(
            responses.GET,
            DATA_GETTER_URL_RE,
            json=_block_body(ts),
            status=200,
        )

    station = _bare_station()
    df = station.get_data(
        begin_date="20150101",
        end_date="20150401",
        product="water_level",
        datum="MLLW",
        units="metric",
        time_zone="gmt",
    )

    assert len(df) == 3
    # attrs["missing_blocks"] should NOT be set when every block succeeds
    assert "missing_blocks" not in df.attrs


@responses.activate
def test_multi_block_partial_failure_warns_and_populates_attrs(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Failed blocks are surfaced via RuntimeWarning + logger.warning + df.attrs.

    This is the fix for the historical silent-data-drop bug: before this
    change, `except COOPSAPIError: continue` swallowed failed blocks with no
    indication to the caller.
    """
    # 3 blocks: 1st succeeds, 2nd fails (503), 3rd succeeds.
    responses.add(
        responses.GET,
        DATA_GETTER_URL_RE,
        json=_block_body("2015-01-15 00:00"),
        status=200,
    )
    # Enough 503s to exhaust retry (3 retries + initial = 4 attempts)
    for _ in range(4):
        responses.add(responses.GET, DATA_GETTER_URL_RE, status=503)
    responses.add(
        responses.GET,
        DATA_GETTER_URL_RE,
        json=_block_body("2015-03-15 00:00"),
        status=200,
    )

    station = _bare_station()

    with (
        pytest.warns(RuntimeWarning, match="block"),
        caplog.at_level(logging.WARNING, logger="noaa_coops.station"),
    ):
        df = station.get_data(
            begin_date="20150101",
            end_date="20150401",
            product="water_level",
            datum="MLLW",
            units="metric",
            time_zone="gmt",
        )

    # Partial DataFrame is returned (2 of 3 blocks succeeded)
    assert len(df) == 2

    # attrs["missing_blocks"] lists exactly the failed block
    assert "missing_blocks" in df.attrs
    missing = df.attrs["missing_blocks"]
    assert len(missing) == 1
    assert "begin" in missing[0]
    assert "end" in missing[0]
    assert "error" in missing[0]

    # The warning also made it to the logger
    station_warnings = [r for r in caplog.records if r.name == "noaa_coops.station"]
    assert any("Block" in r.getMessage() for r in station_warnings)


@responses.activate
def test_multi_block_total_failure_raises() -> None:
    """If EVERY block fails, `get_data` raises COOPSAPIError (empty-df path)."""
    for _ in range(100):
        responses.add(responses.GET, DATA_GETTER_URL_RE, status=503)

    station = _bare_station()
    with pytest.warns(RuntimeWarning), pytest.raises(COOPSAPIError):
        station.get_data(
            begin_date="20150101",
            end_date="20150401",
            product="water_level",
            datum="MLLW",
            units="metric",
            time_zone="gmt",
        )


@responses.activate
def test_ceil_fix_no_spurious_extra_block() -> None:
    """62-day range / 31-day block = exactly 2 blocks, not 3.

    floor(62/31)+1 = 3 (old bug); ceil(62/31) = 2 (fixed).
    A third call would hit a zero-length range and waste a round trip.
    """
    for ts in ["2015-01-15 00:00", "2015-02-15 00:00"]:
        responses.add(
            responses.GET, DATA_GETTER_URL_RE, json=_block_body(ts), status=200
        )

    station = _bare_station()
    station.get_data(
        begin_date="20150101",
        end_date="20150304",
        product="water_level",
        datum="MLLW",
        units="metric",
        time_zone="gmt",
    )

    assert len(responses.calls) == 2


@responses.activate
def test_product_specific_block_size() -> None:
    """one_minute_water_level has a 4-day limit; a 5-day range must produce
    2 API calls, not 1.

    Old code hardcoded 31 days for all products except hourly_height/high_low,
    so a 5-day one_minute_water_level range would have been a single block.
    """
    for ts in ["2015-01-02 00:00", "2015-01-05 00:00"]:
        responses.add(
            responses.GET, DATA_GETTER_URL_RE, json=_block_body(ts), status=200
        )

    station = _bare_station()
    station.get_data(
        begin_date="20150101",
        end_date="20150106",
        product="one_minute_water_level",
        datum="MLLW",
        units="metric",
        time_zone="gmt",
    )

    assert len(responses.calls) == 2
