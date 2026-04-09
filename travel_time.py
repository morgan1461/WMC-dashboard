import pandas as pd
import numpy as np
import combine_uh_doan_stops as combine

def create_travel_time(busstate_df):
    '''
    Calculate travel time dashboard metrics using the original Carmack 2 and Doan Hall stops.

    Args:
        busstate_df (pd.DataFrame): Original consolidated busstate data.

    Returns:
        pd.DataFrame: Travel time summary table with completed loop counts and average runtime by timeframe.
    '''
    # combine UH and Doan stops for travel time calculations
    busstate_df = combine.combine_uh_doan_stops(busstate_df)
    
    time_order = ['5:30-7a', '7-10a', '10a-4p', '4-7p', '7p-12a', '12-5a']
    stop_labels = {403: 'CARMACK 2', 999: 'UH/DOAN'}
    valid_legs = ['CARMACK 2 - UH/DOAN', 'UH/DOAN - CARMACK 2']
    completed_loop_leg = 'UH/DOAN - CARMACK 2'

    def assign_ridecheck_time(hour_value):
        if 5.5 <= hour_value < 7:
            return '5:30-7a'
        if 7 <= hour_value < 10:
            return '7-10a'
        if 10 <= hour_value < 16:
            return '10a-4p'
        if 16 <= hour_value < 19:
            return '4-7p'
        if hour_value >= 19:
            return '7p-12a'
        return '12-5a'

    mc_rt = busstate_df.loc[busstate_df['STOP_ID'].isin([403, 999])].copy()
    mc_rt = mc_rt.sort_values(['BUS_ID', 'DATE', 'RUN_ID', 'ARRIVAL']).reset_index(drop=True)

    same_trip = (
        (mc_rt['BUS_ID'] == mc_rt['BUS_ID'].shift(1))
        & (mc_rt['DATE'] == mc_rt['DATE'].shift(1))
        & (mc_rt['RUN_ID'] == mc_rt['RUN_ID'].shift(1))
    )

    mc_rt['RUN_TIME'] = np.where(
        same_trip,
        (mc_rt['ARRIVAL'] - mc_rt['DEPARTURE'].shift(1)).dt.total_seconds() / 60,
        np.nan
    )
    mc_rt['PREV_STOP_ID'] = mc_rt['STOP_ID'].shift(1)
    mc_rt['PREV_STOP_LABEL'] = mc_rt['PREV_STOP_ID'].map(stop_labels)
    mc_rt['STOP_LABEL'] = mc_rt['STOP_ID'].map(stop_labels)
    mc_rt['LEG'] = np.where(
        same_trip,
        mc_rt['PREV_STOP_LABEL'] + ' - ' + mc_rt['STOP_LABEL'],
        np.nan
    )
    mc_rt['HOUR_FLOAT'] = mc_rt['HOUR'] + (mc_rt['MINUTE'] / 60)
    mc_rt['TIME'] = mc_rt['HOUR_FLOAT'].apply(assign_ridecheck_time)

    mc_rt = mc_rt.loc[mc_rt['LEG'].isin(valid_legs)].copy()
    mc_rt = mc_rt.loc[(mc_rt['RUN_TIME'] >= 0) & (mc_rt['RUN_TIME'] < 20)].copy()

    loop_summary = (
        mc_rt.loc[mc_rt['LEG'] == completed_loop_leg]
        .groupby('TIME', as_index=False)
        .agg(LOOPS=('LEG', 'size'))
    )

    runtime_summary = (
        mc_rt
        .groupby(['TIME', 'LEG'], as_index=False)['RUN_TIME']
        .mean()
    )
    runtime_summary['RUN_TIME'] = runtime_summary['RUN_TIME'].round(1)
    runtime_summary = runtime_summary.pivot(index='TIME', columns='LEG', values='RUN_TIME').reset_index()

    travel_time_summary = loop_summary.merge(runtime_summary, how='left', on='TIME')
    travel_time_summary['TIME'] = pd.Categorical(
        travel_time_summary['TIME'],
        categories=time_order,
        ordered=True
    )
    travel_time_summary = travel_time_summary.sort_values('TIME').reset_index(drop=True)

    return travel_time_summary