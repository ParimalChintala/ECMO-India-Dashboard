
# ECMO India - Live Dashboard (Streamlit)

Tracks ongoing ECMO cases around India with the following key fields:
- **Initiation_Date** (YYYY-MM-DD)
- **Hospital**
- **Location_City**
- **Location_State**
- **ECMO_Type** (VV/VA/Other)
- **Provisional_Diagnosis**
- Optional: **Status** (Active/Weaning/Decannulated), **Latitude**, **Longitude** (for map)

## Quick Start (CSV)
1. Install Python 3.10+
2. `pip install -r requirements.txt`
3. Run:
   ```bash
   export DATA_SOURCE=csv
   export CSV_PATH=ecmo_cases_sample.csv
   streamlit run streamlit_app.py
   ```

## Live Google Sheets (Public Publish-to-Web)
1. File → Share → Publish to web → CSV, copy the URL.
2. Run:
   ```bash
   export DATA_SOURCE=gsheets
   export GSHEET_URL="https://docs.google.com/.../pub?output=csv"
   streamlit run streamlit_app.py
   ```

## Live Google Sheets (Private via Service Account)
1. Create a GCP service account and add the JSON to Streamlit Secrets as `gcp_service_account`.
2. Share the Google Sheet with that service account email.
3. Set:
   ```bash
   export DATA_SOURCE=gsheets
   export USE_SERVICE_ACCOUNT=true
   export GSHEET_URL="<Spreadsheet URL>"
   streamlit run streamlit_app.py
   ```

## Google Form (recommended for data entry)
Create a Google Form with the exact fields above. Link it to the Sheet. The dashboard will auto-refresh (default 60s).

## Map
- If Latitude/Longitude are present, the map is shown automatically.
- If not, the dashboard still works (charts + table).

## Safety
- Do not include patient identifiers.
- For public deployments, keep data de-identified.
