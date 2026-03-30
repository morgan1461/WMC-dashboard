import pandas as pd
from pathlib import Path
import zipfile
import time
import os
import re

def busstate_processing(year, month, root_dir = "K:/AP/TTM/"):
    '''
    Process all busstate zip files in the data directory and save cleaned csv files to the repo directory

    Params:
        year (str): year of busstate data to process (e.g. "25") 
            NOTE: MUST BE IN 2 DIGIT FORMAT
        month (str): month of busstate data to process (e.g. "10") 
            NOTE: MUST BE IN 2 DIGIT FORMAT
        root_dir (str): root directory path - SHOULD ONLY NEED CHANGED IF ON UNIX SYSTEM

    Returns:
        None - saves cleaned csv files to repo directory "K:/AP/TTM/Data/WMC Dashboard/BusState Cleaned"
    '''
    #########################################3
    # Add input validation for year and month?
    ##########################################

    #timer
    start = time.perf_counter()
    print(f"Starting busstate processing for {month}/{year}...")

    data_dir = os.path.join(root_dir, "Data/APC Data") # contains zipped raw busstate txt files
    repo_dir = os.path.join(root_dir, "Data/WMC Dashboard/BusState Cleaned") # temp file to store cleaned data - change in future if necessary

    # Bustate naming convention is busstate0####DDMMYY.txt -> #### is unique 4 digit bus identifier
    # IF this ever changes in the future, change the regex pattern below to reflect new naming convention
    pattern = re.compile(rf"{year}{month}\d{{2}}\.txt\.zip$") # ending of files is YYMMDD.txt.zip

    # list comprehension to get list of all busstate files matching the year/month - will be zipped
    # takes about 30 seconds to run for 1 month of data
    busstates = [
        os.path.normpath(os.path.join(data_dir, f)) 
        for f in os.listdir(data_dir) 
        if pattern.search(f)]

    #print(busstates[:5]) 
    print(f"Found {len(busstates)} busstate files for {month}/{year} in '{data_dir}'")

    # empty dataframe to hold busstate data
    df = pd.DataFrame()

    print(f"Unzipping and processing busstate files for {month}/{year}...")
    # loop through each busstate file, unzip, process, and add to main dataframe
    # definitely a way to make this more performant - will revist later
    for busstate in busstates:
        raw_data = unzip_busstate_to_df(busstate)
        cleaned_data = process_busstate(raw_data)
        df = pd.concat([df, cleaned_data], ignore_index=True)

    print(f"Combined dataframe has {len(df)} records for {month}/{year}")
    # print(df.head())
    # print(df.info())

    # need to change year to 4 digit format got sort and save
    full_year = int("20" + year)
    # print(f"Full year is {full_year} and type is {type(full_year)}")

    # sort and save
    sort_and_save(df, repo_dir, full_year)

    end = time.perf_counter()
    print(f"Finished processing busstate data for {month}/{year} in {end - start:.2f} seconds. Cleaned files saved to '{repo_dir}'")

def unzip_busstate_to_df(zip_path):
    '''
    Unzip A SINGLE busstate zip file and return a pandas dataframe
    NOTE: This assumes ONE file in the zip, which is the case for all busstate zip files. If this ever changes, we will need to modify this function to handle multiple files in the zip.
    NOTE: The first row of the csv file contains data types, so we will drop that row and reset the index.

    Parameters:
        zip_path (str): Path to the busstate zip file

    Returns:
        pandas dataframe containing all busstate data from the zip file specified 

    
    '''
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        # Key assumption is there is only ONE file in the zip 
        file_name = zip_ref.namelist()[0]
        with zip_ref.open(file_name) as f:
            df = (pd.read_csv(f, sep=',', low_memory=False)) # Read all columns as string to avoid dtype issues - we will convert to correct dtypes later
            df = df.drop(df.index[0]).reset_index(drop=True) # DROP first row with "data types"
    return df

def process_busstate(df):
    '''
    Clean and process the busstate dataframe by:
    - Parsing datetime columns
    - Splitting EVENT_TIME into DATE + TIME
    - Keeping only time portion for other datetime columns
    - Converting numeric columns to numeric dtype
    - Creating BOARDINGS + ALIGHTINGS columns
    - Filtering EVENT_TYPE < 17
    - Selecting relevant columns
    - Filtering missing RUN_ID / DEST_SIGN_ROUTE_TEXT
    - Sorting by DATE + EVENT_TIME

    Parameters:
        df (pandas dataframe): Raw unzipped busstate dataframe

    Returns:
        pandas dataframe: Cleaned and processed busstate dataframe
    '''
    #print("BEFORE: ", df["EVENT_TIME"].head(10))

    # cols in YYMMDDhhmmss format
    datetime_cols = [
        "EVENT_TIME",
        "ENTER_STOP_WINDOW_TIME",
        "EXIT_STOP_WINDOW_TIME",
        "TRIP_START_TIME",
        "DEPARTURE_TIME"
    ]

    # convert to datetime,
    for col in datetime_cols:
        df[col] = pd.to_datetime(df[col], format="%y%m%d%H%M%S", errors="coerce")

    #print("AFTER: ", df["EVENT_TIME"].head(10))

    df["DATE"] = df["EVENT_TIME"].dt.date
    df["EVENT_TIME"] = df["EVENT_TIME"].dt.time

    # For the other datetime columns, we only care about the time portion, so we will keep only the time portion
    for col in datetime_cols[1:]:
        df[col] = df[col].dt.time

    # convert numerics from str
    numeric_cols = [
        "STOP_BACK_DOOR_ENTRY",
        "STOP_FRONT_DOOR_ENTRY",
        "STOP_FRONT_DOOR_EXIT",
        "STOP_BACK_DOOR_EXIT",
        "EVENT_TYPE"
    ]

    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # baordings and alightnings
    df["BOARDINGS"] = df["STOP_BACK_DOOR_ENTRY"] + df["STOP_FRONT_DOOR_ENTRY"]
    df["ALIGHTINGS"] = df["STOP_FRONT_DOOR_EXIT"] + df["STOP_BACK_DOOR_EXIT"]

    ##################################
    # not sure why this is BUT is in legacy R code so keeping for now - need to investigate later
    # comment stats this is extraneous event types that we don't care about -  will investigate later if we need to keep any of these event types
    df = df[df["EVENT_TYPE"] < 17]

    df = df[[
        "DATE", "BUS_ID", "RUN_ID", "DEST_SIGN_ROUTE_TEXT", "BLOCK_ID", "TRIP_ID",
        "ROUTE_ID", "STOP_SEQUENCE", "LATITUDE", "LONGITUDE",
        "HEADING", "OPERATOR_ID", "ODOMETER_DISTANCE", "TIMEPOINT_ID",
        "EVENT_TYPE", "EVENT_TIME", "BOARDINGS", "ALIGHTINGS", "PASSENGER_LOAD",
        "TRIP_START_TIME", "DEPARTURE_TIME", "ENTER_STOP_WINDOW_TIME", "EXIT_STOP_WINDOW_TIME"
    ]]

    # filter out missing run id and dest signs 
    df = df[(df["RUN_ID"].notna()) | (df["DEST_SIGN_ROUTE_TEXT"].notna())]

    # arrange based on date and time - also in legacy R code
    df = df.sort_values(by=["DATE", "EVENT_TIME"])

    return df

# Replicate the 'Sort and save function' save it into the repo directory
def sort_and_save(df, output_dir, year):
    """
    Save monthly busstate files - this will act weirdly if there is already existing data - will revisit later.

    Parameters:
        df (pd.DataFrame): cleaned busstate dataframe with 'DATE' column
        output_dir (str): folder path to save files - defaults to repo_dir
        year (int): year to filter - defaults to 2025 for future data, can change if needed
    """
    # hardcoded month names
    month_names = ["JAN","FEB","MAR","APR","MAY","JUN","JUL","AUG","SEP","OCT","NOV","DEC"]

    # ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)

    # ensure date column is datetime
    df['DATE'] = pd.to_datetime(df['DATE'])

    for month in range(1, 13):
        # Filter data for month/year
        month_df = df[(df['DATE'].dt.year == year) & (df['DATE'].dt.month == month)]

        # if no data for a month, skip saving and print message
        if month_df.empty:
            print(f"No data for month {month_names[month-1]} {year}")
            continue

        # sort by date and event time
        month_df = month_df.sort_values(by=['DATE', 'EVENT_TIME'])

        # filepath
        filepath = os.path.normpath(os.path.join(output_dir, f"{year}-{month_names[month-1]}-busstate.csv"))

        # save 
        month_df.to_csv(filepath, index=False)
        # output message
        print(f"Saved {len(month_df)} records for {month_names[month-1]} {year} to '{filepath}'")