"""Fetch and parse NOAA CO-OPS Derived Product API (DPAPI) data.

This module owns validation + URL building + response parsing;
``Station.get_derived_product`` is a thin wrapper that calls into it,
the same way ``Station.__init__`` calls ``populate_metadata`` from ``_metadata.py``.
"""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

import pandas as pd
import requests

from noaa_coops._endpoints import DPAPI_BASE_URL
from noaa_coops._exceptions import COOPSAPIError
from noaa_coops._http import _SESSION, DEFAULT_TIMEOUT
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

#: Pattern: {base}product.json?name={product}
PARAM_PRODUCTS: frozenset[str] = frozenset({"toptenwaterlevels", "extremewaterlevels"})

DATES_REQUIRED: frozenset[str] = frozenset({"htf_daily"})

#: NOAA's endpoints for these don't accept a date range at all — only `year`.
DATES_NOT_APPLICABLE: frozenset[str] = frozenset({"htf_seasonal", "htf_annual"})

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

#: `affil` options — sea_level_trends, slr_projections, slr_projection_offsets.
AFFIL_OPTIONS: frozenset[str] = frozenset({"US", "Global"})

#: API products that accept `affil`.
AFFIL_PRODUCTS: frozenset[str] = frozenset(
    {"sealvltrends", "slr_projections", "slr_projectionOffsets"}
)

#: API products that accept `report_year`.
REPORT_YEAR_PRODUCTS: frozenset[str] = frozenset(
    {"slr_projections", "slr_projectionOffsets"}
)

#: Public product name -> NOAA DPAPI product name.
#: `Station.get_derived_product` accepts and returns the public name; only
#: `build_dpapi_url` needs to know the underlying API spelling. Products
#: already in snake_case (htf_daily, htf_monthly, htf_seasonal, htf_annual,
#: slr_projections) aren't listed since the public and API names match.
PRODUCT_ALIASES: dict[str, str] = {
    "sea_level_trends": "sealvltrends",
    "slr_projection_offsets": "slr_projectionOffsets",
    "top_ten_water_levels": "toptenwaterlevels",
    "extreme_water_levels": "extremewaterlevels",
    "rfa_extreme_water_levels": "extrfa",
}


def _to_api_product(product: str) -> str:
    """Translate a public snake_case product name to NOAA's API name."""
    return PRODUCT_ALIASES.get(product, product)


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
    start_date: str | None,
    end_date: str | None,
    units: str | None,
    datum: str | None,
    detail: str | None = None,
    level_type: str | None = None,
    scenario: str | None = None,
    year: int | None = None,
    affil: str | None = None,
    projection_year: int | None = None,
    report_year: int | None = None,
) -> None:
    """Validate arguments before any DPAPI request is made.

    ``product`` is the public snake_case name (see PRODUCT_ALIASES); error
    messages echo it back so users never see NOAA's internal spelling.

    Raises ValueError on the first failure — same contract as
    _products.validate_params, called before any network activity.
    """
    valid_products = HTF_PRODUCTS | {"slr_projections"} | frozenset(PRODUCT_ALIASES)
    if product not in valid_products:
        raise ValueError(
            f"Invalid product '{product}'. Must be one of: {sorted(valid_products)}. "
            "See https://api.tidesandcurrents.noaa.gov/dpapi/prod/#products"
        )

    api_product = _to_api_product(product)

    if api_product in DATES_REQUIRED and (not start_date or not end_date):
        raise ValueError(
            f"`start_date` and `end_date` are both required for product '{product}'."
        )

    if api_product in DATES_NOT_APPLICABLE and (start_date or end_date):
        raise ValueError(
            f"`start_date`/`end_date` have no effect on '{product}' and "
            "aren't accepted — use `year` instead."
        )

    if start_date and end_date and start_date > end_date:
        raise ValueError(
            f"start_date ({start_date}) must not be after end_date ({end_date})."
        )

    if units is not None and units not in {"metric", "english"}:
        raise ValueError(f"Invalid units '{units}'. Must be 'metric' or 'english'.")

    if datum is not None:
        valid_datums = DATUM_OPTIONS.get(api_product)
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
        if api_product != "sealvltrends":
            raise ValueError(
                f"`detail` is only supported for sea_level_trends, not '{product}'."
            )
        if detail not in SEALVLTRENDS_DETAILS:
            raise ValueError(
                f"Invalid detail '{detail}'. Must be one of: {sorted(SEALVLTRENDS_DETAILS)}"
            )

    if level_type is not None:
        if api_product != "extremewaterlevels":
            raise ValueError(
                f"`level_type` is only supported for extreme_water_levels, not '{product}'."
            )
        if level_type not in EXTREMEWATERLEVELS_LEVEL_TYPES:
            raise ValueError(
                f"Invalid level_type '{level_type}'. "
                f"Must be one of: {sorted(EXTREMEWATERLEVELS_LEVEL_TYPES)}"
            )

    if scenario is not None:
        if api_product != "slr_projections":
            raise ValueError(
                f"`scenario` is only supported for slr_projections, not '{product}'."
            )
        if scenario not in SLR_PROJECTION_SCENARIOS:
            raise ValueError(
                f"Invalid scenario '{scenario}'. "
                f"Must be one of: {sorted(SLR_PROJECTION_SCENARIOS)}"
            )

    if year is not None:
        if api_product not in HTF_PRODUCTS:
            raise ValueError(
                f"`year` is only supported for HTF products, not '{product}'."
            )
        if isinstance(year, bool) or not isinstance(year, int):
            raise ValueError(f"`year` must be an int, got {type(year).__name__}.")
        current_year = datetime.date.today().year
        if not (1800 <= year <= current_year):
            raise ValueError(
                f"Invalid year '{year}'. Must be between 1800 and {current_year}."
            )

    if affil is not None:
        if api_product not in AFFIL_PRODUCTS:
            raise ValueError(
                "`affil` is only supported for sea_level_trends, slr_projections, "
                f"and slr_projection_offsets, not '{product}'."
            )
        if affil not in AFFIL_OPTIONS:
            raise ValueError(
                f"Invalid affil '{affil}'. Must be one of: {sorted(AFFIL_OPTIONS)}"
            )

    if projection_year is not None:
        if api_product != "slr_projections":
            raise ValueError(
                f"`projection_year` is only supported for slr_projections, "
                f"not '{product}'."
            )
        if isinstance(projection_year, bool) or not isinstance(projection_year, int):
            raise ValueError(
                "`projection_year` must be an int, "
                f"got {type(projection_year).__name__}."
            )

    if report_year is not None:
        if api_product not in REPORT_YEAR_PRODUCTS:
            raise ValueError(
                "`report_year` is only supported for slr_projections and "
                f"slr_projection_offsets, not '{product}'."
            )
        if isinstance(report_year, bool) or not isinstance(report_year, int):
            raise ValueError(
                f"`report_year` must be an int, got {type(report_year).__name__}."
            )


# ---------------------------------------------------------------------------
# URL building
# ---------------------------------------------------------------------------


def build_dpapi_url(
    product: str,
    station_id: str,
    start_date: str | None = None,
    end_date: str | None = None,
    year: int | None = None,
    units: str | None = "metric",
    datum: str | None = None,
    affil: str | None = None,
    projection_year: int | None = None,
    report_year: int | None = None,
    scenario: str | None = None,
    detail: str | None = None,
) -> str:
    """Build a DPAPI request URL. Assumes validate_params() already ran.
    ``product`` is the public snake_case name; it's translated to NOAA's
    API spelling here. Internal helper — see Station.get_derived_product()
    for parameter docs.
    """
    product = _to_api_product(product)
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


def _parse_extremewaterlevels(payload: dict, level_type: str | None) -> pd.DataFrame:
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


def _parse_sealvltrends(payload: dict, detail: str | None) -> pd.DataFrame:
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
    detail: str | None = None,
    level_type: str | None = None,
) -> pd.DataFrame:
    """Turn a raw DPAPI JSON payload into a DataFrame.

    ``product`` is the public snake_case name; it's translated to NOAA's
    API spelling here.

    Every Phase 1 product ends up representable as a DataFrame (single-row
    for station-info-only responses, multi-row for exploded sub-tables) —
    extrfa, sealvltrends, and extremewaterlevels get dedicated parsers below;
    everything else falls through to a generic json_normalize on whichever
    top-level key holds a list.
    """
    api_product = _to_api_product(product)
    if api_product == "extrfa":
        df = _parse_extrfa(payload)
    elif api_product == "sealvltrends":
        df = _parse_sealvltrends(payload, detail)
    elif api_product == "extremewaterlevels":
        df = _parse_extremewaterlevels(payload, level_type)
    else:
        top_level_key = next(
            (k for k, v in payload.items() if isinstance(v, list)), None
        )
        if top_level_key is None:
            raise COOPSAPIError(
                f"DPAPI response for product '{product}' contains no list "
                f"value to parse; payload keys: {list(payload)}"
            )
        df = pd.json_normalize(payload[top_level_key])

    return df.reset_index(drop=True)


# ---------------------------------------------------------------------------
# Public orchestrator — called from Station.get_derived_product()
# ---------------------------------------------------------------------------


def get_derived_product(
    station: Station,
    product: str,
    start_date: str | None = None,
    end_date: str | None = None,
    year: int | None = None,
    units: str | None = "metric",
    datum: str | None = None,
    affil: str | None = None,
    projection_year: int | None = None,
    report_year: int | None = None,
    scenario: str | None = None,
    detail: str
    | None = None,  # sea_level_trends: "monthly_means" | "events" | "seasonal_cycle"
    level_type: str | None = None,  # extreme_water_levels: "high" | "low"
) -> pd.DataFrame:
    """Fetch a derived product for ``station`` from the NOAA DPAPI.

    Args:
        station: The bound Station instance — station.id is used as the
            station_id for this request.
        product: DPAPI product name, in conventional snake_case (e.g.
            "sea_level_trends", "slr_projection_offsets",
            "top_ten_water_levels", "extreme_water_levels",
            "rfa_extreme_water_levels") regardless of NOAA's underlying API
            spelling — see PRODUCT_ALIASES for the full mapping. Products
            like "slr_projections" already match NOAA's spelling as-is.
        start_date: Start date, any KNOWN_DATE_FORMATS format, normalized
            to DPAPI's required "%Y%m%d" before the request is sent.
            Required for htf_daily; also accepted (optional) by
            htf_monthly. Not accepted by htf_seasonal or htf_annual — use
            `year` instead.
        end_date: End date, same formats as start_date.
        year: Year filter, used by HTF products. Must be between 1800 and
            the current year.
        units: "metric" or "english". NOAA's server-side default when omitted
            varies by product — top_ten_water_levels, extreme_water_levels,
            rfa_extreme_water_levels, and htf_daily default to english;
            slr_projections defaults to metric. Passing units explicitly is
            recommended.
        datum: Datum reference — valid values depend on product, see
            DATUM_OPTIONS. Not every product accepts a datum.
        affil: "US" or "Global" — sea_level_trends, slr_projections,
            slr_projection_offsets.
        projection_year: slr_projections only.
        report_year: slr_projections, slr_projection_offsets.
        scenario: slr_projections only. One of: 'all', 'low',
            'intermediate-low', 'intermediate', 'intermediate-high',
            'high', 'extreme'. Default (server-side, when omitted) is
            'all'.
        detail: sea_level_trends only. "monthly_means" (deseasonalized monthly
            series), "events" (may be empty), or "seasonal_cycle" (the
            12-month seasonal pattern removed to compute the trend). Omit
            for the top-level trend statistics.
        level_type: extreme_water_levels only. "high" or "low" — filters
            tenYearEvents client-side. Omit for full station metadata.

    Raises:
        ValueError: product invalid, or a required/unsupported/invalid
            param for it.
        COOPSAPIError: DPAPI returned a non-200 response.

    Returns:
        A DataFrame. Single row for station-info-only responses (no
        detail/level_type given on sea_level_trends/extreme_water_levels),
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
        year=year,
        affil=affil,
        projection_year=projection_year,
        report_year=report_year,
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
