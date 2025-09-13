# streamlit_app.py — ECMO India Live Dashboard
# Keep this file and ecmo_cases.csv in the SAME folder: ecmo_india_dashboard/

from pathlib import Path
from urllib.parse import quote_plus
import pandas as pd
import streamlit as st
import os

# ---------- Page setup ----------
st.set_page_config(page_title="ECMO India – Live Dashboard", layout="wide")

# If you publish a Google Sheet "to the web" as CSV, put its URL in GSHEET_URL (optional)
GSHEET_URL = os.environ.get("GSHEET_URL", "").strip()

# ---------- Data loader ----------
@st.cache_data(ttl=60)
def load_data() -> pd.DataFrame:
    if GSHEET_URL:
        # Load directly from a published-to-web Google Sheet CSV URL
        return pd.read_csv(GSHEET_URL)

    # Always read the CSV that lives next to this script
    csv_path = Path(__file__).parent / "ecmo_cases.csv"
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV not found at: {csv_path}")
    return pd.read_csv(csv_path)

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
        "Could not load data. Ensure **ecmo_cases.csv** is inside the "
        "**ecmo_india_dashboard/** folder (same folder as this app).\n\n"
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
    "Tip: Keep **ecmo_cases.csv** in the **ecmo_india_dashboard/** folder. "
    "If you add **Age** or **Google_Maps_Link**, they’ll show automatically."
)
