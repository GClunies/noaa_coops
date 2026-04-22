"""Manual demo of the functionality shown in README.md.

Run this script to hit the live NOAA CO-OPS APIs and confirm that the
package behaves as the README advertises.

Usage:
    uv run python examples/readme_demo.py
"""

# Station populates metadata keys (name, lat_lon, metadata, ...) as
# attributes at runtime, so static attribute checks don't apply here.
# pyright: reportAttributeAccessIssue=false

from datetime import datetime, timedelta, timezone
from pprint import pprint

from noaa_coops import Station, get_stations_from_bbox


def section(title: str) -> None:
    bar = "=" * 72
    print(f"\n{bar}\n{title}\n{bar}")


def demo_station_init() -> Station:
    section("1. Station init — Seattle (id=9447130)")
    seattle = Station(id="9447130")
    print(f"name: {seattle.name}")
    return seattle


def demo_bbox_search() -> None:
    section("2. get_stations_from_bbox — NYC area")
    stations = get_stations_from_bbox(
        lat_coords=[40.389, 40.9397],
        lon_coords=[-74.4751, -73.7432],
    )
    pprint(stations)
    assert stations, "Expected at least one station in the NYC bbox"

    station_one = Station(id=stations[0])
    print(f"first station name: {station_one.name}")


def demo_metadata(seattle: Station) -> None:
    section("3. Metadata attributes")
    pprint(list(seattle.metadata.items())[:5])
    print(f"lat: {seattle.lat_lon['lat']}")
    print(f"lon: {seattle.lat_lon['lon']}")


def demo_data_inventory(seattle: Station) -> None:
    section("4. Data inventory")
    pprint(seattle.data_inventory)


def demo_get_data(seattle: Station) -> None:
    section("5. get_data — Seattle water level, Jan 2015")
    df = seattle.get_data(
        begin_date="20150101",
        end_date="20150131",
        product="water_level",
        datum="MLLW",
        units="metric",
        time_zone="gmt",
    )
    print(f"shape: {df.shape}")
    print(f"columns: {list(df.columns)}")
    print(f"index name: {df.index.name}")
    print("head:")
    print(df.head())
    assert not df.empty, "Expected non-empty water_level DataFrame"
    assert df.index.name == "t", "Expected timestamp index named 't'"


def demo_currents() -> None:
    section("6. get_data — Oakland currents (s09010, bin 2)")
    # Use a two-day window ending yesterday (UTC) so the demo stays fresh
    # against NOAA's rolling real-time currents availability.
    end = datetime.now(timezone.utc).date() - timedelta(days=1)
    begin = end - timedelta(days=1)
    station = Station("s09010")
    df = station.get_data(
        begin_date=begin.strftime("%Y%m%d"),
        end_date=end.strftime("%Y%m%d"),
        product="currents",
        bin_num=2,
        units="metric",
        time_zone="gmt",
    )
    print(f"shape: {df.shape}")
    print("head:")
    print(df.head())
    assert not df.empty, "Expected non-empty currents DataFrame"


def main() -> None:
    seattle = demo_station_init()
    demo_bbox_search()
    demo_metadata(seattle)
    demo_data_inventory(seattle)
    demo_get_data(seattle)
    demo_currents()
    print("\nAll README demos completed successfully.")


if __name__ == "__main__":
    main()
