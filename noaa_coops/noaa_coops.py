import math
from datetime import datetime, timedelta

import pandas as pd
import requests
from pandas.io.json import json_normalize


class Station:
    """
    A class to access station data via the NOAA Tides & Currents
    data retrieval API. See https://tidesandcurrents.noaa.gov/api/.
    """

    data_base_url = 'http://tidesandcurrents.noaa.gov/api/datagetter?'

    def __init__(self, stationid, units='metric'):
        self.stationid = stationid
        self.units = units
    
    def metadata(self, stationid, units='metric'):
        self.stationid = stationid
        units_for_url = '?units=' + units
        metadata_base_url = 'http://tidesandcurrents.noaa.gov/mdapi/v1.0/webapi\
                             /stations/'
        extension = '.json'
        metadata_expand = '?expand=details,sensors,products,disclaimers,notices\
                           ,datums,harcon,tidepredoffets,benchmarks,nearby,bins\
                           ,deployments,currentpredictionoffsets,floodlevels'
        metadata_full_url = (metadata_base_url + str(self.stationid) + extension
                            + metadata_expand + units_for_url)
        
        response = requests.get(metadata_full_url)
        json_dict = response.json()
        
        # Define "self" parameters here (name, lat_lon, bins, etc.)

    def get_data(self, 
                 begin_date,
                 end_date,
                 product,
                 datum,
                 interval=None, 
                 units='metric',
                 time_zone='gmt'):
        pass