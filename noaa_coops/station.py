"""The ``Station`` class — public entry point for fetching NOAA CO-OPS data.

Keeps only orchestration logic. Implementation details live in sibling
modules (see ``_http``, ``_products``, ``_parsing``, ``_metadata``).
"""

from __future__ import annotations

import logging
import math
import warnings
from datetime import datetime, timedelta
from typing import Optional, Union

import pandas as pd
import requests
import zeep

from noaa_coops._endpoints import DATA_GETTER_URL, INVENTORY_WSDL_URL
from noaa_coops._exceptions import COOPSAPIError
from noaa_coops._http import DEFAULT_TIMEOUT, _SESSION, _SOAP_SESSION
from noaa_coops._metadata import populate_metadata
from noaa_coops._parsing import normalize_data_frame, parse_known_date_formats
from noaa_coops._products import build_request_params, validate_params

# Back-compat re-exports (callers did `from noaa_coops.station import COOPSAPIError`
# for years; keep that path working after the Tier 4 split).
__all__ = ["COOPSAPIError", "DEFAULT_TIMEOUT", "Station"]

logger = logging.getLogger(__name__)


class Station:
    """NOAA CO-OPS station client.

    Constructs by ID and immediately fetches metadata. Users then call
    :meth:`get_data` to retrieve time-series observations/predictions,
    or read any of the many metadata attributes populated during
    construction.

    Supported NOAA APIs:
        - Data retrieval — https://tidesandcurrents.noaa.gov/api/
        - Metadata (mdapi) — https://tidesandcurrents.noaa.gov/mdapi/latest/
        - Data inventory (SOAP) — https://opendap.co-ops.nos.noaa.gov/axis/
    """

    # Per-product SOAP data inventory: {product_name: {"start_date": ..., "end_date": ...}}
    # Always set by __init__; empty dict `{}` indicates SOAP fetch failed.
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
        validate_params(product, datum, bin_num, interval, units, time_zone)

        begin_dt, begin_str = parse_known_date_formats(begin_date)
        end_dt, end_str = parse_known_date_formats(end_date)
        delta = end_dt - begin_dt

        single_block = delta.days <= 31 or (
            delta.days <= 365 and product in ("hourly_height", "high_low")
        )

        if single_block:
            data_url = self._build_request_url(
                begin_dt.strftime("%Y%m%d %H:%M"),
                end_dt.strftime("%Y%m%d %H:%M"),
                product=product,
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
    # Internals
    # ------------------------------------------------------------------

    def _build_request_url(
        self,
        begin_date: str,
        end_date: str,
        *,
        product: str,
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
        datum: Optional[str],
        bin_num: Optional[int],
        interval: Optional[Union[str, int]],
        units: Optional[str],
        time_zone: Optional[str],
    ) -> pd.DataFrame:
        """Fetch a date range that spans more than one NOAA block.

        Loops over fixed-size blocks (31 or 365 days), accumulates
        successful block DataFrames into a list, concatenates once at
        the end (O(n) memory vs. the old O(n²) concat-in-loop pattern).
        Failed blocks are surfaced via logger.warning + df.attrs
        rather than silently dropped.
        """
        block_size = 365 if product in ("hourly_height", "high_low") else 31
        delta = end_dt - begin_dt
        num_blocks = int(math.floor(delta.days / block_size))

        blocks: list[pd.DataFrame] = []
        missing_blocks: list[dict[str, str]] = []

        for i in range(num_blocks + 1):
            begin_loop = begin_dt + timedelta(days=(i * block_size))
            end_loop = begin_loop + timedelta(days=block_size)
            end_loop = end_dt if end_loop > end_dt else end_loop

            data_url = self._build_request_url(
                begin_loop.strftime("%Y%m%d %H:%M"),
                end_loop.strftime("%Y%m%d %H:%M"),
                product=product,
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
                    num_blocks + 1,
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
                f"{len(missing_blocks)} of {num_blocks + 1} blocks failed "
                f"for product {product!r}. See df.attrs['missing_blocks'] "
                "for per-block error details.",
                RuntimeWarning,
                stacklevel=2,
            )
        return df

    def _make_api_request(self, data_url: str, product: str) -> pd.DataFrame:
        """GET the datagetter endpoint and return the response JSON as a DataFrame.

        Raises:
            COOPSAPIError: HTTP non-200, or a 200 response whose JSON body
                contains a top-level ``"error"`` key.
        """
        res = _SESSION.get(data_url, timeout=DEFAULT_TIMEOUT)

        if res.status_code != 200:
            raise COOPSAPIError(
                message=(
                    f"CO-OPS API returned an error. Status Code: "
                    f"{res.status_code}. Reason: {res.reason}\n"
                ),
            )

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

        key = "predictions" if product == "predictions" else "data"
        return pd.json_normalize(json_dict[key])
