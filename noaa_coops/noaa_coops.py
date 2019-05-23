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

        elif 'tidepredoffsets' in station_metadata:  # if True --> predicted tide
            self.metadata = station_metadata
            self.state = station_metadata['state']
            self.tide_pred_offsets = station_metadata['tidepredoffsets']
            self.type = station_metadata['type']
            self.time_meridian = station_metadata['timemeridian']
            self.reference_id = station_metadata['reference_id']
            self.timezone_corr = station_metadata['timezonecorr']
            self.station_name = station_metadata['name']
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
            self.station_name = station_metadata['name']
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
        
    def get_data(self, 
                 begin_date,
                 end_date,
                 stationid,
                 product,
                 datum,
                 interval=None, 
                 units='metric',
                 time_zone='gmt'):
        pass

# Test functionality
if __name__ == "__main__":
    
    # Test metadata functionality
    seattle = Station(9447130)     # water levels
    tacoma = Station(9446484)      # tide predictions
    cherry = Station('cp0101')     # currents - side viewing
    humboldt = Station('hb0201')   # currents - down viewing
    alki = Station('PUG1516')      # predicted currents