"""Module-level helper functions that are part of the public API."""

from __future__ import annotations

from noaa_coops._endpoints import STATIONS_LIST_URL
from noaa_coops._exceptions import COOPSAPIError
from noaa_coops._http import DEFAULT_TIMEOUT, _SESSION


def get_stations_from_bbox(
    lat_coords: list[float],
    lon_coords: list[float],
) -> list[str]:
    """Return station IDs whose location falls within a bounding box.

    Args:
        lat_coords: The lower and upper latitudes of the box (order-insensitive).
        lon_coords: The lower and upper longitudes of the box (order-insensitive).

    Raises:
        ValueError: ``lat_coords`` or ``lon_coords`` is not of length 2.
        COOPSAPIError: The NOAA stations list endpoint returned a non-200
            response.

    Returns:
        The IDs of every station strictly inside the lat/lon box.
    """
    if len(lat_coords) != 2 or len(lon_coords) != 2:
        raise ValueError("lat_coords and lon_coords must be of length 2.")

    response = _SESSION.get(STATIONS_LIST_URL, timeout=DEFAULT_TIMEOUT)

    if response.status_code != 200:
        raise COOPSAPIError(
            f"Failed to fetch station list. Status code: {response.status_code}"
        )

    json_dict = response.json()

    lat_coords = sorted(lat_coords)
    lon_coords = sorted(lon_coords)

    return [
        station_dict["id"]
        for station_dict in json_dict["stations"]
        if lon_coords[0] < station_dict["lng"] < lon_coords[1]
        and lat_coords[0] < station_dict["lat"] < lat_coords[1]
    ]
