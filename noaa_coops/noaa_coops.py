import math
from datetime import datetime, timedelta

import pandas as pd
import requests
from pandas.io.json import json_normalize
import zeep


class Station:
    """
    A class to access station data and metadata via the NOAA Tides & Currents
    APIs. 
    
    For data retrieval API, see https://tidesandcurrents.noaa.gov/api/.
    For metadata API, see: https://tidesandcurrents.noaa.gov/mdapi/latest/
    For data inventory info, see: https://opendap.co-ops.nos.noaa.gov/axis/
    """

    data_base_url = 'http://tidesandcurrents.noaa.gov/api/datagetter?'

    def __init__(self, stationid, units='metric'):
        self.stationid = stationid
        self.units = units
        self.get_metadata(self.stationid)

        try:
            self.get_data_inventory(self.stationid)
        except:
            pass
        
    def get_data_inventory(self, stationid):
        """
        Get data inventory for station with water level and meteoroligical data.
        Data inventory is fetched from NOAA CO-OPS SOAP Web Services, see:
        https://opendap.co-ops.nos.noaa.gov/axis/
        """

        wsdl = ('https://opendap.co-ops.nos.noaa.gov/axis/webservices/'
                'datainventory/wsdl/DataInventory.wsdl')
        client = zeep.Client(wsdl=wsdl)
        response = client.service.getDataInventory(str(self.stationid))
        self.data_inventory = response['parameter']    
    
    def get_metadata(self, stationid):
        """
        Build URL for metadata API request. When a Station object is
        initialized, fill out metadata automatically.
        """

        metadata_base_url = ('http://tidesandcurrents.noaa.gov/mdapi/v1.0/'
                             'webapi/stations/')
        extension = '.json'
        metadata_expand = ('?expand=details,sensors,products,disclaimers,'
                           'notices,datums,harcon,tidepredoffets,benchmarks,'
                           'nearby,bins,deployments,currentpredictionoffsets,'
                           'floodlevels')
        units_for_url = '?units=' + self.units
        metadata_url = (metadata_base_url + str(self.stationid) + extension
                            + metadata_expand + units_for_url)
        
        # Get response from Metadata API
        response = requests.get(metadata_url)
        json_dict = response.json()
        station_metadata = json_dict['stations'][0]

        # Determine station type, then assign class attributes accordingly from
        # metadata 
        if 'datums' in station_metadata:  # if True --> water levels
            self.metadata = station_metadata
            self.affiliations = station_metadata['affiliations']
            self.benchmarks = station_metadata['benchmarks']
            self.datums = station_metadata['datums']
            # self.details = station_metadata['details']  # Only 4 water levels
            self.disclaimers = station_metadata['disclaimers']
            self.flood_levels = station_metadata['floodlevels']
            self.greatlakes = station_metadata['greatlakes']
            self.tidal_constituents = station_metadata['harmonicConstituents']
            self.lat_lon = {
                'lat' : station_metadata['lat'],
                'lon' : station_metadata['lng']
            }
            self.name = station_metadata['name']
            self.nearby_stations = station_metadata['nearby']
            self.notices = station_metadata['notices']
            self.observe_dst = station_metadata['observedst']
            self.ports_code = station_metadata['portscode']
            self.products = station_metadata['products']
            self.sensors = station_metadata['sensors']
            self.shef_code = station_metadata['shefcode']
            self.state = station_metadata['state']
            self.storm_surge = station_metadata['stormsurge']
            self.tidal = station_metadata['tidal']
            self.tide_type = station_metadata['tideType']
            self.timezone = station_metadata['timezone']
            self.timezone_corr = station_metadata['timezonecorr']

        elif 'tidepredoffsets' in station_metadata:  # if True --> pred tide
            self.metadata = station_metadata
            self.state = station_metadata['state']
            self.tide_pred_offsets = station_metadata['tidepredoffsets']
            self.type = station_metadata['type']
            self.time_meridian = station_metadata['timemeridian']
            self.reference_id = station_metadata['reference_id']
            self.timezone_corr = station_metadata['timezonecorr']
            self.name = station_metadata['name']
            self.lat_lon = {
                'lat' : station_metadata['lat'],
                'lon' : station_metadata['lng']
            }
            self.affiliations = station_metadata['affiliations']
            self.ports_code = station_metadata['portscode']
            self.products = station_metadata['products']
            self.disclaimers = station_metadata['disclaimers']
            self.notices = station_metadata['notices']
            self.tide_type = station_metadata['tideType']
        
        elif 'bins' in station_metadata:  # if True --> currents
            self.metadata = station_metadata
            self.project = station_metadata['project']
            self.deployed = station_metadata['deployed']
            self.retrieved = station_metadata['retrieved']
            self.timezone_offset = station_metadata['timezone_offset']
            self.observe_dst = station_metadata['observedst']
            self.project_type = station_metadata['project_type']
            self.noaa_chart = station_metadata['noaachart']
            self.deployments = station_metadata['deployments']
            self.bins = station_metadata['bins']
            self.name = station_metadata['name']
            self.lat_lon = {
                'lat' : station_metadata['lat'],
                'lon' : station_metadata['lng']
            }
            self.affiliations = station_metadata['affiliations']
            self.ports_code = station_metadata['portscode']
            self.products = station_metadata['products']
            self.disclaimers = station_metadata['disclaimers']
            self.notices = station_metadata['notices']
            self.tide_type = station_metadata['tideType']
        
        elif 'currbin' in station_metadata:  # if True --> predicted currents
            self.metadata = station_metadata
            self.current_pred_offsets = station_metadata['currentpredictionoffsets']
            self.curr_bin = station_metadata['currbin']
            self.type = station_metadata['type']
            self.depth = station_metadata['depth']
            self.depth_type = station_metadata['depthType']
            self.name = station_metadata['name']
            self.lat_lon = {
                'lat' : station_metadata['lat'],
                'lon' : station_metadata['lng']
            }
            self.affiliations = station_metadata['affiliations']
            self.ports_code = station_metadata['portscode']
            self.products = station_metadata['products']
            self.disclaimers = station_metadata['disclaimers']
            self.notices = station_metadata['notices']
            self.tide_type = station_metadata['tideType']
        
    def _build_query_url(self, begin_date, end_date, product,
                        datum=None, bin_num=None, interval=None,
                        units='metric', time_zone='gmt'):
        """
        Build an URL to be used to fetch data from the NOAA CO-OPS data API
        (see https://tidesandcurrents.noaa.gov/api/)
        """
        base_url = 'http://tidesandcurrents.noaa.gov/api/datagetter?'

        # If the data product is water levels, check that a datum is specified
        if product == 'water_level':
            if datum is None:
                raise ValueError('No datum specified for water level data. See'
                                ' https://tidesandcurrents.noaa.gov/api/#datum '
                                'for list of available datums')
            else:
                # Compile parameter string for use in URL
                parameters = {'begin_date': begin_date,
                            'end_date': end_date,
                            'station': self.stationid,
                            'product': product,
                            'datum': datum,
                            'units': units,
                            'time_zone': time_zone,
                            'application': 'py_noaa',
                            'format': 'json'}

        elif product == 'hourly_height':
            if datum is None:
                raise ValueError('No datum specified for water level data. See'
                                ' https://tidesandcurrents.noaa.gov/api/#datum '
                                'for list of available datums')
            else:
                # Compile parameter string for use in URL
                parameters = {'begin_date': begin_date,
                            'end_date': end_date,
                            'station': self.stationid,
                            'product': product,
                            'datum': datum,
                            'units': units,
                            'time_zone': time_zone,
                            'application': 'py_noaa',
                            'format': 'json'}
        elif product == 'high_low':
            if datum is None:
                raise ValueError('No datum specified for water level data. See'
                                ' https://tidesandcurrents.noaa.gov/api/#datum '
                                'for list of available datums')
            else:
                # Compile parameter string for use in URL
                parameters = {'begin_date': begin_date,
                            'end_date': end_date,
                            'station': self.stationid,
                            'product': product,
                            'datum': datum,
                            'units': units,
                            'time_zone': time_zone,
                            'application': 'py_noaa',
                            'format': 'json'}

        elif product == 'predictions':
            # If no interval provided, return 6-min predictions data
            if interval is None:
                # Compile parameter string for use in URL
                parameters = {'begin_date': begin_date,
                            'end_date': end_date,
                            'station': self.stationid,
                            'product': product,
                            'datum': datum,
                            'units': units,
                            'time_zone': time_zone,
                            'application': 'py_noaa',
                            'format': 'json'}

            else:
                # Compile parameter string, including interval, for use in URL
                parameters = {'begin_date': begin_date,
                            'end_date': end_date,
                            'station': self.stationid,
                            'product': product,
                            'datum': datum,
                            'interval': interval,
                            'units': units,
                            'time_zone': time_zone,
                            'application': 'py_noaa',
                            'format': 'json'}

        # If the data product is currents, check that a bin number is specified
        elif product == 'currents':
            if bin_num is None:
                raise ValueError(
                    'No bin specified for current data. Bin info can be '
                    'found on the station info page'
                    ' (e.g., https://tidesandcurrents.noaa.gov/cdata/StationInfo?id=PUG1515)')
            else:
                # Compile parameter string for use in URL
                parameters = {'begin_date': begin_date,
                            'end_date': end_date,
                            'station': self.stationid,
                            'product': product,
                            'bin': str(bin_num),
                            'units': units,
                            'time_zone': time_zone,
                            'application': 'py_noaa',
                            'format': 'json'}

        # For all other data types (e.g., meteoroligcal conditions)
        else:
            # If no interval provided, return 6-min met data
            if interval is None:
                # Compile parameter string for use in URL
                parameters = {'begin_date': begin_date,
                            'end_date': end_date,
                            'station': self.stationid,
                            'product': product,
                            'units': units,
                            'time_zone': time_zone,
                            'application': 'py_noaa',
                            'format': 'json'}
            else:
                # Compile parameter string, including interval, for use in URL
                parameters = {'begin_date': begin_date,
                            'end_date': end_date,
                            'station': self.stationid,
                            'product': product,
                            'interval': interval,
                            'units': units,
                            'time_zone': time_zone,
                            'application': 'py_noaa',
                            'format': 'json'}

        # Build URL with requests library
        query_url = requests.Request(
            'GET', base_url, params=parameters).prepare().url

        return query_url


    def _url2pandas(self, data_url, product, num_request_blocks):
        """
        Takes in a provided URL using the NOAA CO-OPS API conventions
        (see https://tidesandcurrents.noaa.gov/api/) and converts the 
        corresponding JSON data into a pandas dataframe.
        """

        response = requests.get(data_url)  # Get JSON data from URL
        json_dict = response.json()  # Create a dictionary from JSON data

        df = pd.DataFrame()  # Initialize a empty DataFrame

        # Error when the requested begin_date and/or end_date does not have data
        large_data_gap_error = ('No data was found. This product may not be ' 
                                'offered at this station at the '
                                'requested time.')

        # Handle .get_data() request size & errors from COOPS API, cases below:
            # 1. .get_data() makes a large request (i.e. >1 block requests)
            #    and an error occurs in one of the individual blocks of data

            # 2. .get_data() makes a large request (i.e. >1 block requests) and
            #    an error does not occur in one of the individual blocks of data

            # 3. .get_data() makes a small request (i.e. 1 request)
            #    and an error occurs in the data requested

            # 4. .get_data() makes a small request (i.e. 1 request)
            #    and an error does not occur in the data requested

        # Case 1
        if (num_request_blocks > 1) and ('error' in json_dict): 
            error_message = json_dict['error'].get('message',
                                                'Error retrieving data')
            error_message = error_message.lstrip()
            error_message = error_message.rstrip()

            if error_message == large_data_gap_error:
                return df  # Return the empty DataFrame
            else:
                raise ValueError(
                    json_dict['error'].get('message', 'Error retrieving data'))

        # Case 2
        elif (num_request_blocks > 1) and ('error' not in json_dict):
            if product == 'predictions':
                key = 'predictions'
            else:
                key = 'data'

            df = json_normalize(json_dict[key])  # Parse JSON dict to dataframe

            return df

        # Case 3
        elif (num_request_blocks == 1) and ('error' in json_dict):
            raise ValueError(
                    json_dict['error'].get('message', 'Error retrieving data'))
        
        # Case 4
        else:
            if product == 'predictions':
                key = 'predictions'
            else:
                key = 'data'

            df = json_normalize(json_dict[key])  # Parse JSON dict to dataframe

            return df


    def _parse_known_date_formats(self, dt_string):
        """Attempt to parse CO-OPS accepted date formats."""
        for fmt in ('%Y%m%d', '%Y%m%d %H:%M', '%m/%d/%Y', '%m/%d/%Y %H:%M'):
            try:
                return datetime.strptime(dt_string, fmt)
            except ValueError:
                pass
        raise ValueError("No valid date format found."
                        "See https://tidesandcurrents.noaa.gov/api/ "
                        "for list of accepted date formats.")


    def get_data(self, begin_date, end_date, product, 
                 datum=None, bin_num=None, interval=None,
                 units='metric', time_zone='gmt'):
        """
        Function to get data from NOAA CO-OPS API and convert it to a pandas
        dataframe for convenient analysis.

        Info on the NOOA CO-OPS API can be found at https://tidesandcurrents.noaa.gov/api/,
        the arguments listed below generally follow the same (or a very similar) format.

        Arguments:
        begin_date -- the starting date of request (yyyyMMdd, yyyyMMdd HH:mm, MM/dd/yyyy, or MM/dd/yyyy HH:mm), string
        end_date -- the ending date of request (yyyyMMdd, yyyyMMdd HH:mm, MM/dd/yyyy, or MM/dd/yyyy HH:mm), string
        stationid -- station at which you want data, string
        product -- the product type you would like, string
        datum -- the datum to be used for water level data, string  (default None)
        bin_num -- the bin number you would like your currents data at, int (default None)
        interval -- the interval you would like data returned, string
        units -- units to be used for data output, string (default metric)
        time_zone -- time zone to be used for data output, string (default gmt)
        """
        # Convert dates to datetime objects so deltas can be calculated
        begin_datetime = self._parse_known_date_formats(begin_date)
        end_datetime = self._parse_known_date_formats(end_date)
        delta = end_datetime - begin_datetime

        # If the length of our data request is less or equal to 31 days,
        # we can pull the data from API in one request
        if delta.days <= 31:
            data_url = self._build_query_url(
                begin_datetime.strftime("%Y%m%d %H:%M"),
                end_datetime.strftime("%Y%m%d %H:%M"),
                product, datum, bin_num, interval, units, time_zone)

            df = self._url2pandas(data_url, product, num_request_blocks=1)

        # If the length of the user specified data request is less than 365 days
        # AND the product is hourly_height or high_low, we can pull data 
        # directly from the API in one request
        elif delta.days <= 365 and (
                product == 'hourly_height' or product == 'high_low'):
            data_url = self._build_query_url(
                begin_date, end_date, product, 
                datum, bin_num, interval, units, time_zone)

            df = self._url2pandas(data_url, product, num_request_blocks=1)

        # If the length of the user specified data request is greater than 365 
        # days AND the product is hourly_height or high_low, we need to load 
        # data from the API in 365 day blocks.
        elif product == 'hourly_height' or product == 'high_low':
            # Find the number of 365 day blocks in our desired period,
            # constrain the upper limit of index in the for loop to follow
            num_365day_blocks = int(math.floor(delta.days / 365))

            df = pd.DataFrame([])  # Empty dataframe for data from API requests

            # Loop through in 365 day blocks,
            # adjust the begin_datetime and end_datetime accordingly,
            # make a request to the NOAA CO-OPS API
            for i in range(num_365day_blocks + 1):
                begin_datetime_loop = begin_datetime + timedelta(days=(i * 365))
                end_datetime_loop = begin_datetime_loop + timedelta(days=365)

                # If end_datetime_loop of the current 365 day block is greater
                # than end_datetime specified by user, use end_datetime
                if end_datetime_loop > end_datetime:
                    end_datetime_loop = end_datetime

                # Build url for each API request as we proceed through the loop
                data_url = self._build_query_url(
                    begin_datetime_loop.strftime('%Y%m%d'),
                    end_datetime_loop.strftime('%Y%m%d'),
                    product, datum, bin_num, 
                    interval, units, time_zone)
                
                # Get dataframe for block and append to time series df
                df_new = self._url2pandas(data_url, product, num_365day_blocks)
                df = df.append(df_new)
                
        # If the length of the user specified data request is greater than 31 
        # days for any other products, we need to load data from the API in 31
        # day blocks
        else:
            # Find the number of 31 day blocks in our desired period,
            # constrain the upper limit of index in the for loop to follow
            num_31day_blocks = int(math.floor(delta.days / 31))

            df = pd.DataFrame([])  # Empty dataframe for data from API requests

            # Loop through in 31 day blocks,
            # adjust the begin_datetime and end_datetime accordingly,
            # make a request to the NOAA CO-OPS API
            for i in range(num_31day_blocks + 1):
                begin_datetime_loop = begin_datetime + timedelta(days=(i * 31))
                end_datetime_loop = begin_datetime_loop + timedelta(days=31)

                # If end_datetime_loop of the current 31 day block is greater
                # than end_datetime specified by user, use end_datetime
                if end_datetime_loop > end_datetime:
                    end_datetime_loop = end_datetime

                # Build URL for each API request as we proceed through the loop
                data_url = self._build_query_url(
                    begin_datetime_loop.strftime('%Y%m%d'),
                    end_datetime_loop.strftime('%Y%m%d'),
                    product, datum, 
                    bin_num, interval, units, time_zone)
                
                # Get dataframe for block and append to time series df
                df_new = self._url2pandas(data_url, product, num_31day_blocks)
                df = df.append(df_new)
                
        # Rename output dataframe columns based on requested product
        # and convert to useable data types
        if product == 'water_level':
            # Rename columns for clarity
            df.rename(columns={'f': 'flags', 'q': 'QC', 's': 'sigma',
                            't': 'date_time', 'v': 'water_level'},
                    inplace=True)

            # Convert columns to numeric values
            data_cols = df.columns.drop(['flags', 'QC', 'date_time'])
            df[data_cols] = df[data_cols].apply(
                pd.to_numeric, axis=1, errors='coerce')

            # Convert date & time strings to datetime objects
            df['date_time'] = pd.to_datetime(df['date_time'])

        elif product == 'hourly_height':
            # Rename columns for clarity
            df.rename(columns={'f': 'flags', 's': 'sigma',
                            't': 'date_time', 'v': 'water_level'},
                    inplace=True)

            # Convert columns to numeric values
            data_cols = df.columns.drop(['flags', 'date_time'])
            df[data_cols] = df[data_cols].apply(
                pd.to_numeric, axis=1, errors='coerce')

            # Convert date & time strings to datetime objects
            df['date_time'] = pd.to_datetime(df['date_time'])

        elif product == 'high_low':
            # Rename columns for clarity
            df.rename(columns={'f': 'flags', 'ty': 'high_low',
                            't': 'date_time', 'v': 'water_level'},
                    inplace=True)

            # Separate to high and low dataframes
            df_HH = df[df['high_low'] == "HH"].copy()
            df_HH.rename(columns={'date_time': 'date_time_HH',
                                'water_level': 'HH_water_level'},
                        inplace=True)

            df_H = df[df['high_low'] == "H "].copy()
            df_H.rename(columns={'date_time': 'date_time_H',
                                'water_level': 'H_water_level'},
                        inplace=True)

            df_L = df[df['high_low'].str.contains("L ")].copy()
            df_L.rename(columns={'date_time': 'date_time_L',
                                'water_level': 'L_water_level'},
                        inplace=True)

            df_LL = df[df['high_low'].str.contains("LL")].copy()
            df_LL.rename(columns={'date_time': 'date_time_LL',
                                'water_level': 'LL_water_level'},
                        inplace=True)

            # Extract dates (without time) for each entry
            dates_HH = [x.date() for x in pd.to_datetime(df_HH['date_time_HH'])]
            dates_H = [x.date() for x in pd.to_datetime(df_H['date_time_H'])]
            dates_L = [x.date() for x in pd.to_datetime(df_L['date_time_L'])]
            dates_LL = [x.date() for x in pd.to_datetime(df_LL['date_time_LL'])]

            # Set indices to datetime
            df_HH['date_time'] = dates_HH
            df_HH.index = df_HH['date_time']
            df_H['date_time'] = dates_H
            df_H.index = df_H['date_time']
            df_L['date_time'] = dates_L
            df_L.index = df_L['date_time']
            df_LL['date_time'] = dates_LL
            df_LL.index = df_LL['date_time']

            # Remove flags and combine to single dataframe
            df_HH = df_HH.drop(
                columns=['flags', 'high_low'])
            df_H = df_H.drop(columns=['flags', 'high_low',
                                    'date_time'])
            df_L = df_L.drop(columns=['flags', 'high_low',
                                    'date_time'])
            df_LL = df_LL.drop(columns=['flags', 'high_low',
                                        'date_time'])

            # Keep only one instance per date (based on max/min)
            maxes = df_HH.groupby(df_HH.index).HH_water_level.transform(max)
            df_HH = df_HH.loc[df_HH.HH_water_level == maxes]
            maxes = df_H.groupby(df_H.index).H_water_level.transform(max)
            df_H = df_H.loc[df_H.H_water_level == maxes]
            mins = df_L.groupby(df_L.index).L_water_level.transform(max)
            df_L = df_L.loc[df_L.L_water_level == mins]
            mins = df_LL.groupby(df_LL.index).LL_water_level.transform(max)
            df_LL = df_LL.loc[df_LL.LL_water_level == mins]

            df = df_HH.join(df_H, how='outer')
            df = df.join(df_L, how='outer')
            df = df.join(df_LL, how='outer')

            # Convert columns to numeric values
            data_cols = df.columns.drop(
                ['date_time', 'date_time_HH', 'date_time_H', 'date_time_L',
                'date_time_LL'])
            df[data_cols] = df[data_cols].apply(pd.to_numeric, axis=1,
                                                errors='coerce')

            # Convert date & time strings to datetime objects
            df['date_time'] = pd.to_datetime(df.index)
            df['date_time_HH'] = pd.to_datetime(df['date_time_HH'])
            df['date_time_H'] = pd.to_datetime(df['date_time_H'])
            df['date_time_L'] = pd.to_datetime(df['date_time_L'])
            df['date_time_LL'] = pd.to_datetime(df['date_time_LL'])

        elif product == 'predictions':
            if interval == 'h' or interval is None:
                # Rename columns for clarity
                df.rename(columns={'t': 'date_time', 'v': 'predicted_wl'},
                        inplace=True)

                # Convert columns to numeric values
                data_cols = df.columns.drop(['date_time'])
                df[data_cols] = df[data_cols].apply(pd.to_numeric, axis=1,
                                                errors='coerce')

            elif interval == 'hilo':
                # Rename columns for clarity
                df.rename(columns={'t': 'date_time', 'v': 'predicted_wl',
                                'type': 'hi_lo'},
                        inplace=True)

                # Convert columns to numeric values
                data_cols = df.columns.drop(['date_time', 'hi_lo'])
                df[data_cols] = df[data_cols].apply(pd.to_numeric, axis=1,
                                                errors='coerce')

            # Convert date & time strings to datetime objects
            df['date_time'] = pd.to_datetime(df['date_time'])

        elif product == 'currents':
            # Rename columns for clarity
            df.rename(columns={'b': 'bin', 'd': 'direction',
                            's': 'speed', 't': 'date_time'},
                    inplace=True)

            # Convert columns to numeric values
            data_cols = df.columns.drop(['date_time'])
            df[data_cols] = df[data_cols].apply(pd.to_numeric, axis=1,
                                                errors='coerce')

            # Convert date & time strings to datetime objects
            df['date_time'] = pd.to_datetime(df['date_time'])

        elif product == 'wind':
            # Rename columns for clarity
            df.rename(columns={'d': 'dir', 'dr': 'compass',
                            'f': 'flags', 'g': 'gust_spd',
                            's': 'spd', 't': 'date_time'},
                    inplace=True)

            # Convert columns to numeric values
            data_cols = df.columns.drop(['date_time', 'flags', 'compass'])
            df[data_cols] = df[data_cols].apply(pd.to_numeric, axis=1,
                                                errors='coerce')

            # Convert date & time strings to datetime objects
            df['date_time'] = pd.to_datetime(df['date_time'])

        elif product == 'air_pressure':
            # Rename columns for clarity
            df.rename(columns={'f': 'flags',
                               't': 'date_time',
                               'v': 'air_press'},
                    inplace=True)

            # Convert columns to numeric values
            data_cols = df.columns.drop(['date_time', 'flags'])
            df[data_cols] = df[data_cols].apply(pd.to_numeric, axis=1,
                                                errors='coerce')

            # Convert date & time strings to datetime objects
            df['date_time'] = pd.to_datetime(df['date_time'])

        elif product == 'air_temperature':
            # Rename columns for clarity
            df.rename(columns={'f': 'flags', 't': 'date_time', 'v': 'air_temp'},
                    inplace=True)

            # Convert columns to numeric values
            data_cols = df.columns.drop(['date_time', 'flags'])
            df[data_cols] = df[data_cols].apply(pd.to_numeric, axis=1,
                                                errors='coerce')

            # Convert date & time strings to datetime objects
            df['date_time'] = pd.to_datetime(df['date_time'])

        elif product == 'water_temperature':
            # Rename columns for clarity
            df.rename(columns={'f': 'flags',
                               't': 'date_time',
                               'v': 'water_temp'},
                      inplace=True)

            # Convert columns to numeric values
            data_cols = df.columns.drop(['date_time', 'flags'])
            df[data_cols] = df[data_cols].apply(pd.to_numeric, axis=1,
                                                errors='coerce')

            # Convert date & time strings to datetime objects
            df['date_time'] = pd.to_datetime(df['date_time'])

        # Set datetime to index (for use in resampling)
        df.index = df['date_time']
        df = df.drop(columns=['date_time'])

        # Handle hourly requests for water_level and currents data
        if ((product == 'water_level') | (product == 'currents')) & (
                interval == 'h'):
            df = df.resample('H').first()  # Only return the hourly data

        df.drop_duplicates()  # Handle duplicates due to overlapping requests
        self.data = df
        return df

# -----------------------------------------------

# Test functionality
# if __name__ == "__main__":

#     # Test that except: pass works for stations with noe data inventory
#     # e.g. current stations
    
#     print('Test current station request & that data_inventory exception works')
#     print('\n')

#     puget = Station("PUG1515")

#     puget_data = puget.get_data(
#         begin_date="20150727",
#         end_date="20150910",
#         product="currents",
#         bin_num=1,
#         units="metric",
#         time_zone="gmt"
#         )

#     print(puget_data.head())
#     print('\n')
    
#     # Test metadata functionality
#     seattle = Station(9447130)     # water levels

#     print('Test that metadata is working')
#     print(seattle.sensors)
#     print('\n')

#     print('Test that data_inventory is working')
#     print(seattle.data_inventory)
#     print('\n')

#     print('Test water level station request')

#     sea_data = seattle.get_data(
#         begin_date="20150101",
#         end_date="20150331",
#         product="water_level",
#         datum="MLLW",
#         units="metric",
#         time_zone="gmt"
#         )

#     print(sea_data.head())
#     print('\n')

#     print('Test wind data request with large data gap (>block size)')

#     # Test request qith data gap larger than block size (should throuw an error)
#     npt = Station(9418767)
#     npt_data = npt.get_data(
#         begin_date='20080808',
#         end_date='20120101',
#         product='wind',
#         units='metric',
#         time_zone='gmt'
#         )

#     print(npt_data.head())
#     print('\n')
#     print('__main__ done!')