"""URL constants for the NOAA CO-OPS APIs.

One file so you know where to look when NOAA moves an endpoint.
"""

from __future__ import annotations

#: Metadata API base URL (list of all stations).
STATIONS_LIST_URL = (
    "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations.json"
)

#: Metadata API template for a specific station. Caller appends
#: ``/{station_id}.json?expand=...&units=...``.
METADATA_BASE_URL = "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/"

#: Data retrieval endpoint. Caller appends URL-encoded query parameters.
DATA_GETTER_URL = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?"

#: Derived product (DPAPI) base URL. Caller appends a product-specific
#: sub-path followed by URL-encoded query parameters. See
#: ``_derived.py`` for the URL-pattern routing logic.
DPAPI_BASE_URL = "https://api.tidesandcurrents.noaa.gov/dpapi/prod/webapi/"

#: SOAP WSDL for the (legacy) per-product data-availability endpoint.
INVENTORY_WSDL_URL = (
    "https://opendap.co-ops.nos.noaa.gov/axis/webservices/"
    "datainventory/wsdl/DataInventory.wsdl"
)
