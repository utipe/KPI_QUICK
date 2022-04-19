import base64
from webbrowser import get
import streamlit as st
import pandas as pd
import json
from datetime import datetime as dt, timedelta
from tqdm import tqdm
time_pattern = "%Y-%m-%d %H:%M:%S"

st.title('Extract Robot KPI')
fleet_order = st.file_uploader("Upload fleet_api_order_history.log", type="log", accept_multiple_files=False)
fleet_movement = st.file_uploader("Upload fleet_api_robot_movement.log", type="log", accept_multiple_files=False)

starting_date = st.date_input('Starting date', value=dt.now() - timedelta(days=1))
starting_time = st.time_input('Starting time', value=dt.now() - timedelta(hours=1))
starting_dt = f'{starting_date} {starting_time}'

ending_date = st.date_input('Ending date', value=dt.now() - timedelta(days=1))
ending_time = st.time_input('Ending time', value=dt.now() - timedelta(hours=1))
ending_dt = f'{ending_date} {ending_time}'

def get_delivery_time(starting_time, ending_time):
    starting_time = dt.strptime(starting_time, time_pattern)
    ending_time = dt.strptime(ending_time, time_pattern)
    timepoint = [starting_time]
    output = {"time":[]}
    checkpoint = starting_time + timedelta(hours=1)
    while checkpoint < ending_time:
        timepoint.append(checkpoint)
        output['time'].append(checkpoint.strftime(time_pattern))
        checkpoint += timedelta(hours=1)
    if fleet_order is not None:
        df = fleet_order.read().decode("utf-8")
        df = "[" + df.replace("\n",",")[:-1] + "]"
        df = json.loads(df)
        df = pd.DataFrame(df)
        df.datetime = [dt.strptime(i.split("+")[0].strip(),"%Y-%m-%d %H:%M:%S") for i in df. datetime]
        robot_list = list(df.uuid.unique())
        print(output)
        for robot in robot_list:
            robot_data = []
            for i in tqdm(range(1, len(timepoint))):
                df_temp = df[(df.uuid==robot) & (df.status=="assigning") & (df.datetime>=timepoint[i-1]) & (df.datetime<timepoint[i])]
                robot_data.append(df_temp.shape[0])
            print(robot_data)
            output[robot] = robot_data
        output = pd.DataFrame(output)
        return output

def get_running_ratio(starting_time, ending_time):
    starting_time = dt.strptime(starting_time, time_pattern)
    ending_time = dt.strptime(ending_time, time_pattern)
    output = {"datetime": [], "稼働":[], "待機":[]}
    if fleet_order is not None:
        df = fleet_order.read().decode("utf-8")
        df = "[" + df.replace("\n",",")[:-1] + "]"
        df = json.loads(df)
        df = pd.DataFrame(df)
        df.datetime = [dt.strptime(i.split("+")[0].strip(),"%Y-%m-%d %H:%M:%S") for i in df. datetime]
        robot_list = list(df.uuid.unique())
        # Determine the initial state of each robot
        robot_counter = [0 for _ in robot_list]
        for i in range(len(robot_list)):
            df_temp = df[(df.uuid==robot_list[i]) & (df.datetime<=starting_time)]
            if (df_temp.shape[0] == 0) or (df_temp.iloc[-1].status == "wait_assign"):
                robot_counter[i] = 0
            else:
                robot_counter[i] = 1
        # Iterate through each robot order
        df = df[(df.datetime>=starting_time) & (df.datetime<=ending_time)].reset_index()
        timepoint = starting_time
        for _, row in df.iterrows():
            if row['status'] != "wait_assign":
                robot_counter[robot_list.index(row['uuid'])] = 1
            else:
                robot_counter[robot_list.index(row['uuid'])] = 0
            work_ratio = int(sum(robot_counter)*100/len(robot_counter))
            idle_ratio = 100 - work_ratio
            while timepoint<=row["datetime"]:
                output["datetime"].append(timepoint.strftime(time_pattern))
                output["稼働"].append(work_ratio)
                output["待機"].append(idle_ratio)
                timepoint += timedelta(seconds=1)
        output = pd.DataFrame(output)
        return output

def get_delivery_distance(starting_time, ending_time):
    starting_time = dt.strptime(starting_time, time_pattern)
    ending_time = dt.strptime(ending_time, time_pattern)
    output = {"datetime": [], "シナリオ":[], "ロボット":[], "牽引あり時間(s)":[], "牽引なし時間(s)":[], "平均速度(/s)":[]}
    if fleet_order is not None:
        df = fleet_order.read().decode("utf-8")
        df = "[" + df.replace("\n",",")[:-1] + "]"
        df = json.loads(df)
        df = pd.DataFrame(df)
        df.datetime = [dt.strptime(i.split("+")[0].strip(),"%Y-%m-%d %H:%M:%S") for i in df.datetime]
        df = df[(df.datetime>=starting_time)].reset_index()
        if fleet_movement is not None:
            df_movement = fleet_movement.read().decode("utf-8")
            df_movement = "[" + df_movement.replace("\n",",")[:-1] + "]"
            df_movement = json.loads(df_movement)
            df_movement = pd.DataFrame(df_movement)
            df_movement.datetime = [dt.strptime(i.split("+")[0].strip(),"%Y-%m-%d %H:%M:%S") for i in df_movement.datetime]
            df_movement = df_movement[(df_movement.datetime>=starting_time)].reset_index()
            # Iterate through each preset
            timepoint = starting_time
            while (timepoint < ending_time):
                preset_start = df[(df.datetime>=timepoint) & (df.status=="assigning") & (pd.notna(df.preset_name))].reset_index()
                if (preset_start.shape[0]>0):
                    preset_start = preset_start.iloc[0]
                    preset_stop = df[(df.datetime>=preset_start.datetime) & (df.status=="wait_assign")].reset_index()
                    if (preset_stop.shape[0]>0):
                        preset_stop = preset_stop.iloc[0]
                        df_tow = df_movement[(df_movement.datetime>=preset_start.datetime) & (df_movement.datetime<=preset_stop.datetime)].reset_index()
                        df_tow["speed"] = [abs(i) for i in df_tow.linear_speed_x]
                        total_time = df_tow.shape[0]
                        total_towing_time = df_tow[df_tow.towing_status=="1"].shape[0]
                        average_speed = df_tow.speed.mean()
                        output["datetime"].append(preset_start.datetime.strftime(time_pattern))
                        output["シナリオ"].append(preset_start.preset_name)
                        output["ロボット"].append(preset_start.uuid)
                        output["牽引あり時間(s)"].append(total_towing_time)
                        output["牽引なし時間(s)"].append(total_time - total_towing_time)
                        output["平均速度(/s)"].append(average_speed)
                        timepoint = preset_stop.datetime
                    else:
                        timepoint = ending_time
                else:
                    timepoint = ending_time
            output = pd.DataFrame(output)
            return output


@st.cache
def convert_df(df):
   return df.to_csv().encode('utf-8')

if st.button("搬送回数"):
    check = get_delivery_time(starting_dt, ending_dt)
    st.dataframe(check)
    csv = convert_df(check)
    st.download_button(
        "Download CSV",
        csv,
        f'搬送回数-{starting_dt}-{ending_dt}.csv',
        "text/csv",
        key='download-csv'
        )

if st.button("稼働率"):
    check = get_running_ratio(starting_dt, ending_dt)
    st.dataframe(check)
    csv = convert_df(check)
    st.download_button(
        "Download CSV",
        csv,
        f'稼働率-{starting_dt}-{ending_dt}.csv',
        "text/csv",
        key='download-csv'
        )

if st.button("搬送距離・時間"):
    check = get_delivery_distance(starting_dt, ending_dt)
    st.dataframe(check)
    csv = convert_df(check)
    st.download_button(
        "Download CSV",
        csv,
        f'搬送距離・時間-{starting_dt}-{ending_dt}.csv',
        "text/csv",
        key='download-csv'
        )