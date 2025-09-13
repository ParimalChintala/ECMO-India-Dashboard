
import os, math
import pandas as pd
import streamlit as st
import plotly.express as px
from datetime import datetime, date

st.set_page_config(page_title="ECMO India - Live Dashboard", layout="wide")

# -------- Settings via env vars --------
DATA_SOURCE = os.environ.get("DATA_SOURCE", "csv")   # csv | gsheets
CSV_PATH = os.environ.get("CSV_PATH", "ecmo_cases_sample.csv")
GSHEET_URL = os.environ.get("GSHEET_URL", "")
REFRESH_SECONDS = int(os.environ.get("REFRESH_SECONDS", "60"))
USE_SERVICE_ACCOUNT = os.environ.get("USE_SERVICE_ACCOUNT", "false").lower()=="true"

REQUIRED_COLS = ["Initiation_Date","Hospital","Location_City","Location_State","ECMO_Type","Provisional_Diagnosis"]
OPTIONAL_COLS = ["Status","Latitude","Longitude"]

@st.cache_data(ttl=REFRESH_SECONDS)
def load_data():
    if DATA_SOURCE == "csv":
        return pd.read_csv(CSV_PATH)
    elif DATA_SOURCE == "gsheets":
        if USE_SERVICE_ACCOUNT:
            import gspread
            from google.oauth2.service_account import Credentials
            creds_dict = st.secrets["gcp_service_account"]
            creds = Credentials.from_service_account_info(creds_dict, scopes=[
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive.readonly",
            ])
            gc = gspread.authorize(creds)
            sh = gc.open_by_url(GSHEET_URL)
            ws_name = st.secrets.get("worksheet_name", "Sheet1")
            ws = sh.worksheet(ws_name)
            data = ws.get_all_records()
            return pd.DataFrame(data)
        else:
            if not GSHEET_URL:
                st.stop()
            return pd.read_csv(GSHEET_URL)
    else:
        st.error("Unknown DATA_SOURCE")
        st.stop()

df = load_data()

# Validate columns
missing = [c for c in REQUIRED_COLS if c not in df.columns]
if missing:
    st.error(f"Missing required columns: {missing}. Expected columns: {REQUIRED_COLS + OPTIONAL_COLS}")
    st.stop()

# Parse dates
if "Initiation_Date" in df.columns:
    try:
        df["Initiation_Date"] = pd.to_datetime(df["Initiation_Date"]).dt.date
    except Exception:
        pass

# Derived metric: Days on ECMO (for non-decannulated cases)
today = date.today()
df["Days_on_ECMO"] = (pd.to_datetime(today) - pd.to_datetime(df["Initiation_Date"])).dt.days

# Sidebar filters
st.sidebar.header("Filters")
state = st.sidebar.selectbox("State", ["All"] + sorted(df["Location_State"].dropna().unique().tolist()))
ecmo_type = st.sidebar.selectbox("ECMO Type", ["All"] + sorted(df["ECMO_Type"].dropna().unique().tolist()))
status_vals = ["All"] + sorted(df["Status"].dropna().unique().tolist()) if "Status" in df.columns else ["All"]
status = st.sidebar.selectbox("Status", status_vals)

q = df.copy()
if state != "All": q = q[q["Location_State"] == state]
if ecmo_type != "All": q = q[q["ECMO_Type"] == ecmo_type]
if "Status" in q.columns and status != "All": q = q[q["Status"] == status]

# KPI row
c1,c2,c3,c4 = st.columns(4)
with c1:
    st.metric("Total Cases (filtered)", len(q))
with c2:
    if "Status" in q.columns:
        active = (q["Status"] == "Active").sum()
        st.metric("Active", int(active))
    else:
        st.metric("Active", "—")
with c3:
    st.metric("Median Days on ECMO", int(q["Days_on_ECMO"].median()) if len(q) else 0)
with c4:
    by_type = q["ECMO_Type"].value_counts()
    vv = int(by_type.get("VV",0)); va = int(by_type.get("VA",0))
    st.metric("VV / VA", f"{vv} / {va}")

# Map (if lat/lon present)
if "Latitude" in q.columns and "Longitude" in q.columns and q[["Latitude","Longitude"]].dropna().shape[0] > 0:
    st.subheader("Geographic distribution")
    fig_map = px.scatter_mapbox(
        q.dropna(subset=["Latitude","Longitude"]),
        lat="Latitude", lon="Longitude",
        hover_name="Hospital",
        hover_data={"Location_City":True, "Location_State":True, "ECMO_Type":True, "Days_on_ECMO":True, "Latitude":False, "Longitude":False},
        color="ECMO_Type", zoom=4, height=450
    )
    fig_map.update_layout(mapbox_style="open-street-map", margin=dict(l=0,r=0,t=0,b=0))
    st.plotly_chart(fig_map, use_container_width=True)

# Charts
st.subheader("Cases by State and ECMO Type")
if len(q):
    fig1 = px.histogram(q, x="Location_State", color="ECMO_Type", barmode="group")
    st.plotly_chart(fig1, use_container_width=True)

    st.subheader("New ECMO Initiations Over Time")
    q_time = q.copy()
    if "Initiation_Date" in q_time.columns:
        q_time["Initiation_Date"] = pd.to_datetime(q_time["Initiation_Date"])
        ts = q_time.groupby(q_time["Initiation_Date"].dt.to_period("D")).size().reset_index(name="count")
        ts["Initiation_Date"] = ts["Initiation_Date"].dt.to_timestamp()
        fig2 = px.line(ts, x="Initiation_Date", y="count", markers=True)
        st.plotly_chart(fig2, use_container_width=True)

# Table
st.subheader("ECMO Cases (Filtered)")
display_cols = ["Initiation_Date","Hospital","Location_City","Location_State","ECMO_Type","Provisional_Diagnosis","Status","Days_on_ECMO"]
display_cols = [c for c in display_cols if c in q.columns]
st.dataframe(q[display_cols].sort_values(by="Initiation_Date", ascending=False), use_container_width=True)

st.caption("Data refresh every {}s. Expected columns: Initiation_Date, Hospital, Location_City, Location_State, ECMO_Type, Provisional_Diagnosis (optional: Status, Latitude, Longitude).".format(REFRESH_SECONDS))
