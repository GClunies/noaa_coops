"""Fetch and apply station metadata.

Implements ``populate_metadata(station, units)``: a single entry point
the ``Station`` class calls from its constructor. Metadata comes from
the NOAA mdapi and the fields actually populated depend on the station
type (water-level vs. tide-prediction-offset vs. currents vs. predicted-
currents), so this module branches on the response shape.
"""

# Station attributes are populated dynamically based on the mdapi response
# shape (water_level stations get `datums` + `benchmarks`, currents stations
# get `bins` + `deployments`, etc.). mypy can't see that through setattr,
# and declaring every possible attribute on the Station class would force
# every attribute to be Optional everywhere. Disable the relevant check at
# file scope — this is the one place in the package that needs it.
# mypy: disable-error-code="attr-defined"

from __future__ import annotations

from typing import TYPE_CHECKING

from noaa_coops._endpoints import METADATA_BASE_URL
from noaa_coops._exceptions import COOPSAPIError
from noaa_coops._http import DEFAULT_TIMEOUT, _SESSION

if TYPE_CHECKING:
    from noaa_coops.station import Station


_EXPAND_FIELDS = (
    "details",
    "sensors",
    "products",
    "disclaimers",
    "notices",
    "datums",
    "harcon",
    "tidepredoffsets",  # NOTE: confirmed via live test, NOAA wants the
    # correctly-spelled param; the typo'd version silently
    # returned only the {"self": url} , never real offsets.
    "benchmarks",
    "nearby",
    "bins",
    "deployments",
    "currentpredictionoffsets",
    "floodlevels",
    "supersededdatums",
)

#: Attributes shared by every station type.
_COMMON_ATTRS: tuple[tuple[str, str], ...] = (
    ("affiliations", "affiliations"),
    ("ports_code", "portscode"),
    ("products", "products"),
    ("disclaimers", "disclaimers"),
    ("notices", "notices"),
    ("tide_type", "tideType"),
)


def populate_metadata(station: Station, units: str) -> None:
    """Fetch mdapi metadata for ``station.id`` and copy fields onto ``station``.

    Args:
        station: The ``Station`` instance being constructed.
        units: Either ``"metric"`` or ``"english"`` — passed to NOAA so
            elevations etc. come back in the chosen units.
    """
    url = (
        f"{METADATA_BASE_URL}{station.id}.json"
        f"?expand={','.join(_EXPAND_FIELDS)}"
        f"&units={units}"
    )
    response = _SESSION.get(url, timeout=DEFAULT_TIMEOUT)

    # NOAA's mdapi occasionally 5xx's after retries are exhausted (504s during
    # the nightly canary). Surface that as COOPSAPIError instead of a
    # confusing JSONDecodeError from trying to parse an HTML error page.
    if response.status_code != 200:
        raise COOPSAPIError(
            f"Failed to fetch station metadata for id={station.id}. "
            f"Status code: {response.status_code}. Reason: {response.reason}"
        )

    payload = response.json()
    # NOAA returns one record per current bin, so a multi-bin current
    # prediction station yields several entries. Keep the full list; `md`
    # stays the first record so existing attributes are unchanged.
    records = payload["stations"]
    md = records[0]
    station.metadata_records = records

    # Always-present fields, previously duplicated across 4 branches.
    station.details = md.get("details", {})
    station.bins = md.get("bins", [])
    station.deployments = md.get("deployments", [])
    station.metadata = md
    station.name = md.get("name")
    if "lat" in md and "lng" in md:
        station.lat_lon = {"lat": md["lat"], "lon": md["lng"]}

    # Branch into station-type-specific fields.

    # datums and tidePredOffsets are NOT mutually exclusive, and both keys are
    # present on nearly every full-expand response regardless of station type,
    # so key presence can't discriminate -- check the nested value. Sparse
    # responses use a lowercase "tidepredoffsets" for the same payload.
    tide_pred_offsets = md.get("tidePredOffsets") or md.get("tidepredoffsets")
    if md.get("datums", {}).get("datums") is not None:
        _populate_water_level(station, md)
    if tide_pred_offsets and tide_pred_offsets.get("refStationId"):
        _populate_tide_prediction_offsets(station, md, tide_pred_offsets)
    if "bins" in md:
        _populate_currents(station, md)
    elif "currbin" in md:
        _populate_predicted_currents(station, md, records)


# ---------------------------------------------------------------------------
# Branch helpers
# ---------------------------------------------------------------------------


def _apply_common(station: Station, md: dict) -> None:
    """Copy every entry in ``_COMMON_ATTRS`` from ``md`` onto ``station``."""
    for attr_name, md_key in _COMMON_ATTRS:
        setattr(station, attr_name, md.get(md_key))


def _populate_water_level(station: Station, md: dict) -> None:
    _apply_common(station, md)
    station.benchmarks = md.get("benchmarks")
    station.datums = md.get("datums")
    station.superseded_datums = md.get("supersededdatums")
    station.flood_levels = md.get("floodlevels")
    station.greatlakes = md.get("greatlakes")
    station.tidal_constituents = md.get("harmonicConstituents")
    station.nearby_stations = md.get("nearby")
    station.observe_dst = md.get("observedst")
    station.sensors = md.get("sensors")
    station.shef_code = md.get("shefcode")
    station.state = md.get("state")
    station.storm_surge = md.get("stormsurge")
    station.tidal = md.get("tidal")
    station.timezone = md.get("timezone")
    station.timezone_corr = md.get("timezonecorr")
    station.forecast = md.get("forecast")
    station.outlook = md.get("outlook")
    station.htf_historical = md.get("HTFhistorical")
    station.non_navigational = md.get("nonNavigational")
    station.inundation_db = md.get("inundationdb")


def _populate_tide_prediction_offsets(
    station: Station, md: dict, tide_pred_offsets: dict
) -> None:
    _apply_common(station, md)
    station.state = md.get("state")
    station.tide_pred_offsets = tide_pred_offsets
    station.type = tide_pred_offsets.get("type")
    # Sparse responses put timemeridian and reference_id at the top level.
    # Full-expand ones nest timemeridian under `details` and omit
    # reference_id entirely, so fall back to tidePredOffsets.refStationId.
    station.time_meridian = md.get("details", {}).get("timemeridian") or md.get(
        "timemeridian"
    )
    station.reference_id = md.get("reference_id") or tide_pred_offsets.get(
        "refStationId"
    )
    station.timezone_corr = md.get("timezonecorr")


def _populate_currents(station: Station, md: dict) -> None:
    """Active and historic current stations - same response shape either way.

    A non-empty `retrieved` marks a station historic, but no other field
    differs, so no separate branch is needed.
    """
    _apply_common(station, md)
    station.project = md.get("project")
    station.deployed = md.get("deployed")
    station.retrieved = md.get("retrieved")
    station.timezone_offset = md.get("timezone_offset")
    station.observe_dst = md.get("observedst")
    station.project_type = md.get("project_type")
    station.noaa_chart = md.get("noaachart")
    station.deployments = md.get("deployments")
    station.bins = md.get("bins")
    station.tidal_constituents = md.get("harmonicConstituents")
    station.height_from_bottom = md.get("height_from_bottom")
    station.center_bin_1_dist = md.get("center_bin_1_dist")


def _populate_predicted_currents(
    station: Station, md: dict, records: list[dict] | None = None
) -> None:
    """Current prediction stations, including multi-bin ones.

    NOAA returns one record per bin, so the scalar attributes below describe
    only the first; `current_pred_offsets_by_bin` exposes every bin keyed by
    its `currbin` number and is always set.
    """
    _apply_common(station, md)
    station.current_pred_offsets = md.get("currentpredictionoffsets")
    station.curr_bin = md.get("currbin")
    station.type = md.get("type")
    station.depth = md.get("depth")
    station.depth_type = md.get("depthType")
    station.tidal_constituents = md.get("harmonicConstituents")
    station.current_pred_offsets_by_bin = {
        r["currbin"]: r.get("currentpredictionoffsets")
        for r in (records or [md])
        if "currbin" in r
    }
