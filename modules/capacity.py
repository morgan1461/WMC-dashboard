import pandas as pd
import numpy as np
from modules import combine_uh_doan_stops as combine

def create_capacity(busstate_consolidated):
    '''
    Create capacity dataframe by combining University Hospital and Doan stops, then calculating capacity metrics for the dashboard.

    Args:
        busstate_consolidated (pd.DataFrame): The consolidated busstate dataframe.
    Returns:
        pd.DataFrame: A summary dataframe containing the capacity metrics for the medical center monthly dashboard.
    '''
    mc_rider = combine.combine_uh_doan_stops(busstate_consolidated) # investigate this for werid results?

    # Legacy R logic excludes suspect 1705 events only when boardings or
    # alightings exceed 60 rather than dropping the bus entirely.
    mc_rider = mc_rider.loc[
        ~(
            (mc_rider['BUS_ID'] == 1705)
            & ((mc_rider['BOARDINGS'] > 60) | (mc_rider['ALIGHTINGS'] > 60))
        )
    ].copy()

    # print("="*50)
    # print((mc_rider['BOARDINGS'].max() >= 65) | (mc_rider['ALIGHTINGS'].max() >= 65)) # investigate this for werid results?
    # print("="*50)
    # Investigate the  66+ passengers load 
    # mc_rider['LOAD'].describe()
    # mc_rider[mc_rider['LOAD'] > 64]

    mc_rider_combined_stop = mc_rider.loc[mc_rider['STOP_ID'] == 999].copy() 
    capacity_table = calculate_capacity_dashboard_metrics(mc_rider_combined_stop)

    return capacity_table

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
            "5-6a" if row['HOUR'] == 5 else
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

    #print(mc_loads[mc_loads['SIZE'] == "66+ Passengers"]) 

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
