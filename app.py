import streamlit as st
from streamlit_autorefresh import st_autorefresh
import toml
import paho.mqtt.client as mqtt
import paho.mqtt.subscribe as subscribe
import re
import matplotlib.pyplot as plt
import datetime 
import matplotlib.dates as mdates

from client import get_message_distance, get_message_bme

config = toml.load(".streamlit/secrets.toml")
mqtt_server = config["mqtt"]["broker"]
mqtt_topic_distance = config["mqtt"]["topic_distance"]
mqtt_topic_bme = config["mqtt"]["topic_bme"]

refresh_interval_ms = 30 * 60000
count = st_autorefresh(interval=refresh_interval_ms, limit=None, key="bme_refresh")

max_len = 50 # max lenght of data list

json_path = "data/data.json"

if 'dist_list' not in st.session_state:
    st.session_state.dist_list = []
    
if 'temp_list' not in st.session_state:
    st.session_state.temp_list = []
    
if 'hum_list' not in st.session_state:
    st.session_state.hum_list = []
    
if 'pressure_list' not in st.session_state:
    st.session_state.pressure_list = []
    
# ---------------------------------------------------------------------------

# UI
# ---------------------------------------------------------------------------
# Page config

# function to plot and adjust the chart title
def show_plot(json_path, chart_placeholder, title, y_label):
    data_points = load_json(json_path, title)
    
    timestamps_str = [item[0] for item in data_points]
    values = [item[1] for item in data_points]
    
    date_format = "%Y-%m-%d %H:%M:%S" 
    try:
        timestamps_dt = [datetime.datetime.strptime(ts, date_format) for ts in timestamps_str]
    except (ValueError, TypeError):
        # Use original strings if parsing fails
        timestamps_dt = timestamps_str
    
    fig, ax = plt.subplots(figsize=(4,2))
    fig.patch.set_facecolor("#262f40")
    
    ax.set_facecolor("#0e1117")
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    ax.tick_params(axis='x', colors='gray')
    ax.tick_params(axis='y', colors='gray')
    ax.spines['bottom'].set_color('gray')
    ax.spines['left'].set_color('gray')
    ax.spines['top'].set_color('gray')
    ax.spines['right'].set_color('gray')
    
    ax.plot(timestamps_dt, values, marker='o', color='cyan', markersize=5)
    fig.autofmt_xdate()
    
    if y_label == "Temperatura [℃]":
        ax.set_ylim(bottom=10, top=35) # min & max value
        ax.axhspan(22, 28, facecolor="green", alpha=0.35)
    elif y_label == "Ciśnienie [hPa]":
        ax.set_ylim(bottom=900, top=1100) # min & max value
    elif y_label == "Wilgotność [%]":   
        ax.set_ylim(bottom=40, top=100) # min & max value
        ax.axhspan(60, 80, facecolor="green", alpha=0.35)
    
    
    ax.set_title(title, color='white')
    ax.set_xlabel("godzina", color='gray')
    ax.set_ylabel(y_label, color='gray')
    
    chart_placeholder.pyplot(fig, use_container_width=False)
    plt.close(fig) # close figure to avoid warning
    
    
def load_json(json_path, title):
    try:
        import json
        with open(json_path, "r") as f:
            data = json.load(f)
        
        timestamps = [item["timestamp"] for item in data]
        values = []
        
        if "Temperatura" in title:
            values = [item["temperature"] for item in data]
        elif "Wilgotność" in title:
            values = [item["humidity"] for item in data]
        elif "Ciśnienie" in title:
            values = [item["pressure"] for item in data]
        
        data_points = list(zip(timestamps, values))
        return data_points
        
    except Exception as e:
        st.error(f"Błąd podczas rysowania wykresu: {e}")

st.set_page_config(page_title="Sensor Dashboard", layout="wide")

# -----------------------------
# Sidebar
# -----------------------------
with st.sidebar:
    st.title("Czujniki")
    menu = ["Odległość", "Wilgotność", "Temperatura"]
    icons = ["📏", "💧", "🌡️"]

    # Adding mechanism to maintain page selection in session state
    if 'current_page' not in st.session_state:
        st.session_state.current_page = None
    
    page = st.session_state.current_page
    for i, item in enumerate(menu):
        if st.button(f"{icons[i]} {item}", key=i):
            st.session_state.current_page = item
            page = item 
    status_placeholder = st.empty()


# -------------------------------------------------------
# Main page
# -------------------------------------------------------
if page is None:
    st.info("Wybierz czujnik z menu po lewej")
else:
    # Widget
    st.header(f"{icons[menu.index(page)]} {page}")
    # Placeholders and columns
    left, right = st.columns([1,2])
    
    # Download data from MQTT
    try:
        temp_float, hum, pressure, timestamp = get_message_bme(mqtt_topic_bme, mqtt_server)
        temp_display = int(temp_float) 
        
    except Exception as e:
        status_placeholder.error(f"Błąd pobierania BME: {e}")
        temp_float, hum, pressure = 0.0, 0.0, 0.0
        temp_display = 0

    # choosable data based on selected page
    value_to_show = 0.0
    label = "Brak danych"

    if page == "Odległość":
        try:
            value_raw, timestamp = get_message_distance(mqtt_topic_distance, mqtt_server)
            value_to_show = value_raw
            data_list = st.session_state.dist_list
            label = "Odległość [cm]"
        except Exception as e:
            status_placeholder.warning(f"Błąd pobierania Odległości: {e}")
            
    elif page == "Wilgotność":
        value_to_show = hum
        label = "Wilgotność [%]"
        
    elif page == "Temperatura":
        value_to_show = temp_display
        label = "Temperatura [℃]"

    with left:
        # formatting
        if page == "Temperatura":
            value_display_str = f"{value_to_show} ℃"
        elif page == "Wilgotność":
            value_display_str = f"{value_to_show:.2f} %"
        elif page == "Odległość":
            value_display_str = f"{value_to_show:.2f} cm"
        else:
            value_display_str = "Brak danych"
            
        # print value as H1
        st.markdown(f"# {value_display_str}")
        
        # label
        st.caption(label)
        
    with right:
        # plot figure
        plot_title = f"{page} (ostatnie 24h)"
        show_plot(json_path, st.empty(), plot_title, label)