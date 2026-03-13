import streamlit as st
import geopandas as gpd
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path

st.set_page_config(page_title="Analytics - GEO-ANOM", layout="wide", page_icon="📊")

st.title("📊 GEO-ANOM Analytics Dashboard")

@st.cache_data
def load_data():
    try:
        sites = gpd.read_file("data/processed/optimization/optimal_digester_sites.geojson").dropna(subset=['geometry'])
        afos = gpd.read_file("data/processed/optimization/afo_assignments.geojson").dropna(subset=['geometry'])
        permits = gpd.read_file("data/processed/afo_permits.gpkg")
        return sites, afos, permits
    except Exception as e:
        return None, None, None

sites, afos, permits = load_data()

if sites is None or afos is None:
    st.error("Could not load optimization data. Run Phase 4 first.")
    st.stop()

# Main Metrics
st.header("Key Performance Indicators")
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        "Total AFOs",
        f"{len(permits):,}",
        help="All AFO permits in Maryland database"
    )
with col2:
    total_animals = permits['headcount'].sum()
    st.metric(
        "Total Animals",
        f"{total_animals:,.0f}",
        help="Total animal headcount across all facilities"
    )
with col3:
    mapped_afos = len(afos)
    st.metric(
        "Mapped AFOs",
        f"{mapped_afos:,}",
        delta=f"{(mapped_afos/len(permits)*100):.1f}%",
        help="AFOs with valid coordinates displayed on map"
    )
with col4:
    st.metric(
        "Digester Hubs",
        f"{len(sites)}",
        help="Optimal hub locations calculated"
    )

# Charts Row 1
st.header("Supply Distribution Analysis")
col_chart1, col_chart2 = st.columns(2)

with col_chart1:
    st.subheader("AFOs by County")
    county_counts = permits.groupby('county').size().reset_index(name='count')
    county_counts = county_counts.sort_values('count', ascending=False).head(10)

    fig_county = px.bar(
        county_counts,
        x='county',
        y='count',
        title="Top 10 Counties by AFO Count",
        labels={'county': 'County', 'count': 'Number of AFOs'},
        color='count',
        color_continuous_scale='viridis'
    )
    fig_county.update_layout(showlegend=False)
    st.plotly_chart(fig_county, use_container_width=True)

with col_chart2:
    st.subheader("Animal Type Distribution")
    animal_counts = permits.groupby('animal_type')['headcount'].sum().reset_index()
    animal_counts = animal_counts.sort_values('headcount', ascending=False)

    fig_animals = px.pie(
        animal_counts,
        values='headcount',
        names='animal_type',
        title="Animal Population by Type",
        hole=0.4
    )
    st.plotly_chart(fig_animals, use_container_width=True)

# Charts Row 2
st.header("Hub Zone Analysis")
col_chart3, col_chart4 = st.columns(2)

with col_chart3:
    st.subheader("AFOs per Hub Zone")
    hub_counts = afos.groupby('assigned_site_idx').agg({
        'headcount': ['count', 'sum']
    }).reset_index()
    hub_counts.columns = ['Hub', 'AFO_Count', 'Total_Animals']

    fig_hub = go.Figure()
    fig_hub.add_trace(go.Bar(
        x=hub_counts['Hub'],
        y=hub_counts['AFO_Count'],
        name='Number of AFOs',
        marker_color='lightblue'
    ))
    fig_hub.update_layout(
        title="AFOs Assigned to Each Hub",
        xaxis_title="Hub ID",
        yaxis_title="Number of AFOs",
        showlegend=False
    )
    st.plotly_chart(fig_hub, use_container_width=True)

with col_chart4:
    st.subheader("Animal Population per Hub")
    fig_pop = px.bar(
        hub_counts,
        x='Hub',
        y='Total_Animals',
        title="Total Animal Headcount by Hub Zone",
        labels={'Hub': 'Hub ID', 'Total_Animals': 'Total Animals'},
        color='Total_Animals',
        color_continuous_scale='reds'
    )
    st.plotly_chart(fig_pop, use_container_width=True)

# Headcount Distribution
st.header("Facility Size Distribution")
col_chart5, col_chart6 = st.columns(2)

with col_chart5:
    # Filter out zero headcounts for cleaner visualization
    active_permits = permits[permits['headcount'] > 0].copy()

    # Create size categories
    def categorize_size(headcount):
        if headcount < 1000:
            return "< 1K"
        elif headcount < 10000:
            return "1K-10K"
        elif headcount < 100000:
            return "10K-100K"
        elif headcount < 1000000:
            return "100K-1M"
        else:
            return "> 1M"

    active_permits['size_category'] = active_permits['headcount'].apply(categorize_size)
    size_dist = active_permits.groupby('size_category').size().reset_index(name='count')

    # Order categories
    category_order = ["< 1K", "1K-10K", "10K-100K", "100K-1M", "> 1M"]
    size_dist['size_category'] = pd.Categorical(size_dist['size_category'], categories=category_order, ordered=True)
    size_dist = size_dist.sort_values('size_category')

    fig_size = px.bar(
        size_dist,
        x='size_category',
        y='count',
        title="AFO Size Distribution",
        labels={'size_category': 'Facility Size (animals)', 'count': 'Number of Facilities'},
        color='count',
        color_continuous_scale='blues'
    )
    st.plotly_chart(fig_size, use_container_width=True)

with col_chart6:
    st.subheader("Top 15 Largest Facilities")
    top_facilities = permits.nlargest(15, 'headcount')[['farm_name', 'headcount', 'animal_type', 'county']]
    top_facilities = top_facilities.copy()
    top_facilities['headcount'] = top_facilities['headcount'].apply(lambda x: f"{x:,.0f}")
    st.dataframe(top_facilities, use_container_width=True, hide_index=True)

# Geographic Distribution
st.header("Geographic Distribution")

# Create a heatmap of AFO density by county
county_stats = permits.groupby('county').agg({
    'headcount': ['count', 'sum']
}).reset_index()
county_stats.columns = ['County', 'AFO_Count', 'Total_Animals']
county_stats['Avg_Animals_per_AFO'] = county_stats['Total_Animals'] / county_stats['AFO_Count']
county_stats = county_stats.sort_values('Total_Animals', ascending=False).head(15)

fig_geo = go.Figure()
fig_geo.add_trace(go.Bar(
    x=county_stats['County'],
    y=county_stats['Total_Animals'],
    name='Total Animals',
    marker_color='indianred'
))
fig_geo.update_layout(
    title="Top 15 Counties by Animal Population",
    xaxis_title="County",
    yaxis_title="Total Animals",
    xaxis_tickangle=-45,
    height=500
)
st.plotly_chart(fig_geo, use_container_width=True)

# Summary Statistics Table
st.header("Detailed Statistics by Hub Zone")
hub_detailed = afos.groupby('assigned_site_idx').agg({
    'farm_name': 'count',
    'headcount': ['sum', 'mean', 'median', 'max']
}).round(0)
hub_detailed.columns = ['AFO Count', 'Total Animals', 'Avg Animals', 'Median Animals', 'Max Animals']
hub_detailed.index.name = 'Hub ID'
st.dataframe(hub_detailed.style.format({
    'AFO Count': '{:.0f}',
    'Total Animals': '{:,.0f}',
    'Avg Animals': '{:,.0f}',
    'Median Animals': '{:,.0f}',
    'Max Animals': '{:,.0f}'
}), use_container_width=True)
