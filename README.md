# Monthly Med Center Express Shuttle Dashboard

## Overview
This project generates montly dashboard metrics for The Ohio State University Wexner Medical Center Shuttle. This report is used for external reporting to the Ohio State University Department of Performance Excellence and the Medical Center. It processes raw Automatic Passenger Counter (APC) BusState files and produces three summary tables; headway, capacity, and travel time, as well as a total ridership number.

This code is adapted from a legacy R pipeline used in the OSU Department of Transportation and Traffic Management (TTM). This has been adapted and updated to reflect the current medical center route configuration.

**Author:** Clayton Morgan (Morgan.1461), Reporting and Analytics Analyst, OSU Transportation and Traffic Management

## Table of Contents

- [File Structure](#file-structure)
- [Prerequisites](#prerequisites)
- [Usage](#usage)
- [Module Descriptions](#module-descriptions)
- [Data Sources](#data-sources)
- [Output](#output)
- [Stop Reference](#stop-reference)
- [Known Issues and Notes](#known-issues-and-notes)

---

### File Structure
```
.
├── analysis_data/ # Archive of data used for targeted analysis
├── analysis_notebooks/ # Notebooks for targeted analysis
├── stops/
│   ├── pattern_stops.csv
│   └── stop_inventory.csv
├── busstate_cleaned/
│   └── YYYY-MMM-busstate.csv
├── dashboard_data/
│   ├── 2025/
│   ├── 2026/
│   │   └── MMM/
|   |       ├── 1-Headway-MMM-YYYY.csv
|   |       ├── 2-Capacity-MMM-YYYY.csv
|   |       ├── 3-TravelTime-MMM-YYYY.csv
│   │       └── TotalBoardings-MMM-YYYY.txt
│   └── Med Ctr Expr Dashboard - Template.xlsx
├── modules/
│   ├── busstate_processing.py
│   ├── headway.py
│   ├── capacity.py
│   ├── travel_time.py
│   ├── combine_uh_doan_stops.py
│   └── med_center_dashboard_metrics.py
├── busstate_processing_pipeline.ipynb
├── med_center_dashboard_metrics.ipynb
├── .gitignore
└── README.md
```

---

## Prerequisites

- Python 3.14+
- Network access to `K:/AP/TTM/` shared drive

---

## Usage

Processing is done in two sequential steps in two separate notebooks.

### Step 1 - Clean Raw BusState Files

Open `busstate_processing_pipeline.ipynb` and set the target year and month in the following format:

```python
year = "25"
month = "04"
```

This reads all matching zipped .txt raw BusState files from the APC Data directory, cleans, and processes them before saving a consolidated monthly .csv files to ./busstate_cleaned

**Expected runtime:**  ~3-5 minutes per month of data.

### Step 2 - Generate Dashboard Metrics

Open `med_center_dashboard_metrics.ipynb` and set the target year and month in the following format:

```python
year = "25"
month = "04"
```

This produces 3 .csv files and 1 .txt file in ./dashboard_data/YYYY/MMM/ that will be used to feed into the dashboard template.

**Expected runtime:**  ~3-5 minutes per month of data.

### Step 3 - Fill In Dashboard Template

The following month's template will be copied and used until December of each year.  

---

## Module Descriptions

### `busstate_processing.py`

Ingests raw compressed BusState .txt.zip files from the APC Data directory. Parses datetime fields, computes boardings and alightings, filters extraneous event types, and saves cleaned monthly .csv files. 

This module functions as a standalone busstate file processor. It is designed to be easily adapted and to be utilized in other future projects or workflows.

### `med_center_dashboard.py`
Main controller module. Filters cleaned busstate data to MC runs (`RUN_ID` 1500–1600), assigns geographic stop IDs via coordinate matching, consolidates repeated stop-visit events into single stop events, and orchestrates all downstream metric modules.

The `which_stop` module is designed to be reused in future projects or workflows. However, this does NOT account for the curvature of the earth in the distance calculations, and may need to be considered in future use cases.

This module's function will save a .txt file containing the sum of all boardings of the consolidated busstate med center dataframe.

### `headway.py`
Calculates the headway (time between bus arrivals) at Carmack 2 , Carmack 3 , University Hospital , and Doan Hall. Computes percent of headways meeting target thresholds and 50th/75th/90th percentile headway times by various time of day windows.

- MET is calculated by dividing the total number of target headways met against the total count of headways calculated in the specified timeframe.

### `capacity.py`
Filters to the combined UH/Doan stop and categorizes each loop by passenger load size in the following categories: 0–30, 31–50, 51–65, 66+. Produces a summary of loop counts by load category and time of day window.

- Capacity is calculated by taking the maximum total boardings or alightings across both the Unviersity Hospital and Doan Hall stops in a single trip.
- A bus with over 65 passengers is considered overcapacity.

### `travel_time.py`
Calculates run time in minutes for each leg between Carmack 2 and the combined UH/Doan stop. Summarizes completed loop counts and average run times by ridecheck time window.

- Inbound trip is considered the time from departure at Carmack 2 -> arrival at University Hospital
    - Note that the inbound trip includes stops at Carmack 3 and Carmack 5.
- Outbound trip is considered the time from departure at Doan Hall -> arrival at Carmack 2

### `combine_uh_doan_stops.py`
Helper module. Merges consecutive University Hospital and Doan Hall stops within a configurable time gap (default 5 minutes) into a single synthetic stop with ID 999. Used by both `capacity.py` and `travel_time.py`.

---

## Data Sources

| Source | Location | Notes |
|---|---|---|
| Raw BusState files | `K:/AP/TTM/Data/APC Data/` | Compressed `.txt.zip`, one file per bus per day, uploaded once per day |
| Pattern stops | `stops/pattern_stops.csv` | Maps routes to stop IDs; update when route changes |
| Stop inventory | `stops/stop_inventory.csv` | Stop IDs, names, lat/lon; update when stops change |

**BusState file naming convention:**
  ```
  busstate0####DDMMYY.txt.zip
  ```

  * `####` = bus identifier
  * `DD` = day
  * `MM` = month
  * `YY` = year (2-digit)

---

## Output

Three `.csv` files and one `.txt` file are written to `./dashboard_data_YYYY/MMM/` after each run:

| File | Contents |
|---|---|
| `1-Headway-MMM-YYYY.csv` | Percentage of headways met by target time, 50th, 75th, and 90th percentile headway times sorted by timeframe windows. |
| `2-Capacity-MMM-YYYY.csv` | Loop counts by passenger load category and sorted by timeframe windows. |
| `3-TravelTime-MMM-YYYY.csv` | Completed loops and average run time per leg and sorted by timeframe windows. |
| `TotalBoardings-MMM-YYYY.txt` | Number of total ridership for the specified month on the Medical Center shuttle.

  ---

  ## Stop Reference

| Stop ID | Name | Notes |
|---|---|---|
| 403 | Carmack 2 |  |
| 404 | Carmack 3 |  |
| 401 | University Hospital |  |
| 37 | Doan Hall |  |
| 999 | UH/Doan (combined) | Synthetic stop combining boardings/alightings, arrival at University Hospital, and departure from Doan Hall. Used for capacity and travel time calculations. |
| 27 | [Dummy stop] | Outbound designation, filtered out |
| 461 | [Dummy stop] | Inbound designation, filtered out |

  ---

## Known Issues and Notes

- **`pattern_stops.csv` and `stop_inventory.csv` are static files** and will need to be manually changed before running if there is a change to the MC route.
- **The BusState file** reading is based on regular expression, and this will need to be addressed if some runs are not being accounted for, or the naming convention changes.
- **The `sort_and_save` function in `busstate_processing.py` will overwrite existing monthly files** if re-run for the same month. Existing cleaned files are not appended to, ensure that busstate processing is run for the desired month directly before processing dashboard metrics.
- **If running on a Mac or Linux based operating system**, the root directories will need to be changed to reflect this.
- **Buses arriving after midnight** are adjusted to the previous calendar date and assigned `HOUR = 24` in headway calculations to maintain correct time grouping.