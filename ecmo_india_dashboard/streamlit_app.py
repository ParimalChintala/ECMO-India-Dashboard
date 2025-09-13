# streamlit_app.py — ECMO India Live Dashboard
# Place this file inside: ecmo_india_dashboard/

import os
from pathlib import Path
from urllib.parse import quote_plus

import pandas as pd
import streamlit as st

# ---------- Page setup ----------
st.set_page_config(page_title="ECMO India – Live Dashboard", layout="wide")

# ---------- Settings (change if you want) ----------
# If you publish a Google Sheet "to the web" as CSV, paste that URL in STREAMLIT secrets or env:
GSHEET_URL = os.environ.get("GSHEET_URL", "").strip()
# If using a local CSV in the repo, set/keep this file name (relative to THIS file's folder):
CSV_FILENAME = os.environ.get("CSV_PATH", "ecmo_cases.csv")
# Auto-refresh interval (seconds) for cached data:
REFRESH_SECONDS = int(os.environ.get("REFRESH_SECONDS", "60"))

# ---------- Data loader ----------
@st.cache_data(ttl=REFRESH_SECONDS)
def load_data(gsheet_url: str, csv_filename: str) -> pd.DataFrame:
    if gsheet_url:
        # Works if the sheet is published as CSV (no extra packages needed)
        df = pd.read_csv(gsheet_url)
    else:
        # Read from the CSV that lives in the SAME folder as this app
        base = Path(__file__).parent
        csv_path = Path(csv_filename)
        if not csv_path.is_absolute():
            csv_path = base / csv_path
        if not csv_path.exists():
            raise FileNotFoundError(f"CSV not found at: {csv_path}")
        df = pd.read_csv(csv_path)
    return df

# ---------- Safe Google Maps link builder ----------
def build_maps_link(hospital: str, city: str, state: str) -> str:
    q = " ".join(str(x) for x in [hospital, city, state] if str(x).strip())
    return f"https://www.google.com/maps/search/?api=1&query={quote_plus(q)}"

# ---------- App body ----------
st.title("🫀 ECMO India – Live Dashboard")

try:
    df = load_data(GSHEET_URL, CSV_FILENAME)
except Exception as e:
    st.error(
        "Could not load data. If you're using a CSV, make sure "
        f"`{CSV_FILENAME}` is inside the **ecmo_india_dashboard/** folder.\n\n"
        f"Error: {e}"
    )
    st.stop()

# Normalize expected columns (keep whatever the file has)
df.columns = [c.strip() for c in df.columns]

# If Google_Maps_Link column is missing, create it from Hospital + City + State
if "Google_Maps_Link" not in df.columns:
    # We will be liberal with column names to avoid key errors
    hospital_col = next((c for c in df.columns if c.lower() == "hospital"), None)
    city_col     = next((c for c in df.columns if c.lower() in ("location_city", "city")), None)
    state_col    = next((c for c in df.columns if c.lower() in ("location_state", "state")), None)

    if hospital_col and city_col and state_col:
        df["Google_Maps_Link"] = df.apply(
            lambda r: build_maps_link(r.get(hospital_col, ""), r.get(city_col, ""), r.get(state_col, "")),
            axis=1
        )

# Make a separate “Map” link column for reliable clickable links
if "Google_Maps_Link" in df.columns:
    df["Map"] = df["Google_Maps_Link"]

# Make Hospital name itself clickable if we have the link
if "Google_Maps_Link" in df.columns and "Hospital" in df.columns:
    df["Hospital"] = df.apply(
        lambda r: f"[{r['Hospital']}]({r['Google_Maps_Link']})" if pd.notna(r.get("Google_Maps_Link", "")) else r["Hospital"],
        axis=1
    )

# Choose columns to display (include Age if present)
default_cols = [
    c for c in ["Initiation_Date", "Hospital", "Location_City", "Location_State",
                "ECMO_Type", "Provisional_Diagnosis"] if c in df.columns
]
if "Age" in df.columns:
    default_cols.append("Age")
if "Map" in df.columns:
    default_cols.append("Map")

# If none of the expected columns exist, just show the whole frame
if not default_cols:
    default_cols = list(df.columns)

# ---------- Table ----------
st.dataframe(
    df[default_cols],
    use_container_width=True,
    column_config={
        # turns the Map column into clickable links with a label
        "Map": st.column_config.LinkColumn("Google Maps")
    }
)

# ---------- Controls ----------
col1, col2 = st.columns([1, 3])
with col1:
    if st.button("🔄 Reload data"):
        st.cache_data.clear()

st.caption(
    "Tip: Keep your CSV named **ecmo_cases.csv** inside the **ecmo_india_dashboard/** folder. "
    "If you add an **Age** column or **Google_Maps_Link**, they’ll appear automatically."
)
