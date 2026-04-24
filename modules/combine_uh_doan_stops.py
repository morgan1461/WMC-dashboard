"""
Notes from the 4/23/2026 notebook rebuild
-----------------------------------------
- The previous cluster-based combine logic was suspected to be causing unreliable
  downstream capacity and travel-time results.
- The notebook investigation rebuilt the pairing from scratch and narrowed the
  rule to a strict adjacent stop merge.
- The intended output should preserve the original dataframe schema while
  replacing valid University Hospital -> Doan pairs with one artificial stop
  record using STOP_ID 999.
- A valid pair is defined as:
    * current stop is 401 (UH)
    * next stop is 37 (Doan)
    * same BUS_ID, DATE, and RUN_ID when those fields are present
    * next stop occurs within max_gap_minutes of the UH stop
- Unmatched 37/401 rows are left in place by design. The notebook showed that
  some rows are non-adjacent or otherwise fail the pairing rule.
- An outbound-only filter was explored in the notebook, but the production
  dataframe passed into this module does not always include BOARDING_DIRECTIONS,
  so the module now operates directly on the input schema.
"""





# def _coerce_service_timestamp(date_series, arrival_series):
#     """Build a service timestamp from DATE and ARRIVAL without changing caller schema."""
#     date_str = date_series.astype(str)
#     arrival_str = arrival_series.astype(str).str.split().str[-1]

#     return pd.to_datetime(
#         date_str + " " + arrival_str,
#         format="%Y-%m-%d %H:%M:%S",
#         errors="coerce",
#     )


# def _merge_adjacent_hospital_pair(current, next_row, combined_stop_id):
#     """Create a merged 999 row while preserving the input row shape."""
#     merged = current.copy()
#     merged["STOP_ID"] = combined_stop_id

#     if "BOARDINGS" in merged.index:
#         merged["BOARDINGS"] = current["BOARDINGS"] + next_row["BOARDINGS"]
#     if "ALIGHTINGS" in merged.index:
#         merged["ALIGHTINGS"] = current["ALIGHTINGS"] + next_row["ALIGHTINGS"]
#     if "LOAD" in merged.index:
#         merged["LOAD"] = max(current["LOAD"], next_row["LOAD"])
#     if "DEPARTURE" in merged.index:
#         merged["DEPARTURE"] = next_row["DEPARTURE"]

#     if {"ARRIVAL", "DEPARTURE", "DWELL"}.issubset(merged.index):
#         arrival_ts = pd.to_datetime(str(merged["ARRIVAL"]), errors="coerce")
#         departure_ts = pd.to_datetime(str(merged["DEPARTURE"]), errors="coerce")
#         merged["DWELL"] = (
#             departure_ts - arrival_ts
#             if pd.notna(arrival_ts) and pd.notna(departure_ts)
#             else pd.NaT
#         )

#     if "ARRIVAL" in merged.index and "HOUR" in merged.index:
#         arrival_ts = pd.to_datetime(str(merged["ARRIVAL"]), errors="coerce")
#         if pd.notna(arrival_ts):
#             merged["HOUR"] = int(arrival_ts.hour)

#     if "ARRIVAL" in merged.index and "MINUTE" in merged.index:
#         arrival_ts = pd.to_datetime(str(merged["ARRIVAL"]), errors="coerce")
#         if pd.notna(arrival_ts):
#             merged["MINUTE"] = int(arrival_ts.minute)

#     return merged


# def combine_uh_doan_stops(df, max_gap_minutes=10, combined_stop_id=COMBINED_STOP_ID):
#     """
#     Combine adjacent University Hospital and Doan rows into one synthetic stop.

#     This is a strict adjacent-pair merge ported from the investigation notebook.
#     The returned dataframe preserves the caller's original columns and ordering
#     semantics as closely as possible, except that valid 401 -> 37 pairs are
#     replaced by one row whose STOP_ID is 999.

#     Args:
#         df (pd.DataFrame): Consolidated stop-level dataframe.
#         max_gap_minutes (int, optional): Maximum allowed gap between the UH row
#             and the following Doan row. Defaults to 5.
#         combined_stop_id (int, optional): Synthetic stop id used for merged
#             hospital pairs. Defaults to 999.

#     Returns:
#         pd.DataFrame: Copy of the input data with valid 401 -> 37 pairs merged.
#     """
#     if df.empty:
#         return df.copy()

#     work = df.copy()
#     work["_PAIR_TIME"] = _coerce_service_timestamp(work["DATE"], work["ARRIVAL"])
#     work = work.sort_values(by=["RUN_ID", "_PAIR_TIME"]).reset_index(drop=True)

#     combined_rows = []
#     max_gap = pd.Timedelta(minutes=max_gap_minutes)
#     index = 0

#     while index < len(work):
#         current = work.iloc[index]

#         if index + 1 >= len(work):
#             combined_rows.append(current.drop(labels="_PAIR_TIME").to_dict())
#             break

#         next_row = work.iloc[index + 1]

#         same_run = current["RUN_ID"] == next_row["RUN_ID"]
#         same_date = current["DATE"] == next_row["DATE"]
#         same_bus = (
#             current["BUS_ID"] == next_row["BUS_ID"]
#             if "BUS_ID" in work.columns
#             else True
#         )
#         in_order = current["STOP_ID"] == UH_STOP_ID and next_row["STOP_ID"] == DOAN_STOP_ID
#         gap = next_row["_PAIR_TIME"] - current["_PAIR_TIME"]
#         within_gap = pd.notna(gap) and pd.Timedelta(0) <= gap <= max_gap

#         if in_order and same_run and same_date and same_bus and within_gap:
#             merged = _merge_adjacent_hospital_pair(current, next_row, combined_stop_id)
#             combined_rows.append(merged.drop(labels="_PAIR_TIME").to_dict())
#             index += 2
#             continue

#         combined_rows.append(current.drop(labels="_PAIR_TIME").to_dict())
#         index += 1

#     return pd.DataFrame(combined_rows, columns=df.columns)

#----------------------------------------------------------------------

import pandas as pd

UH_STOP_ID = 401
DOAN_STOP_ID = 37
COMBINED_STOP_ID = 999

'''
NOTE: 4/23/2026 suspect that there is an issue with this function causing unreliable downstream results. 
Rebuilding the function from scratch to investigate.
'''
def combine_uh_doan_stops(df, max_gap_minutes=10, combined_stop_id=COMBINED_STOP_ID):
    """
    Combine adjacent University Hospital and Doan rows into one synthetic stop.

    This is a strict adjacent-pair merge ported from the investigation notebook.
    The returned dataframe preserves the caller's original columns and ordering
    semantics as closely as possible, except that valid 401 -> 37 pairs are
    replaced by one row whose STOP_ID is 999.

    Args:
        df (pd.DataFrame): Consolidated stop-level dataframe.
        max_gap_minutes (int, optional): Maximum allowed gap between the UH row
            and the following Doan row. Defaults to 5.
        combined_stop_id (int, optional): Synthetic stop id used for merged
            hospital pairs. Defaults to 999.

    Returns:
        pd.DataFrame: Copy of the input data with valid 401 -> 37 pairs merged.
    """
    # add inbound and outbound labels
    # inbound: Carmack stops
    # outbound: UH, Doan
    df['BOARDING_DIRECTIONS'] = df['STOP_ID'].apply(
        lambda x: 
        'IB' if x in [403, 404, 94, 95] 
        else 'OB' if x in [37, 401] # OB indicates the hospital stops
        else np.nan
    )

    # create a separate time variable to reduce chance of crossing midnight issues
    # df['TIME'] = pd.to_datetime(
    #     df['DATE'].astype(str) + ' ' + df['ARRIVAL'].astype(str),
    #     errors='coerce'
    # )
    date_base = pd.to_datetime(df['DATE'], errors='coerce').dt.normalize()

    arr = df['ARRIVAL']
    if pd.api.types.is_datetime64_any_dtype(arr):
        arr_dt = pd.to_datetime(arr, errors='coerce')
    else:
        arr_str = arr.astype(str).str.strip()
        arr_dt = pd.to_datetime(arr_str, format='%H:%M:%S', errors='coerce')
        mask = arr_dt.isna()
        arr_dt.loc[mask] = pd.to_datetime(arr_str.loc[mask], format='%H:%M', errors='coerce')
        mask = arr_dt.isna()
        arr_dt.loc[mask] = pd.to_datetime(arr_str.loc[mask], format='%I:%M:%S %p', errors='coerce')
        mask = arr_dt.isna()
        arr_dt.loc[mask] = pd.to_datetime(arr_str.loc[mask], format='%I:%M %p', errors='coerce')

    time_part = arr_dt - arr_dt.dt.normalize()
    df['TIME'] = date_base + time_part

    # df['TIME'] = pd.to_datetime(df['DATE']) + pd.to_timedelta(df['ARRIVAL'])
    # create a separate time variable to reduce chance of crossing midnight issues


    # loop through each run to identify adjacent UH and Doan stops and combine them
    pairing_stops = df.sort_values(by = ['RUN_ID', 'TIME']).copy() # sort by run, date, and arrival time to ensure correct sequence

    # subset to only OB stops
    # pairing_stops = pairing_stops[pairing_stops['BOARDING_DIRECTIONS'] == 'OB']
    # 12593 rows of OB stops -> should condense to about 6296 rows after combining

    # TROUBLESHOOTING
    # # walk rows in order and merge when stop_id is 37 or 401
    # # combine when stop order is 401 -> 37, arrival time is within 5 minutes, and same run_id and date
    # for i in range(len(pairing_stops) - 1):
    #     current_stop = pairing_stops.iloc[i] # current stop
    #     next_stop = pairing_stops.iloc[i + 1] # next stop by time

    #     if current_stop['STOP_ID'] == 401: # UH stop
            
    #         if next_stop['STOP_ID'] != 37: # Doan stop
    #             print(f"UH stop at index {i} not followed by Doan stop. Current stop time: {current_stop['TIME']}, Next stop time: {next_stop['TIME']}")

    # # 21 instances where there is a UH stop not followed by Doan stop.
    # walk rows in order and merge when stop_id is 37 or 401
    # combine when stop order is 401 -> 37, arrival time is within 5 minutes, and same run_id and date
    # for i in range(1, len(pairing_stops)):
    #     current_stop = pairing_stops.iloc[i] # current stop
    #     last_stop = pairing_stops.iloc[i - 1] # last stop by time

    #     if current_stop['STOP_ID'] == 37: 
            
    #         if last_stop['STOP_ID'] != 401: 
    #             sum += 1
    #             print(f"Doan stop at index {i} not preceded by UH stop. Current stop time: {current_stop['TIME']}, Last stop time: {last_stop['TIME']}")

    # # 154 instances where there is a Doan stop not preceded by UH stop.
    work = pairing_stops.sort_values(by=['RUN_ID', 'TIME']).reset_index(drop=True).copy()
    combined_rows = []
    i = 0

    while i < len(work):
        current = work.iloc[i]

        can_check_next = i + 1 < len(work)
        if not can_check_next:
            combined_rows.append(current.to_dict())
            break

        nxt = work.iloc[i + 1]

        same_run = current['RUN_ID'] == nxt['RUN_ID']
        same_date = current['DATE'] == nxt['DATE']
        same_bus = True if 'BUS_ID' not in work.columns else current['BUS_ID'] == nxt['BUS_ID']
        in_order = (current['STOP_ID'] == 401) and (nxt['STOP_ID'] == 37)
        gap = nxt['TIME'] - current['TIME']
        within_gap = pd.Timedelta(0) <= gap <= pd.Timedelta(minutes=max_gap_minutes)

        if in_order and same_run and same_date and same_bus and within_gap:
            merged = current.copy()
            merged['STOP_ID'] = combined_stop_id

            if 'BOARDINGS' in work.columns:
                merged['BOARDINGS'] = current['BOARDINGS'] + nxt['BOARDINGS']
            if 'ALIGHTINGS' in work.columns:
                merged['ALIGHTINGS'] = current['ALIGHTINGS'] + nxt['ALIGHTINGS']
            if 'LOAD' in work.columns:
                merged['LOAD'] = max(current['LOAD'], nxt['LOAD'])
            if 'DEPARTURE' in work.columns:
                merged['DEPARTURE'] = nxt['DEPARTURE']
            if 'DWELL' in work.columns and 'ARRIVAL' in work.columns and 'DEPARTURE' in work.columns:
                arr_ts = pd.to_datetime(str(merged['ARRIVAL']), errors='coerce')
                dep_ts = pd.to_datetime(str(merged['DEPARTURE']), errors='coerce')
                merged['DWELL'] = dep_ts - arr_ts if pd.notna(arr_ts) and pd.notna(dep_ts) else pd.NaT
            if 'HOUR' in work.columns and 'ARRIVAL' in work.columns:
                arr_ts = pd.to_datetime(str(merged['ARRIVAL']), errors='coerce')
                merged['HOUR'] = int(arr_ts.hour) if pd.notna(arr_ts) else merged.get('HOUR', np.nan)
            if 'MINUTE' in work.columns and 'ARRIVAL' in work.columns:
                arr_ts = pd.to_datetime(str(merged['ARRIVAL']), errors='coerce')
                merged['MINUTE'] = int(arr_ts.minute) if pd.notna(arr_ts) else merged.get('MINUTE', np.nan)

            combined_rows.append(merged.to_dict())
            i += 2
        else:
            combined_rows.append(current.to_dict())
            i += 1

    pairing_stops_combined = pd.DataFrame(combined_rows, columns=pairing_stops.columns)

    #---------------#
    # This may or may not screw up the analysis
    # reassign any leftover 37, 401 stops as 999
    # should only be about 1% of the OB stops
    pairing_stops_combined['STOP_ID'] = pairing_stops_combined['STOP_ID'].replace({37: 999, 401: 999})

    return pairing_stops_combined