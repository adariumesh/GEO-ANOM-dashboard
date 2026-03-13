import streamlit as st
import geopandas as gpd
import pandas as pd
from pathlib import Path

st.set_page_config(page_title="Data Explorer - GEO-ANOM", layout="wide", page_icon="🗂️")

st.title("🗂️ Data Explorer")
st.markdown("Explore and filter the complete AFO dataset")

@st.cache_data
def load_all_data():
    try:
        permits = gpd.read_file("data/processed/afo_permits.gpkg")
        sites = gpd.read_file("data/processed/optimization/optimal_digester_sites.geojson")
        assignments = gpd.read_file("data/processed/optimization/afo_assignments.geojson")
        return permits, sites, assignments
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return None, None, None

permits, sites, assignments = load_all_data()

if permits is None:
    st.error("Could not load data files.")
    st.stop()

# Sidebar Filters
st.sidebar.header("🔍 Filters")

# County filter
counties = sorted(permits['county'].dropna().unique())
selected_counties = st.sidebar.multiselect(
    "Counties",
    options=counties,
    default=[]
)

# Animal type filter
animal_types = sorted(permits['animal_type'].dropna().unique())
selected_animals = st.sidebar.multiselect(
    "Animal Types",
    options=animal_types,
    default=[]
)

# Headcount range
min_headcount = int(permits['headcount'].min())
max_headcount = int(permits['headcount'].max())
headcount_range = st.sidebar.slider(
    "Headcount Range",
    min_value=min_headcount,
    max_value=max_headcount,
    value=(min_headcount, max_headcount),
    step=1000
)

# Status filter
statuses = sorted(permits['status'].dropna().unique())
selected_statuses = st.sidebar.multiselect(
    "Status",
    options=statuses,
    default=statuses
)

# Apply filters
filtered_permits = permits.copy()

if selected_counties:
    filtered_permits = filtered_permits[filtered_permits['county'].isin(selected_counties)]

if selected_animals:
    filtered_permits = filtered_permits[filtered_permits['animal_type'].isin(selected_animals)]

filtered_permits = filtered_permits[
    (filtered_permits['headcount'] >= headcount_range[0]) &
    (filtered_permits['headcount'] <= headcount_range[1])
]

if selected_statuses:
    filtered_permits = filtered_permits[filtered_permits['status'].isin(selected_statuses)]

# Display Results
st.header(f"Results: {len(filtered_permits)} AFOs")

# Summary metrics
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Facilities", f"{len(filtered_permits):,}")
with col2:
    total_animals = filtered_permits['headcount'].sum()
    st.metric("Total Animals", f"{total_animals:,.0f}")
with col3:
    avg_animals = filtered_permits['headcount'].mean()
    st.metric("Avg Animals/Facility", f"{avg_animals:,.0f}")
with col4:
    counties_count = filtered_permits['county'].nunique()
    st.metric("Counties Represented", f"{counties_count}")

# Data table with download
st.subheader("AFO Permits Data")

# Prepare display dataframe (drop geometry for table view)
display_df = filtered_permits.drop(columns=['geometry']) if 'geometry' in filtered_permits.columns else filtered_permits

# Format for better display
display_df = display_df[[
    'farm_name', 'animal_type', 'headcount', 'status',
    'county', 'city', 'latitude', 'longitude'
]].copy()

display_df['headcount'] = display_df['headcount'].apply(lambda x: f"{x:,.0f}")
display_df['latitude'] = display_df['latitude'].apply(lambda x: f"{x:.4f}" if pd.notna(x) else "")
display_df['longitude'] = display_df['longitude'].apply(lambda x: f"{x:.4f}" if pd.notna(x) else "")

# Display with sorting
st.dataframe(
    display_df,
    use_container_width=True,
    height=500,
    hide_index=True
)

# Download options
st.subheader("📥 Export Data")
col_dl1, col_dl2, col_dl3 = st.columns(3)

with col_dl1:
    # CSV download
    csv = filtered_permits.drop(columns=['geometry']).to_csv(index=False)
    st.download_button(
        label="Download as CSV",
        data=csv,
        file_name="afo_permits_filtered.csv",
        mime="text/csv"
    )

with col_dl2:
    # GeoJSON download (if geometry exists)
    if 'geometry' in filtered_permits.columns:
        geojson = filtered_permits.to_json()
        st.download_button(
            label="Download as GeoJSON",
            data=geojson,
            file_name="afo_permits_filtered.geojson",
            mime="application/json"
        )

with col_dl3:
    # Summary stats download
    summary_stats = filtered_permits.groupby('county').agg({
        'farm_name': 'count',
        'headcount': ['sum', 'mean', 'median']
    }).round(0)
    summary_stats.columns = ['AFO_Count', 'Total_Animals', 'Avg_Animals', 'Median_Animals']
    summary_csv = summary_stats.to_csv()
    st.download_button(
        label="Download Summary Stats",
        data=summary_csv,
        file_name="afo_summary_by_county.csv",
        mime="text/csv"
    )

# Detailed Hub Assignments
st.header("Hub Assignments")
st.markdown("Explore which AFOs are assigned to each digester hub")

if assignments is not None and 'assigned_site_idx' in assignments.columns:
    hub_tab1, hub_tab2, hub_tab3 = st.tabs([f"Hub {i}" for i in range(len(sites))])

    for i, tab in enumerate([hub_tab1, hub_tab2, hub_tab3]):
        with tab:
            hub_afos = assignments[assignments['assigned_site_idx'] == i]

            # Hub summary
            col_h1, col_h2, col_h3 = st.columns(3)
            with col_h1:
                st.metric("AFOs in Zone", len(hub_afos))
            with col_h2:
                hub_animals = hub_afos['headcount'].sum()
                st.metric("Total Animals", f"{hub_animals:,.0f}")
            with col_h3:
                hub_avg = hub_afos['headcount'].mean()
                st.metric("Avg Animals/AFO", f"{hub_avg:,.0f}")

            # Hub AFO table
            hub_display = hub_afos.drop(columns=['geometry']) if 'geometry' in hub_afos.columns else hub_afos
            hub_display = hub_display[['farm_name', 'animal_type', 'headcount', 'county']].copy()
            hub_display = hub_display.sort_values('headcount', ascending=False)

            st.dataframe(hub_display, use_container_width=True, height=400, hide_index=True)
