# streamlit_app.py — ECMO India Live Dashboard (Google Sheets only)

from urllib.parse import quote_plus
import pandas as pd
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

# ---------------- Page setup ----------------
st.set_page_config(page_title="ECMO India – Live Dashboard", layout="wide")
st.title("🫀 ECMO India – Live Dashboard")

# ---------------- Your Google Sheet (hard-coded) ----------------
SHEET_ID = "19MGz1nP5k0B-by9dLE9LgA3BTuQ4FYn1cEAGklvZprE"   # <- from your URL
WORKSHEET_NAME = "Form_Responses"                           # <- purple tab name in your screenshot

# ---------------- Auth / loader ----------------
SCOPE = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

@st.cache_data(ttl=60)
def load_data_from_sheet(sheet_id: str, ws_name: str) -> pd.DataFrame:
    # authenticate using secrets you saved under [gcp_service_account]
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"], scopes=SCOPE
    )
    gc = gspread.authorize(creds)

    # open spreadsheet (404 here => wrong ID or not shared with service account)
    sh = gc.open_by_key(sheet_id)

    # open worksheet by name; show helpful error if wrong
    try:
        ws = sh.worksheet(ws_name)
    except gspread.exceptions.WorksheetNotFound:
        tabs = [(w.title, getattr(w, "id", None)) for w in sh.worksheets()]
        raise RuntimeError(
            f"Worksheet '{ws_name}' not found. Available tabs: {tabs}"
        )

    records = ws.get_all_records()
    return pd.DataFrame(records)

# ---------------- Helpers ----------------
def build_maps_link(hospital: str, city: str, state: str) -> str:
    parts = [str(x).strip() for x in [hospital, city, state] if str(x).strip()]
    return f"https://www.google.com/maps/search/?api=1&query={quote_plus(' '.join(parts))}"

# ---------------- Debug sidebar ----------------
with st.sidebar:
    st.header("Debug")
    sa_email = st.secrets["gcp_service_account"].get("client_email", "n/a")
    st.write("Service account:", sa_email)
    st.write("Sheet ID:", SHEET_ID)
    st.write("Worksheet:", WORKSHEET_NAME)
    if st.button("Clear cache"):
        st.cache_data.clear()
        st.success("Cache cleared")

# ---------------- Load data ----------------
try:
    df = load_data_from_sheet(SHEET_ID, WORKSHEET_NAME)
except Exception as e:
    st.error(
        "❌ Could not load data from Google Sheets.\n\n"
        f"Details: {e}\n\n"
        "Checklist:\n"
        "• This sheet is shared with the service account as **Editor**\n"
        "• SHEET_ID matches the part between /d/ and /edit in the URL\n"
        "• WORKSHEET_NAME matches the bottom tab name exactly"
    )
    st.stop()

# ---------------- Transform / display ----------------
# Clean headers
df.columns = [c.strip() for c in df.columns]

# Build Google_Maps_Link if missing and enough info is present
if "Google_Maps_Link" not in df.columns:
    hosp_col  = next((c for c in df.columns if c.lower() == "hospital"), None)
    city_col  = next((c for c in df.columns if c.lower() in ("location_city", "city")), None)
    state_col = next((c for c in df.columns if c.lower() in ("location_state", "state")), None)
    if hosp_col and city_col and state_col:
        df["Google_Maps_Link"] = df.apply(
            lambda r: build_maps_link(
                r.get(hosp_col, ""), r.get(city_col, ""), r.get(state_col, "")
            ),
            axis=1,
        )

# Optional Map link column
if "Google_Maps_Link" in df.columns:
    df["Map"] = df["Google_Maps_Link"]

# Make Hospital clickable when link available
if "Google_Maps_Link" in df.columns and "Hospital" in df.columns:
    df["Hospital"] = df.apply(
        lambda r: (
            f"[{r['Hospital']}]({r['Google_Maps_Link']})"
            if pd.notna(r.get("Google_Maps_Link", "")) and str(r["Google_Maps_Link"]).strip()
            else r["Hospital"]
        ),
        axis=1,
    )

# Columns to show (fall back to all if missing)
cols_pref = [
    "Initiation date",          # your sheet header appears like this in the screenshot
    "Hospital",
    "Location_City",
    "Location_State",
    "ECMO_Type",
    "Provisional Diagnos",      # adjust if your exact header differs
]
cols = [c for c in cols_pref if c in df.columns]
if "Age of the patient" in df.columns:
    cols.append("Age of the patient")
if "Map" in df.columns:
    cols.append("Map")
if not cols:
    cols = list(df.columns)

st.dataframe(
    df[cols],
    use_container_width=True,
    column_config={"Map": st.column_config.LinkColumn("Google Maps")},
)

# Reload button
col1, _ = st.columns([1, 4])
with col1:
    if st.button("🔄 Reload data"):
        st.cache_data.clear()

st.caption(
    "Data source: Google Sheet → tab 'Form_Responses'. "
    "Edit the sheet and click Reload (or wait ~60s cache)."
)
