from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Optional, Union

import pandas as pd
import requests
import zeep
from pandas import json_normalize


class COOPSAPIError(Exception):
    """Raised when a NOAA CO-OPS API request returns an error."""

    def __init__(self, message: str, error: dict) -> None:
        """Initialize COOPSAPIError.

        Args:
            message (str): The error message.
            error (dict): The error dict returned by the NOAA CO-OPS API.
        """
        self.message = message
        self.error = error
        super().__init__(self.message)


def get_stations_from_bbox(
    lat_coords: list[float, float],
    lon_coords: list[float, float],
) -> list[str]:
    """Return a list of stations IDs found within a bounding box.

    Args:
        lat_coords (list[float]): The lower and upper latitudes of the box.
        lon_coords (list[float]): The lower and upper longitudes of the box.

    Raises:
        ValueError: lat_coords or lon_coords are not of length 2.

    Returns:
        list[str]: A list of station IDs.
    """
    data_url = "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations.json"
    response = requests.get(data_url)
    json_dict = response.json()

    station_list = []

    if len(lat_coords) != 2 or len(lon_coords) != 2:
        raise ValueError("lat_coords and lon_coords must be of length 2.")

    # Ensure lat_coords and lon_coords are in the correct order
    if lat_coords[0] > lat_coords[1]:
        lat_coords[0], lat_coords[1] = lat_coords[1], lat_coords[0]

    if lon_coords[0] > lon_coords[1]:
        lon_coords[0], lon_coords[1] = lon_coords[1], lon_coords[0]

    # Search through stations and append to station_list if within bounding box
    for station_dict in json_dict["stations"]:
        if lon_coords[0] < station_dict["lng"] < lon_coords[1]:
            if lat_coords[0] < station_dict["lat"] < lat_coords[1]:
                station_list.append(station_dict["id"])

    return station_list


class Station:
    """noaa_coops Station class to interact with NOAA CO-OPS APIs.

    Supported APIs:
    - Data retrieval API, see https://tidesandcurrents.noaa.gov/api/
    - Metadata API, see: https://tidesandcurrents.noaa.gov/mdapi/latest/
    - Data inventory API, see: https://opendap.co-ops.nos.noaa.gov/axis/

    Stations are identified by a unique station ID (see
    https://tidesandcurrents.noaa.gov/ to find stations and their IDs). Stations
    have:
    - metadata
    - data inventory
    - data (observed or predicted)
    """

    def __init__(self, id: str, units: str = "metric"):
        """Initialize Station object.

        Args:
            id (str): The Station's ID. See
                https://tidesandcurrents.noaa.gov/ to find stations and their IDs
            units (str): The units data should be reported in.
                Defaults to "metric".
        """
        self.id = id
        self.units = units
        self.get_metadata()

        try:
            self.get_data_inventory()
        except:  # noqa: E722
            pass

    def get_data_inventory(self):
        """Get data inventory for Station and append to Station object.

        Data inventory is fetched from the NOAA CO-OPS SOAP Web Service
        (https://opendap.co-ops.nos.noaa.gov/axis/).
        """
        wsdl = (
            "https://opendap.co-ops.nos.noaa.gov/axis/webservices/"
            "datainventory/wsdl/DataInventory.wsdl"
        )
        client = zeep.Client(wsdl=wsdl)
        response = client.service.getDataInventory(self.id)["parameter"]
        names = [x["name"] for x in response]
        starts = [x["first"] for x in response]
        ends = [x["last"] for x in response]
        unique_names = list(set(names))
        inventory_dict = {}

        for name in unique_names:
            idxs = [i for i, x in enumerate(names) if x == name]
            inventory_dict[name] = {
                "start_date": [starts[i] for i in idxs][0],
                "end_date": [ends[i] for i in idxs][-1],
            }

        self.data_inventory = inventory_dict

    def get_metadata(self):
        """Get metadata for Station and append to Station object."""
        metadata_base_url = (
            "https://api.tidesandcurrents.noaa.gov/mdapi/" "prod/webapi/stations/"
        )
        extension = ".json"
        metadata_expand = (
            "?expand=details,sensors,products,disclaimers,"
            "notices,datums,harcon,tidepredoffets,benchmarks,"
            "nearby,bins,deployments,currentpredictionoffsets,"
            "floodlevels"
        )
        units_for_url = "?units=" + self.units
        metadata_url = (
            metadata_base_url + self.id + extension + metadata_expand + units_for_url
        )
        response = requests.get(metadata_url)
        json_dict = response.json()
        station_metadata = json_dict["stations"][0]

        # Set class attributes base on provided metadata
        if "datums" in station_metadata:  # if True --> water levels
            self.metadata = station_metadata
            self.affiliations = station_metadata["affiliations"]
            self.benchmarks = station_metadata["benchmarks"]
            self.datums = station_metadata["datums"]
            # self.details = station_metadata['details']  # Only 4 water levels
            self.disclaimers = station_metadata["disclaimers"]
            self.flood_levels = station_metadata["floodlevels"]
            self.greatlakes = station_metadata["greatlakes"]
            self.tidal_constituents = station_metadata["harmonicConstituents"]
            self.lat_lon = {
                "lat": station_metadata["lat"],
                "lon": station_metadata["lng"],
            }
            self.name = station_metadata["name"]
            self.nearby_stations = station_metadata["nearby"]
            self.notices = station_metadata["notices"]
            self.observe_dst = station_metadata["observedst"]
            self.ports_code = station_metadata["portscode"]
            self.products = station_metadata["products"]
            self.sensors = station_metadata["sensors"]
            self.shef_code = station_metadata["shefcode"]
            self.state = station_metadata["state"]
            self.storm_surge = station_metadata["stormsurge"]
            self.tidal = station_metadata["tidal"]
            self.tide_type = station_metadata["tideType"]
            self.timezone = station_metadata["timezone"]
            self.timezone_corr = station_metadata["timezonecorr"]

        elif "tidepredoffsets" in station_metadata:  # if True --> pred tide
            self.metadata = station_metadata
            self.state = station_metadata["state"]
            self.tide_pred_offsets = station_metadata["tidepredoffsets"]
            self.type = station_metadata["type"]
            self.time_meridian = station_metadata["timemeridian"]
            self.reference_id = station_metadata["reference_id"]
            self.timezone_corr = station_metadata["timezonecorr"]
            self.name = station_metadata["name"]
            self.lat_lon = {
                "lat": station_metadata["lat"],
                "lon": station_metadata["lng"],
            }
            self.affiliations = station_metadata["affiliations"]
            self.ports_code = station_metadata["portscode"]
            self.products = station_metadata["products"]
            self.disclaimers = station_metadata["disclaimers"]
            self.notices = station_metadata["notices"]
            self.tide_type = station_metadata["tideType"]

        elif "bins" in station_metadata:  # if True --> currents
            self.metadata = station_metadata
            self.project = station_metadata["project"]
            self.deployed = station_metadata["deployed"]
            self.retrieved = station_metadata["retrieved"]
            self.timezone_offset = station_metadata["timezone_offset"]
            self.observe_dst = station_metadata["observedst"]
            self.project_type = station_metadata["project_type"]
            self.noaa_chart = station_metadata["noaachart"]
            self.deployments = station_metadata["deployments"]
            self.bins = station_metadata["bins"]
            self.name = station_metadata["name"]
            self.lat_lon = {
                "lat": station_metadata["lat"],
                "lon": station_metadata["lng"],
            }
            self.affiliations = station_metadata["affiliations"]
            self.ports_code = station_metadata["portscode"]
            self.products = station_metadata["products"]
            self.disclaimers = station_metadata["disclaimers"]
            self.notices = station_metadata["notices"]
            self.tide_type = station_metadata["tideType"]

        elif "currbin" in station_metadata:  # if True --> predicted currents
            self.metadata = station_metadata
            self.current_pred_offsets = station_metadata["currentpredictionoffsets"]
            self.curr_bin = station_metadata["currbin"]
            self.type = station_metadata["type"]
            self.depth = station_metadata["depth"]
            self.depth_type = station_metadata["depthType"]
            self.name = station_metadata["name"]
            self.lat_lon = {
                "lat": station_metadata["lat"],
                "lon": station_metadata["lng"],
            }
            self.affiliations = station_metadata["affiliations"]
            self.ports_code = station_metadata["portscode"]
            self.products = station_metadata["products"]
            self.disclaimers = station_metadata["disclaimers"]
            self.notices = station_metadata["notices"]
            self.tide_type = station_metadata["tideType"]

    def _build_request_url(
        self,
        begin_date: str,
        end_date: str,
        product: str,
        datum: Optional[str] = None,
        bin_num: Optional[int] = None,
        interval: Optional[Union[str, int]] = None,
        units: Optional[str] = "metric",
        time_zone: Optional[str] = "gmt",
    ) -> str:
        """Build a request URL for the NOAA CO-OPS API.

        See: https://tidesandcurrents.noaa.gov/api/

        Args:
            begin_date (str): Start date of the data to be fetched.
            end_date (str): End date of the data to be fetched.
            product (str): Data product to be fetched.
            datum (str, optional): Datum to use for water level products.
            bin_num (int, optional): Bin to use for current products. Defaults to None.
            interval (Union[str, int], optional): Time interval of fetched data.
                Defaults to None.
            units (str, optional): Units of fetched data. Defaults to "metric".
            time_zone (str, optional): Time zone used when returning fetched data.
                Defaults to "gmt".

        Raises:
            ValueError: One of the specified arguments is invalid.

        Returns:
            str: Request URL for NOAA CO-OPS API.
        """
        base_url = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?"

        if product == "water_level":
            if datum is None:
                raise ValueError(
                    "No datum specified for water level data. See"
                    " https://tidesandcurrents.noaa.gov/api/#datum "
                    "for list of available datums"
                )
            else:
                parameters = {
                    "begin_date": begin_date,
                    "end_date": end_date,
                    "station": self.id,
                    "product": product,
                    "datum": datum,
                    "units": units,
                    "time_zone": time_zone,
                    "application": "noaa_coops",
                    "format": "json",
                }

                if interval is not None:
                    parameters["interval"] = interval

        elif product == "hourly_height":
            if datum is None:
                raise ValueError(
                    "No datum specified for water level data. See"
                    " https://tidesandcurrents.noaa.gov/api/#datum "
                    "for list of available datums"
                )
            else:
                parameters = {
                    "begin_date": begin_date,
                    "end_date": end_date,
                    "station": self.id,
                    "product": product,
                    "datum": datum,
                    "units": units,
                    "time_zone": time_zone,
                    "application": "noaa_coops",
                    "format": "json",
                }

        elif product == "high_low":
            if datum is None:
                raise ValueError(
                    "No datum specified for water level data. See"
                    " https://tidesandcurrents.noaa.gov/api/#datum "
                    "for list of available datums"
                )
            else:
                parameters = {
                    "begin_date": begin_date,
                    "end_date": end_date,
                    "station": self.id,
                    "product": product,
                    "datum": datum,
                    "units": units,
                    "time_zone": time_zone,
                    "application": "noaa_coops",
                    "format": "json",
                }

        elif product == "predictions":
            parameters = {
                "begin_date": begin_date,
                "end_date": end_date,
                "station": self.id,
                "product": product,
                "datum": datum,
                "units": units,
                "time_zone": time_zone,
                "application": "noaa_coops",
                "format": "json",
            }

            if interval is not None:
                parameters["interval"] = interval

        elif product == "currents":
            if bin_num is None:
                raise ValueError(
                    "No bin specified for current data. Bin info can be "
                    "found on the station info page"
                    " (e.g., https://tidesandcurrents.noaa.gov/cdata/StationInfo?id=PUG1515)"  # noqa
                )
            else:
                parameters = {
                    "begin_date": begin_date,
                    "end_date": end_date,
                    "station": self.id,
                    "product": product,
                    "bin": str(bin_num),
                    "units": units,
                    "time_zone": time_zone,
                    "application": "noaa_coops",
                    "format": "json",
                }

        else:  # All other data types (e.g., meteoroligcal conditions)
            parameters = {
                "begin_date": begin_date,
                "end_date": end_date,
                "station": self.id,
                "product": product,
                "interval": interval,
                "units": units,
                "time_zone": time_zone,
                "application": "noaa_coops",
                "format": "json",
            }

            if interval is not None:
                parameters["interval"] = interval

        request_url = requests.Request("GET", base_url, params=parameters).prepare().url

        return request_url

    def _url2pandas(
        self, data_url: str, product: str, num_request_blocks: int
    ) -> pd.DataFrame:
        """Request data from CO-OPS API and handle response. Return data in DataFrame.

        Handles 4 scenarios based on the original request from the end user:
            1. Single 'block' request, no error in response from API
            2. Single 'block' request, error in response from API
            3. Multiple 'block' request, no error in response from API
            4. Multiple 'block' request, error in response from API

        Args:
            data_url (str): The URL to fetch data from.
            product (str): The data product being fetched.
            num_request_blocks (int): The number of blocks of data requested.

        Raises:
            COOPSAPIError: Error occurred while fetching data from the NOAA CO-OPS API.

        Returns:
            DataFrame: Pandas DataFrame containing data from NOAA CO-OPS API.
        """
        df = pd.DataFrame()
        response = requests.get(data_url)
        json_dict = response.json()
        no_data_error = (  # Error message when no data is found
            "No data was found. This product may not be "
            "offered at this station at the "
            "requested time."
        )

        if "error" not in json_dict:  # Case 1 or 3 (no error in response)
            key = "predictions" if product == "predictions" else "data"
            df = json_normalize(json_dict[key])

            return df

        else:  # Case 2 or 4 (error in response)
            if num_request_blocks == 1:
                error_message = (
                    json_dict["error"]
                    .get("message", "Error retrieving data")
                    .lstrip()
                    .rstrip()
                )
                raise COOPSAPIError(error_message, json_dict["error"])
            else:
                if json_dict["error"]["message"] == no_data_error:
                    return df
                else:
                    error_message = (
                        json_dict["error"]
                        .get("message", "Error retrieving data")
                        .lstrip()
                        .rstrip()
                    )
                    raise COOPSAPIError(error_message, json_dict["error"])

    def _parse_known_date_formats(self, dt_string: str):
        """Parse known date formats and return a datetime object.

        Args:
            dt_string (str): The date string to parse.

        Raises:
            ValueError: Invalid date format was provided.

        Returns:
            datetime: The parsed date.
        """
        for fmt in ("%Y%m%d", "%Y%m%d %H:%M", "%m/%d/%Y", "%m/%d/%Y %H:%M"):
            try:
                return datetime.strptime(dt_string, fmt)
            except ValueError:
                match = False  # Flag indicating no match for current format
                pass

        if not match:  # No match after trying all formats
            raise ValueError(
                f"Invalid date format '{dt_string}' provided."
                "See https://tidesandcurrents.noaa.gov/api/ "
                "for list of accepted date formats."
            )

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
        """Fetch data from NOAA CO-OPS API and convert to a Pandas DataFrame.

        Args:
            begin_date (str): Start date of the data to be fetched.
            end_date (str): End date of the data to be fetched.
            product (str): Data product to be fetched.
            datum (str, optional): Datum to use for water level products.
            bin_num (int, optional): Bin to use for current products. Defaults to None.
            interval (Union[str, int], optional): Time interval of fetched data.
                Defaults to None.
            units (str, optional): Units of fetched data. Defaults to "metric".
            time_zone (str, optional): Time zone used when returning fetched data.
                Defaults to "gmt".

        Returns:
            DataFrame: Pandas DataFrame containing data from NOAA CO-OPS API.
        """
        begin_datetime = self._parse_known_date_formats(begin_date)
        end_datetime = self._parse_known_date_formats(end_date)
        delta = end_datetime - begin_datetime

        # If the length of the data request is less or equal to 31 days,
        # make a single request to the API
        if delta.days <= 31:
            data_url = self._build_request_url(
                begin_datetime.strftime("%Y%m%d %H:%M"),
                end_datetime.strftime("%Y%m%d %H:%M"),
                product,
                datum,
                bin_num,
                interval,
                units,
                time_zone,
            )

            df = self._url2pandas(data_url, product, num_request_blocks=1)

        # If the length of the data request is < 365 days AND the product is
        # hourly_height or high_low, make a single request to the API
        elif delta.days <= 365 and (
            product == "hourly_height" or product == "high_low"
        ):
            data_url = self._build_request_url(
                begin_date,
                end_date,
                product,
                datum,
                bin_num,
                interval,
                units,
                time_zone,
            )
            df = self._url2pandas(data_url, product, num_request_blocks=1)

        # If the data request is greater than 365 days AND the product is
        # hourly_height or high_low, make multiple requests to the API in 365 day blocks
        elif product == "hourly_height" or product == "high_low":
            df = pd.DataFrame([])
            num_365day_blocks = int(math.floor(delta.days / 365))

            # Loop through 365 day blocks, update request params accordingly
            for i in range(num_365day_blocks + 1):
                begin_datetime_loop = begin_datetime + timedelta(days=(i * 365))
                end_datetime_loop = begin_datetime_loop + timedelta(days=365)
                end_datetime_loop = (
                    end_datetime
                    if end_datetime_loop > end_datetime
                    else end_datetime_loop
                )
                data_url = self._build_request_url(
                    begin_datetime_loop.strftime("%Y%m%d"),
                    end_datetime_loop.strftime("%Y%m%d"),
                    product,
                    datum,
                    bin_num,
                    interval,
                    units,
                    time_zone,
                )
                df_block = self._url2pandas(data_url, product, num_365day_blocks)
                df = pd.concat([df, df_block])

        # If any other product is requested for >31 days, make multiple requests to the
        # API in 31 day blocks
        else:
            df = pd.DataFrame([])
            num_31day_blocks = int(math.floor(delta.days / 31))

            for i in range(num_31day_blocks + 1):
                begin_datetime_loop = begin_datetime + timedelta(days=(i * 31))
                end_datetime_loop = begin_datetime_loop + timedelta(days=31)
                end_datetime_loop = (
                    end_datetime
                    if end_datetime_loop > end_datetime
                    else end_datetime_loop
                )
                data_url = self._build_request_url(
                    begin_datetime_loop.strftime("%Y%m%d"),
                    end_datetime_loop.strftime("%Y%m%d"),
                    product,
                    datum,
                    bin_num,
                    interval,
                    units,
                    time_zone,
                )
                df_block = self._url2pandas(data_url, product, num_31day_blocks)
                df = pd.concat([df, df_block])

        # Rename output DataFrame columns based on requested product
        # and convert to useable data types
        if product == "water_level":
            # Rename columns for clarity
            df.rename(
                columns={
                    "f": "flags",
                    "q": "QC",
                    "s": "sigma",
                    "t": "date_time",
                    "v": "water_level",
                },
                inplace=True,
            )

            # Convert columns to numeric values
            data_cols = df.columns.drop(["flags", "QC", "date_time"])
            df[data_cols] = df[data_cols].apply(pd.to_numeric, axis=1, errors="coerce")

            # Convert date & time strings to datetime objects
            df["date_time"] = pd.to_datetime(df["date_time"])

        elif product == "hourly_height":
            # Rename columns for clarity
            df.rename(
                columns={
                    "f": "flags",
                    "s": "sigma",
                    "t": "date_time",
                    "v": "hourly_height",
                },
                inplace=True,
            )

            # Convert columns to numeric values
            data_cols = df.columns.drop(["flags", "date_time"])
            df[data_cols] = df[data_cols].apply(pd.to_numeric, axis=1, errors="coerce")

            # Convert date & time strings to datetime objects
            df["date_time"] = pd.to_datetime(df["date_time"])

        elif product == "high_low":
            # Rename columns for clarity
            df.rename(
                columns={
                    "f": "flags",
                    "ty": "high_low",
                    "t": "date_time",
                    "v": "water_level",
                },
                inplace=True,
            )

            # Separate to high and low DataFrames
            df_HH = df[df["high_low"] == "HH"].copy()
            df_HH.rename(
                columns={
                    "date_time": "date_time_HH",
                    "water_level": "HH_water_level",
                },
                inplace=True,
            )

            df_H = df[df["high_low"] == "H "].copy()
            df_H.rename(
                columns={
                    "date_time": "date_time_H",
                    "water_level": "H_water_level",
                },
                inplace=True,
            )

            df_L = df[df["high_low"].str.contains("L ")].copy()
            df_L.rename(
                columns={
                    "date_time": "date_time_L",
                    "water_level": "L_water_level",
                },
                inplace=True,
            )

            df_LL = df[df["high_low"].str.contains("LL")].copy()
            df_LL.rename(
                columns={
                    "date_time": "date_time_LL",
                    "water_level": "LL_water_level",
                },
                inplace=True,
            )

            # Extract dates (without time) for each entry
            dates_HH = [x.date() for x in pd.to_datetime(df_HH["date_time_HH"])]
            dates_H = [x.date() for x in pd.to_datetime(df_H["date_time_H"])]
            dates_L = [x.date() for x in pd.to_datetime(df_L["date_time_L"])]
            dates_LL = [x.date() for x in pd.to_datetime(df_LL["date_time_LL"])]

            # Set indices to datetime
            df_HH["date_time"] = dates_HH
            df_HH.index = df_HH["date_time"]
            df_H["date_time"] = dates_H
            df_H.index = df_H["date_time"]
            df_L["date_time"] = dates_L
            df_L.index = df_L["date_time"]
            df_LL["date_time"] = dates_LL
            df_LL.index = df_LL["date_time"]

            # Remove flags and combine to single DataFrame
            df_HH = df_HH.drop(columns=["flags", "high_low"])
            df_H = df_H.drop(columns=["flags", "high_low", "date_time"])
            df_L = df_L.drop(columns=["flags", "high_low", "date_time"])
            df_LL = df_LL.drop(columns=["flags", "high_low", "date_time"])

            # Keep only one instance per date (based on max/min)
            maxes = df_HH.groupby(df_HH.index).HH_water_level.transform(max)
            df_HH = df_HH.loc[df_HH.HH_water_level == maxes]
            maxes = df_H.groupby(df_H.index).H_water_level.transform(max)
            df_H = df_H.loc[df_H.H_water_level == maxes]
            mins = df_L.groupby(df_L.index).L_water_level.transform(max)
            df_L = df_L.loc[df_L.L_water_level == mins]
            mins = df_LL.groupby(df_LL.index).LL_water_level.transform(max)
            df_LL = df_LL.loc[df_LL.LL_water_level == mins]

            df = df_HH.join(df_H, how="outer")
            df = df.join(df_L, how="outer")
            df = df.join(df_LL, how="outer")

            # Convert columns to numeric values
            data_cols = df.columns.drop(
                [
                    "date_time",
                    "date_time_HH",
                    "date_time_H",
                    "date_time_L",
                    "date_time_LL",
                ]
            )
            df[data_cols] = df[data_cols].apply(pd.to_numeric, axis=1, errors="coerce")

            # Convert date & time strings to datetime objects
            df["date_time"] = pd.to_datetime(df.index)
            df["date_time_HH"] = pd.to_datetime(df["date_time_HH"])
            df["date_time_H"] = pd.to_datetime(df["date_time_H"])
            df["date_time_L"] = pd.to_datetime(df["date_time_L"])
            df["date_time_LL"] = pd.to_datetime(df["date_time_LL"])

        elif product == "predictions":
            if interval == "h" or interval is None:
                # Rename columns for clarity
                df.rename(
                    columns={"t": "date_time", "v": "predictions"},
                    inplace=True,
                )

                # Convert columns to numeric values
                data_cols = df.columns.drop(["date_time"])
                df[data_cols] = df[data_cols].apply(
                    pd.to_numeric, axis=1, errors="coerce"
                )

            elif interval == "hilo":
                # Rename columns for clarity
                df.rename(
                    columns={
                        "t": "date_time",
                        "v": "predictions",
                        "type": "hi_lo",
                    },
                    inplace=True,
                )

                # Convert columns to numeric values
                data_cols = df.columns.drop(["date_time", "hi_lo"])
                df[data_cols] = df[data_cols].apply(
                    pd.to_numeric, axis=1, errors="coerce"
                )

            # Convert date & time strings to datetime objects
            df["date_time"] = pd.to_datetime(df["date_time"])

        elif product == "currents":
            # Rename columns for clarity
            df.rename(
                columns={
                    "b": "bin",
                    "d": "direction",
                    "s": "speed",
                    "t": "date_time",
                },
                inplace=True,
            )

            # Convert columns to numeric values
            data_cols = df.columns.drop(["date_time"])
            df[data_cols] = df[data_cols].apply(pd.to_numeric, axis=1, errors="coerce")

            # Convert date & time strings to datetime objects
            df["date_time"] = pd.to_datetime(df["date_time"])

        elif product == "wind":
            # Rename columns for clarity
            df.rename(
                columns={
                    "d": "dir",
                    "dr": "compass",
                    "f": "flags",
                    "g": "gust_speed",
                    "s": "wind_speed",
                    "t": "date_time",
                },
                inplace=True,
            )

            # Convert columns to numeric values
            data_cols = df.columns.drop(["date_time", "flags", "compass"])
            df[data_cols] = df[data_cols].apply(pd.to_numeric, axis=1, errors="coerce")

            # Convert date & time strings to datetime objects
            df["date_time"] = pd.to_datetime(df["date_time"])

        elif product == "air_pressure":
            # Rename columns for clarity
            df.rename(
                columns={"f": "flags", "t": "date_time", "v": "air_pressure"},
                inplace=True,
            )

            # Convert columns to numeric values
            data_cols = df.columns.drop(["date_time", "flags"])
            df[data_cols] = df[data_cols].apply(pd.to_numeric, axis=1, errors="coerce")

            # Convert date & time strings to datetime objects
            df["date_time"] = pd.to_datetime(df["date_time"])

        elif product == "air_temperature":
            # Rename columns for clarity
            df.rename(
                columns={"f": "flags", "t": "date_time", "v": "air_temperature"},
                inplace=True,
            )

            # Convert columns to numeric values
            data_cols = df.columns.drop(["date_time", "flags"])
            df[data_cols] = df[data_cols].apply(pd.to_numeric, axis=1, errors="coerce")

            # Convert date & time strings to datetime objects
            df["date_time"] = pd.to_datetime(df["date_time"])

        elif product == "water_temperature":
            # Rename columns for clarity
            df.rename(
                columns={"f": "flags", "t": "date_time", "v": "water_temperature"},
                inplace=True,
            )

            # Convert columns to numeric values
            data_cols = df.columns.drop(["date_time", "flags"])
            df[data_cols] = df[data_cols].apply(pd.to_numeric, axis=1, errors="coerce")

            # Convert date & time strings to datetime objects
            df["date_time"] = pd.to_datetime(df["date_time"])

        # Set datetime to index (for use in resampling)
        df.index = df["date_time"]
        df = df.drop(columns=["date_time"])

        # Handle hourly requests for water_level and currents data
        if ((product == "water_level") | (product == "currents")) & (interval == "h"):
            df = df.resample("H").first()  # Only return the hourly data

        df.drop_duplicates()  # Handle duplicates due to overlapping requests
        self.data = df
        return df


if __name__ == "__main__":
    # DEBUGGING
    # from pprint import pprint

    # import noaa_coops as nc

    # station = nc.Station("8771510")

    # print(f"CO-OPS MetaData API Station ID: {station.id}")
    # print(f"CO-OPS MetaData API Station Name: {station.name}")
    # print("CO-OPS MetaData API Station Products: ")
    # pprint(station.products, indent=4)
    # print("\n")

    # data1 = station.get_data(
    #     begin_date="19951201 00:00",
    #     end_date="19960131 00:00",
    #     product="water_level",
    #     datum="MSL",
    #     interval="h",
    #     units="english",
    #     time_zone="gmt",
    # )
    # pprint(data1)
    # print("\n")

    # data2 = station.get_data(
    #     begin_date="19951201 00:00",
    #     end_date="19951210 00:00",
    #     product="water_level",
    #     datum="MSL",
    #     interval="h",
    #     units="english",
    #     time_zone="gmt",
    # )
    # pprint(data2)
    # print("\n")

    # print(
    #     "CO-OPS SOAP Data Inventory: ",
    # )
    # pprint(station.data_inventory, indent=4, compact=True, width=100)
    # print("\n")

    # seattle = Station(id="9447130")  # water levels
    # print("Test that metadata is working:")
    # pprint(seattle.metadata)
    # print("\n" * 2)
    # print("Test that attributes are populated from metadata:")
    # pprint(seattle.sensors)
    # print("\n" * 2)
    # print("Test that data_inventory is working:")
    # pprint(seattle.data_inventory)
    # print("\n" * 2)
    # print("Test water level station request:")
    # sea_data = seattle.get_data(
    #     begin_date="20150101",
    #     end_date="20150331",
    #     product="water_level",
    #     datum="MLLW",
    #     units="metric",
    #     time_zone="gmt",
    # )
    # pprint(sea_data.head())
    # print("\n" * 2)

    pass
