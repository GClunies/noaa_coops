"""Cassette-backed coverage for station-type metadata population.

Each test here pins a specific mdapi response shape that the previous
exclusive ``if/elif`` branching in ``populate_metadata`` handled wrongly.
Station IDs are documented per test so cassettes can be re-recorded:

    uv run pytest tests/test_station_metadata.py --record-mode=rewrite
"""

from __future__ import annotations
 
import pytest
 
import noaa_coops as nc

@pytest.mark.vcr
def test_subordinate_station_keeps_both_datums_and_offsets() -> None:
    """A station can be both a subordinate tide-prediction station and carry
    real datum values.

    8721994 (Micco, Indian River FL) has a populated ``datums`` block and a
    populated ``tidePredOffsets`` block, so both attribute sets must be
    present. Key presence alone can't discriminate between the two.
    """
    station = nc.Station(id="8721994")

    # Tide-prediction side -- this is what used to be lost.
    assert station.tide_pred_offsets is not None
    assert station.tide_pred_offsets["refStationId"] == "8723178"
    assert station.tide_pred_offsets["type"] == "S"
    assert station.reference_id == "8723178"
    assert station.type == "S"

    # Water-level side -- must still be populated, not clobbered.
    assert station.datums is not None
    assert station.datums["datums"], "expected a non-empty datum list"


@pytest.mark.vcr
def test_reference_station_has_datums_and_no_offsets() -> None:
    """The mirror case: a reference (R-type) tide station.

    8720030 (Fernandina Beach, FL) carries real datums, and its
    ``tidePredOffsets`` has an empty ``refStationId`` because reference
    stations have nothing to offset from, so no offset attributes are set.
    """
    station = nc.Station(id="8720030")

    assert station.datums is not None
    assert station.datums["datums"], "expected a non-empty datum list"
    assert not hasattr(station, "tide_pred_offsets")


@pytest.mark.vcr
def test_sparse_station_lowercase_offsets_key() -> None:
    """Sparse responses use a lowercase ``tidepredoffsets`` key.

    TEC5647 (Belize City) returns the offsets under ``tidepredoffsets`` and
    carries ``reference_id`` at the top level rather than only inside the
    offsets block. Both spellings resolve to the same attributes.
    """
    station = nc.Station(id="TEC5647")

    assert station.tide_pred_offsets is not None
    assert station.tide_pred_offsets["refStationId"] == "8724580"
    assert station.reference_id == "8724580"
    assert station.type == "S"


@pytest.mark.vcr
def test_multi_bin_current_prediction_station() -> None:
    """Current prediction stations return one record per bin.

    ACT0311 (Turtle Head Pt., Penobscot Bay) has two bins, each with its own
    offsets, depth and depthType. All bins are exposed via
    ``current_pred_offsets_by_bin``; the scalar attributes describe the first.
    """
    station = nc.Station(id="ACT0311")

    by_bin = station.current_pred_offsets_by_bin
    assert set(by_bin) == {1, 2}
    for offsets in by_bin.values():
        assert offsets is not None
        assert offsets["refStationId"] == "PEB0607"

    # Scalar attributes still describe the first record, unchanged.
    assert station.curr_bin in by_bin
    assert station.current_pred_offsets == by_bin[station.curr_bin]


@pytest.mark.vcr
def test_single_bin_current_prediction_station() -> None:
    """``current_pred_offsets_by_bin`` is set even for single-bin stations.

    ACT0091 has one bin. The attribute must still exist as a one-entry dict
    so callers never need ``hasattr``.
    """
    station = nc.Station(id="ACT0091")

    by_bin = station.current_pred_offsets_by_bin
    assert len(by_bin) == 1
    assert station.curr_bin in by_bin


@pytest.mark.vcr
def test_currents_station_bin_geometry() -> None:
    """``height_from_bottom`` / ``center_bin_1_dist`` are stored for currents.

    bh0101 is an active PORTS currents station. Values are floats whose
    magnitude depends on the requested units, so only presence and type are
    asserted.
    """
    station = nc.Station(id="bh0101")

    assert isinstance(station.height_from_bottom, float)
    assert isinstance(station.center_bin_1_dist, float)


@pytest.mark.vcr
def test_historic_currents_station() -> None:
    """Historic currents stations share the active shape.

    cb0701 (Dominion Terminal) was retrieved in 2022. A non-empty
    ``retrieved`` is the only thing distinguishing it from an active station,
    so it flows through the same populate path and must keep the same fields.
    """
    station = nc.Station(id="cb0701")

    assert station.retrieved, "historic station should carry a retrieved date"
    assert isinstance(station.height_from_bottom, float)
    assert isinstance(station.center_bin_1_dist, float)


@pytest.mark.vcr
def test_water_level_station_extra_schema_fields() -> None:
    """Water-level schema fields beyond the core set.

    ``supersededdatums`` and the boolean product flags are part of the Water
    Level schema and are stored on every water-level station.
    """
    station = nc.Station(id="9447130")

    assert station.superseded_datums is not None
    for attr in (
        "forecast",
        "outlook",
        "htf_historical",
        "non_navigational",
        "inundation_db",
    ):
        assert isinstance(getattr(station, attr), bool), f"{attr} not stored"