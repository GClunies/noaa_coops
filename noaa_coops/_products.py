"""Declarative product registry + parameter validation + URL-param builder.

Replaces the 186-line ``if/elif`` tree formerly in ``Station._check_product_params``
and the parallel tree in ``Station._build_request_url``. Adding or editing a
product is now a one-place change instead of three.
"""

from __future__ import annotations

from typing import Optional, Union

VALID_DATUMS: frozenset[str] = frozenset(
    {"CRD", "IGLD", "LWD", "MHHW", "MHW", "MTL", "MSL", "MLW", "MLLW", "NAVD", "STND"}
)
VALID_UNITS: frozenset[str] = frozenset({"metric", "english"})
VALID_TIME_ZONES: frozenset[str] = frozenset({"gmt", "lst", "lst_ldt"})

#: Every product NOAA exposes through the datagetter endpoint.
ALL_PRODUCTS: frozenset[str] = frozenset(
    {
        "water_level",
        "hourly_height",
        "high_low",
        "daily_mean",
        "monthly_mean",
        "one_minute_water_level",
        "predictions",
        "datums",
        "air_gap",
        "air_temperature",
        "water_temperature",
        "wind",
        "air_pressure",
        "conductivity",
        "visibility",
        "humidity",
        "salinity",
        "currents",
        "currents_predictions",
        "ofs_water_level",
    }
)

#: Products that require a ``datum`` parameter.
DATUM_REQUIRED: frozenset[str] = frozenset(
    {
        "water_level",
        "hourly_height",
        "high_low",
        "daily_mean",
        "monthly_mean",
        "one_minute_water_level",
        "predictions",
    }
)

#: Products that explicitly reject the ``interval`` parameter.
INTERVAL_FORBIDDEN: frozenset[str] = frozenset(
    {"water_level", "hourly_height", "one_minute_water_level"}
)

#: Products that require a ``bin_num`` parameter.
BIN_REQUIRED: frozenset[str] = frozenset({"currents", "currents_predictions"})

#: Allowed ``interval`` values per product. Products not in this map accept
#: any value unless they're also in ``INTERVAL_FORBIDDEN``.
ALLOWED_INTERVALS: dict[str, frozenset[str]] = {
    "predictions": frozenset({"h", "1", "5", "10", "15", "30", "60", "hilo"}),
    "currents": frozenset({"6", "h"}),
    "currents_predictions": frozenset({"h", "1", "6", "10", "30", "60", "max_slack"}),
}


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_params(
    product: str,
    datum: Optional[str],
    bin_num: Optional[int],
    interval: Optional[Union[str, int]],
    units: Optional[str],
    time_zone: Optional[str],
) -> None:
    """Validate every user-provided argument to ``Station.get_data``.

    Raises ``ValueError`` on the first failure. Called before any HTTP
    request is made.
    """
    if product not in ALL_PRODUCTS:
        raise ValueError(
            f"Invalid product '{product}' provided. See "
            "https://api.tidesandcurrents.noaa.gov/api/prod/#products "
            "for list of available products"
        )

    if product in DATUM_REQUIRED:
        if datum is None:
            raise ValueError(
                "No datum specified for water level data. See "
                "https://api.tidesandcurrents.noaa.gov/api/prod/#datum "
                "for list of available datums"
            )
        if datum.upper() not in VALID_DATUMS:
            raise ValueError(
                f"Invalid datum '{datum}' provided. See "
                "https://tidesandcurrents.noaa.gov/api/prod/#datum "
                "for list of available datums"
            )

    if product in INTERVAL_FORBIDDEN and interval is not None:
        raise ValueError(
            f"`interval` parameter is not supported for `{product}` product. "
            "See https://tidesandcurrents.noaa.gov/api/prod/#interval "
            "for details. These products have the following intervals "
            "that cannot be modified:\n"
            "    one_minute_water_level: 1 minute\n"
            "    water_level: 6 minutes\n"
            "    hourly_height: 1 hour\n"
        )

    if interval is not None and product in ALLOWED_INTERVALS:
        if str(interval) not in ALLOWED_INTERVALS[product]:
            raise ValueError(
                f"`interval` parameter {interval} is not supported for "
                f"`{product}` product. See "
                "https://tidesandcurrents.noaa.gov/api/prod/#interval "
                "for list of available intervals."
            )

    if product in BIN_REQUIRED and bin_num is None:
        raise ValueError(
            f"No `bin_num` specified for `{product}` product. Bin info can be "
            "found on the station info page "
            "(e.g., https://tidesandcurrents.noaa.gov/cdata/StationInfo?id=PUG1515)"
        )

    if units is not None and units not in VALID_UNITS:
        raise ValueError(
            f"Invalid units '{units}' provided. Must be one of: {sorted(VALID_UNITS)}"
        )

    if time_zone is not None and time_zone not in VALID_TIME_ZONES:
        raise ValueError(
            f"Invalid time zone '{time_zone}' provided. "
            f"Must be one of: {sorted(VALID_TIME_ZONES)}"
        )


# ---------------------------------------------------------------------------
# Request parameter assembly
# ---------------------------------------------------------------------------


def build_request_params(
    *,
    station_id: str,
    begin_date: str,
    end_date: str,
    product: str,
    datum: Optional[str],
    bin_num: Optional[int],
    interval: Optional[Union[str, int]],
    units: Optional[str],
    time_zone: Optional[str],
) -> dict[str, str]:
    """Build the URL-encoded query params dict for the datagetter endpoint.

    Assumes ``validate_params`` has already been called, i.e., every
    argument is valid for ``product``.
    """
    params: dict[str, str] = {
        "begin_date": begin_date,
        "end_date": end_date,
        "station": station_id,
        "product": product,
        "application": "noaa_coops",
        "format": "json",
    }

    if units is not None:
        params["units"] = units
    if time_zone is not None:
        params["time_zone"] = time_zone

    if product in DATUM_REQUIRED:
        # validate_params has already raised if datum is None/invalid here.
        assert datum is not None
        params["datum"] = datum
    elif product == "predictions" and datum is not None:
        # `predictions` historically accepts (but doesn't require) a datum.
        params["datum"] = datum

    if product in BIN_REQUIRED:
        assert bin_num is not None
        params["bin"] = str(bin_num)

    if interval is not None and product not in INTERVAL_FORBIDDEN:
        params["interval"] = str(interval)

    return params
