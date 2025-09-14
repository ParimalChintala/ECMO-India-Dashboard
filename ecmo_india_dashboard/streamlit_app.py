# streamlit_app.py — ECMO India Live Dashboard + Charts (Hospital Treemap)

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
SHEET_ID = "19MGz1nP5k0B-by9dLE9LgA3BTuQ4FYn1cEAGklvZprE"
WORKSHEET_NAME = "Form Responses 1"  # change if your tab name differs

# ---------------- Auth / loader ----------------
SCOPE = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


@st.cache_data(ttl=60)
def load_raw_from_sheet(sheet_id: str, ws_name: str) -> pd.DataFrame:
    """Load values from the worksheet, keeping duplicate headers safe."""
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"], scopes=SCOPE
    )
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(sheet_id)

    try:
        ws = sh.worksheet(ws_name)
    except gspread.exceptions.WorksheetNotFound:
        tabs = [w.title for w in sh.worksheets()]
        if tabs:
            ws = sh.sheet1
            st.warning(
                f"Worksheet '{ws_name}' not found — using first tab: '{ws.title}'. "
                f"Available tabs: {tabs}"
            )
        else:
            raise RuntimeError("This spreadsheet has no worksheets.")

    values = ws.get_all_values()  # full grid (strings)
    if not values:
        return pd.DataFrame()

    headers = [h.strip() for h in values[0]]
    rows = values[1:]

    # Make headers unique if needed (e.g., duplicate 'Miscellaneous comments')
    seen = {}
    unique_headers = []
    for h in headers:
        key = h if h else "Column"
        seen[key] = seen.get(key, 0) + 1
        if seen[key] > 1:
            unique_headers.append(f"{key} ({seen[key]})")
        else:
            unique_headers.append(key)

    df = pd.DataFrame(rows, columns=unique_headers)
    df = df.replace("", pd.NA).dropna(how="all")
    return df


def pick(df: pd.DataFrame, *names):
    """Return the first column name that exists (case-sensitive)."""
    for n in names:
        if n in df.columns:
            return n
    return None


def build_maps_link(hospital: str, city: str, state: str) -> str:
    parts = [str(x).strip() for x in [hospital, city, state] if str(x).strip()]
    if not parts:
        return ""
    return f"https://www.google.com/maps/search/?api=1&query={quote_plus(' '.join(parts))}"


# ---------------- Load + Clean ----------------
try:
    df = load_raw_from_sheet(SHEET_ID, WORKSHEET_NAME)
except Exception as e:
    st.error(
        "❌ Could not load data from Google Sheets.\n\n"
        f"Details: {e}\n\n"
        "Checklist:\n"
        "• Sheet is shared with the service account (Editor)\n"
        "• SHEET_ID matches the part between /d/ and /edit\n"
        "• WORKSHEET_NAME matches the bottom tab name exactly"
    )
    st.stop()

if df.empty:
    st.info("No rows yet. Add responses to the sheet, then click **Reload data**.")
else:
    # Trim header whitespace and normalize
    df.columns = [c.strip() for c in df.columns]

    # Combine duplicate/variant "Misc comments" columns into a single one (keep first non-empty per row)
    misc_like = [c for c in df.columns if c.lower().startswith("misc")]
    if misc_like:
        df["Miscellaneous comments"] = None
        for c in misc_like:
            df["Miscellaneous comments"] = df["Miscellaneous comments"].fillna(df[c])
        for c in misc_like:
            if c != "Miscellaneous comments":
                df.drop(columns=c, inplace=True, errors="ignore")

    # Map likely column names
    col_time = pick(df, "Timestamp", "Time stamp")
    col_init = pick(df, "Initiation time", "Initiation date", "Initation date")
    col_hosp = pick(df, "Hospital")
    col_city = pick(df, "Location City", "Location city", "City", "Location_City")
    col_state = pick(df, "Location State", "Location state", "State", "Location_State")
    col_ecmo = pick(df, "ECMO Type", "ECMO type", "Type", "Type of ECMO", "ECMO_Type")
    col_diag = pick(df, "Provisional Diagnosis", "Provisional diagnosis", "Diagnosis")
    col_age = pick(df, "Age of the patient", "Age")
    col_email = pick(df, "Email address", "Email")
    col_senior = pick(
        df, "Name of Senior intensivist supervising the procedure",
        "Name of Senior intensivist supervising the p"
    )

    # Build Google Maps link
    if col_hosp and (col_city or col_state) and "Google Maps" not in df.columns:
        df["Google Maps"] = df.apply(
            lambda r: build_maps_link(
                r.get(col_hosp, ""), r.get(col_city, ""), r.get(col_state, "")
            ),
            axis=1,
        )

    # -------- Table (hide Initiation date & Email) --------
    df_display = df.copy()
    df_display.insert(0, "S.No", range(1, len(df_display) + 1))

    preferred = [
        col_time,
        col_init,               # hidden below
        col_hosp,
        col_city,
        col_state,
        col_ecmo,
        col_diag,
        col_age,
        col_senior,
        "Miscellaneous comments",
        "Google Maps",
    ]
    display_cols = [c for c in preferred if c and c in df_display.columns]

    if col_init in display_cols:
        display_cols.remove(col_init)
    if col_email in display_cols:
        display_cols.remove(col_email)

    display_cols = ["S.No"] + display_cols

    st.dataframe(
        df_display[display_cols],
        use_container_width=True,
        column_config={"Google Maps": st.column_config.LinkColumn("Google Maps")},
    )

    # Controls
    col_btn, _ = st.columns([1, 8])
    with col_btn:
        if st.button("🔄 Reload data"):
            st.cache_data.clear()

    st.markdown("---")
    st.subheader("📊 ECMO Overview (Interactive)")

    # -------- Helpers --------
    def safe_counts(series: pd.Series) -> pd.DataFrame:
        s = (
            series.dropna()
            .astype(str)
            .str.strip()
            .replace({"": pd.NA})
            .dropna()
        )
        if s.empty:
            return pd.DataFrame(columns=["Label", "Count"])
        counts = s.value_counts().reset_index()
        counts.columns = ["Label", "Count"]
        return counts.sort_values("Count", ascending=False)

    # ECMO Type: donut + bar
    if col_ecmo and col_ecmo in df.columns:
        c = safe_counts(df[col_ecmo])
        if not c.empty:
            left, right = st.columns(2)
            with left:
                pie = px.pie(
                    c, names="Label", values="Count",
                    hole=0.45, title="ECMO Type — Share"
                )
                pie.update_traces(textinfo="percent+label")
                st.plotly_chart(pie, use_container_width=True)
            with right:
                bar = px.bar(
                    c, x="Count", y="Label", orientation="h",
                    title="ECMO Type — Counts"
                )
                bar.update_layout(yaxis_title="", xaxis_title="Cases")
                st.plotly_chart(bar, use_container_width=True)
        else:
            st.info("No data found for ECMO Type.")
    else:
        st.info("ECMO Type column not found.")

    # State-wise: horizontal bar
    if col_state and col_state in df.columns:
        c = safe_counts(df[col_state])
        if not c.empty:
            bar = px.bar(
                c, x="Count", y="Label", orientation="h",
                title="State-wise ECMO Cases"
            )
            bar.update_layout(yaxis_title="", xaxis_title="Cases")
            st.plotly_chart(bar, use_container_width=True)
        else:
            st.info("No state values to plot.")
    else:
        st.info("State column not found.")

    # Hospital-wise: TREEMAP (replaces horizontal bar)
    if col_hosp and col_hosp in df.columns:
        c = safe_counts(df[col_hosp])
        if not c.empty:
            # Treemap with hospital names as leaves sized by case count
            tree = px.treemap(
                c,
                path=["Label"],          # one level: hospital
                values="Count",
                title="Hospital-wise ECMO Cases (Treemap)",
            )
            # show counts on boxes
            tree.update_traces(textinfo="label+value")
            st.plotly_chart(tree, use_container_width=True)
        else:
            st.info("No hospital values to plot.")
    else:
        st.info("Hospital column not found.")
