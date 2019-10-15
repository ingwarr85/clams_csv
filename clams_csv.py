#!/usr/bin/env python3

import pandas as pd
import numpy as np
import re
import glob
import sys
import datetime
import argparse
import os

# set default directory to current working directory
wd = os.getcwd()
input_filepath = wd
output_filepath = wd

# parse input and output arguments arguments
parser = argparse.ArgumentParser(description = "Concatenate CSV files from CLAMS to one file for analysis by clams-vis")

parser.add_argument('-i', '--input', help = "Path to input files")
parser.add_argument('-o', '--output', help = "Path where the output will be stored")
parser.add_argument('-f', '--format', help = "Format of the data", choices = ("classic", "tse"), default = "classic")
args = parser.parse_args()

if args.input:
    input_filepath = args.input

if args.output:
    output_filepath = args.output

table_format = args.format

# array to be populated with list of files
file_list = []

# find csv files to process or exit
for file in glob.glob(str(input_filepath)+"/*.[Cc][Ss][Vv]"):
    file_list.append(file)

if len(file_list) == 0:
    sys.exit("No CSV files to process")

# name of the columns in the csv file generated by CLAMS machine
column_names = ["Interval", "Date/Time", "Volume O2", "O2 In",	"O2 Out","Delta O2", "Accumulated O2",
                "Volume CO2", "CO2 In", "CO2 Out", "Delta CO2", "Accumulated CO2", "RER", "Heat", "Flow",
                "Feed Weight 1", "Feed Acc. 1", "Drink Weight 1",	"Drink Acc. 1", "X Total", "X Ambulatory", "Y Total",
                "Y Ambulatory", "Z Total", "Light/Dark"]

# data frame to be appended with individual animal data
data_frame_final = pd.DataFrame()

if table_format == "classic":
    # columns reordered to match the shinyapps utility
    use_columns = [0]+list(range(2,16))+list(range(17,26))+[31]

    # RE patterns to identify lines of interest in csv data
    subject_id_pattern = re.compile("Subject ID")
    start_data_pattern = re.compile(":DATA") # start of data header
    csv_file_pattern = re.compile("Oxymax CSV File") # animal file type
    events_pattern = re.compile(":EVENTS") # start of events

    # repeat for all csv files in file list
    for csv in file_list:

        subject_id = None
        start_data_line = None
        end_data_line = None
        csv_file_type = False

        events_line = None
        events = {}

        # variable will hold array of csv lines
        text = []

        # determine the line locations for RE patterns of interest and set corresponding line numbers
        with open(csv, "r") as file:
            text = file.read().splitlines()
            text = [line for line in text if len(line) > 0] # remove empty lines from csv file

            for i, line in enumerate(text):
                if re.match(csv_file_pattern, line):
                    csv_file_type = True
                if re.match(subject_id_pattern, line):
                    subject_id = line
                if re.match(start_data_pattern, line):
                    start_data_line = i+5  # might change in CLAMS system updates
                if re.match(events_pattern, line):
                    events_line = i+4 # might change in CLAMS system updates
                    end_data_line = i-1

        # skip if csv file is a parameter file not an animal file
        if csv_file_type == False:
            print("Skipping: "+csv+" - Not an animal data file")
            continue
        else:
            print("Processing: "+csv)

        # parse subject ID
        subject_id = subject_id.strip().split(',')[1]

        # split lines from array on comma
        records = [x.split(',') for x in text]
        # generate a numpy array that would converted to data frame
        data_records = np.array(records[start_data_line:end_data_line])

        # data frame of records
        data = pd.DataFrame(data_records)
        data = data.iloc[:,use_columns] # use only selected columns
        data.columns = column_names

        # reorder columns to match shinyapps utility specification
        cols = data.columns.tolist()
        cols = cols[:2]+cols[-1:]+cols[2:-1]
        data = data[cols]

        # match the date/time format of shiny_app
        data.loc[:,"Date/Time"] = pd.to_datetime(data.loc[:, "Date/Time"], infer_datetime_format = True)
        data.loc[:,"Date/Time"] = data.loc[:,"Date/Time"].dt.strftime("%m/%d/%Y %I:%M:%S %p")
        data.loc[:,"Date/Time"] = data.loc[:,"Date/Time"].astype(str)

        # rename Light/Dark phase to match shinyapps utility specification
        data.iloc[:,2].replace("ON", "Light", inplace = True)
        data.iloc[:,2].replace("OFF", "Dark", inplace = True)

        # insert subject ID column and Event Log column
        data.insert(loc = 0, column = "Subject", value = subject_id)
        data.insert(loc = len(data.columns), column = "Event Log", value = "") # starts as empty string

        # parse events from csv file
        event_records = np.array(records[events_line:])

        if len(event_records) > 0:
            # select Intervals and Description for data frame
            events = pd.DataFrame(event_records[:,[0,3]])
            events.columns = ["Interval", "Event Log"] # rename

            # convert intervals to numeric and set as index for merging to data dataframe
            events.Interval = events.Interval.apply(pd.to_numeric)
            events = events.set_index("Interval")

            # merge events to data dataframe keeping intervals without description as an empty string
            data.iloc[list(events.index), [-1]] = events["Event Log"]

        #TODO set float precision

        # append processed files to final data frame
        if data_frame_final.empty:
            data_frame_final = data
        else:
            data_frame_final = data_frame_final.append(data)



if table_format == "tse":
#
#    if len(file_list) > 2:
#        sys.exit("Too many csv files to process")
#    elif len(file_list) == 2:
#        if
#
    if len(file_list) > 1:
        sys.exit("Too many csv files to process")

    csv = file_list[0]

    tse_start_pattern = re.compile("Date,Time")
    use_columns = [2, 0, 6, 16, 8, 12, 14, 18, 19, 9, 13, 15, 21, 22, 23, 10, 44, 44, 43, 43, 27, 28, 30, 31, 33]
    tse_colnames = [column_names[i] for i in [1,-1] + list(range(2,len(column_names)-1))]
    tse_colnames = ["Subject"] + tse_colnames

    with open(csv, "r") as file:
        text = file.read().splitlines()
        text = [line for line in text if len(line) > 0]

        for i, line in enumerate(text):
            if re.match(tse_start_pattern, line):
                tse_start_line = i

    data = pd.read_csv(csv, skiprows = tse_start_line + 3, header = None, na_values = '-')

    print(data)

    data.drop(axis = 1, labels = 45, inplace = True)
    data = data.interpolate(axis = 0)

    data[0] = data[0].astype(str)
    data[1] = data[1].astype(str)
    data[0] = data[0] + " " + data[1]

    data = data[use_columns]
    data.columns = tse_colnames

    data.loc[:,"Date/Time"] = pd.to_datetime(data.loc[:, "Date/Time"], infer_datetime_format = True)
    data.loc[:,"Date/Time"] = data.loc[:,"Date/Time"].dt.strftime("%m/%d/%Y %I:%M:%S %p")
    data.loc[:,"Date/Time"] = data.loc[:,"Date/Time"].astype(str)

    data.loc[:,"Light/Dark"] = data.loc[:,"Light/Dark"].apply(lambda x: "Light" if x > 50 else "Dark")

    ser = []
    interval_count = list(data.groupby(["Subject"]).count()["Date/Time"])
    for x in interval_count:
        ser = ser + list(range(0,x))
    data.insert(1, "Interval", ser)

    data["Feed Weight 1"] = data.loc[:,"Feed Acc. 1"].diff()
    data["Drink Weight 1"] = data.loc[:,"Drink Acc. 1"].diff()

    data["Event_Log"] = ""

    data = data[data["Interval"] != 0]

    data_frame_final = data

print("Processing complete")

# export the final data frame
filename = str(datetime.date.today())+"_result_all.csv"
with open(str(output_filepath)+"/"+filename, "w") as file:
    data_frame_final.to_csv(file, index = False)

print("\n")
print("Results were saved to file: "+filename)
