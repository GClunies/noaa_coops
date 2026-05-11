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
    "tidepredoffets",  # NOTE: historical typo preserved by the NOAA API itself
    "benchmarks",
    "nearby",
    "bins",
    "deployments",
    "currentpredictionoffsets",
    "floodlevels",
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
        f"?units={units}"
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
    md = payload["stations"][0]

    # Always-present fields, previously duplicated across 4 branches.
    station.details = md.get("details", {})
    station.bins = md.get("bins", [])
    station.deployments = md.get("deployments", [])
    station.metadata = md
    station.name = md.get("name")
    if "lat" in md and "lng" in md:
        station.lat_lon = {"lat": md["lat"], "lon": md["lng"]}

    # Branch into station-type-specific fields.
    if "datums" in md:
        _populate_water_level(station, md)
    elif "tidepredoffsets" in md:
        _populate_tide_prediction_offsets(station, md)
    elif "bins" in md:
        _populate_currents(station, md)
    elif "currbin" in md:
        _populate_predicted_currents(station, md)


# ---------------------------------------------------------------------------
# Branch helpers
# ---------------------------------------------------------------------------


def _apply_common(station: Station, md: dict) -> None:
    """Copy every entry in ``_COMMON_ATTRS`` from ``md`` onto ``station``."""
    for attr_name, md_key in _COMMON_ATTRS:
        setattr(station, attr_name, md.get(md_key))


def _populate_water_level(station: Station, md: dict) -> None:
    _apply_common(station, md)
    station.benchmarks = md["benchmarks"]
    station.datums = md["datums"]
    station.flood_levels = md["floodlevels"]
    station.greatlakes = md["greatlakes"]
    station.tidal_constituents = md["harmonicConstituents"]
    station.nearby_stations = md["nearby"]
    station.observe_dst = md["observedst"]
    station.sensors = md["sensors"]
    station.shef_code = md["shefcode"]
    station.state = md["state"]
    station.storm_surge = md["stormsurge"]
    station.tidal = md["tidal"]
    station.timezone = md["timezone"]
    station.timezone_corr = md["timezonecorr"]


def _populate_tide_prediction_offsets(station: Station, md: dict) -> None:
    _apply_common(station, md)
    station.state = md["state"]
    station.tide_pred_offsets = md["tidepredoffsets"]
    station.type = md["type"]
    station.time_meridian = md["timemeridian"]
    station.reference_id = md["reference_id"]
    station.timezone_corr = md["timezonecorr"]


def _populate_currents(station: Station, md: dict) -> None:
    _apply_common(station, md)
    station.project = md["project"]
    station.deployed = md["deployed"]
    station.retrieved = md["retrieved"]
    station.timezone_offset = md["timezone_offset"]
    station.observe_dst = md["observedst"]
    station.project_type = md["project_type"]
    station.noaa_chart = md["noaachart"]
    station.deployments = md["deployments"]
    station.bins = md["bins"]


def _populate_predicted_currents(station: Station, md: dict) -> None:
    _apply_common(station, md)
    station.current_pred_offsets = md["currentpredictionoffsets"]
    station.curr_bin = md["currbin"]
    station.type = md["type"]
    station.depth = md["depth"]
    station.depth_type = md["depthType"]
