# ---------- Build Google_Maps_Link if we have hospital/city/state ----------
if "Google_Maps_Link" not in df.columns:
    hosp_col  = next((c for c in df.columns if c.strip().lower() == "hospital"), None)
    city_col  = next((c for c in df.columns if "location city"  in c.strip().lower() or c.strip().lower()=="city"), None)
    state_col = next((c for c in df.columns if "location state" in c.strip().lower() or c.strip().lower()=="state"), None)
    if hosp_col and city_col and state_col and not df.empty:
        df["Google_Maps_Link"] = df.apply(
            lambda r: build_maps_link(r.get(hosp_col, ""), r.get(city_col, ""), r.get(state_col, "")),
            axis=1
        )

# Optional Map link column (keeps Hospital as plain text)
if "Google_Maps_Link" in df.columns:
    df["Google Maps"] = df["Google_Maps_Link"]  # nicer label for display

# ---------- Show ALL columns, with S.No first and Google Maps last ----------
# Reindex rows and add S.No starting from 1
df = df.reset_index(drop=True)
df.insert(0, "S.No", range(1, len(df) + 1))

# Put Google Maps at the end if present
if "Google Maps" in df.columns:
    display_cols = [c for c in df.columns if c != "Google Maps"] + ["Google Maps"]
else:
    display_cols = list(df.columns)

st.dataframe(
    df[display_cols],
    use_container_width=True,
    column_config={"Google Maps": st.column_config.LinkColumn("Google Maps")}
)
