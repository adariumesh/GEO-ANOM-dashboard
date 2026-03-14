"""
Simplified Streamlit app for testing deployment.
Use this if the main app.py has issues on Streamlit Cloud.
"""

import streamlit as st
import geopandas as gpd
import pandas as pd
import folium
from streamlit_folium import st_folium
from pathlib import Path

st.set_page_config(
    page_title="Maryland Regional Digester Network",
    layout="wide",
    page_icon="🗺️"
)

st.title("🗺️ Maryland Regional Digester Network")
st.subheader("10-Hub Optimal Solution | $141.7M NPV | 7.2-month payback")

# Try to load data
@st.cache_data
def load_data():
    try:
        base_path = Path("data/processed/scenarios/scenario_10hubs")
        sites = gpd.read_file(base_path / "optimal_hubs_realistic.geojson")
        afos = gpd.read_file(base_path / "afo_assignments_realistic.geojson")
        return sites, afos
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return None, None

with st.spinner("Loading data..."):
    sites, afos = load_data()

if sites is None or afos is None:
    st.error("❌ Could not load optimization data.")
    st.info("**Data files needed:** Check that scenario_10hubs folder contains GeoJSON files")
    st.stop()

# Display metrics
col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    st.metric("AFOs Served", f"{len(afos):,}")
with col2:
    st.metric("Animals", f"{afos['headcount'].sum()/1e6:.1f}M")
with col3:
    st.metric("Hubs", len(sites))
with col4:
    st.metric("NPV", "$141.7M")
with col5:
    st.metric("Payback", "7.2 months")

# Create map
st.subheader("📍 Interactive Map")

m = folium.Map(location=[39.0, -76.7], zoom_start=8)

colors = ['red', 'blue', 'green', 'purple', 'orange', 'darkred', 'darkblue', 'darkgreen', 'cadetblue', 'pink']

# Add AFOs
for idx, row in afos.iterrows():
    if row.geometry is None or row.geometry.is_empty:
        continue

    site_idx = int(row.get("assigned_site_idx", 0))
    color = colors[site_idx % len(colors)]
    headcount = row.get('headcount', 0)

    radius = 5 if headcount < 100000 else 8

    folium.CircleMarker(
        location=[row.geometry.centroid.y, row.geometry.centroid.x],
        radius=radius,
        color=color,
        fill=True,
        fill_opacity=0.6,
        tooltip=f"{row.get('farm_name', 'Unknown')}: {headcount:,} animals"
    ).add_to(m)

# Add Hubs
for idx, row in sites.iterrows():
    site_id = row.get('site_id', idx)
    color = colors[int(site_id) % len(colors)]
    county = row.get('county', 'Unknown')

    folium.Marker(
        location=[row.geometry.centroid.y, row.geometry.centroid.x],
        icon=folium.Icon(color=color, icon='industry', prefix='fa'),
        tooltip=f"Hub {site_id} - {county}"
    ).add_to(m)

st_folium(m, width=1200, height=600)

# Display data
st.subheader("📊 Hub Details")
if 'site_id' in sites.columns:
    hub_data = sites[['site_id', 'county', 'zone_afos', 'zone_animals']].copy()
    hub_data.columns = ['Hub', 'County', 'AFOs', 'Animals']
    st.dataframe(hub_data, use_container_width=True)

st.success("✅ Dashboard loaded successfully!")
