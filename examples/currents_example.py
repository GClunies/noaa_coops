import noaa_coops as nc


oakland_outer_LB3 = nc.Station("s09010")
currents = oakland_outer_LB3.get_data(
    begin_date="20210414",
    end_date="20210415",
    product="currents",
    bin_num=2,
    units="metric",
    time_zone="gmt",
)

currents.head(20)
