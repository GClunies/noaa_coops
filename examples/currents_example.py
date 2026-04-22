from datetime import datetime, timedelta, timezone

import noaa_coops as nc

# Use a two-day window ending yesterday (UTC) so this example stays fresh
# against NOAA's rolling real-time currents availability.
end = datetime.now(timezone.utc).date() - timedelta(days=1)
begin = end - timedelta(days=1)

oakland_outer_LB3 = nc.Station("s09010")
currents = oakland_outer_LB3.get_data(
    begin_date=begin.strftime("%Y%m%d"),
    end_date=end.strftime("%Y%m%d"),
    product="currents",
    bin_num=2,
    units="metric",
    time_zone="gmt",
)

currents.head(20)
