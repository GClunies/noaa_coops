"""Python wrapper for the NOAA Tides & Currents (CO-OPS) APIs."""

from importlib.metadata import version

from noaa_coops._exceptions import COOPSAPIError
from noaa_coops.api import get_stations_from_bbox
from noaa_coops.station import Station

__all__ = ["COOPSAPIError", "Station", "get_stations_from_bbox"]
__version__ = version("noaa-coops")
