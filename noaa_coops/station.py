"""The ``Station`` class — public entry point for fetching NOAA CO-OPS data.

Keeps only orchestration logic. Implementation details live in sibling
modules (see ``_http``, ``_products``, ``_parsing``, ``_metadata``).
"""

from __future__ import annotations

import logging
import math
import re
import warnings
from datetime import datetime, timedelta
from typing import Optional, Union

import pandas as pd
import requests
import zeep

from noaa_coops._derived import get_derived_product as _get_derived_product
from noaa_coops._endpoints import DATA_GETTER_URL, INVENTORY_WSDL_URL
from noaa_coops._exceptions import COOPSAPIError
from noaa_coops._http import DEFAULT_TIMEOUT, _SESSION, _SOAP_SESSION
from noaa_coops._metadata import populate_metadata
from noaa_coops._parsing import normalize_data_frame, parse_known_date_formats
from noaa_coops._products import (
    build_request_params,
    get_max_days,
    validate_params,
)

# Back-compat re-exports (callers did `from noaa_coops.station import COOPSAPIError`
# for years; keep that path working after the Tier 4 split).
__all__ = ["COOPSAPIError", "DEFAULT_TIMEOUT", "Station"]

logger = logging.getLogger(__name__)

# NOAA's SOAP DataInventory service accepts only 7-digit numeric station IDs
# (water-level / tide stations). Currents / PORTS stations use alphanumeric
# IDs like ``"s09010"`` and ``"PUG1515"`` -- the SOAP endpoint rejects these
# deterministically with a ``Wrong Station ID`` fault. Skip the call for
# non-eligible IDs instead of logging a warning on every ``Station(...)``.
_SOAP_INVENTORY_ID_PATTERN = re.compile(r"^\d{7}$")


class Station:
    """NOAA CO-OPS station client.

    Constructs by ID and immediately fetches metadata. Users then call
    :meth:`get_data` to retrieve time-series observations/predictions,
    :meth:`get_derived_product` for computed/aggregate products like sea
    level trends and high-tide-flooding counts, or read any of the many
    metadata attributes populated during construction.

    Supported NOAA APIs:
        - Data retrieval — https://tidesandcurrents.noaa.gov/api/
        - Metadata (mdapi) — https://tidesandcurrents.noaa.gov/mdapi/latest/
        - Data inventory (SOAP) — https://opendap.co-ops.nos.noaa.gov/axis/
        - Derived products (DPAPI) — https://api.tidesandcurrents.noaa.gov/dpapi/prod/
    """

    # Per-product SOAP data inventory: {product_name: {"start_date": ..., "end_date": ...}}
    # Always set by __init__. An empty dict ``{}`` means either (a) the
    # station ID is not eligible for SOAP DataInventory -- NOAA only
    # supports 7-digit numeric IDs there, so currents/PORTS stations like
    # ``s09010`` always produce ``{}`` by design -- or (b) an eligible ID
    # had a transient SOAP failure (network error, malformed response).
    data_inventory: dict[str, dict[str, str]]

    def __init__(self, id: str, units: str = "metric") -> None:
        """Initialize a Station.

        Args:
            id: The NOAA CO-OPS station ID (e.g., ``"9447130"`` for Seattle).
                See https://tidesandcurrents.noaa.gov/ to find stations.
            units: Either ``"metric"`` or ``"english"``. Defaults to ``"metric"``.
        """
        self.id: str = str(id)
        self.units: str = units
        self.get_metadata()

        if not _SOAP_INVENTORY_ID_PATTERN.match(self.id):
            # SOAP DataInventory requires a 7-digit numeric ID. Alphanumeric
            # currents/PORTS IDs (e.g. "s09010") get an empty inventory by
            # design -- no SOAP endpoint exists for them. Log at INFO so
            # anyone wondering why ``data_inventory`` is empty sees the
            # reason when they bump their log level, without warning-level
            # noise for every currents Station(...) call.
            self.data_inventory = {}
            logger.info(
                "Station %s uses a non-7-digit ID; NOAA's SOAP "
                "DataInventory service only supports water-level/met "
                "stations with 7-digit numeric IDs, so data_inventory "
                "will be empty. This is expected for currents/PORTS "
                "stations.",
                self.id,
            )
            return

        try:
            self.get_data_inventory()
        except (
            requests.RequestException,
            zeep.exceptions.Error,
            AttributeError,
            TypeError,
        ) as exc:
            # Data inventory is best-effort metadata. If the SOAP endpoint is
            # unreachable, returns a fault, or raises a built-in from zeep's
            # parsing internals (malformed WSDL, missing attributes), degrade
            # gracefully rather than failing Station construction.
            # KeyboardInterrupt / SystemExit are intentionally NOT caught --
            # those must propagate.
            self.data_inventory = {}
            logger.warning(
                "Data inventory fetch failed for station %s: %s",
                self.id,
                exc,
            )

    # ------------------------------------------------------------------
    # Metadata + inventory
    # ------------------------------------------------------------------

    def get_metadata(self) -> None:
        """Fetch station metadata from the NOAA mdapi and populate attributes."""
        populate_metadata(self, self.units)

    def get_data_inventory(self) -> None:
        """Populate :attr:`data_inventory` from NOAA's SOAP DataInventory service.

        mdapi has no equivalent endpoint for per-product first/last-date
        coverage, so this path uses SOAP. Best-effort: failures degrade to
        an empty dict and log a warning (see :meth:`__init__`).
        """
        transport = zeep.Transport(session=_SOAP_SESSION)
        client = zeep.Client(wsdl=INVENTORY_WSDL_URL, transport=transport)
        response = client.service.getDataInventory(self.id)
        # zeep marshals SOAP complex types into CompoundValue objects that
        # support `[]` subscript but NOT `.get()`. Use subscript + catch
        # missing-key / wrong-shape cases uniformly.
        try:
            parameters = response["parameter"] or []
        except (KeyError, TypeError):
            parameters = []

        names = [x["name"] for x in parameters]
        starts = [x["first"] for x in parameters]
        ends = [x["last"] for x in parameters]
        unique_names = list(set(names))

        inventory: dict[str, dict[str, str]] = {}
        for name in unique_names:
            idxs = [i for i, x in enumerate(names) if x == name]
            inventory[name] = {
                "start_date": starts[idxs[0]],
                "end_date": ends[idxs[-1]],
            }
        self.data_inventory = inventory

    # ------------------------------------------------------------------
    # Data retrieval
    # ------------------------------------------------------------------

    def get_data(
        self,
        begin_date: str,
        end_date: str,
        product: str,
        max_min_type: Optional[str] = None,
        datum: Optional[str] = None,
        bin_num: Optional[int] = None,
        interval: Optional[Union[str, int]] = None,
        units: Optional[str] = "metric",
        time_zone: Optional[str] = "gmt",
    ) -> pd.DataFrame:
        """Fetch data from the NOAA CO-OPS API as a pandas DataFrame.

        Args:
            begin_date: Start date. Accepts any of the formats in
                :data:`noaa_coops._parsing.KNOWN_DATE_FORMATS`.
            end_date: End date, same formats as ``begin_date``.
            product: Data product name. See
                https://api.tidesandcurrents.noaa.gov/api/prod/#products.
            max_min_type: Optional; ``"max"`` or ``"min"``. Only valid when
                ``product="daily_max_min"``.
            datum: Required for water-level products.
            bin_num: Required for ``currents`` / ``currents_predictions``.
            interval: Optional; allowed values depend on ``product``.
            units: ``"metric"`` (default) or ``"english"``.
            time_zone: ``"gmt"`` (default), ``"lst"``, or ``"lst_ldt"``.

        Raises:
            ValueError: A parameter is invalid for the chosen product.
            COOPSAPIError: The API returned an error for one of the requested
                blocks AND every block failed (partial failures surface via
                a ``RuntimeWarning`` and ``df.attrs["missing_blocks"]``).

        Returns:
            A DataFrame indexed by timestamp. Column set depends on
            ``product``. When partial failures occurred,
            ``df.attrs["missing_blocks"]`` lists them.
        """
        validate_params(
            product, max_min_type, datum, bin_num, interval, units, time_zone
        )

        begin_dt, begin_str = parse_known_date_formats(begin_date)
        end_dt, end_str = parse_known_date_formats(end_date)
        delta = end_dt - begin_dt

        if interval is None and product == "daily_max_min":
            interval = "h"

        max_days = get_max_days(product, interval)
        single_block = delta.days <= max_days

        if single_block:
            data_url = self._build_request_url(
                begin_dt.strftime("%Y%m%d %H:%M"),
                end_dt.strftime("%Y%m%d %H:%M"),
                product=product,
                max_min_type=max_min_type,
                datum=datum,
                bin_num=bin_num,
                interval=interval,
                units=units,
                time_zone=time_zone,
            )
            df = self._make_api_request(data_url, product)
        else:
            df = self._fetch_in_blocks(
                begin_dt=begin_dt,
                end_dt=end_dt,
                product=product,
                max_min_type=max_min_type,
                datum=datum,
                bin_num=bin_num,
                interval=interval,
                units=units,
                time_zone=time_zone,
            )

        if df.empty:
            raise COOPSAPIError(
                f"No data returned for {product} product between "
                f"{begin_str} and {end_str}"
            )

        df = normalize_data_frame(df)
        self.data = df
        return df

    # ------------------------------------------------------------------
    # Derived products (DPAPI)
    # ------------------------------------------------------------------

    def get_derived_product(
        self,
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
        detail: Optional[str] = None,
        level_type: Optional[str] = None,
    ) -> pd.DataFrame:
        """Fetch a derived product from the NOAA CO-OPS Derived Product API (DPAPI).

        The DPAPI provides access to computed/aggregate products — sea
        level trends, sea level rise projections, high-tide-flooding
        counts, extreme water levels, and regional frequency analysis —
        as opposed to :meth:`get_data`'s raw time-series observations.
        Always scoped to this station (``station.id`` is used as the
        station_id for every request).

        Args:
            product: DPAPI product name. One of: ``"htf_daily"``,
                ``"htf_monthly"``, ``"htf_seasonal"``,
                ``"htf_annual"``, ``"sea_level_trends"``,
                ``"slr_projections"``, ``"slr_projection_offsets"``,
                ``"rfa_extreme_water_levels"``, ``"top_ten_water_levels"``,
                ``"extreme_water_levels"``.
            start_date: Start date. Accepts any of the formats in
                :data:`noaa_coops._parsing.KNOWN_DATE_FORMATS`; normalized
                to DPAPI's required ``"%Y%m%d"`` before the request is
                sent. Required for ``"htf_daily"``; also accepted
                (optional) by ``"htf_monthly"``. Not accepted by
                ``"htf_seasonal"`` or ``"htf_annual"`` — use ``year``
                instead.
            end_date: End date, same formats as ``start_date``.
            year: Year filter, used by HTF products. Must be between 1800
                and the current year.
            units: ``"metric"`` (default) or ``"english"``. NOAA's
                server-side default when omitted varies by product —
                ``top_ten_water_levels``, ``extreme_water_levels``,
                ``rfa_extreme_water_levels``, and ``htf_daily`` default to
                english; ``slr_projections`` defaults to metric. Passing
                units explicitly is recommended.
            datum: Datum reference. Valid values depend on ``product`` —
                not every product accepts a datum at all.
            affil: ``"US"`` or ``"Global"`` — ``sea_level_trends``,
                ``slr_projections``, ``slr_projection_offsets``.
            projection_year: ``slr_projections`` only.
            report_year: ``slr_projections``, ``slr_projection_offsets``.
                Not every report year has published data — if you get an
                empty result, try omitting this or checking which years
                are available.
            scenario: ``slr_projections`` only. One of ``"all"``,
                ``"low"``, ``"intermediate-low"``, ``"intermediate"``,
                ``"intermediate-high"``, ``"high"``, ``"extreme"``.
                Default (server-side, when omitted) is ``"all"``.
            detail: ``sea_level_trends`` only. ``"monthly_means"``
                (deseasonalized monthly series), ``"events"`` (may be
                empty), or ``"seasonal_cycle"`` (the 12-month seasonal
                pattern removed to compute the trend). Omit for the
                top-level trend statistics.
            level_type: ``extreme_water_levels`` only. ``"high"`` or
                ``"low"`` — filters the ten-year event history. Omit for
                full station metadata.

        Raises:
            ValueError: ``product`` is invalid, or a parameter is
                required/unsupported/invalid for the chosen product.
            COOPSAPIError: DPAPI returned a non-200 response.

        Returns:
            A DataFrame. Multi-row results
            (e.g. RFA's exploded return-period table)
            include station identity columns so each row
            remains attributable to its station even after
            the DataFrame leaves this call's scope.
        """
        return _get_derived_product(
            self,
            product,
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
            level_type=level_type,
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _build_request_url(
        self,
        begin_date: str,
        end_date: str,
        *,
        product: str,
        max_min_type: Optional[str],
        datum: Optional[str],
        bin_num: Optional[int],
        interval: Optional[Union[str, int]],
        units: Optional[str],
        time_zone: Optional[str],
    ) -> str:
        """URL-encode the datagetter query for this product + date range."""
        params = build_request_params(
            station_id=self.id,
            begin_date=begin_date,
            end_date=end_date,
            product=product,
            max_min_type=max_min_type,
            datum=datum,
            bin_num=bin_num,
            interval=interval,
            units=units,
            time_zone=time_zone,
        )
        request_url = (
            requests.Request("GET", DATA_GETTER_URL, params=params).prepare().url
        )
        if request_url is None:
            raise COOPSAPIError(f"Failed to build request URL for product {product!r}")
        return request_url

    def _fetch_in_blocks(
        self,
        *,
        begin_dt: datetime,
        end_dt: datetime,
        product: str,
        max_min_type: Optional[str],
        datum: Optional[str],
        bin_num: Optional[int],
        interval: Optional[Union[str, int]],
        units: Optional[str],
        time_zone: Optional[str],
    ) -> pd.DataFrame:
        """Fetch a date range that spans more than one NOAA block.

        Loops over product-specific blocks (see ``PRODUCT_LIMITS`` in
        ``_products.py`` for per-product day limits), accumulates
        successful block DataFrames into a list, concatenates once at
        the end (O(n) memory vs. the old O(n²) concat-in-loop pattern).
        Failed blocks are surfaced via logger.warning + df.attrs
        rather than silently dropped.
        """
        block_size = get_max_days(product, interval)
        delta = end_dt - begin_dt
        num_blocks = int(math.ceil(delta.days / block_size))

        blocks: list[pd.DataFrame] = []
        missing_blocks: list[dict[str, str]] = []

        for i in range(num_blocks):
            begin_loop = begin_dt + timedelta(days=(i * block_size))
            end_loop = begin_loop + timedelta(days=block_size)
            end_loop = end_dt if end_loop > end_dt else end_loop

            data_url = self._build_request_url(
                begin_loop.strftime("%Y%m%d %H:%M"),
                end_loop.strftime("%Y%m%d %H:%M"),
                product=product,
                max_min_type=max_min_type,
                datum=datum,
                bin_num=bin_num,
                interval=interval,
                units=units,
                time_zone=time_zone,
            )
            try:
                blocks.append(self._make_api_request(data_url, product))
            except COOPSAPIError as exc:
                missing_blocks.append(
                    {
                        "begin": begin_loop.isoformat(),
                        "end": end_loop.isoformat(),
                        "error": str(exc),
                    }
                )
                logger.warning(
                    "Block %d/%d (%s → %s) failed: %s",
                    i + 1,
                    num_blocks,
                    begin_loop.date(),
                    end_loop.date(),
                    exc,
                )

        df = pd.concat(blocks) if blocks else pd.DataFrame()
        if missing_blocks:
            # attrs must be assigned AFTER the final concat (concat
            # discards intermediate attrs).
            df.attrs["missing_blocks"] = missing_blocks
            warnings.warn(
                f"{len(missing_blocks)} of {num_blocks} blocks failed "
                f"for product {product!r}. See df.attrs['missing_blocks'] "
                "for per-block error details.",
                RuntimeWarning,
                stacklevel=2,
            )
        return df

    def _make_api_request(self, data_url: str, product: str) -> pd.DataFrame:
        """GET the datagetter endpoint and return the response JSON as a DataFrame.

        Routes payload extraction based on the `product` type, flattening
        nested/heterogenous dictionaries (like `daily_max_min`) into a
        standardized column schema before passing to Pandas.

        Raises:
            COOPSAPIError: HTTP non-200, or a 200 response whose JSON body
                contains a top-level ``"error"`` key.
            KeyError: If a recognizable data payload cannot be found.
        """
        res = _SESSION.get(data_url, timeout=DEFAULT_TIMEOUT)

        # Check the status code
        if res.status_code != 200:
            err_msg = (
                f"CO-OPS API returned an error. Status Code: "
                f"{res.status_code}. Reason: {res.reason}"
            )
            # Extract a specific JSON error message, if it exists
            try:
                err_payload = res.json()
                if "error" in err_payload and "message" in err_payload["error"]:
                    err_msg += f" | NOAA Message: {err_payload['error']['message']}"
            except Exception:
                pass  # If it's a 503 HTML page, just ignore and raise the base error
            raise COOPSAPIError(message=err_msg + "\n")
        json_dict = res.json()

        if "error" in json_dict:
            err_msg = f"CO-OPS API returned an error: {json_dict['error']['message']}"
            if product == "water_level":
                err_msg += (
                    "\n\nNOTE: The requested product `water_level` is only "
                    "available from 1996 and onwards. Try using `hourly_height` "
                    "or `high_low` products instead."
                )
            raise COOPSAPIError(message=err_msg)

        # ------------------------------------------------------------
        # Explicitly route the payload extraction based on the product
        # ------------------------------------------------------------

        if product == "daily_max_min":
            if "data" not in json_dict or not isinstance(json_dict["data"], list):
                payload = []
            else:
                flattened_payload = []
                for item in json_dict["data"]:
                    for key, records in item.items():
                        if "dailyMin" in key:
                            record_type = "min"
                        elif "dailyMax" in key:
                            record_type = "max"
                        else:
                            raise KeyError(
                                f"Unexpected record key '{key}' in daily_max_min "
                                "response; expected a key containing 'dailyMax' "
                                "or 'dailyMin'."
                            )
                        for record in records:
                            # Standardize the varying NOAA keys using safe fallbacks
                            clean_record = {
                                "record_type": record_type,
                                "date": record.get(
                                    "date6Min", record.get("dateHourly")
                                ),
                                "time": record.get(
                                    "time6Min", record.get("timeHourly")
                                ),
                                "value": record.get(
                                    "value6Min", record.get("valueHourly")
                                ),
                                "pcComplete": record.get(
                                    "pcComplete6Min", record.get("pcCompleteHourly")
                                ),
                                "flag": record.get(
                                    "flag6Min", record.get("flagHourly")
                                ),
                            }
                            flattened_payload.append(clean_record)
                payload = flattened_payload

        elif product == "predictions":
            payload = json_dict.get("predictions", [])

        elif product == "currents_predictions":
            payload = json_dict.get("current_predictions", {}).get("cp", [])

        elif "data" in json_dict:
            payload = json_dict["data"]

        else:
            found_keys = list(json_dict.keys())
            raise KeyError(
                f"Could not locate a recognizable data payload for product '{product}'. "
                f"Keys found: {found_keys}"
            )

        return pd.json_normalize(payload)
