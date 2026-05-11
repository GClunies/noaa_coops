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

#: SOAP WSDL for the (legacy) per-product data-availability endpoint.
INVENTORY_WSDL_URL = (
    "https://opendap.co-ops.nos.noaa.gov/axis/webservices/"
    "datainventory/wsdl/DataInventory.wsdl"
)
