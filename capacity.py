import pandas as pd

def create_capacity(busstate_consolidated):
    '''
    Create capacity dataframe by combining University Hospital and Doan stops, then calculating capacity metrics for the dashboard.

    Args:
        busstate_consolidated (pd.DataFrame): The consolidated busstate dataframe.
    Returns:
        pd.DataFrame: A summary dataframe containing the capacity metrics for the medical center monthly dashboard.
    '''
    mc_rider = combine_uh_doan_stops(busstate_consolidated) # investigate this for werid results?
    # Investigate the  66+ passengers load 
    # mc_rider['LOAD'].describe()
    # mc_rider[mc_rider['LOAD'] > 64]

    mc_rider_combined_stop = mc_rider.loc[mc_rider['STOP_ID'] == 999].copy() 
    capacity_table = calculate_capacity_dashboard_metrics(mc_rider_combined_stop)

    return capacity_table

def combine_uh_doan_stops(df, max_gap_minutes = 5):
    # combine UH and Doan stops for capacity
    # Carmack -> UH is inbound, Doan -> Carmack is outbound
    # Treating UH and Doan as one stop.
    """
    Combine University Hospital and Doan stops into a single stop in the stop inventory for metrics.

    Args:
        df (DataFrame): The consolidated bus state DataFrame containing stop-level data.
        max_gap_minutes (int, optional): The maximum time gap in minutes between the UH and Doan stops to consider them as a pair. Defaults to 5 minutes.

    Returns:
        DataFrame: A DataFrame with University Hospital and Doan stops combined into a single stop with ID of 999.
    """
    df = df.copy()

    # will keep the original stop column for UH and Doan for reference, but assign a new combined stop - potential for debugging purposes
    # Assigning the number 999 for combined stop - no actual meaning for this and an unused stop number
    df['STOP_ORIGINAL'] = df['STOP_ID'] # keep original stop id for reference

    doan_stop_id = 37
    uh_stop_id = 401
 
    combined_id = 999 # completely arbitrary 

    max_gap = pd.Timedelta(minutes=max_gap_minutes)

    sort_cols = ['BUS_ID', 'DATE', 'RUN_ID', 'ARRIVAL', 'DEPARTURE']
    df = df.sort_values(sort_cols).reset_index(drop=True)

    combined_rows = []
    row_index = 0

    while row_index < len(df):
        current = df.iloc[row_index]

        if row_index < len(df) - 1:
            next_row = df.iloc[row_index + 1]

            # check if this is a UH->Doan pair within max_gap
            is_candidate_pair = (
                current['STOP_ID'] == uh_stop_id
                and next_row['STOP_ID'] == doan_stop_id
                and current['BUS_ID'] == next_row['BUS_ID']
                and current['DATE'] == next_row['DATE']
                and current['RUN_ID'] == next_row['RUN_ID']
                and pd.Timedelta(0) <= (next_row['ARRIVAL'] - current['DEPARTURE']) <= max_gap
            )

            if is_candidate_pair:
                merged = current.copy()
                merged['STOP_ID'] = combined_id
                merged['STOP_ORIGINAL'] = f"{uh_stop_id}_{doan_stop_id}"
                merged['BOARDINGS'] = current['BOARDINGS'] + next_row['BOARDINGS']
                merged['ALIGHTINGS'] = current['ALIGHTINGS'] + next_row['ALIGHTINGS']
                merged['LOAD'] = max(current['LOAD'], next_row['LOAD'])
                merged['DEPARTURE'] = next_row['DEPARTURE']
                merged['DWELL'] = merged['DEPARTURE'] - merged['ARRIVAL']
                merged['HOUR'] = merged['ARRIVAL'].hour
                merged['MINUTE'] = merged['ARRIVAL'].minute

                combined_rows.append(merged)
                row_index += 2  # skip next row because it was merged
                continue

        # if not merged, just add current
        combined_rows.append(current.copy())
        row_index += 1

    return pd.DataFrame(combined_rows).reset_index(drop=True)


#mc_rider = combine_uh_doan_stops(mc_busstate_consolidated)
def calculate_capacity_dashboard_metrics(busstate_df):
    '''
    Calculate capacity dashboard metrics for the given busstate dataframe.

    Args:
        busstate_df (pd.DataFrame): The busstate dataframe containing the bus events with combined UH and Doan stops.
    Returns:
        pd.DataFrame: A summary dataframe containing 
    '''
    # calculate the load based on max of boardings and alightings for each stop event
    mc_loads = busstate_df.copy()
    mc_loads['LOAD'] = mc_loads[['BOARDINGS', 'ALIGHTINGS']].max(axis=1)

    # NOTE: If an hourly view is desired, can edit this part
    # add time col with timeframes on the report
    mc_loads['TIME'] = mc_loads.apply(
        lambda row: 
            "5-6a" if row['HOUR'] <= 5 else
            "6-7a" if row['HOUR'] == 6 else
            "7-8a" if row['HOUR'] == 7 else
            "8a-2p" if 8 <= row['HOUR'] < 14 else
            "2-8p" if 14 <= row['HOUR'] < 20 else
            "8-10p" if 20 <= row['HOUR'] < 22 else
            "10p-12a" if row['HOUR'] >= 22 else np.nan,
        axis=1
    )

    # create size col based on load for each stop event - report metrics
    mc_loads['SIZE'] = mc_loads['LOAD'].apply(
        lambda load: "0-30 Passengers" if load <= 30 else
        "31-50 Passengers" if 30 < load <= 50 else
        "51-65 Passengers" if 50 < load <= 65 else
        "66+ Passengers" if load > 65 else None
    )

    print(mc_loads[mc_loads['SIZE'] == "66+ Passengers"]) 

    # create summary table for load size by time of day
    time_order = ['5-6a', '6-7a', '7-8a', '8a-2p', '2-8p', '8-10p', '10p-12a']

    # set time col as categorical with correct order for grouping and reporting
    mc_loads['TIME'] = pd.Categorical(
        mc_loads['TIME'],
        categories=time_order,
        ordered=True
    )

    # summarize the results
    load_summary = (
        mc_loads
        .groupby('TIME', observed=True)
        .agg(
            LOOPS=('SIZE', 'size'),
            p0_30=('SIZE', lambda x: (x == "0-30 Passengers").sum()),
            p31_50=('SIZE', lambda x: (x == "31-50 Passengers").sum()),
            p51_65=('SIZE', lambda x: (x == "51-65 Passengers").sum()),
            p66_plus=('SIZE', lambda x: (x == "66+ Passengers").sum()),
        )
        .reindex(time_order)
        .fillna(0)
        .reset_index()
        
        )
    return load_summary 
