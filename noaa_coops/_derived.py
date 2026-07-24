"""Fetch and parse NOAA CO-OPS Derived Product API (DPAPI) data.

This module owns validation + URL building + response parsing;
``Station.get_derived_product`` is a thin wrapper that calls into it,
the same way ``Station.__init__`` calls ``populate_metadata`` from ``_metadata.py``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import pandas as pd
import requests

from noaa_coops._endpoints import DPAPI_BASE_URL
from noaa_coops._exceptions import COOPSAPIError
from noaa_coops._http import DEFAULT_TIMEOUT, _SESSION
from noaa_coops._parsing import parse_known_date_formats

if TYPE_CHECKING:
    from noaa_coops.station import Station


# ---------------------------------------------------------------------------
# Product registry — Phase 1 only.
# ---------------------------------------------------------------------------

#: Pattern: {base}htf/{product}.json
HTF_PRODUCTS: frozenset[str] = frozenset(
    {"htf_daily", "htf_monthly", "htf_seasonal", "htf_annual"}
)

#: Pattern: {base}product/{product}.json  (NOT extrfa — it has its own pattern)
PATH_PRODUCTS: frozenset[str] = frozenset({"sealvltrends", "slr_projections"})

#: Pattern: {base}product.json?name={product}
PARAM_PRODUCTS: frozenset[str] = frozenset({"toptenwaterlevels", "extremewaterlevels"})

DATES_REQUIRED: frozenset[str] = frozenset({"htf_daily"})

#: sealvltrends `detail` options:
#: None/omitted -> top-level scalar fields only (station identity + trend stats)
#: "monthly_means" -> deseasonalized monthly series. Separate NOAA query
#:     param (details=monthlymeans), same endpoint, NOT a separate fetch.
#: "events" -> the (possibly empty) `events` list from the base response
#: "seasonal_cycle" -> the `seasonalCycleMonth` list from the base response
SEALVLTRENDS_DETAILS: frozenset[str] = frozenset(
    {"monthly_means", "events", "seasonal_cycle"}
)

#: extremewaterlevels `level_type` options — filters tenYearEvents client-side;
#: client-side only for the base endpoint
#: Phase 2 sub-endpoints will send this as a real query param
#: NOAA always returns both highs and lows in one response; there's no
#: server-side param for this specific field
EXTREMEWATERLEVELS_LEVEL_TYPES: frozenset[str] = frozenset({"high", "low"})

#: slr_projections `scenario` options. Default (server-side, when omitted) is "all".
SLR_PROJECTION_SCENARIOS: frozenset[str] = frozenset(
    {
        "all",
        "low",
        "intermediate-low",
        "intermediate",
        "intermediate-high",
        "high",
        "extreme",
    }
)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

DATUM_OPTIONS: dict[str, frozenset[str]] = {
    "toptenwaterlevels": frozenset(
        {"STND", "MHHW", "MHW", "MSL", "MTL", "MLW", "MLLW", "NAVD", "IGLD", "LWD"}
    ),
    "extrfa": frozenset({"STND", "MLLW", "MHHW", "MSL", "MLW", "MHW"}),
    "htf_daily": frozenset({"STND", "MLLW", "MHHW", "GT", "MSL", "MLW", "MHW"}),
}


def validate_params(
    product: str,
    start_date: Optional[str],
    end_date: Optional[str],
    units: Optional[str],
    datum: Optional[str],
    detail: Optional[str] = None,
    level_type: Optional[str] = None,
    scenario: Optional[str] = None,
) -> None:
    """Validate arguments before any DPAPI request is made.

    Raises ValueError on the first failure — same contract as
    _products.validate_params, called before any network activity.
    """
    valid_products = (
        HTF_PRODUCTS
        | PATH_PRODUCTS
        | PARAM_PRODUCTS
        | {
            "extrfa",
            "slr_projectionOffsets",
        }
    )
    if product not in valid_products:
        raise ValueError(
            f"Invalid product '{product}'. Must be one of: {sorted(valid_products)}. "
            "See https://api.tidesandcurrents.noaa.gov/dpapi/prod/#products"
        )

    if product in DATES_REQUIRED:
        if not start_date or not end_date:
            raise ValueError(
                f"`start_date` and `end_date` are both required for product '{product}'."
            )

    if start_date and end_date and start_date > end_date:
        raise ValueError(
            f"start_date ({start_date}) must not be after end_date ({end_date})."
        )

    if units is not None and units not in {"metric", "english"}:
        raise ValueError(f"Invalid units '{units}'. Must be 'metric' or 'english'.")

    if datum is not None:
        valid_datums = DATUM_OPTIONS.get(product)
        if valid_datums is None:
            raise ValueError(
                f"Product '{product}' does not accept a `datum` parameter."
            )
        if datum.upper() not in valid_datums:
            raise ValueError(
                f"Invalid datum '{datum}' for product '{product}'. "
                f"Must be one of: {sorted(valid_datums)}"
            )

    if detail is not None:
        if product != "sealvltrends":
            raise ValueError(
                f"`detail` is only supported for sealvltrends, not '{product}'."
            )
        if detail not in SEALVLTRENDS_DETAILS:
            raise ValueError(
                f"Invalid detail '{detail}'. Must be one of: {sorted(SEALVLTRENDS_DETAILS)}"
            )

    if level_type is not None:
        if product != "extremewaterlevels":
            raise ValueError(
                f"`level_type` is only supported for extremewaterlevels, not '{product}'."
            )
        if level_type not in EXTREMEWATERLEVELS_LEVEL_TYPES:
            raise ValueError(
                f"Invalid level_type '{level_type}'. "
                f"Must be one of: {sorted(EXTREMEWATERLEVELS_LEVEL_TYPES)}"
            )

    if scenario is not None:
        if product != "slr_projections":
            raise ValueError(
                f"`scenario` is only supported for slr_projections, not '{product}'."
            )
        if scenario not in SLR_PROJECTION_SCENARIOS:
            raise ValueError(
                f"Invalid scenario '{scenario}'. "
                f"Must be one of: {sorted(SLR_PROJECTION_SCENARIOS)}"
            )


# ---------------------------------------------------------------------------
# URL building
# ---------------------------------------------------------------------------


def build_dpapi_url(
    product: str,
    station_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    year: Optional[int] = None,
    units: Optional[str] = "metric",
    datum: Optional[str] = None,
    affil: Optional[str] = None,
    projection_year: Optional[int] = None,
    report_year: Optional[int] = None,
    scenario: Optional[str] = None,
    detail: Optional[str] = None,
) -> str:
    """Build a DPAPI request URL. Assumes validate_params() already ran.
    Internal helper — see Station.get_derived_product() for parameter docs.
    """
    parameters: dict[str, str] = {}
    if station_id:
        parameters["station"] = station_id

    if product in HTF_PRODUCTS:
        if start_date:
            parameters["start_date"] = start_date
        if end_date:
            parameters["end_date"] = end_date
        if year:
            parameters["year"] = str(year)
        if datum:
            parameters["datum"] = datum
        if units:
            parameters["units"] = units
        url = f"{DPAPI_BASE_URL}htf/{product}.json"

    elif product == "extrfa":
        if datum:
            parameters["datum"] = datum
        if units:
            parameters["units"] = units
        url = f"{DPAPI_BASE_URL}extrfa.json"

    elif product == "sealvltrends":
        if affil:
            parameters["affil"] = affil
        if units:
            parameters["units"] = units
        if detail == "monthly_means":
            parameters["details"] = "monthlymeans"
            # confirmed: all 510 stations report trendType=SINGLE as of this
            # check; hardcoded rather than fetched per-call.
            parameters["trendType"] = "SINGLE"
        url = f"{DPAPI_BASE_URL}product/{product}.json"

    elif product == "slr_projections":
        if affil:
            parameters["affil"] = affil
        if projection_year:
            parameters["projection_year"] = str(projection_year)
        if report_year:
            parameters["report_year"] = str(report_year)
        if scenario:
            parameters["scenario"] = scenario
        if units:
            parameters["units"] = units
        url = f"{DPAPI_BASE_URL}product/{product}.json"

    elif product == "slr_projectionOffsets":
        if affil:
            parameters["affil"] = affil
        if report_year:
            parameters["report_year"] = str(report_year)
        if units:
            parameters["units"] = units
        url = f"{DPAPI_BASE_URL}product/{product}.json"

    elif product in PARAM_PRODUCTS:  # toptenwaterlevels, extremewaterlevels
        if datum:
            parameters["datum"] = datum
        if units:
            parameters["units"] = units
        parameters["name"] = product
        url = f"{DPAPI_BASE_URL}product/.json"

    else:
        raise ValueError(f"No URL pattern defined for product '{product}'")

    prepared_url = requests.Request("GET", url, params=parameters).prepare().url
    if prepared_url is None:
        raise COOPSAPIError(f"Failed to build a request URL for product '{product}'.")
    return prepared_url


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------


def _parse_extrfa(payload: dict) -> pd.DataFrame:
    records = payload["ExtRfa"]

    # Unwrap the scalar-wrapped single-element lists onto each record
    # before normalizing, so meta can reference them as plain fields
    # instead of leaving raw [{'Uindex': ..., 'unit': ...}] objects in
    # every row.
    for record in records:
        record["localUIndex_value"] = record["localUIndex"][0]["Uindex"]
        record["localUIndex_unit"] = record["localUIndex"][0]["unit"]
        record["localUTrend_value"] = record["localUTrend"][0]["Utrend"]
        record["localUTrend_unit"] = record["localUTrend"][0]["unit"]

    meta_fields: list[str | list[str]] = [
        "stationId",
        "name",
        "lat",
        "lon",
        "tidalEpoch",
        "gridNum",
        "gridLat",
        "gridLong",
        "region",
        "startDate",
        "endDate",
        "validDays",
        "totalDays",
        "percentValidDays",
        "probabilitiesUnit",
        "long_term_flag",
        "short_term_flag",
        "localUIndex_value",
        "localUIndex_unit",
        "localUTrend_value",
        "localUTrend_unit",
    ]
    return pd.json_normalize(
        records,
        record_path="ewlProbabilities",
        meta=meta_fields,
        errors="ignore",
    )


def _parse_extremewaterlevels(payload: dict, level_type: Optional[str]) -> pd.DataFrame:
    records = payload["ExtremeWaterLevels"]
    meta_fields: list[str | list[str]] = [
        "stationId",
        "stationName",
        "stationTitle",
        "state",
        "epoch",
        "epochMidyear",
        "latitude",
        "longitude",
        "annotation",
    ]

    if level_type in ("high", "low"):
        key = "highs" if level_type == "high" else "lows"
        df = pd.json_normalize(
            records,
            record_path=["tenYearEvents", key],
            meta=meta_fields,
            errors="ignore",
        )
        df["annotation"] = df["annotation"].replace("null", float("nan"))
        return df

    record = records[0]  # multi-station response not handled yet
    annotation = record["annotation"]
    annotation = float("nan") if annotation == "null" else annotation
    return pd.DataFrame(
        [
            {
                "stationId": record["stationId"],
                "stationName": record["stationName"],
                "stationTitle": record["stationTitle"],
                "state": record["state"],
                "epoch": record["epoch"],
                "epochMidyear": record["epochMidyear"],
                "latitude": record["latitude"],
                "longitude": record["longitude"],
                "annotation": annotation,
                "tenYearEventCount": record["tenYearEvents"]["count"],
            }
        ]
    )


def _parse_sealvltrends(payload: dict, detail: Optional[str]) -> pd.DataFrame:
    if detail == "monthly_means":
        return pd.json_normalize(payload["data"])

    records = payload["SeaLvlTrends"]
    meta_fields: list[str | list[str]] = [
        "stationId",
        "stationName",
        "affil",
        "trendUnits",
        "seasonalUnits",
        "seasonalAverage",
        "latitude",
        "longitude",
        "trendType",
        "autoregressive",
        "autoregressiveError",
        "trend",
        "trendError",
        "y2000_offset",
        "startDate",
        "endDate",
    ]

    if detail == "events":
        # station has no events (numberEvents=0) -> 0-row DataFrame, valid.
        return pd.json_normalize(
            records,
            record_path="events",
            meta=meta_fields,
            meta_prefix="station_",
            errors="ignore",
        )
    if detail == "seasonal_cycle":
        return pd.json_normalize(
            records, record_path="seasonalCycleMonth", meta=meta_fields, errors="ignore"
        )

    record = records[0]  # multi-station response not handled yet
    return pd.DataFrame([{k: record[k] for k in meta_fields}])


def parse_dpapi_response(
    payload: dict,
    product: str,
    detail: Optional[str] = None,
    level_type: Optional[str] = None,
) -> pd.DataFrame:
    """Turn a raw DPAPI JSON payload into a DataFrame.

    Every Phase 1 product ends up representable as a DataFrame (single-row
    for station-info-only responses, multi-row for exploded sub-tables) —
    """
    if product == "extrfa":
        return _parse_extrfa(payload)
    if product == "sealvltrends":
        return _parse_sealvltrends(payload, detail)
    if product == "extremewaterlevels":
        return _parse_extremewaterlevels(payload, level_type)

    top_level_key = next(k for k, v in payload.items() if isinstance(v, list))
    return pd.json_normalize(payload[top_level_key])


# ---------------------------------------------------------------------------
# Public orchestrator — called from Station.get_derived_product()
# ---------------------------------------------------------------------------


def get_derived_product(
    station: "Station",
    product: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    year: Optional[int] = None,
    units: Optional[str] = "metric",
    datum: Optional[str] = None,
    affil: Optional[str] = None,
    projection_year: Optional[int] = None,
    report_year: Optional[int] = None,
    scenario: Optional[str] = None,
    detail: Optional[
        str
    ] = None,  # sealvltrends: "monthly_means" | "events" | "seasonal_cycle"
    level_type: Optional[str] = None,  # extremewaterlevels: "high" | "low"
) -> pd.DataFrame:
    """Fetch a derived product for ``station`` from the NOAA DPAPI.

    Args:
        station: The bound Station instance — station.id is used as the
            station_id for this request.
        product: DPAPI product name.
        start_date: Start date, any KNOWN_DATE_FORMATS format, normalized
            to DPAPI's required "%Y%m%d" before the request is sent.
        end_date: End date, same formats as start_date.
        year: Year filter, used by HTF products.
        units: "metric" or "english". NOAA's server-side default when omitted varies by product —
                toptenwaterlevels, extremewaterlevels, extrfa, and htf_daily default to english;
                slr_projections defaults to metric.
                Passing units explicitly is recommended.
        datum: Datum reference — valid values depend on product, see
            DATUM_OPTIONS. Not every product accepts a datum.
        affil: "US" or "Global" — sealvltrends, slr_projections, offsets.
        projection_year: slr_projections only.
        report_year: slr_projections, slr_projectionOffsets.
        scenario: slr_projections only. One of: 'all', 'low',
            'intermediate-low', 'intermediate', 'intermediate-high',
            'high', 'extreme'. Default (server-side, when omitted) is
            'all'.
        detail: sealvltrends only. "monthly_means" (deseasonalized monthly
            series), "events" (may be empty), or "seasonal_cycle" (the
            12-month seasonal pattern removed to compute the trend). Omit
            for the top-level trend statistics.
        level_type: extremewaterlevels only. "high" or "low" — filters
            tenYearEvents client-side. Omit for full station metadata.

    Raises:
        ValueError: product invalid, or a required/unsupported/invalid
            param for it.
        COOPSAPIError: DPAPI returned a non-200 response.

    Returns:
        A DataFrame. Single row for station-info-only responses (no
        detail/level_type given on sealvltrends/extremewaterlevels),
        multiple rows with station identity columns included for exploded
        sub-tables (e.g. RFA's ewlProbabilities, HTF time series).
    """
    if start_date:
        parsed_start, _ = parse_known_date_formats(start_date)
        start_date = parsed_start.strftime("%Y%m%d")
    if end_date:
        parsed_end, _ = parse_known_date_formats(end_date)
        end_date = parsed_end.strftime("%Y%m%d")

    validate_params(
        product=product,
        start_date=start_date,
        end_date=end_date,
        units=units,
        datum=datum,
        detail=detail,
        level_type=level_type,
        scenario=scenario,
    )

    url = build_dpapi_url(
        product=product,
        station_id=station.id,
        start_date=start_date,
        end_date=end_date,
        year=year,
        units=units,
        datum=datum,
        affil=affil,
        projection_year=projection_year,
        report_year=report_year,
        scenario=scenario,
        detail=detail,
    )

    response = _SESSION.get(url, timeout=DEFAULT_TIMEOUT)

    if response.status_code != 200:
        raise COOPSAPIError(
            f"Failed to fetch derived product '{product}' for station "
            f"id={station.id}. Status code: {response.status_code}. "
            f"Reason: {response.reason}"
        )

    payload = response.json()
    return parse_dpapi_response(payload, product, detail=detail, level_type=level_type)
