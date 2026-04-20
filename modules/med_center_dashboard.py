import time
import pandas as pd
import numpy as np
import pathlib
from modules import headway
from modules import capacity
from modules import travel_time

MODULE_DIR = pathlib.Path(__file__).resolve().parent
REPO_ROOT = MODULE_DIR.parent

def med_center_dashboard(year, month):
    '''
    Main function to run the medical center dashboard. This will process the busstate data for the medical center route and return a dataframe with the relevant metrics for the dashboard.

    Args:
        year (str): The 2 digit year of the busstate data.
        month (str): The 2 digit month of the busstate data.
    Returns:
        None: This function saves 3 .csv files to ./dashboard_data/YEAR/MONTH/
    '''
    # Month and year input validation and formatting
    if not isinstance(year, str) or len(year) != 2 or not year.isdigit():
        raise ValueError("Year must be a 2-digit string (e.g., '25')")
    
    if not isinstance(month, str) or len(month) != 2 or not month.isdigit():
        raise ValueError("Month must be a 2-digit string (e.g., '09')")
    
    if not (1 <= int(month) <= 12):
        raise ValueError("Month must be between 01 and 12")
    
    # convert to full year and map to month abbrev
    months = {
        "01": "JAN",
        "02": "FEB",
        "03": "MAR",
        "04": "APR",
        "05": "MAY",
        "06": "JUN",
        "07": "JUL",
        "08": "AUG",
        "09": "SEP",
        "10": "OCT",
        "11": "NOV",
        "12": "DEC"
    }
    full_year = int("20" + year)
    month_abbrev = months[month]

    #timer
    start = time.perf_counter()
    print(f"Processing medical center dashboard for {month_abbrev} {full_year}...")

    # process busstate data for medical center route
    mc_busstate_consolidated = process_mc_busstate(full_year, month_abbrev)
    # NOTE: this could be used for future internal dashboard use
    #mc_busstate_consolidated.to_csv(REPO_ROOT / f"mc_busstate_consolidated_{month_abbrev}_{full_year}.csv", index = False) # save the consolidated busstate data for reference - this is a large file but could be useful for future internal dashboard use and debugging

    print("Calculating headway, capacity, and travel time metrics for the dashboard...")

    # headway, capacity and travel time are imported from separate modules for organization
    headway_table = headway.create_headway(mc_busstate_consolidated)
    capacity_table = capacity.create_capacity(mc_busstate_consolidated)
    travel_time_table = travel_time.create_travel_time(mc_busstate_consolidated)

    print("Metrics below calculated, saving to .csv...")

    # # preview
    # print(headway_table)
    # print(capacity_table)  
    # print(travel_time_table)

    # save all metrics tables as .csv in 
    metric_dir = REPO_ROOT / "dashboard_data" / f"{full_year}" / f"{month_abbrev}"
    metric_dir.mkdir(parents = True, exist_ok = True) # create directory if it doesn't exist

    headway_table.to_csv(metric_dir / f'1-Headway-{month_abbrev}-{full_year}.csv')
    capacity_table.to_csv(metric_dir / f'2-Capacity-{month_abbrev}-{full_year}.csv')
    travel_time_table.to_csv(metric_dir / f'3-TravelTime-{month_abbrev}-{full_year}.csv')

    end = time.perf_counter()
    print(f"Finished processing medical center data for {month}/{year} in {end - start:.2f} seconds.")
    print(f"Headway, capacity, and travel time metrics saved to '{metric_dir}'")

    # Finally, print out the total boardings for the month
    total_boardings = mc_busstate_consolidated['BOARDINGS'].sum()

    # print passenger count to .txt
    with open(metric_dir / f'TotalBoardings-{month_abbrev}-{full_year}.txt', 'w') as f:
        f.write(f"Total boardings of {month_abbrev} {full_year}: {total_boardings} passengers\n")
    print(f"Total boardings of {month_abbrev} {full_year}: {total_boardings} passengers")

def build_stops_df():
    '''
    Build stops dataframe by merging static pattern stops and stop inventory files. Anytime that stops change, this will need to be re run after the csv files are updated.
    This contains every stop for CABS.

    Parameters:
        None
    Returns:
        stops_df (pd.DataFrame): dataframe with stop id, stop name, and lat/lon coordinates for all stops in the pattern stops file
    '''
    # set directory paths for stop data - stored as 2 csv files in ./stops/
    stop_data_dir = REPO_ROOT / "stops"
    pattern_stops_path = stop_data_dir / "pattern_stops.csv"
    stop_inventory_path = stop_data_dir / "stop_inventory.csv"

    # read in static stop files
    pattern_stops = pd.read_csv(pattern_stops_path, header = None) # no header
    stop_inventory = pd.read_csv(stop_inventory_path)

    # only need cols 0 and 9 and can drop any dups
    pattern_stops = pattern_stops.iloc[:, [0, 9]].drop_duplicates()
    pattern_stops.columns = ["ROUTE", "STOP_ID"] # rename cols for merge

    # Merge pattern stops and stop inventory on stop id - left merge 
    stops_df = pattern_stops.merge(stop_inventory, how = "left", on = "STOP_ID")

    return stops_df

def which_stop(lat, lon, stops_df = build_stops_df(), route = "MC", max_distance = 0.0005):
    '''
    Determine the closest stop to a given latitude and longitude. Med center route is default, but can be updated to other routes as needed. 
    NOTE: stops_df must be a global variable for this function to work, so build_stops_df() must be run before this function is called.

    Args:
        lat (float): The latitude of the point of interest.
        lon (float): The longitude of the point of interest.
        stops_df (pd.DataFrame): DataFrame containing stop information created from build_stops_df() function
        route (str): The route to filter stops by. Default is "MC" for medical center. Based on ROUTE col in stops DataFrame. Potentially important in future for overlapping stops.
        max_distance (float): The maximum distance to consider for a stop. Default is 0.0005 per legacy R code. approximately 150ish feet

    Returns:
        int: The STOP_ID of the closest stop within approximately 150 feet, or None if no stops are within the specified distance.
    '''
    # subset the stops to route of interest
    route_stops = stops_df[stops_df['ROUTE'] == route]

    distance_lon = route_stops['LONG'].values - lon
    distance_lat = route_stops['LAT'].values - lat

    # calculate the distance to each stop
    distances = np.sqrt(distance_lon**2 + distance_lat**2)

    mask = distances < max_distance
    # lowest distance should be the closest stop now. - each stop is at minimum approx 430ft apart so margin of 150 should be fine for MC route.
    selected_stop = route_stops[mask]

    # if no stops within alloted distance, return None
    if not np.any(mask):
        return None

    return int(route_stops.loc[mask, 'STOP_ID'].iloc[0])

# NOTE: Will need to update function with year and month functionality.
def process_mc_busstate(year, month, current_dir = REPO_ROOT, repo_dir = REPO_ROOT):
    """
    Process the busstate data for the medical center route. This step is the most intensive and will take a couple minutes to run.
    NOTE: This will ONLY work for the medical center route.
    NOTE: This will return a significantly smaller dataframe
    Args:
        year (int): The 4 digit year of the busstate data.
        month (str): The 3 letter month abbreviation of the busstate data.
        current_dir (str): The directory where the raw busstate data is stored. Default is the repo root, but can be updated to point to a different directory as needed.
        repo_dir (str): The directory where the processed busstate data will be saved. Default
    Returns:
        DataFrame: A pandas DataFrame containing the processed busstate data for the medical center route.
    """

    current_dir = REPO_ROOT / current_dir
    busstate_path = current_dir / f"{year}-{month}-busstate.csv"
    busstate_df = pd.read_csv(busstate_path) # Now cleaned busstate data read in

    # Process the busstate data for medical center routes
    #busstate_df.info()

    # should filter to just MC routes
    filtered_busstate_df = busstate_df.loc[(busstate_df['RUN_ID'] > 1500) & (busstate_df['RUN_ID'] < 1600)].copy()

    # Convert time metrics to datetime
    filtered_busstate_df['EVENT_TIME'] = pd.to_datetime(filtered_busstate_df['EVENT_TIME'], format = "%H:%M:%S")
    filtered_busstate_df['DEPARTURE_TIME'] = pd.to_datetime(filtered_busstate_df['DEPARTURE_TIME'], format = "%H:%M:%S")
    filtered_busstate_df['ENTER_STOP_WINDOW_TIME'] = pd.to_datetime(filtered_busstate_df['ENTER_STOP_WINDOW_TIME'], format = "%H:%M:%S")
    filtered_busstate_df['EXIT_STOP_WINDOW_TIME'] = pd.to_datetime(filtered_busstate_df['EXIT_STOP_WINDOW_TIME'], format = "%H:%M:%S")

    # sort by date and event time
    filtered_busstate_df = filtered_busstate_df.sort_values(['DATE', 'EVENT_TIME'])

    # Assign stop ID - most resource intensive step - as INT not float
    filtered_busstate_df['STOP_ID'] = filtered_busstate_df.apply(lambda row: which_stop(row['LATITUDE'], row['LONGITUDE']), axis = 1)

    # filter out 'dummy' stops, 27 and 461
    filtered_busstate_df = filtered_busstate_df.drop(filtered_busstate_df[filtered_busstate_df['STOP_ID'].isin([27, 461])].index)

    # filter out empty stops - where bus was on route and not at a stop geographically
    filtered_busstate_df = filtered_busstate_df.drop(filtered_busstate_df[filtered_busstate_df['STOP_ID'].isna()].index)

    # Convert to int
    filtered_busstate_df['STOP_ID'] = filtered_busstate_df['STOP_ID'].astype(int)

    # filter by bus id, date, event time
    filtered_busstate_df = filtered_busstate_df.sort_values(['BUS_ID', 'DATE', 'EVENT_TIME']).reset_index(drop = True) # restting index

    # create a new col for each new event
    # when stop changes OR bus_id changes OR elapsed time > 60
    count = (
        (filtered_busstate_df['STOP_ID'] != filtered_busstate_df['STOP_ID'].shift(1)) |
        (filtered_busstate_df['BUS_ID'] != filtered_busstate_df['BUS_ID'].shift(1)) |
        ((filtered_busstate_df['EVENT_TIME'] - filtered_busstate_df['EVENT_TIME'].shift(1)).dt.total_seconds() >= 3600) 
        # this should create a new event if more than an hour has passed since the last event
    )

    # take cumsum of count to assign 
    filtered_busstate_df['COUNT'] = count.cumsum()

    # consolidate df
    consolidated_busstate_df = filtered_busstate_df.groupby(['BUS_ID', 'DATE', 'COUNT', 'STOP_ID', 'RUN_ID'], as_index = False).agg(
        BOARDINGS = ('BOARDINGS', 'sum'), # this WAS max
        ALIGHTINGS = ('ALIGHTINGS', 'sum'), # this WAS max
        LOAD = ('PASSENGER_LOAD', 'max'),
        EARLY_EVENT=("EVENT_TIME", "min"),
        LATE_EVENT=("EVENT_TIME", "max"),
        DEPARTURE_TIME=("DEPARTURE_TIME", "max"),
        ENTER_STOP=("ENTER_STOP_WINDOW_TIME", "min"),
        EXIT_STOP=("EXIT_STOP_WINDOW_TIME", "max"),
        RUN_ID = ("RUN_ID", "last"),
        DEST=("DEST_SIGN_ROUTE_TEXT", "last"),
    )
    #print(consolidated_busstate_df)

    # calculate the arrival and departure times for each event
    consolidated_busstate_df['ARRIVAL'] = consolidated_busstate_df[['EARLY_EVENT', 'ENTER_STOP']].min(axis=1) # arrival is earlier enter stop or early event
    consolidated_busstate_df['DEPARTURE'] = consolidated_busstate_df[['LATE_EVENT', 'DEPARTURE_TIME', 'EXIT_STOP']].max(axis=1) # departure is latest of late event or departure time or exit stop
    consolidated_busstate_df['DWELL'] = (consolidated_busstate_df['DEPARTURE'] - consolidated_busstate_df['ARRIVAL']) # total dwell time at stop

    # can drop unnecessary cols now
    consolidated_busstate_df = consolidated_busstate_df.drop(columns = ['EARLY_EVENT', 'LATE_EVENT', 'DEPARTURE_TIME', 'ENTER_STOP', 'EXIT_STOP'])

    # add hour and minute cols for filtering 
    consolidated_busstate_df['HOUR'] = consolidated_busstate_df['ARRIVAL'].dt.hour
    consolidated_busstate_df['MINUTE'] = consolidated_busstate_df['ARRIVAL'].dt.minute

    # convert 'DATE' to datetime
    consolidated_busstate_df['DATE'] = pd.to_datetime(consolidated_busstate_df['DATE'], format = "%Y-%m-%d")

    # ok - consolidated busstate df should now be ready for processing of the metrics.
    return consolidated_busstate_df
