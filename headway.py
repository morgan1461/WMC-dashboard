import pandas as pd
import numpy as np

def create_headway(busstate_consolidated):
    '''
    Create headway dataframe by calculating headways for each stop and combining into a single dataframe, then calculating headway metrics for the dashboard.

    Args:
        busstate_consolidated (pd.DataFrame): The consolidated busstate dataframe.
    Returns:
        pd.DataFrame: A single dataframe containing the headway table for the medical center monthly dashboard.
    '''
    # combine headways into a single dataframe
    combined_headway_df = combine_headways(busstate_consolidated)
    # calculate headway metrics for the dashboard and save as .csv
    combined_headway_df = calculate_headway_dashboard_metrics(combined_headway_df)
    
    return combined_headway_df

def calculate_headway(busstate_df, stop_id):
    '''
    Calculate the headway for a given stop id in the busstate dataframe.

    Args:
        busstate_df (pd.DataFrame): The busstate dataframe containing the bus events.
        stop_id (int): The stop ID for which to calculate headways.
    Returns:
        pd.DataFrame: A subset dataframe containing the headways for the specified stop ID.
    '''
    # calculate headways of carmack 2 stop - 403
    stop_hw = busstate_df[busstate_df['STOP_ID'] == stop_id]

    stop_hw = stop_hw.sort_values(['DATE', 'ARRIVAL'])

    # stop_hw['ARRIVAL'].isna().sum() # zero NA
    stop_hw['HEADWAY'] = stop_hw['ARRIVAL'] - stop_hw['ARRIVAL'].shift(1) # headway in minutes

    stop_hw = stop_hw.loc[
        (stop_hw['HEADWAY'].dt.total_seconds() / 60 >= 0) & # filter out negative headways
        (stop_hw['HEADWAY'].dt.total_seconds() / 60 < 22) # filter out headways greater than 22 minutes - per legacy R code
        ] 

    # adjust for midnight arrivals where hour == 0
    stop_hw['DATE'] = stop_hw['DATE'].where(stop_hw['ARRIVAL'].dt.hour != 0,
                                                        stop_hw['DATE'] - pd.Timedelta(days = 1))
    stop_hw['HOUR'] = stop_hw['ARRIVAL'].dt.hour.where(stop_hw['ARRIVAL'].dt.hour != 0, 24)

    stop_hw.groupby(['DATE', 'ARRIVAL'])
    
    return stop_hw

def combine_headways(busstate_consolidated, carmack_2_id = 403, carmack_3_id = 404, university_hospital_id = 401, doan_hall_id = 37):
    '''
    Combine headway dataframes for each stop into a single dataframe.

    Args:
        busstate_consolidated (pd.DataFrame): The consolidated busstate dataframe.
        carmack_2_id (int): Stop ID for Carmack 2.
        carmack_3_id (int): Stop ID for Carmack 3.
        university_hospital_id (int): Stop ID for University Hospital.
        doan_hall_id (int): Stop ID for Doan Hall.
    Returns:
        pd.DataFrame: A single dataframe containing all headways.
    '''

    carmack_2_hw = calculate_headway(busstate_consolidated, carmack_2_id)
    carmack_3_hw = calculate_headway(busstate_consolidated, carmack_3_id)
    university_hospital_hw = calculate_headway(busstate_consolidated, university_hospital_id)
    doan_hall_hw = calculate_headway(busstate_consolidated, doan_hall_id)
    # Now have headways for each stop in separate dataframes, can calculate metrics from here.
    # If we wanted to calculate headway metrics BY STOP, we could do that here without concatenating

    combined_hw = pd.concat([carmack_2_hw, carmack_3_hw, university_hospital_hw, doan_hall_hw], ignore_index = True)

    # future use?
    # (combined_hw['HEADWAY'].dt.total_seconds() / 60).mean() # should be the average headway across all 4 stops for month of Dec in minutes.
    # (combined_hw['HEADWAY'].dt.total_seconds() / 60).median() # should be the median headway across all 4 stops for month of Dec in minutes.

    return combined_hw # this can be inspected for weird headways

def calculate_headway_dashboard_metrics(combined_headway_df):
    '''
    Calculate headway metrics for each target hour, intended for external reporting use.
    NOTE: Target hour is stored as a constant within this function, so if target hours change, this function will need to be updated.

    Args:
        combined_headway_df (pd.DataFrame): The combined headway dataframe containing headway information and target hours.
    Returns:
        pd.DataFrame: A summary dataframe containing the percentage of headways that met the target, as well as the 50th, 75th, and 90th percentile headway times for each target hour.
    '''
    # Target headways to calculate % on time for each timeframe
    TARGET_HEADWAYS = { # based on R code and report
        "5-6a": 10,
        "6-7a": 3,
        "7-8a": 3,
        "8a-2p": 10,
        "2-8p": 5,
        "8-10p": 10,
        "10p-12a": 5
    }
    # add in target headways to combined_headway_df based on hour of arrival
    combined_headway_df['TARGET'] = combined_headway_df['HOUR'].apply(
        lambda hour: TARGET_HEADWAYS["5-6a"] if hour == 5 else (
            TARGET_HEADWAYS["6-7a"] if hour == 6 else (
                TARGET_HEADWAYS["7-8a"] if hour == 7 else (
                    TARGET_HEADWAYS["8a-2p"] if 8 <= hour < 14 else (
                        TARGET_HEADWAYS["2-8p"] if 14 <= hour < 20 else (
                            TARGET_HEADWAYS["8-10p"] if 20 <= hour < 22 else (
                                TARGET_HEADWAYS["10p-12a"] if 22 <= hour or hour == 0 else np.nan
                            )
                        )
                    )
                )
            )
        )
    )
    # create min of headway col to compare to target
    combined_headway_df['HEADWAY_MIN'] = combined_headway_df['HEADWAY'].dt.total_seconds() / 60

    # create met col for met headway target
    combined_headway_df['MET'] = ((combined_headway_df['TARGET'].notna()) & (combined_headway_df['HEADWAY_MIN'] <= combined_headway_df['TARGET'])).astype(int)
    # 1 if met, 0 if not met, only calculate if target is not NA

    # create target hour where each hour is broken into the target timeframes
    combined_headway_df['TARGET_HOUR'] = combined_headway_df['HOUR'].apply(
        lambda hour: "5-6a" if hour == 5 else (
            "6-7a" if hour == 6 else (
                "7-8a" if hour == 7 else (
                    "8a-2p" if 8 <= hour < 14 else (
                        "2-8p" if 14 <= hour < 20 else (
                            "8-10p" if 20 <= hour < 22 else (
                                "10p-12a" if 22 <= hour or hour == 0 else np.nan
                            )
                        )
                    )
                )
            )
        )
    )

    # combined_hw['HEADWAY_MIN'].head(20)
    # sort by chronological order
    target_order = list(TARGET_HEADWAYS.keys())
    combined_headway_df['TARGET_HOUR'] = pd.Categorical(combined_headway_df['TARGET_HOUR'], categories = target_order, ordered = True)

    # use HOUR col to create a metrics table with current combined data
    headway_summary = (
        combined_headway_df
        .groupby('TARGET_HOUR') # grupby HOUR to have metrics by each individual hour, or TARGET_HOUR for the target timeframes
        .agg(
            MET = ("MET", "sum"),
            COUNT = ("HEADWAY", "size"),
            p50 = ("HEADWAY_MIN", lambda x: x.quantile(0.5)),
            p75 = ("HEADWAY_MIN", lambda x: x.quantile(0.75)),
            p90 = ("HEADWAY_MIN", lambda x: x.quantile(0.9)),
        )
    )
    # count here is LIKELY artificially inflated due to the 4th stop being added.
    headway_summary['MET'] = headway_summary['MET'] / headway_summary['COUNT'] # convert to percentage of headways that met target for each hour
    headway_summary.drop(columns = ['COUNT'], inplace = True)
    headway_summary.sort_values('TARGET_HOUR')

    return headway_summary
        
# NOTE: This is for future internal use for hourly breakdowns
def calculate_headway_internal_metrics(headway_df):
    '''
    Calculate internal headway metrics for each target hour, intended for internal use only and not external reporting. 
    This also can be configured to calculate metrics by stop if necessary, but currently is set up to calculate across all stops for each hour.
    This function is intended to be edited for future use as needed internally.

    Args:
        headway_df (pd.DataFrame): The combined headway dataframe containing headway information and target hours.
    Returns:
        pd.DataFrame: A summary dataframe containing headways by hour with summary statistcs includign mean, median, min, max, etc
    '''
    headway_summary = (
        headway_df
        .groupby('HOUR') # grupby HOUR to have metrics by each individual hour
        .agg(
            COUNT = ("HEADWAY", "size"),
            MEAN = ("HEADWAY_MIN", "mean"),
            MEDIAN = ("HEADWAY_MIN", "median"),
            MIN = ("HEADWAY_MIN", "min"),
            MAX = ("HEADWAY_MIN", "max"),
            p50 = ("HEADWAY_MIN", lambda x: x.quantile(0.5)),
            p75 = ("HEADWAY_MIN", lambda x: x.quantile(0.75)),
            p90 = ("HEADWAY_MIN", lambda x: x.quantile(0.9)),
        )
    )

    return headway_summary