import pandas as pd


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


UH_STOP_ID = 401
DOAN_STOP_ID = 37
COMBINED_STOP_ID = 999


def _coerce_service_timestamp(date_series, arrival_series):
    """Build a service timestamp from DATE and ARRIVAL without changing caller schema."""
    date_str = date_series.astype(str)
    arrival_str = arrival_series.astype(str).str.split().str[-1]

    return pd.to_datetime(
        date_str + " " + arrival_str,
        format="%Y-%m-%d %H:%M:%S",
        errors="coerce",
    )


def _merge_adjacent_hospital_pair(current, next_row, combined_stop_id):
    """Create a merged 999 row while preserving the input row shape."""
    merged = current.copy()
    merged["STOP_ID"] = combined_stop_id

    if "BOARDINGS" in merged.index:
        merged["BOARDINGS"] = current["BOARDINGS"] + next_row["BOARDINGS"]
    if "ALIGHTINGS" in merged.index:
        merged["ALIGHTINGS"] = current["ALIGHTINGS"] + next_row["ALIGHTINGS"]
    if "LOAD" in merged.index:
        merged["LOAD"] = max(current["LOAD"], next_row["LOAD"])
    if "DEPARTURE" in merged.index:
        merged["DEPARTURE"] = next_row["DEPARTURE"]

    if {"ARRIVAL", "DEPARTURE", "DWELL"}.issubset(merged.index):
        arrival_ts = pd.to_datetime(str(merged["ARRIVAL"]), errors="coerce")
        departure_ts = pd.to_datetime(str(merged["DEPARTURE"]), errors="coerce")
        merged["DWELL"] = (
            departure_ts - arrival_ts
            if pd.notna(arrival_ts) and pd.notna(departure_ts)
            else pd.NaT
        )

    if "ARRIVAL" in merged.index and "HOUR" in merged.index:
        arrival_ts = pd.to_datetime(str(merged["ARRIVAL"]), errors="coerce")
        if pd.notna(arrival_ts):
            merged["HOUR"] = int(arrival_ts.hour)

    if "ARRIVAL" in merged.index and "MINUTE" in merged.index:
        arrival_ts = pd.to_datetime(str(merged["ARRIVAL"]), errors="coerce")
        if pd.notna(arrival_ts):
            merged["MINUTE"] = int(arrival_ts.minute)

    return merged


def combine_uh_doan_stops(df, max_gap_minutes=5, combined_stop_id=COMBINED_STOP_ID):
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
    if df.empty:
        return df.copy()

    work = df.copy()
    work["_PAIR_TIME"] = _coerce_service_timestamp(work["DATE"], work["ARRIVAL"])
    work = work.sort_values(by=["RUN_ID", "_PAIR_TIME"]).reset_index(drop=True)

    combined_rows = []
    max_gap = pd.Timedelta(minutes=max_gap_minutes)
    index = 0

    while index < len(work):
        current = work.iloc[index]

        if index + 1 >= len(work):
            combined_rows.append(current.drop(labels="_PAIR_TIME").to_dict())
            break

        next_row = work.iloc[index + 1]

        same_run = current["RUN_ID"] == next_row["RUN_ID"]
        same_date = current["DATE"] == next_row["DATE"]
        same_bus = (
            current["BUS_ID"] == next_row["BUS_ID"]
            if "BUS_ID" in work.columns
            else True
        )
        in_order = current["STOP_ID"] == UH_STOP_ID and next_row["STOP_ID"] == DOAN_STOP_ID
        gap = next_row["_PAIR_TIME"] - current["_PAIR_TIME"]
        within_gap = pd.notna(gap) and pd.Timedelta(0) <= gap <= max_gap

        if in_order and same_run and same_date and same_bus and within_gap:
            merged = _merge_adjacent_hospital_pair(current, next_row, combined_stop_id)
            combined_rows.append(merged.drop(labels="_PAIR_TIME").to_dict())
            index += 2
            continue

        combined_rows.append(current.drop(labels="_PAIR_TIME").to_dict())
        index += 1

    return pd.DataFrame(combined_rows, columns=df.columns)