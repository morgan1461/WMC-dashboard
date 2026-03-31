import os
from pathlib import Path
import time
import numpy as np
import pandas as pd

# constants
MONTH_ABBREV_MAP = {
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
    "12": "DEC",
}

CAPACITY_TIME_ORDER = ["5-6a", "6-7a", "7-8a", "8a-2p", "2-8p", "8-10p", "10p-12a"]
RIDECHECK_TIME_ORDER = ["5:30-7a", "7-10a", "10a-4p", "4-7p", "7p-12a", "12-5a"]
VALID_RUNTIME_LEGS = ["CARMACK 2 - JOHN HERRICK LOOP", "JOHN HERRICK LOOP - CARMACK 2"]

############
# helper functions for processing and metric calculations
############
# Input checking for month and year with status
def convert_year_month(year, month):
    """
    Resolve two-digit year/month inputs to the dashboard naming format.

    Args:
        year (str): two-digit year, e.g. "25"
        month (str): two-digit month, e.g. "10"

    Returns:
        tuple: (year_full, month_full)
    """
    # add leading zeros if necessary
    year = str(year).zfill(2)
    month = str(month).zfill(2)

    # error if month not in expected format
    if month not in MONTH_ABBREV_MAP:
        raise ValueError(f"Invalid month '{month}'. Expected values 01-12.")

    # must convert to int
    year_full = 2000 + int(year)
    month_full = MONTH_ABBREV_MAP[month]
    return year_full, month_full


def load_dashboard_inputs(year, month, root_dir="K:/AP/TTM/"):
    """
    Load busstate + static stop files required for dashboard metrics.

    Args:
        year (str): two-digit year, e.g. "25"
        month (str): two-digit month, e.g. "10"
        root_dir (str): root directory - would need changed if folder structure changes

    Returns:
        tuple: (busstate, stop_inventory, pattern_stops, dashboard_dir, year_full, month_full)
    """
    year_full, month_full = convert_year_month(year, month)

    # if any of these change, loading will break
    busstate_dir = os.path.join(root_dir, "Data/WMC Dashboard/BusState Cleaned")
    stops_dir = os.path.join(root_dir, "Data/WMC Dashboard/stops")
    dashboard_dir = os.path.join(root_dir, f"Data/WMC Dashboard/Dashboard Data/{year_full}/{month_full}")
    # likely will not exist, ok to create if not
    Path(dashboard_dir).mkdir(parents=True, exist_ok=True)

    # static files that WILL need updated for stop pattern changes
    stop_inventory = pd.read_csv(os.path.join(stops_dir, "stop_inventory.csv"))
    pattern_stops = pd.read_csv(os.path.join(stops_dir, "pattern_stops.csv"), header=None)

    # saved from previous step
    busstate_path = os.path.normpath(os.path.join(busstate_dir, f"{year_full}-{month_full}-busstate.csv"))
    busstate = pd.read_csv(busstate_path)

    return busstate, stop_inventory, pattern_stops, dashboard_dir, year_full, month_full


def build_stops_df(pattern_stops, stop_inventory):
    """
    Build route-stop lookup using the same schema used in the notebook. 
    NOTE: WILL NEED UPDATED TO CHANGE STOP PATTERNS

    Args: 
        pattern_stops (DataFrame): raw pattern stops csv file, no header, from source folder
        stop_inventory (DataFrame): stop inventory csv file with lat/long, from source folder

    Returns:
        DataFrame: columns=["ROUTE", "STOP_ID", "STOP_NAME", "LAT", "LONG"]
    """
    pattern_stops_filtered = pattern_stops.iloc[:, [0, 9]].drop_duplicates()
    pattern_stops_filtered.columns = ["ROUTE", "STOP_ID"]
    return pattern_stops_filtered.merge(stop_inventory, on="STOP_ID", how="left")

# create distance function
# NOTE: This does NOT account for curvature of the earth, but locations are close enough that it is negligible
# NOTE: If we want to be more precise in the future, this function can be updated.
def distance(x1, x2, y1, y2):
    '''
    Calculate the distance between two points.

    Args:
        x1 (float): The x-coordinate of the first point longitude.
        x2 (float): The x-coordinate of the second point longitude.
        y1 (float): The y-coordinate of the first point latitude.
        y2 (float): The y-coordinate of the second point latitude.
    Returns:
        float: The distance between the two points.
    '''
    return np.sqrt((x2 - x1)**2 + (y2 - y1)**2)

# Create function to determine the closest stop
def which_stop(lat, lon, route="MC", stops=None, max_distance=0.0005):
    '''
    Determine the closest stop to a given latitude and longitude. Med center route is default, but can be updated to other routes as needed. 
    NOTE: This will potentially break when new stops are added start Dec. 2025 - be careful when updating stop inventory.

    Args:
        lat (float): The latitude of the point of interest.
        lon (float): The longitude of the point of interest.
        route (str): The route to filter stops by. Default is "MC" for medical center. Based on ROUTE col in stops DataFrame.
        stops (DataFrame): A DataFrame containing stop information, including 'STOP_ID', 'LAT', and 'LONG' columns.
        max_distance (float): The maximum distance to consider for a stop. Default is 0.0005 per legacy R code.

    Returns:
        int: The STOP_ID of the closest stop.
    '''
    if stops is None:
        raise ValueError("stops DataFrame is required.")

    # isolate the specified route stops
    selected_stops = stops[stops['ROUTE'] == route].copy()

    # Calculate distance to each stop
    selected_stops['DISTANCE'] = distance(lon, selected_stops['LONG'], lat, selected_stops['LAT'])

    # subsetting only stops within max_distance units
    selected_stops = selected_stops[selected_stops['DISTANCE'] < max_distance]
    selected_stops = selected_stops.sort_values('DISTANCE')

    # sorted by distance, therfore return first stop which is closest
    if not selected_stops.empty:
        return selected_stops.iloc[0]["STOP_ID"]
    else:
        return None

# ---------------------------
# Process busstate data for med center shuttle
# ---------------------------
def process_mc_busstate(busstate_df, stops_df, stop_inventory):
    """
    Process the busstate data for the medical center route.
    NOTE: This will ONLY work for the medical center route.
    NOTE: This will return a significantly smaller dataframe
    Args:
        busstate_df (DataFrame): A DataFrame containing busstate data from the cleaned busstate files.
        stops_df (DataFrame): A DataFrame containing stop information, including 'STOP_ID', 'LAT', and 'LONG' columns.
        stop_inventory (DataFrame): A DataFrame containing stop inventory information.
    Returns:
        DataFrame: A pandas DataFrame containing the processed busstate data for the medical center route.
    """
    processed = (
        busstate_df
        # filtering directly for med center routes within 1500 and 1600
        # NOTE: R code uses > 1500 (exclusive), matching that boundary here
        .loc[(busstate_df["RUN_ID"] > 1500) & (busstate_df["RUN_ID"] < 1600)]
        .copy()
    )

    processed = (
        processed

        # convert time 
        .assign(
            EVENT_TIME=lambda df: pd.to_datetime(df["EVENT_TIME"], format="%H:%M:%S", errors="coerce"),
            DEPARTURE_TIME=lambda df: pd.to_datetime(df["DEPARTURE_TIME"], format="%H:%M:%S", errors="coerce"),
            ENTER_STOP_WINDOW_TIME=lambda df: pd.to_datetime(df["ENTER_STOP_WINDOW_TIME"], format="%H:%M:%S", errors="coerce"),
            EXIT_STOP_WINDOW_TIME=lambda df: pd.to_datetime(df["EXIT_STOP_WINDOW_TIME"], format="%H:%M:%S", errors="coerce"),
        )

        # sort by date and event time
        .sort_values(["DATE", "EVENT_TIME"])

        # Assign stop ID
        # NOTE: Might need to edit this function to address not being at a stop?
        .assign(
            STOP=lambda df: df.apply(
                lambda row: which_stop(row["LATITUDE"], row["LONGITUDE"], stops=stops_df), axis=1
            )
        )

        # filter out rows where a stop is not found
        .loc[lambda df: df["STOP"].notna()]

        # convert stop to numeric
        .assign(STOP=lambda df: pd.to_numeric(df["STOP"], errors="coerce"))

        # join with stop inventory
        .merge(stop_inventory, how="left", left_on="STOP", right_on="STOP_ID")

        # remove dummy stops - R code has 27 and 461 as inbound and outbound dummy stops.
        .loc[lambda df: ~df["STOP"].isin([27, 461])]

        # sort by BUS_ID, DATE, EVENT_TIME for elapsed calculations
        .sort_values(["BUS_ID", "DATE", "EVENT_TIME"])

        # convert times to minutes for easier calculations, and calculate elapsed time between events for grouping logic later
        .assign(
            EVENT_TIME_MIN=lambda df: df["EVENT_TIME"].dt.hour * 60
            + df["EVENT_TIME"].dt.minute
            + df["EVENT_TIME"].dt.second / 60,
            DEPARTURE_TIME_MIN=lambda df: df["DEPARTURE_TIME"].dt.hour * 60
            + df["DEPARTURE_TIME"].dt.minute
            + df["DEPARTURE_TIME"].dt.second / 60,
            ENTER_STOP_WINDOW_TIME_MIN=lambda df: df["ENTER_STOP_WINDOW_TIME"].dt.hour * 60
            + df["ENTER_STOP_WINDOW_TIME"].dt.minute
            + df["ENTER_STOP_WINDOW_TIME"].dt.second / 60,
            EXIT_STOP_WINDOW_TIME_MIN=lambda df: df["EXIT_STOP_WINDOW_TIME"].dt.hour * 60
            + df["EXIT_STOP_WINDOW_TIME"].dt.minute
            + df["EXIT_STOP_WINDOW_TIME"].dt.second / 60,
        )

        # compute elapsed time between rows
        .assign(ELAPSED=lambda df: (df["EVENT_TIME_MIN"] - df["EVENT_TIME_MIN"].shift(1)).round(2))
    )

    # Group and count logic - previously fixed R code - keep as redundant for now, but may be able to simplify in the future
    processed = processed.assign(
        NEW_GROUP=lambda df: (
            df["ELAPSED"].isna()
            | df["STOP"].isna()
            | df["STOP"].shift(1).isna()
            | df["BUS_ID"].isna()
            | df["BUS_ID"].shift(1).isna()
            | (df["STOP"] != df["STOP"].shift(1))
            | (df["BUS_ID"] != df["BUS_ID"].shift(1))
            | (df["ELAPSED"] >= 60)
        ).astype(int),
        COUNT=lambda df: df["NEW_GROUP"].cumsum(),
    )

    # no longer needed
    processed = processed.drop(columns=["NEW_GROUP"])

    #get rid of non existing event times
    processed = processed.loc[processed["EVENT_TIME"].notna()].copy()

    # consolidate ridership
    consolidated = (
        processed
        .groupby(["BUS_ID", "DATE", "COUNT", "STOP_NAME", "STOP", "RUN_ID"], as_index=False)
        
        # Summary statistics
        .agg(
            BOARDINGS=("BOARDINGS", "sum"),
            ALIGHTINGS=("ALIGHTINGS", "sum"),
            LOAD=("PASSENGER_LOAD", "max"),
            EARLY_EVENT=("EVENT_TIME_MIN", "min"),
            LATE_EVENT=("EVENT_TIME_MIN", "max"),
            DEPARTURE_TIME=("DEPARTURE_TIME_MIN", "max"),
            ENTER_STOP=("ENTER_STOP_WINDOW_TIME_MIN", "min"),
            EXIT_STOP=("EXIT_STOP_WINDOW_TIME_MIN", "max"),
            DEST=("DEST_SIGN_ROUTE_TEXT", "last"),
        )

        # Arrival and departure logic - from R code
        .assign(
            ARRIVAL=lambda df: df[["EARLY_EVENT", "ENTER_STOP"]].min(axis=1),
            DEPARTURE=lambda df: df[["LATE_EVENT", "DEPARTURE_TIME", "EXIT_STOP"]].max(axis=1),
            DWELL=lambda df: df["DEPARTURE"] - df["ARRIVAL"],
        )

        # drop extra time cols
        .drop(columns=["EARLY_EVENT", "LATE_EVENT", "DEPARTURE_TIME", "ENTER_STOP", "EXIT_STOP"])
        
        # assign hour and min
        .assign(
            HOUR=lambda df: np.floor(df["ARRIVAL"] / 60),
            MIN=lambda df: np.floor(df["ARRIVAL"] % 60), # modulus to get remaining min after hour
        )
    )

    
    # clean infinities - previously fixed r code,  may be able to change in future
    consolidated[['ARRIVAL', 'DEPARTURE', 'DWELL']] = (
        consolidated[['ARRIVAL', 'DEPARTURE', 'DWELL']]
        .replace([np.inf, -np.inf], np.nan)
    )

    return consolidated


# ---------------------------
# Metric 1: Headway
# ---------------------------
def calculate_headways(df, stop_num):
    '''
    Calculate the headways for the given stop number. Key for stop numbers is in stop_inventory.csv file.
    NOTE: This should work with any stop with cleaned busstate data from processing.py

    Args:
        df (DataFrame): A pandas DataFrame containing processed busstate data.
        stop_num (int): The stop number of the stop to calculate the headways for.
    Returns:
        DataFrame: A pandas DataFrame containing the headways for the specified stop.
    '''
    df_hw = (
        df
        .loc[(df["STOP"] == stop_num) & (df["ARRIVAL"].notna())]
        .sort_values(["DATE", "ARRIVAL"])
        .copy()
    )

    df_hw["HEADWAY"] = df_hw.groupby("DATE")["ARRIVAL"].diff()

    # Filter to valid headways only - matches R: filter(HEADWAY < 22 & HEADWAY >= 0 & !is.na(HEADWAY))
    # Removes cross-day artifacts (first record of each day) and outliers > one loop cycle
    df_hw = df_hw.loc[
        (df_hw["HEADWAY"] < 22) & (df_hw["HEADWAY"] >= 0) & (df_hw["HEADWAY"].notna())
    ].copy()

    df_hw["DATE"] = pd.to_datetime(df_hw["DATE"])
    #NOTE: Eventually change this to convert midnight BEFORE headway>?
    df_hw["DATE"] = df_hw["DATE"].where(df_hw["HOUR"] != 0, df_hw["DATE"] - pd.Timedelta(days=1))
    df_hw["HOUR"] = df_hw["HOUR"].where(df_hw["HOUR"] != 0, 24)

    return df_hw


def build_headway_metric(mc_busstate):
    '''
    Build the headway metric summary table for the dashboard.
    NOTE: This follows methods and time buckets defined in the R code
    Args:
        mc_busstate (DataFrame): A pandas DataFrame containing the processed busstate data for the medical center route.
    Returns:
        DataFrame: A pandas DataFrame containing the headway metric summary table for the dashboard.
    '''
    carmack_2_headways = calculate_headways(mc_busstate, 403)
    carmack_3_headways = calculate_headways(mc_busstate, 404)
    transport_hub_headways = calculate_headways(mc_busstate, 405)

    # bind to one dataframe
    headway_df = pd.concat(
        [carmack_2_headways, carmack_3_headways, transport_hub_headways], ignore_index=True
    )

    # Set time frames and headways with ~10 minutes on either end for adjustment 
    # same method from the legacy R code
    time_frames = [
        (headway_df["HOUR"] <= 5),
        (headway_df["ARRIVAL"] >= 370) & (headway_df["ARRIVAL"] < 411),
        (headway_df["ARRIVAL"] >= 430) & (headway_df["ARRIVAL"] < 471),
        (headway_df["ARRIVAL"] >= 490) & (headway_df["ARRIVAL"] < 831),
        (headway_df["ARRIVAL"] >= 850) & (headway_df["ARRIVAL"] < 1190),
        (headway_df["ARRIVAL"] >= 1210) & (headway_df["ARRIVAL"] < 1310),
        (headway_df["ARRIVAL"] >= 1330) & (headway_df["ARRIVAL"] < 1431),
    ]

    # Use same time labels as R code - stored as constant at top of file
    time_labels = CAPACITY_TIME_ORDER
    target_times = [ # the target headway for each timeframe
        10,  # <=5
        3,   # 6-7a
        3,   # 7-8a
        10,  # 8a-2p
        5,   # 2-8p
        10,  # 8-10p
        5    # 10p-12a
    ]

    # Apply time buckets
    headway_df["TIME"] = np.select(time_frames, time_labels, default=pd.NA)

    # Apply targets. Use np.nan (not pd.NA) to keep numeric dtype for safe comparisons.
    headway_df["TARGET"] = np.select(time_frames, target_times, default=np.nan)

    # filter out missing
    headway_df = headway_df.loc[headway_df["TIME"].notna()].copy()

    # Create metric flag with NA-safe numeric comparison to avoid RuntimeWarning.
    headway_num = pd.to_numeric(headway_df["HEADWAY"], errors="coerce")
    target_num = pd.to_numeric(headway_df["TARGET"], errors="coerce")
    headway_df["MET"] = (headway_num.notna() & target_num.notna() & (headway_num <= target_num)).astype(int)

    headway_summary = (
        headway_df
        .groupby("TIME")
        .agg(
            MET=("MET", "sum"),
            COUNT=("HEADWAY", "size"),
            p50=("HEADWAY", lambda x: x.quantile(0.5)),
            p75=("HEADWAY", lambda x: x.quantile(0.75)),
            p90=("HEADWAY", lambda x: x.quantile(0.9)),
        )
        .reset_index()
    )

    # calculate percentage of headways that met the target for each time bucket
    headway_summary["MET"] = headway_summary["MET"] / headway_summary["COUNT"]
    headway_summary["TIME"] = pd.Categorical(
        headway_summary["TIME"], categories=CAPACITY_TIME_ORDER, ordered=True
    )
    headway_summary = headway_summary.sort_values("TIME").drop(columns=["COUNT"])

    return headway_summary


# ---------------------------
# Metric 2: Capacity
# ---------------------------
def assign_capacity_time_bucket(hour):
    """
    Map hour into capacity metric bucket.

    Args:
        hour (int): hour of the day (0-23)

    Returns:
        str: time bucket label for capacity metric
    """
    if hour <= 5:
        return "5-6a"
    if hour == 6:
        return "6-7a"
    if hour == 7:
        return "7-8a"
    if 8 <= hour < 14:
        return "8a-2p"
    if 14 <= hour < 20:
        return "2-8p"
    if 20 <= hour < 22:
        return "8-10p"
    return "10p-12a"


def assign_load_category(load):
    """
    Map rider load into the dashboard category bands.

    Args:
        load (int): the passenger load to categorize    
    Returns:
        str: load category label for capacity metric
    """
    if load <= 30:
        return "0-30 Passengers"
    if load <= 50:
        return "31-50 Passengers"
    if load <= 65:
        return "51-65 Passengers"
    return "66+ Passengers"


def build_capacity_metric(mc_busstate):
    """
    Build dashboard capacity table (metric 2).

    Args:
        mc_busstate (DataFrame): A pandas DataFrame containing the processed busstate data specifically for the medical center route, from the process_mc_busstate function.

    Returns:
        tuple: (mc_loads, mc_rider_df)
    """

    # this will need to be updated when stops change
    mc_rider_df = mc_busstate.loc[mc_busstate["STOP_NAME"] == "JOHN HERRICK LOOP"].copy()
    
    # load as max of boarding or alighitngs at the thub
    mc_rider_df["LOAD"] = mc_rider_df[["BOARDINGS", "ALIGHTINGS"]].max(axis=1)

    mc_rider_df["TIME"] = mc_rider_df["HOUR"].apply(assign_capacity_time_bucket)

    mc_loads_time = mc_rider_df.groupby("TIME").size().reset_index(name="LOOPS")

    mc_rider_df["SIZE"] = mc_rider_df["LOAD"].apply(assign_load_category)

    # assign by hour and load cat
    mc_loads_pax = (
        mc_rider_df
        .groupby(["HOUR", "SIZE"])
        .size()
        .reset_index(name="LOOPS")
    )

    # pivot to get load categories as columns, with hours as rows, then assign time buckets and sum by time bucket
    mc_loads_pax_size = (
        mc_loads_pax
        .pivot_table(index="HOUR", columns="SIZE", values="LOOPS", fill_value=0)
        .reset_index()
    )

    # assign time buckets to the pivoted dataframe and sum by time bucket
    mc_loads_pax_size["TIME"] = mc_loads_pax_size["HOUR"].apply(assign_capacity_time_bucket)
    mc_loads_pax_size_sum = mc_loads_pax_size.groupby("TIME").sum().reset_index()

    # this can probably be done better - will revisit
    for col in ["0-30 Passengers", "31-50 Passengers", "51-65 Passengers", "66+ Passengers"]:
        if col not in mc_loads_pax_size_sum.columns:
            mc_loads_pax_size_sum[col] = 0

    # join the time bucket counts with the load category counts
    mc_loads = mc_loads_time.merge(mc_loads_pax_size_sum, on="TIME", how="inner")

    if "HOUR" in mc_loads.columns:
        mc_loads = mc_loads.drop(columns=["HOUR"])

    # create final capacity summary
    mc_loads["TIME"] = pd.Categorical(mc_loads["TIME"], categories=CAPACITY_TIME_ORDER, ordered=True)
    mc_loads = mc_loads.sort_values("TIME")

    return mc_loads, mc_rider_df


# ---------------------------
# Metric 3: Travel time
# ---------------------------
def assign_ridecheck_time(partial_hour_series):
    """
    Map fractional hour to ridecheck/travel-time buckets.

    Args:
        partial_hour_series (Series): pandas Series with fractional hour values
    Returns:
        Series: pandas Series with time bucket labels for ridecheck/travel-time metric
    """
    conditions = [
        (partial_hour_series >= 5.5) & (partial_hour_series < 7),
        (partial_hour_series >= 7) & (partial_hour_series < 10),
        (partial_hour_series >= 10) & (partial_hour_series < 16),
        (partial_hour_series >= 16) & (partial_hour_series < 19),
        (partial_hour_series >= 19),
    ]
    labels = RIDECHECK_TIME_ORDER[:-1]
    # default to the 12-5a bucket if no other conditions are met, which matches the R code logic of assigning 12-5a as default and then overwriting with other buckets if conditions are met
    return np.select(conditions, labels, default="12-5a")


def build_travel_time_metric(mc_busstate, mc_rider_df):
    """
    Build dashboard travel-time table (metric 3).

    Args:
        mc_busstate (DataFrame): A pandas DataFrame containing the processed busstate data specifically for the medical center route, from the process_mc_busstate function.
        mc_rider_df (DataFrame): A pandas DataFrame containing the processed busstate data specifically for the medical center route filtered to the John Herrick Loop stop
    """
    # loop counts 
    mc_loads_ridecheck = mc_rider_df.copy()
    mc_loads_ridecheck["HOUR_PARTIAL"] = mc_loads_ridecheck["HOUR"] + (mc_loads_ridecheck["MIN"] / 60)
    mc_loads_ridecheck["TIME"] = assign_ridecheck_time(mc_loads_ridecheck["HOUR_PARTIAL"])

    # group by time bucket and count loops
    mc_loads_ridecheck = (
        mc_loads_ridecheck
        .groupby("TIME", as_index=False)
        .size()
        .rename(columns={"size": "LOOPS"})
    )

    # assign time bucket order and fill missing buckets with 0 loops
    mc_loads_ridecheck["TIME"] = pd.Categorical(
        mc_loads_ridecheck["TIME"], categories=RIDECHECK_TIME_ORDER, ordered=True
    )


    mc_loads_ridecheck = (
        mc_loads_ridecheck
        .set_index("TIME")
        .reindex(RIDECHECK_TIME_ORDER, fill_value=0)
        .reset_index()
    )

    # runtime by leg MC.RT/MC.RT.grouped in R code
    mc_rt = (
        mc_busstate
        .sort_values(["BUS_ID", "DATE", "ARRIVAL"])
        .loc[~mc_busstate["STOP"].isin([94, 95, 404])]
        .copy()
    )

    # lag values within bus/day
    mc_rt["PREV_DEPARTURE"] = mc_rt.groupby(["BUS_ID", "DATE"])["DEPARTURE"].shift(1)
    mc_rt["PREV_STOP_NAME"] = mc_rt.groupby(["BUS_ID", "DATE"])["STOP_NAME"].shift(1)
    mc_rt["RUN_TIME"] = mc_rt["ARRIVAL"] - mc_rt["PREV_DEPARTURE"]
    mc_rt["LEG"] = mc_rt["PREV_STOP_NAME"] + " - " + mc_rt["STOP_NAME"]

    # filter to just the two legs of interest
    mc_rt = mc_rt.loc[
        mc_rt["LEG"].isin(VALID_RUNTIME_LEGS)
        & mc_rt["RUN_TIME"].notna()
        & (mc_rt["RUN_TIME"] >= 0)
        & (mc_rt["RUN_TIME"] < 20)
    ].copy()

    # assign time buckets based on arrival time at John Herrick Loop
    mc_rt["HOUR_PARTIAL"] = mc_rt["HOUR"] + (mc_rt["MIN"] / 60)
    mc_rt["TIME"] = assign_ridecheck_time(mc_rt["HOUR_PARTIAL"])

    mc_rt_grouped = (
        mc_rt
        .groupby(["TIME", "LEG"], as_index=False)["RUN_TIME"]
        .mean()
    )

    # round to 1 decimal place to match R code output
    mc_rt_grouped["RUN_TIME"] = mc_rt_grouped["RUN_TIME"].round(1)
    mc_rt_grouped = mc_rt_grouped.pivot(index="TIME", columns="LEG", values="RUN_TIME").reset_index()

    # final metric table is a merge of the loop counts and the runtime tables
    travel_time = mc_loads_ridecheck.merge(mc_rt_grouped, on="TIME", how="left")
    travel_time["TIME"] = pd.Categorical(
        travel_time["TIME"], categories=RIDECHECK_TIME_ORDER, ordered=True
    )
    travel_time = travel_time.sort_values("TIME")

    return travel_time


# ---------------------------
# Output
# ---------------------------
def save_dashboard_outputs(headway_summary, capacity_summary, travel_time_summary, dashboard_dir, month_full, year_full):
    """
    Save all dashboard metric csv outputs to the expected folder.

    Args:
        headway_summary (DataFrame): DataFrame containing the headway metric summary table for the month
        capacity_summary (DataFrame): DataFrame containing the capacity metric summary table for the month
        travel_time_summary (DataFrame): DataFrame containing the travel time metric summary table for the month
        dashboard_dir (str): the directory to save the outputs in, expected to be in the
        month_full (str): the full month name for the output file naming, e.g. "OCT"
        year_full (str): the full year for the output file naming, e.g. "2025"
    
    Returns:
        None - outputs are saved as csv files in the specified directory
    """
    headway_summary.to_csv(f"{dashboard_dir}/1-Headway-{month_full}-{year_full}.csv", index=False)
    capacity_summary.to_csv(f"{dashboard_dir}/2-Capacity-{month_full}-{year_full}.csv", index=False)
    travel_time_summary.to_csv(f"{dashboard_dir}/3-TravelTime-{month_full}-{year_full}.csv", index=False)


def run_dashboard_metrics(year, month, root_dir="K:/AP/TTM/", save_outputs=True):
    """
    Master function to run the full WMC dashboard workflow in one call.

    Parameters:
        year (str): two-digit year, e.g. "25"
        month (str): two-digit month, e.g. "10"
        root_dir (str): root directory where source/output folders exist
        save_outputs (bool): whether to write csv outputs to dashboard directory

    Returns:
        None
    """
    print(f"Starting dashboard metrics for {month}/{year}...")

    busstate, stop_inventory, pattern_stops, dashboard_dir, year_full, month_full = load_dashboard_inputs(
        year=year,
        month=month,
        root_dir=root_dir,
    )

    stops_df = build_stops_df(pattern_stops, stop_inventory)

    # status and timer, most intensive step
    print(f'Processing busstate data for medical center route...')
    start = time.perf_counter()

    mc_busstate = process_mc_busstate(busstate, stops_df, stop_inventory)

    end = time.perf_counter()
    print(f"Finished processing busstate data for {month}/{year} in {end - start:.2f} seconds")

    print(f'Calculating dashboard metrics for medical center route...')
    headway_summary = build_headway_metric(mc_busstate)
    capacity_summary, mc_rider_df = build_capacity_metric(mc_busstate)
    travel_time_summary = build_travel_time_metric(mc_busstate, mc_rider_df)
    print(f"Finished calculating dashboard metrics for {month}/{year}.")

    if save_outputs:
        save_dashboard_outputs(
            headway_summary=headway_summary,
            capacity_summary=capacity_summary,
            travel_time_summary=travel_time_summary,
            dashboard_dir=dashboard_dir,
            month_full=month_full,
            year_full=year_full,
        )
        print(f"Saved dashboard metric outputs to '{dashboard_dir}'.")

    print("Dashboard metrics completed.")

    # return {
    #     "headway_summary": headway_summary,
    #     "capacity_summary": capacity_summary,
    #     "travel_time_summary": travel_time_summary,
    #     "mc_busstate": mc_busstate,
    #     "dashboard_dir": dashboard_dir,
    #     "year_full": year_full,
    #     "month_full": month_full,
    # }