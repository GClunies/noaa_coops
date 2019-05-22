import math
from datetime import datetime, timedelta

import pandas as pd
import requests
from pandas.io.json import json_normalize


class Station:
    """
    A class to access station data and metadata via the NOAA Tides & Currents
    APIs. 
    
    For data retrieval API, see https://tidesandcurrents.noaa.gov/api/.
    For metadata API, see: https://tidesandcurrents.noaa.gov/mdapi/latest/
    """

    data_base_url = 'http://tidesandcurrents.noaa.gov/api/datagetter?'

    def __init__(self, stationid, units='metric'):
        self.stationid = stationid
        self.units = units
        self.get_metadata(self.stationid)   
    
    def get_metadata(self, stationid):
        # Build URL for metadata API request. When a Station object is
        # initialized, fill out metadata automatically.
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
        if station_metadata['datums']:  # if True --> water levels
            self.metadata = station_metadata
            self.affiliations = station_metadata['affiliations']
            self.benchmarks = station_metadata['benchmarks']
            self.datums = station_metadata['datums']
            self.details = station_metadata['details']
            self.disclaimers = station_metadata['disclaimers']
            self.flood_levels = station_metadata['floodlevels']
            self.greatlakes = station_metadata['greatlakes']
            self.tidal_constituents = station_metadata['harmonicConstituents']
            self.lat_lon = {
                'lat' : station_metadata['lat'],
                'lon' : station_metadata['lng']
            }
            self.station_name = station_metadata['name']
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

        elif station_metadata['tidepredoffsets']:  # if True --> predicted tide
            pass
        
        elif station_metadata['bins']:  # if True --> currents
            pass
        
        elif station_metadata['currbin']:  # if True --> predicted currents
            pass
        
    def get_data(self, 
                 begin_date,
                 end_date,
                 product,
                 datum,
                 interval=None, 
                 units='metric',
                 time_zone='gmt'):
        pass

# Us e
if __name__ == "__main__":
    
    seattle = Station(9447130, units='metric')