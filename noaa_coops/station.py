from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Optional, Union

import pandas as pd
import requests
import zeep


class COOPSAPIError(Exception):
    """Raised when a NOAA CO-OPS API request returns an error."""

    def __init__(self, message: str) -> None:
        """Initialize COOPSAPIError.

        Args:
            message (str): The error message.
        """
        self.message = message
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
    station_list = []
    data_url = "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations.json"
    response = requests.get(data_url)
    json_dict = response.json()

    if len(lat_coords) != 2 or len(lon_coords) != 2:
        raise ValueError("lat_coords and lon_coords must be of length 2.")

    # Ensure lat_coords and lon_coords are in the correct order
    lat_coords = sorted(lat_coords)
    lon_coords = sorted(lon_coords)

    # if lat_coords[0] > lat_coords[1]:
    #     lat_coords[0], lat_coords[1] = lat_coords[1], lat_coords[0]

    # if lon_coords[0] > lon_coords[1]:
    #     lon_coords[0], lon_coords[1] = lon_coords[1], lon_coords[0]

    # Find stations in bounding box
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
        self.id: str = str(id)
        self.units: str = units
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
                    " https://tidesandcurrents.noaa.gov/api/prod/#datum "
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

        elif product == "hourly_height":
            if datum is None:
                raise ValueError(
                    "No datum specified for water level data. See"
                    " https://tidesandcurrents.noaa.gov/api/prod/#datum "
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
                    " https://tidesandcurrents.noaa.gov/api/prod/#datum "
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
                "units": units,
                "time_zone": time_zone,
                "application": "noaa_coops",
                "format": "json",
            }

            if interval is not None:
                parameters["interval"] = interval

        request_url = requests.Request("GET", base_url, params=parameters).prepare().url

        return request_url

    def _make_api_request(self, data_url: str, product: str) -> pd.DataFrame:
        """Request data from CO-OPS API, handle response, return data as a DataFrame.

        Args:
            data_url (str): The URL to fetch data from.
            product (str): The data product being fetched.

        Raises:
            COOPSAPIError: Error occurred while fetching data from the NOAA CO-OPS API.

        Returns:
            DataFrame: Pandas DataFrame containing data from NOAA CO-OPS API.
        """
        res = requests.get(data_url)

        if res.status_code != 200:
            raise COOPSAPIError(
                message=(
                    f"CO-OPS API returned an error. Status Code: "
                    f"{res.status_code}. Reason: {res.reason}\n"
                ),
            )

        json_dict = res.json()

        if "error" in json_dict:  # API can return an error even if status code is 200
            err_msg = f"CO-OPS API returned an error: {json_dict['error']['message']}"

            if product == "water_level":
                err_msg += (
                    "\n\nNOTE: The requested product `water_levels` is only available "
                    "from 1996 and onwards. Try using `hourly_height` or `high_low` "
                    "products instead."
                )

            raise COOPSAPIError(message=err_msg)

        key = "predictions" if product == "predictions" else "data"

        return pd.json_normalize(json_dict[key])

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
                date_time = datetime.strptime(dt_string, fmt)
                # Standardize date format to yyyyMMdd HH:mm for all requests
                str_yyyyMMdd_HHmm = date_time.strftime("%Y%m%d %H:%M")
                return date_time, str_yyyyMMdd_HHmm
            except ValueError:
                match = False  # Flag indicating no match for current format

        if not match:  # No match after trying all formats
            raise ValueError(
                f"Invalid date format '{dt_string}' provided."
                "See https://tidesandcurrents.noaa.gov/api/ "
                "for list of accepted date formats."
            )

    def _check_product_params(
        self,
        product: str,
        datum: Optional[str] = None,
        bin_num: Optional[int] = None,
        interval: Optional[Union[str, int]] = None,
        units: Optional[str] = "metric",
        time_zone: Optional[str] = "gmt",
    ):
        """Check that requested product parameters are valid.

        Args:
            product (str): Data product to be fetched.
            datum (str, optional): Datum to use for water level products.
            bin_num (int, optional): Bin to use for current products. Defaults to None.
            interval (Union[str, int], optional): Time interval of fetched data.
                Defaults to None
            units (str, optional): Units to use for fetched data. Defaults to "metric".
            time_zone (str, optional): Time zone to use for fetched data.
                Defaults to "gmt".

        Raises:
            ValueError: Invalid request parameters were provided.
        """
        if product not in [
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
        ]:
            raise ValueError(
                f"Invalid product '{product}' provided. See"
                " https://api.tidesandcurrents.noaa.gov/api/prod/#products "
                "for list of available products"
            )

        if product in [
            "water_level",
            "hourly_height",
            "high_low",
            "daily_mean",
            "monthly_mean",
            "one_minute_water_level",
            "predictions",
        ]:
            if datum is None:
                raise ValueError(
                    "No datum specified for water level data. See"
                    " https://api.tidesandcurrents.noaa.gov/api/prod/#datum "
                    "for list of available datums"
                )
            elif str.upper(datum) not in [
                "CRD",
                "IGLD",
                "LWD",
                "MHHW",
                "MHW",
                "MTL",
                "MSL",
                "MLW",
                "MLLW",
                "NAVD",
                "STND",
            ]:
                raise ValueError(
                    f"Invalid datum '{datum}' provided. See"
                    " https://tidesandcurrents.noaa.gov/api/prod/#datum "
                    "for list of available datums"
                )

        if product in ["water_level", "hourly_height", "one_minute_water_level"]:
            if interval is not None:
                raise ValueError(
                    f"`interval` parameter is not supported for `{product}` product. "
                    "See https://tidesandcurrents.noaa.gov/api/prod/#interval "
                    "for details. These products have the following intervals "
                    "that cannot be modified:\n"
                    "    one_minute_water_level: 1 minute\n"
                    "    water_level: 6 minutes\n"
                    "    hourly_height: 1 hour\n"
                )

        if product == "predictions":
            if interval is not None and str(interval) not in [
                "h",
                "1",
                "5",
                "10",
                "15",
                "30",
                "60",
                "hilo",
            ]:
                raise ValueError(
                    f"`interval` parameter {interval} is not supported for "
                    "`predictions` product. See "
                    "https://tidesandcurrents.noaa.gov/api/prod/#interval "
                    "for list of available intervals."
                )

        if product == "currents":
            if bin_num is None:
                raise ValueError(
                    "No `bin_num` specified for `currents` product. Bin info can be "
                    "found on the station info page"
                    " (e.g., https://tidesandcurrents.noaa.gov/cdata/StationInfo?id=PUG1515)"  # noqa
                )

            if interval is not None and str(interval) not in ["6", "h"]:
                raise ValueError(
                    f"`interval` parameter {interval} is not supported for `currents` "
                    "product. See https://tidesandcurrents.noaa.gov/api/prod/#interval "
                    "for list of available intervals."
                )

        if product == "currents_predictions":
            if bin_num is None:
                raise ValueError(
                    "No `bin_num` specified for `currents_predictions` data. Bin info "
                    "can be found on the station info page"
                    " (e.g., https://tidesandcurrents.noaa.gov/cdata/StationInfo?id=PUG1515)"  # noqa
                )

            if interval is not None and str(interval) not in [
                "h",
                "1",
                "6",
                "10",
                "30",
                "60",
                "max_slack",
            ]:
                raise ValueError(
                    f"`interval` parameter {interval} is not supported for "
                    "`currents_predictions` product. "
                    "See https://tidesandcurrents.noaa.gov/api/prod/#interval "
                    "for list of available intervals."
                )

        if product in [
            "air_temperature",
            "water_temperature",
            "wind",
            "air_pressure",
            "conductivity",
            "visibility",
            "humidity",
            "salinity",
        ]:
            if interval is not None and str(interval) not in ["h", "6"]:
                raise ValueError(
                    f"`interval` parameter {interval} is not supported for "
                    f"`{product}` product. See "
                    "https://tidesandcurrents.noaa.gov/api/prod/#interval "
                    "for list of available intervals."
                )

        if units not in ["english", "metric"]:
            raise ValueError(
                f"Invalid units '{units}' provided. See"
                " https://tidesandcurrents.noaa.gov/api/prod/#units "
                "for list of available units"
            )

        if time_zone not in ["gmt", "lst", "lst_ldt"]:
            raise ValueError(
                f"Invalid time zone '{time_zone}' provided. See"
                " https://tidesandcurrents.noaa.gov/api/prod/#timezones "
                "for list of available time zones"
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

        Raises:
            COOPSAPIError: Raised when NOAA CO-OPS API returns an error.

        Returns:
            DataFrame: Pandas DataFrame containing data from NOAA CO-OPS API.
        """
        # Check for valid params
        self._check_product_params(product, datum, bin_num, interval, units, time_zone)

        # Parse user provided dates, convert to datetime for block size calcs
        begin_dt, begin_str = self._parse_known_date_formats(begin_date)
        end_dt, end_str = self._parse_known_date_formats(end_date)
        delta = end_dt - begin_dt

        # Query params fit within *single block* API request
        if delta.days <= 31 or (
            delta.days <= 365 and (product == "hourly_height" or product == "high_low")
        ):
            data_url = self._build_request_url(
                begin_dt.strftime("%Y%m%d %H:%M"),
                end_dt.strftime("%Y%m%d %H:%M"),
                product,
                datum,
                bin_num,
                interval,
                units,
                time_zone,
            )
            df = self._make_api_request(data_url, product)

        # Query params require *multiple block* API request
        else:
            block_size = (
                365 if product == "hourly_height" or product == "high_low" else 31
            )
            num_blocks = int(math.floor(delta.days / block_size))
            df = pd.DataFrame([])

            for i in range(num_blocks + 1):
                begin_dt_loop = begin_dt + timedelta(days=(i * block_size))
                end_dt_loop = begin_dt_loop + timedelta(days=block_size)
                end_dt_loop = end_dt if end_dt_loop > end_dt else end_dt_loop
                data_url = self._build_request_url(
                    begin_dt_loop.strftime("%Y%m%d %H:%M"),
                    end_dt_loop.strftime("%Y%m%d %H:%M"),
                    product,
                    datum,
                    bin_num,
                    interval,
                    units,
                    time_zone,
                )
                try:
                    df_block = self._make_api_request(data_url, product)
                except COOPSAPIError:
                    continue  # Skip block if no data returned (e.g, station was down)

                df = pd.concat([df, df_block])

        if df.empty:
            raise COOPSAPIError(
                f"No data returned for {product} product between "
                f"{begin_str} and {end_str}"
            )

        df.index = pd.to_datetime(df["t"])
        df = df.drop(columns=["t"])

        # Try to convert strings to numeric values where possible
        for col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="ignore")

        df = df[~df.index.duplicated(keep="first")]
        self.data = df

        return df


if __name__ == "__main__":
    # DEBUGGING
    from pprint import pprint

    import noaa_coops as nc

    station = nc.Station(id="8775241")

    df = station.get_data(
        begin_date="20230320 00:00",
        end_date="20230421 00:00",
        product="predictions",
        datum="MSL",
        interval="h",
        units="english",
        time_zone="gmt",
    )

    pprint(df.head())
    print("\n" * 2)

    pprint(df.tail())
    print("\n" * 2)

    print(df.info())

    df.to_csv("debug.csv")

    # station = nc.Station(id="9447130")  # Seattle, WA

    # Test replicating the data seen on the station page:
    # https://tidesandcurrents.noaa.gov/waterlevels.html?id=9447130&units=metric&bdate=20220101&edate=20220430&timezone=GMT&datum=MLLW&interval=h&action=
    # 2022-01-01 00:00:00, 2022-04-30 23:00:00, 1-hr, MLLW, GMT, metric

    # print("Test that metadata is working:")
    # pprint(station.metadata)
    # print("\n" * 2)

    # print("Test that attributes are populated from metadata:")
    # pprint(station.sensors)
    # print("\n" * 2)

    # print("Test that data_inventory is working:")
    # pprint(station.data_inventory, indent=4, compact=True, width=100)
    # print("\n" * 2)

    # print("6-min water level station request:")
    # data = station.get_data(
    #     begin_date="20220101 00:00",
    #     end_date="20220430 23:00",
    #     product="hourly_height",
    #     datum="MLLW",
    #     units="metric",
    #     time_zone="gmt",
    # )
    # pprint(data.head())
    # print("\n" * 2)

    # pprint(data.tail())
    # print("\n" * 2)

    # print("6-min water level station request:")
    # data = station.get_data(
    #     begin_date="20150101",
    #     end_date="20150331",
    #     product="water_level",
    #     datum="MLLW",
    #     units="metric",
    #     time_zone="gmt",
    # )
    # pprint(data.head())
    # print("\n" * 2)

    # print("1-hr water level station request (SHOULD NOT WORK):")
    # data = station.get_data(
    #     begin_date="20150101",
    #     end_date="20150331",
    #     product="water_level",
    #     interval="h",
    #     datum="MLLW",
    #     units="metric",
    #     time_zone="gmt",
    # )
    # pprint(data.head())
    # print("\n" * 2)

    # print("high-low request:")
    # data = station.get_data(
    #     begin_date="20150101",
    #     end_date="20150331",
    #     product="high_low",
    #     datum="MLLW",
    #     units="metric",
    #     time_zone="gmt",
    # )
    # pprint(data.head())
    # print("\n" * 2)
    # pprint(data.loc["2015"])
