# streamlit_app.py — ECMO India Live Dashboard (Sheets + charts, tolerant headers)

from urllib.parse import quote_plus
import pandas as pd
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import plotly.express as px

# ---------------- Page setup ----------------
st.set_page_config(page_title="ECMO India – Live Dashboard", layout="wide")
st.title("🫀 ECMO India – Live Dashboard")

# ---------------- Your Google Sheet ----------------
SHEET_ID = "19MGz1nP5k0B-by9dLE9LgA3BTuQ4FYn1cEAGklvZprE"   # spreadsheet id
WORKSHEET_NAME = "Form responses 1"                         # exact tab name

# ---------------- Auth / loader ----------------
SCOPE = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

def _dedupe_headers(headers: list[str]) -> list[str]:
    """If headers contain duplicates, append ' (2)', ' (3)', ... to later ones."""
    seen = {}
    result = []
    for h in headers:
        key = (h or "").strip()
        if key == "":
            key = "Unnamed"
        if key not in seen:
            seen[key] = 1
            result.append(key)
        else:
            seen[key] += 1
            result.append(f"{key} ({seen[key]})")
    return result

@st.cache_data(ttl=60)
def load_data_from_sheet(sheet_id: str, ws_name: str) -> pd.DataFrame:
    """Load a worksheet into a DataFrame, allowing duplicate headers safely."""
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"], scopes=SCOPE
    )
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(sheet_id)

    # Try exact tab name; if missing, fall back to first sheet with a notice
    try:
        ws = sh.worksheet(ws_name)
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.sheet1
        st.warning(
            f"Worksheet '{ws_name}' not found — using first tab: '{ws.title}'. "
            f"Available tabs: {[w.title for w in sh.worksheets()]}"
        )

    # Pull raw grid values; FIRST ROW = headers (may contain duplicates)
    values = ws.get_all_values() or []
    if not values:
        return pd.DataFrame()

    raw_headers = [h.strip() for h in values[0]]
    headers = _dedupe_headers(raw_headers)   # make them unique
    rows = values[1:]
    df = pd.DataFrame(rows, columns=headers)

    # strip surrounding whitespace in all column names
    df.columns = [c.strip() for c in df.columns]
    return df

# ---------------- Helpers ----------------
def build_maps_link(hospital: str, city: str, state: str) -> str:
    parts = [str(x).strip() for x in [hospital, city, state] if str(x).strip()]
    if not parts:
        return ""
    return f"https://www.google.com/maps/search/?api=1&query={quote_plus(' '.join(parts))}"

def first_nonempty(a, b):
    a_str = str(a).strip()
    b_str = str(b).strip()
    return a if a_str else (b if b_str else "")

# ---------------- Load + tidy data ----------------
try:
    df = load_data_from_sheet(SHEET_ID, WORKSHEET_NAME)
except Exception as e:
    st.error(
        "❌ Could not load data from Google Sheets.\n\n"
        f"Details: {e}\n\n"
        "Checklist:\n"
        "• Sheet is shared with the service account as **Editor**\n"
        "• SHEET_ID matches the part between /d/ and /edit\n"
        "• WORKSHEET_NAME matches the bottom tab name exactly"
    )
    st.stop()

# Map flexible column names
def pick(cols, *candidates):
    for c in candidates:
        if c in cols:
            return c
    return None

col_time   = pick(df.columns, "Timestamp")
col_hosp   = pick(df.columns, "Hospital")
col_city   = pick(df.columns, "Location City", "Location_City")
col_state  = pick(df.columns, "Location State", "Location_State")
col_ecmo   = pick(df.columns, "ECMO Type", "ECMO_Type")
col_diag   = pick(df.columns, "Provisional Diagnosis", "Provisional diagnos", "Provisional Diagnos")
col_age    = pick(df.columns, "Age of the patient", "Age")
col_senior = pick(df.columns, "Name of Senior intensivist supervising the procedure")
# handle duplicates coming from dedup (e.g., "Miscellaneous comments", "Miscellaneous comments (2)")
col_misc1  = pick(df.columns, "Miscellaneous comments", "Miscellaneous comments (1)")
col_misc2  = pick(df.columns, "Miscellaneous comments (2)")

# Combine Misc columns into one (prefer non-empty)
col_misc = None
if col_misc1 and col_misc2:
    df["Miscellaneous comments"] = df.apply(lambda r: first_nonempty(r[col_misc1], r[col_misc2]), axis=1)
    col_misc = "Miscellaneous comments"
elif col_misc1:
    col_misc = col_misc1
elif col_misc2:
    df.rename(columns={col_misc2: "Miscellaneous comments"}, inplace=True)
    col_misc = "Miscellaneous comments"

# Single Google Maps link
if col_hosp or col_city or col_state:
    df["Google Maps"] = df.apply(
        lambda r: build_maps_link(r.get(col_hosp, ""), r.get(col_city, ""), r.get(col_state, "")),
        axis=1,
    )

# Add 1-based serial number
df.insert(0, "S.No", range(1, len(df) + 1))

# Choose table columns (no email / initiation date)
table_cols = [
    "S.No", col_time, col_hosp, col_city, col_state, col_ecmo, col_diag,
    col_age, col_senior, col_misc, "Google Maps"
]
table_cols = [c for c in table_cols if c in df.columns or c == "S.No"]

# Show table
st.dataframe(
    df[table_cols],
    use_container_width=True,
    column_config={"Google Maps": st.column_config.LinkColumn("Google Maps")},
)

# Reload button
left, _ = st.columns([1, 6])
with left:
    if st.button("🔄 Reload data"):
        st.cache_data.clear()

# ---------------- Charts ----------------
st.markdown("---")
st.subheader("📊 Quick Visuals")

# Pie: ECMO Type
if col_ecmo and df[col_ecmo].notna().any():
    pie_df = (
        df[[col_ecmo]]
        .assign(**{col_ecmo: df[col_ecmo].fillna("Unknown").astype(str).str.strip()})
        .groupby(col_ecmo, dropna=False).size().reset_index(name="count")
        .sort_values("count", ascending=False)
    )
    fig_pie = px.pie(pie_df, names=col_ecmo, values="count", title="ECMO Type distribution", hole=0.3)
    st.plotly_chart(fig_pie, use_container_width=True)
else:
    st.info("No ECMO Type data to chart yet.")

# Bar: State-wise counts
if col_state and df[col_state].notna().any():
    bar_df = (
        df[[col_state]]
        .assign(**{col_state: df[col_state].fillna("Unknown").astype(str).str.strip()})
        .groupby(col_state, dropna=False).size().reset_index(name="count")
        .sort_values("count", ascending=False)
    )
    fig_bar = px.bar(bar_df, x="count", y=col_state, orientation="h", title="State-wise ECMO cases")
    fig_bar.update_layout(yaxis={"categoryorder": "total ascending"})
    st.plotly_chart(fig_bar, use_container_width=True)
else:
    st.info("No Location State data to chart yet.")
