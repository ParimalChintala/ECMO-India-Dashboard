# streamlit_app.py — ECMO India Live Dashboard
# Updated to load directly from Google Sheets via service account

from pathlib import Path
from urllib.parse import quote_plus
import pandas as pd
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

# ---------- Page setup ----------
st.set_page_config(page_title="ECMO India – Live Dashboard", layout="wide")

# ---------- Google Sheets connector ----------
SCOPE = ["https://www.googleapis.com/auth/spreadsheets",
         "https://www.googleapis.com/auth/drive"]

@st.cache_data(ttl=60)
def load_data() -> pd.DataFrame:
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"], scopes=SCOPE
    )
    gc = gspread.authorize(creds)

    # Open by sheet ID (recommended: safer than name)
    # Replace with your actual sheet ID from the URL:
    # https://docs.google.com/spreadsheets/d/<SHEET_ID>/edit
    sh = gc.open_by_key("YOUR_SHEET_ID_HERE")
    ws = sh.sheet1  # or use worksheet("Form Responses 1")
    data = ws.get_all_records()
    return pd.DataFrame(data)

# ---------- Safe Google Maps link builder ----------
def build_maps_link(hospital: str, city: str, state: str) -> str:
    parts = [str(x).strip() for x in [hospital, city, state] if str(x).strip()]
    return f"https://www.google.com/maps/search/?api=1&query={quote_plus(' '.join(parts))}"

# ---------- App body ----------
st.title("🫀 ECMO India – Live Dashboard")

try:
    df = load_data()
except Exception as e:
    st.error(
        "❌ Could not load data from Google Sheets. "
        "Make sure the service account has Editor access to your sheet.\n\n"
        f"Error: {e}"
    )
    st.stop()

# Clean headers
df.columns = [c.strip() for c in df.columns]

# Build Google_Maps_Link if missing
if "Google_Maps_Link" not in df.columns:
    hosp_col  = next((c for c in df.columns if c.lower() == "hospital"), None)
    city_col  = next((c for c in df.columns if c.lower() in ("location_city", "city")), None)
    state_col = next((c for c in df.columns if c.lower() in ("location_state", "state")), None)
    if hosp_col and city_col and state_col:
        df["Google_Maps_Link"] = df.apply(
            lambda r: build_maps_link(r.get(hosp_col, ""), r.get(city_col, ""), r.get(state_col, "")),
            axis=1
        )

# Optional Map link column
if "Google_Maps_Link" in df.columns:
    df["Map"] = df["Google_Maps_Link"]

# Make Hospital clickable when link available
if "Google_Maps_Link" in df.columns and "Hospital" in df.columns:
    df["Hospital"] = df.apply(
        lambda r: f"[{r['Hospital']}]({r['Google_Maps_Link']})"
        if pd.notna(r.get("Google_Maps_Link", "")) and str(r["Google_Maps_Link"]).strip()
        else r["Hospital"],
        axis=1
    )

# Columns to show
cols = [c for c in ["Initiation_Date","Hospital","Location_City","Location_State",
                    "ECMO_Type","Provisional_Diagnosis"] if c in df.columns]
if "Age" in df.columns:
    cols.append("Age")
if "Map" in df.columns:
    cols.append("Map")
if not cols:
    cols = list(df.columns)

# Table
st.dataframe(
    df[cols],
    use_container_width=True,
    column_config={"Map": st.column_config.LinkColumn("Google Maps")}
)

# Controls
col1, _ = st.columns([1, 4])
with col1:
    if st.button("🔄 Reload data"):
        st.cache_data.clear()

st.caption(
    "This dashboard now updates directly from the Google Sheet. "
    "Remove or edit rows in the sheet → changes reflect here after reload."
)
