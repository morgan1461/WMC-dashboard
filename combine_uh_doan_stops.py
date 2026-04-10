import pandas as pd
import numpy as np

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
    # df = df.copy()
    # print("="*50)
    # print(f'Before combining: {len(df)}')
    # print(f'Unique stops before combining: {(df["STOP_ID"] == 401).sum()} UH, {(df["STOP_ID"] == 37).sum()} Doan')
    # print("="*50)

    # # will keep the original stop column for UH and Doan for reference, but assign a new combined stop - potential for debugging purposes
    # # Assigning the number 999 for combined stop - no actual meaning for this and an unused stop number
    # df['STOP_ORIGINAL'] = df['STOP_ID'] # keep original stop id for reference

    # doan_stop_id = 37
    # uh_stop_id = 401
 
    # combined_id = 999 # completely arbitrary 

    # max_gap = pd.Timedelta(minutes=max_gap_minutes)

    # sort_cols = ['BUS_ID', 'DATE', 'RUN_ID', 'ARRIVAL', 'DEPARTURE']
    # df = df.sort_values(sort_cols).reset_index(drop=True)

    # combined_rows = []
    # row_index = 0

    # while row_index < len(df):
    #     current = df.iloc[row_index]

    #     if row_index < len(df) - 1:
    #         next_row = df.iloc[row_index + 1]

    #         # check if this is a UH->Doan pair within max_gap
    #         is_candidate_pair = (
    #             current['STOP_ID'] == uh_stop_id
    #             and next_row['STOP_ID'] == doan_stop_id
    #             and current['BUS_ID'] == next_row['BUS_ID']
    #             and current['DATE'] == next_row['DATE']
    #             and current['RUN_ID'] == next_row['RUN_ID']
    #             and pd.Timedelta(0) <= (next_row['ARRIVAL'] - current['DEPARTURE']) <= max_gap
    #         )

    #         if is_candidate_pair:
    #             merged = current.copy()
    #             merged['STOP_ID'] = combined_id
    #             merged['STOP_ORIGINAL'] = f"{uh_stop_id}_{doan_stop_id}"
    #             merged['BOARDINGS'] = current['BOARDINGS'] + next_row['BOARDINGS']
    #             merged['ALIGHTINGS'] = current['ALIGHTINGS'] + next_row['ALIGHTINGS']
    #             merged['LOAD'] = max(current['LOAD'], next_row['LOAD'])
    #             merged['DEPARTURE'] = next_row['DEPARTURE']
    #             merged['DWELL'] = merged['DEPARTURE'] - merged['ARRIVAL']
    #             merged['HOUR'] = merged['ARRIVAL'].hour
    #             merged['MINUTE'] = merged['ARRIVAL'].minute

    #             combined_rows.append(merged)
    #             row_index += 2  # skip next row because it was merged
    #             continue

    #     # if not merged, just add current
    #     combined_rows.append(current.copy())
    #     row_index += 1

    # combined_df = pd.DataFrame(combined_rows).reset_index(drop=True)

    # print("="*50)
    # print(f'After combining: {len(combined_df)}')
    # print(f'Unique stops after combining: {(combined_df["STOP_ID"] == 999).sum()} UH/Doan, {(combined_df["STOP_ID"] == 401).sum()} UH, {(combined_df["STOP_ID"] == 37).sum()} Doan')
    # combined_df[combined_df['STOP_ID'] == 401][['BUS_ID', 'DATE', 'RUN_ID', 'ARRIVAL', 'DEPARTURE', 'BOARDINGS', 'ALIGHTINGS', 'LOAD', 'DWELL']].to_csv('uh_stop_sample.csv', index=False)
    # combined_df[combined_df['STOP_ID'] == 37][['BUS_ID', 'DATE', 'RUN_ID', 'ARRIVAL', 'DEPARTURE', 'BOARDINGS', 'ALIGHTINGS', 'LOAD', 'DWELL']].to_csv('doan_stop_sample.csv', index=False)
    # print("="*50)
    

    # # debugging 
    # # ---------------------------
    # # Debug: show unmerged UH / Doan with context
    # # ---------------------------
    # debug_indices = combined_df[
    #     (combined_df['STOP_ID'].isin([uh_stop_id, doan_stop_id]))
    # ].index

    # print("\n" + "="*80)
    # print("DEBUG: Unmerged UH / Doan Stops with Context")
    # print("="*80)

    # window = 5

    # for idx in debug_indices[:20]:  # limit to first 20 cases to avoid huge output
    #     start = max(idx - window, 0)
    #     end = min(idx + window + 1, len(combined_df))

    #     print("\n" + "-"*60)
    #     print(f"Context around index {idx} (STOP_ID={combined_df.loc[idx, 'STOP_ID']})")
    #     print("-"*60)

    #     context_df = combined_df.iloc[start:end][[
    #         'BUS_ID', 'DATE', 'RUN_ID', 'STOP_ID',
    #         'ARRIVAL', 'DEPARTURE',
    #         'BOARDINGS', 'ALIGHTINGS', 'LOAD'
    #     ]]

    #     print(context_df.to_string(index=True))

    # return combined_df
    df = df.copy()
    # print("="*50)
    # print(f'Before combining: {len(df)}')
    # print(f'Unique stops before combining: {(df["STOP_ID"] == 401).sum()} UH, {(df["STOP_ID"] == 37).sum()} Doan')
    # print("="*50)

    doan_stop_id = 37
    uh_stop_id = 401
    combined_id = 999

    max_gap = pd.Timedelta(minutes=max_gap_minutes)

    df['STOP_ORIGINAL'] = df['STOP_ID']

    sort_cols = ['BUS_ID', 'DATE', 'RUN_ID', 'ARRIVAL']
    df = df.sort_values(sort_cols).reset_index(drop=True)

    combined_rows = []

    group_cols = ['BUS_ID', 'DATE', 'RUN_ID']

    for _, group in df.groupby(group_cols):
        group = group.sort_values('ARRIVAL').reset_index(drop=True)

        i = 0
        while i < len(group):

            current = group.iloc[i]

            # Only start clustering if it's UH or Doan
            if current['STOP_ID'] not in [uh_stop_id, doan_stop_id]:
                combined_rows.append(current.copy())
                i += 1
                continue

            # Start cluster
            cluster = [current]
            j = i + 1

            while j < len(group):
                next_row = group.iloc[j]

                time_gap = next_row['ARRIVAL'] - cluster[-1]['DEPARTURE']

                if (
                    next_row['STOP_ID'] in [uh_stop_id, doan_stop_id]
                    and pd.Timedelta(0) <= time_gap <= max_gap
                ):
                    cluster.append(next_row)
                    j += 1
                else:
                    break

            # If cluster has more than 1 row → merge
            if len(cluster) > 1:
                merged = cluster[0].copy()

                merged['STOP_ID'] = combined_id
                merged['STOP_ORIGINAL'] = "_".join(str(r['STOP_ID']) for r in cluster)

                merged['BOARDINGS'] = sum(r['BOARDINGS'] for r in cluster)
                merged['ALIGHTINGS'] = sum(r['ALIGHTINGS'] for r in cluster)
                merged['LOAD'] = max(r['LOAD'] for r in cluster)

                merged['DEPARTURE'] = cluster[-1]['DEPARTURE']
                merged['DWELL'] = merged['DEPARTURE'] - merged['ARRIVAL']

                merged['HOUR'] = merged['ARRIVAL'].hour
                merged['MINUTE'] = merged['ARRIVAL'].minute

                combined_rows.append(merged)

            else:
                combined_rows.append(current.copy())

            i = j  # jump past cluster

    combined_df = pd.DataFrame(combined_rows).reset_index(drop=True)
    # print("="*50)
    # print(f'After combining: {len(combined_df)}')
    # print(f'Unique stops after combining: {(combined_df["STOP_ID"] == 999).sum()} UH/Doan, {(combined_df["STOP_ID"] == 401).sum()} UH, {(combined_df["STOP_ID"] == 37).sum()} Doan')
    # combined_df[combined_df['STOP_ID'] == 401][['BUS_ID', 'DATE', 'RUN_ID', 'ARRIVAL', 'DEPARTURE', 'BOARDINGS', 'ALIGHTINGS', 'LOAD', 'DWELL']].to_csv('uh_stop_sample.csv', index=False)
    # combined_df[combined_df['STOP_ID'] == 37][['BUS_ID', 'DATE', 'RUN_ID', 'ARRIVAL', 'DEPARTURE', 'BOARDINGS', 'ALIGHTINGS', 'LOAD', 'DWELL']].to_csv('doan_stop_sample.csv', index=False)
    # print("="*50)

    return combined_df