# streamlit_app.py — ECMO India Live Dashboard (hide Initiation Date & Email address)

from urllib.parse import quote_plus
import pandas as pd
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

# ---------------- Page setup ----------------
st.set_page_config(page_title="ECMO India – Live Dashboard", layout="wide")
st.title("🫀 ECMO India – Live Dashboard")

# ---------------- Your Google Sheet ----------------
SHEET_ID = "19MGz1nP5k0B-by9dLE9LgA3BTuQ4FYn1cEAGklvZprE"   # <- change if needed
WORKSHEET_NAME = "Form responses 1"                         # <- change if your tab name differs

# ---------------- Auth / loader ----------------
SCOPE = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

@st.cache_data(ttl=60)
def load_data_from_sheet(sheet_id: str, ws_name: str) -> pd.DataFrame:
    """Read the worksheet and tolerate duplicate/blank headers."""
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

    rows = ws.get_all_values()
    if not rows:
        return pd.DataFrame()

    # Make headers unique and non-empty
    raw_headers = [h.strip() for h in (rows[0] or [])]
    headers, seen = [], {}
    for i, h in enumerate(raw_headers):
        base = h or f"Column_{i+1}"
        name, k = base, 1
        while name in seen:
            k += 1
            name = f"{base} ({k})"
        seen[name] = True
        headers.append(name)

    df = pd.DataFrame(rows[1:], columns=headers)
    df = df.replace("", pd.NA).dropna(how="all").fillna("")
    return df

# ---------------- Helpers ----------------
def build_maps_link(hospital: str, city: str, state: str) -> str:
    parts = [str(x).strip() for x in [hospital, city, state] if str(x).strip()]
    return f"https://www.google.com/maps/search/?api=1&query={quote_plus(' '.join(parts))}"

def find_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    """Case-insensitive finder with partial matching support."""
    cols_lc = {c.lower(): c for c in df.columns}
    for cand in candidates:
        cand = cand.lower()
        # exact first
        if cand in cols_lc:
            return cols_lc[cand]
        # then partial
        for lc, orig in cols_lc.items():
            if cand in lc:
                return orig
    return None

# ---------------- Load data ----------------
try:
    df = load_data_from_sheet(SHEET_ID, WORKSHEET_NAME)
except Exception as e:
    st.error(
        "❌ Could not load data from Google Sheets.\n\n"
        f"Details: {e}\n\n"
        "Checklist:\n"
        "• Sheet shared with the service account (Editor)\n"
        "• SHEET_ID is correct\n"
        "• WORKSHEET_NAME matches the bottom tab name exactly"
    )
    st.stop()

# ---------------- Enrich & display ----------------
# Clean headers (trim spaces)
df.columns = [c.strip() for c in df.columns]

# Drop columns you don't want to show
to_drop = []
init_date_col = find_col(df, ["initiation date"])         # e.g., "Initiation Date"
email_col     = find_col(df, ["email address", "email"])  # e.g., "Email address"
for c in (init_date_col, email_col):
    if c:
        to_drop.append(c)
if to_drop:
    df = df.drop(columns=to_drop, errors="ignore")

# Add Google Maps link if we can find hospital, city, state
hosp_col  = find_col(df, ["hospital"])
city_col  = find_col(df, ["location city", "city"])
state_col = find_col(df, ["location state", "state"])

if "Google_Maps_Link" not in df.columns and all([hosp_col, city_col, state_col]) and not df.empty:
    df["Google_Maps_Link"] = df.apply(
        lambda r: build_maps_link(r.get(hosp_col, ""), r.get(city_col, ""), r.get(state_col, "")),
        axis=1
    )

# Keep only the single rightmost clickable column: "Google Maps"
if "Google_Maps_Link" in df.columns:
    df["Google Maps"] = df["Google_Maps_Link"]    # nicer label
    df = df.drop(columns=["Google_Maps_Link"])    # drop the raw column

# Add S.No starting at 1
df = df.reset_index(drop=True)
df.insert(0, "S.No", range(1, len(df) + 1))

# Put Google Maps as the last column (if present)
if "Google Maps" in df.columns:
    display_cols = [c for c in df.columns if c != "Google Maps"] + ["Google Maps"]
else:
    display_cols = list(df.columns)

st.dataframe(
    df[display_cols],
    use_container_width=True,
    column_config={"Google Maps": st.column_config.LinkColumn("Google Maps")},
)

# Reload button
col1, _ = st.columns([1, 5])
with col1:
    if st.button("🔄 Reload data"):
        st.cache_data.clear()
