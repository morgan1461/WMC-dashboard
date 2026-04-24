import pandas as pd
import numpy as np
import sys
import os

# Add modules directory to path
sys.path.append("modules")
try:
    from med_center_dashboard import which_stop
except ImportError as e:
    def which_stop(lat, lon): return 1 

file_path = "busstate_cleaned/2026-APR-busstate.csv"
if not os.path.exists(file_path):
    print(f"File not found: {file_path}")
    sys.exit(1)

# Columns to parse as time: EVENT_TIME, TRIP_START_TIME, DEPARTURE_TIME, ENTER_STOP_WINDOW_TIME, EXIT_STOP_WINDOW_TIME
chunks = pd.read_csv(file_path, chunksize=100000)
df_list = []
for chunk in chunks:
    filtered = chunk[(chunk["RUN_ID"] >= 1500) & (chunk["RUN_ID"] <= 1600)].copy()
    if not filtered.empty:
        df_list.append(filtered)

if not df_list:
    print("No rows found with RUN_ID 1500-1600")
    sys.exit(0)

df = pd.concat(df_list)

# Parse time columns
time_cols = ["EVENT_TIME", "TRIP_START_TIME", "DEPARTURE_TIME", "ENTER_STOP_WINDOW_TIME", "EXIT_STOP_WINDOW_TIME"]
for col in time_cols:
    if col in df.columns:
        df[col] = pd.to_datetime(df[col], errors="coerce")

df["DATE_PARSED"] = df["EVENT_TIME"].dt.date
df["STOP_ID"] = df.apply(lambda row: which_stop(row["LATITUDE"], row["LONGITUDE"]), axis=1)
df = df.dropna(subset=["STOP_ID"])
df = df[~df["STOP_ID"].isin([27, 461])]
df = df.sort_values(by=["BUS_ID", "DATE_PARSED", "EVENT_TIME"])

df["stop_change"] = df["STOP_ID"] != df["STOP_ID"].shift(1)
df["bus_change"] = df["BUS_ID"] != df["BUS_ID"].shift(1)
df["time_gap"] = (df["EVENT_TIME"] - df["EVENT_TIME"].shift(1)).dt.total_seconds() >= 3600

df["new_group"] = df["stop_change"] | df["bus_change"] | df["time_gap"]
df["COUNT"] = df["new_group"].cumsum()

group_cols = ["BUS_ID", "DATE_PARSED", "COUNT", "STOP_ID", "RUN_ID"]
grouped = df.groupby(group_cols)
multi_row = grouped.filter(lambda x: len(x) > 1)

if multi_row.empty:
    print("No multi-row groups found.")
    sys.exit(0)

multi_row_grouped = multi_row.groupby(group_cols)
num_multi_row_groups = multi_row_grouped.ngroups

stats = multi_row_grouped.agg({
    "BOARDINGS": ["sum", "max"],
    "ALIGHTINGS": ["sum", "max"]
})

board_diff = stats[("BOARDINGS", "sum")] != stats[("BOARDINGS", "max")]
alight_diff = stats[("ALIGHTINGS", "sum")] != stats[("ALIGHTINGS", "max")]

print(f"Number of multi-row groups: {num_multi_row_groups}")
print(f"Groups with board_sum != board_max: {board_diff.sum()}")
print(f"Groups with alight_sum != alight_max: {alight_diff.sum()}")

if board_diff.any():
    print(f"Median extra boardings (sum-max): {(stats[('BOARDINGS', 'sum')] - stats[('BOARDINGS', 'max')])[board_diff].median()}")
if alight_diff.any():
    print(f"Median extra alightings (sum-max): {(stats[('ALIGHTINGS', 'sum')] - stats[('ALIGHTINGS', 'max')])[alight_diff].median()}")

stats["total_diff"] = (stats[("BOARDINGS", "sum")] - stats[("BOARDINGS", "max")]) + (stats[("ALIGHTINGS", "sum")] - stats[("ALIGHTINGS", "max")])
worst_groups = stats.sort_values("total_diff", ascending=False).head(3)

print("\n3 Representative Worst-case Groups:")
for idx, row in worst_groups.iterrows():
    print(f"\nGroup {idx}:")
    detail = df[(df["BUS_ID"]==idx[0]) & (df["DATE_PARSED"]==idx[1]) & (df["COUNT"]==idx[2]) & (df["STOP_ID"]==idx[3]) & (df["RUN_ID"]==idx[4])][["EVENT_TIME", "BOARDINGS", "ALIGHTINGS"]]
    print(f"  Rows: {len(detail)}")
    print(f"  Boardings (Sum/Max): {row[('BOARDINGS', 'sum')]}/{row[('BOARDINGS', 'max')]}")
    print(f"  Alightings (Sum/Max): {row[('ALIGHTINGS', 'sum')]}/{row[('ALIGHTINGS', 'max')]}")
    print(detail.to_string(index=False))
