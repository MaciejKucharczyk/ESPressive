import streamlit as st
from streamlit_autorefresh import st_autorefresh
import time
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

# unction to plot and adjust the chart title
def show_plot(value_list, chart_placeholder, title, y_label):
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
    ax.plot(value_list, marker='o', color='cyan', markersize=5)
    ax.set_ylim(bottom=10, top=90) # min & max value
    ax.set_title(title, color='white')
    ax.set_xlabel("Pomiar (co 30 min)", color='gray')
    ax.set_ylabel(y_label, color='gray')
    chart_placeholder.pyplot(fig, use_container_width=False)
    plt.close(fig) # close figure to avoid warning

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
        
        # Adding data to session state lists
        st.session_state.hum_list.append(hum)
        st.session_state.temp_list.append(temp_float)
        st.session_state.pressure_list.append(pressure) # pressure not used now
        
        st.session_state.hum_list = st.session_state.hum_list[-max_len:]
        st.session_state.temp_list = st.session_state.temp_list[-max_len:]
        st.session_state.pressure_list = st.session_state.pressure_list[-max_len:] 
    except Exception as e:
        status_placeholder.error(f"Błąd pobierania BME: {e}")
        temp_float, hum, pressure = 0.0, 0.0, 0.0
        temp_display = 0

    # choosable data based on selected page
    value_to_show = 0.0
    data_list = []
    label = "Brak danych"

    if page == "Odległość":
        try:
            value_raw, timestamp = get_message_distance(mqtt_topic_distance, mqtt_server)
            st.session_state.dist_list.append(value_raw)
            st.session_state.dist_list = st.session_state.dist_list[-max_len:]
            value_to_show = value_raw
            data_list = st.session_state.dist_list
            label = "Odległość [cm]"
        except Exception as e:
            status_placeholder.warning(f"Błąd pobierania Odległości: {e}")
            
    elif page == "Wilgotność":
        value_to_show = hum
        data_list = st.session_state.hum_list
        label = "Wilgotność [%]"
        
    elif page == "Temperatura":
        value_to_show = temp_display
        data_list = st.session_state.temp_list
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
        if data_list:
            plot_title = f"{page} (ostatnie 24h)"
            show_plot(data_list, st.empty(), plot_title, label)
        else:
            st.warning("Oczekiwanie na pierwsze dane z czujnika...")