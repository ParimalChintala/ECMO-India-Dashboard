# streamlit_app.py — ECMO India Live Dashboard
# (robust headers + diagnostics + S.No + Misc + state-wise pie chart)

from urllib.parse import quote_plus
import pandas as pd
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

# ---------------- Page setup ----------------
st.set_page_config(page_title="ECMO India – Live Dashboard", layout="wide")
st.title("🫀 ECMO India – Live Dashboard")

# ---------------- Your Google Sheet ----------------
SHEET_ID = "19MGz1nP5k0B-by9dLE9LgA3BTuQ4FYn1cEAGklvZprE"   # from your URL
WORKSHEET_NAME = "Form responses 1"                          # bottom tab name (case/space sensitive)

# ---------------- Auth / loader ----------------
SCOPE = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

@st.cache_data(ttl=60)
def load_data_from_sheet(sheet_id: str, ws_name: str) -> pd.DataFrame:
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"], scopes=SCOPE
    )
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(sheet_id)

    try:
        ws = sh.worksheet(ws_name)
    except gspread.exceptions.WorksheetNotFound:
        tabs = [(w.title, getattr(w, "id", None)) for w in sh.worksheets()]
        if tabs:
            ws = sh.sheet1
            st.warning(
                f"Worksheet '{ws_name}' not found — using first tab: '{ws.title}'. "
                f"Available tabs: {tabs}"
            )
        else:
            raise RuntimeError("This spreadsheet has no worksheets.")

    records = ws.get_all_records()
    if not records:
        headers = ws.row_values(1) or []
        # Empty DF with headers so the table still renders
        return pd.DataFrame(columns=[h.strip() for h in headers])

    return pd.DataFrame(records)

# ---------------- Helpers ----------------
def build_maps_link(hospital: str, city: str, state: str) -> str:
    parts = [str(x).strip() for x in [hospital, city, state] if str(x).strip()]
    return f"https://www.google.com/maps/search/?api=1&query={quote_plus(' '.join(parts))}"

def pick(df: pd.DataFrame, *names):
    """Return the first column name that exists in df (case-sensitive)."""
    for n in names:
        if n in df.columns:
            return n
    return None

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

# ---------------- Load & diagnostics ----------------
try:
    df = load_data_from_sheet(SHEET_ID, WORKSHEET_NAME)
except Exception as e:
    st.error(
        "❌ Could not load data from Google Sheets.\n\n"
        f"Details: {e}\n\n"
        "Checklist:\n"
        "• Sheet shared with the service account (Editor)\n"
        "• SHEET_ID matches the part between /d/ and /edit\n"
        "• WORKSHEET_NAME matches the bottom tab name exactly"
    )
    st.stop()

st.caption(f"Loaded **{df.shape[0]} rows** × **{df.shape[1]} cols**")
st.caption(f"Columns: {list(df.columns)}")

# ---------------- Transform / display ----------------
try:
    # Clean headers
    df.columns = [c.strip() for c in df.columns]

    # Resolve column names (accept variations)
    col_time   = pick(df, "Timestamp")
    col_init   = pick(df, "Initiation date", "Initation date")
    col_hosp   = pick(df, "Hospital")
    col_city   = pick(df, "Location City", "Location_City", "City")
    col_state  = pick(df, "Location State", "Location_State", "State")
    col_ecmo   = pick(df, "ECMO Type", "ECMO_Type")
    col_diag   = pick(df, "Provisional Diagnosis", "Provisional Diagnos")
    col_age    = pick(df, "Age of the patient", "Age")
    col_misc   = pick(df, "Misc comments", "Misc comment", "Misc", "Comments", "Notes", "Remarks")

    # Build Google_Maps_Link if missing and enough info is present
    if "Google_Maps_Link" not in df.columns and all(x for x in [col_hosp, col_city, col_state]) and not df.empty:
        df["Google_Maps_Link"] = df.apply(
            lambda r: build_maps_link(
                r.get(col_hosp, ""), r.get(col_city, ""), r.get(col_state, "")
            ),
            axis=1,
        )

    # Dedicated Map link column (keep Hospital plain text)
    if "Google_Maps_Link" in df.columns:
        df["Map"] = df["Google_Maps_Link"]

    # Add 1-based serial numbers as the first column
    if not df.empty:
        df = df.reset_index(drop=True)
        df.insert(0, "S.No", range(1, len(df) + 1))

    # Display order (includes Misc)
    display_cols = ["S.No"] if "S.No" in df.columns else []
    for c in [col_time, col_init, col_hosp, col_city, col_state, col_ecmo, col_diag, col_age, col_misc, "Map"]:
        if c and (c in df.columns or c == "Map"):
            display_cols.append(c)
    if not display_cols:
        display_cols = list(df.columns)

    st.dataframe(
        df[display_cols],
        use_container_width=True,
        hide_index=True,  # hide the 0-based dataframe index
        column_config={
            "S.No": st.column_config.NumberColumn("S.No"),
            "Map": st.column_config.LinkColumn("Google Maps"),
        },
    )

    # ---------- Charts ----------
    # Pie chart: ECMO cases by state
    if col_state and not df.empty:
        # Clean/aggregate state values
        counts = (
            df[col_state].astype(str).str.strip()
            .replace({"": None, "nan": None})
            .dropna()
            .value_counts()
            .sort_values(ascending=False)
        )

        if not counts.empty:
            import matplotlib.pyplot as plt  # local import

            st.subheader("ECMO cases by State")
            fig, ax = plt.subplots()
            ax.pie(
                counts.values,
                labels=counts.index,
                autopct="%1.0f%%",
                startangle=90,
            )
            ax.axis("equal")  # make it a circle
            st.pyplot(fig)
        else:
            st.info("No state values found to chart yet.")
    else:
        st.info("Add some rows with a state to see the state-wise pie chart.")

    # Reload button
    col1, _ = st.columns([1, 4])
    with col1:
        if st.button("🔄 Reload data"):
            st.cache_data.clear()

    st.caption(
        "Data source: Google Sheet → tab 'Form responses 1'. "
        "Edit the sheet and click Reload (or wait ~60s cache)."
    )

except Exception as e:
    st.error("⚠️ Rendering error — see details below.")
    st.exception(e)
    st.dataframe(df, use_container_width=True, hide_index=True)
