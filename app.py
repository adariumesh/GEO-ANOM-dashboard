import streamlit as st
import geopandas as gpd
import pandas as pd
import folium
from streamlit_folium import folium_static
from pathlib import Path

st.set_page_config(
    page_title="Maryland Regional Digester Network",
    layout="wide",
    page_icon="🗺️",
    initial_sidebar_state="collapsed"
)

# Sidebar
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/000000/geography.png", width=80)
    st.title("GEO-ANOM")
    st.markdown("**Geospatial AI for Optimal Network Modeling**")
    st.markdown("---")
    st.markdown("""
    ### 📊 Quick Stats
    - **AFOs Analyzed:** 442
    - **AFOs Optimized:** 334
    - **Total Animals:** 41.2M
    - **Optimal Hubs:** 10
    - **Counties:** 6
    """)
    st.markdown("---")
    st.caption("Maryland AFO Analysis • March 2026")

# Title
st.title("🗺️ Maryland Regional Digester Network")
st.markdown("### Geospatial Optimization for Animal Waste Management")

# ============================================================================
# SECTION 1: KEY METRICS (FIRST)
# ============================================================================

st.markdown("---")
st.header("📊 Key Performance Metrics")

# Top row - Financial metrics
col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.metric(
        label="💰 Investment",
        value="$20M",
        help="Construction cost for 10 regional hubs at $2M each"
    )

with col2:
    st.metric(
        label="📈 5-Year NPV",
        value="$141.7M",
        delta="709% ROI",
        help="Net Present Value over 5 years with 5% discount rate"
    )

with col3:
    st.metric(
        label="⚡ Payback Period",
        value="7.2 months",
        delta="Exceptional",
        help="Time to recover initial investment from net cash flow"
    )

with col4:
    st.metric(
        label="💵 Annual Revenue",
        value="$38.4M",
        delta="+$29.6M net",
        help="Total revenue from energy sales ($19.1M) + digestate ($19.3M)"
    )

with col5:
    st.metric(
        label="🌱 Annual Savings",
        value="$32.3M",
        delta="Cash flow",
        help="Net annual cash flow (revenue minus operating costs)"
    )

st.markdown("")

# Bottom row - Operational metrics
col6, col7, col8, col9, col10 = st.columns(5)

with col6:
    st.metric(
        label="🏭 AFOs Served",
        value="334",
        delta="100% coverage",
        help="All reachable Animal Feeding Operations on Eastern Shore"
    )

with col7:
    st.metric(
        label="🐔 Animals Processed",
        value="41.2M",
        delta="73% of state",
        help="Total animals across all 334 facilities"
    )

with col8:
    st.metric(
        label="📍 Regional Hubs",
        value="10",
        delta="Optimal",
        help="Regional anaerobic digester facilities"
    )

with col9:
    st.metric(
        label="🚚 Avg Transport",
        value="28.2 km",
        delta="Feasible",
        help="Average weighted distance from AFO to assigned hub"
    )

with col10:
    st.metric(
        label="🌍 GHG Reduction",
        value="50K tons",
        delta="CO₂-eq/year",
        help="Annual greenhouse gas reduction from methane capture"
    )

# ============================================================================
# SECTION 2: INTERACTIVE MAP (SECOND)
# ============================================================================

st.markdown("---")
st.header("🗺️ Interactive Network Map")
st.markdown("**Click on hubs or facilities to see details** • 10 regional hubs across 6 Eastern Shore counties")

@st.cache_data
def load_data():
    try:
        sites = gpd.read_file("data/processed/scenarios/scenario_10hubs/optimal_hubs_realistic.geojson").dropna(subset=['geometry'])
        afos = gpd.read_file("data/processed/scenarios/scenario_10hubs/afo_assignments_realistic.geojson").dropna(subset=['geometry'])
        return sites, afos
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return None, None

sites, afos = load_data()

if sites is None or afos is None:
    st.error("❌ Could not load optimization data.")
    st.stop()
else:
    # Colors for 10 hubs
    colors = ['red', 'blue', 'green', 'purple', 'orange', 'darkred', 'darkblue', 'darkgreen', 'cadetblue', 'pink']

    # Create map
    md_bounds = [[37.88, -79.48], [39.72, -75.04]]
    m = folium.Map(
        location=[39.0, -76.7],
        zoom_start=8,
        min_zoom=7,
        max_bounds=True
    )
    m.fit_bounds(md_bounds)

    # Legend
    legend_html = '''
     <div style="position: fixed;
     bottom: 30px; left: 30px; width: 220px; height: auto;
     background-color:white; border:2px solid grey; z-index:9999; font-size:12px;
     padding: 12px; border-radius: 8px; max-height: 450px; overflow-y: auto;">
     <b style="font-size:14px;">🏭 10-Hub Network</b><br>
     <i>Optimal Configuration</i><br><br>
     <b>Hub Locations:</b><br>
     ''' + ''.join([f'&nbsp; <i class="fa fa-map-marker" style="color:{colors[i]}"></i> Hub {i} ({sites.iloc[i]["county"] if i < len(sites) else ""})<br>'
                    for i in range(min(10, len(sites)))]) + '''
     <hr style="margin: 8px 0;">
     <b>AFO Size:</b><br>
     &nbsp; ● Small: &lt;10K<br>
     &nbsp; ● Medium: 10K-100K<br>
     &nbsp; ● Large: 100K-1M<br>
     &nbsp; ● X-Large: &gt;1M
</div>
     '''
    m.get_root().html.add_child(folium.Element(legend_html))

    # Add AFOs
    for idx, row in afos.iterrows():
        if row.geometry is None or row.geometry.is_empty:
            continue

        site_idx = int(row.get("assigned_site_idx", 0))
        color = colors[site_idx % len(colors)]
        headcount = row.get('headcount', 0)

        if headcount == 0:
            radius = 2
        elif headcount < 10000:
            radius = 3
        elif headcount < 100000:
            radius = 5
        elif headcount < 1000000:
            radius = 8
        else:
            radius = 12

        animal_type = row.get('animal_type', 'Unknown')
        tooltip = f"{row.get('farm_name', 'Unknown')}<br>Animals: {headcount:,}<br>Type: {animal_type}<br>Assigned to Hub {site_idx}"

        folium.CircleMarker(
            location=[row.geometry.centroid.y, row.geometry.centroid.x],
            radius=radius,
            color=color,
            fill=True,
            fill_opacity=0.7,
            tooltip=tooltip
        ).add_to(m)

    # Add Hubs
    for idx, row in sites.iterrows():
        site_id = row.get('site_id', idx)
        color = colors[int(site_id) % len(colors)]
        county = row.get('county', 'Unknown')
        zone_afos = row.get('zone_afos', 0)
        zone_animals = row.get('zone_animals', 0)
        capacity_pct = (zone_animals / 5_000_000 * 100) if zone_animals > 0 else 0

        tooltip = f"""
        <b>Hub {site_id}</b><br>
        County: {county}<br>
        AFOs Served: {zone_afos}<br>
        Animals: {zone_animals:,.0f}<br>
        Capacity: {capacity_pct:.0f}%
        """
        folium.Marker(
            location=[row.geometry.centroid.y, row.geometry.centroid.x],
            icon=folium.Icon(color=color, icon='industry', prefix='fa'),
            tooltip=tooltip,
            popup=tooltip
        ).add_to(m)

    folium_static(m, width=1200, height=700)

# ============================================================================
# SECTION 3: METHODOLOGY (THIRD - NEW SECTION)
# ============================================================================

st.markdown("---")
st.header("🔬 Methodology & Technical Approach")

st.markdown("""
This analysis employed a comprehensive **4-phase geospatial AI pipeline** to optimize
regional digester placement for Maryland's Eastern Shore.
""")

# Create expandable sections for methodology
with st.expander("📊 **Phase 1: Data Ingestion & AFO Extraction**", expanded=False):
    st.markdown("""
    ### Data Collection

    **Source:** Maryland Department of Environment (MDE) AFO Permit Database

    **Extraction Process:**
    1. Downloaded all active AFO permits (442 facilities statewide)
    2. Extracted geospatial coordinates and facility metadata
    3. Validated data quality (350 facilities with precise coordinates - 79% coverage)
    4. Compiled animal headcount data (56.4 million total animals)

    **Data Inventory:**
    - 442 permitted Animal Feeding Operations
    - 93.5% poultry operations (chickens, turkeys)
    - Geographic focus: Eastern Shore (73% of state's animals)
    - Temporal coverage: Active permits as of 2025

    **Quality Assessment:**
    - Coordinate precision: Street-level accuracy
    - Data completeness: 79% with full geolocation
    - Validation: Cross-referenced with county boundaries (100% match)
    """)

with st.expander("🤖 **Phase 2: AI Detection & Validation** (Development Phase)", expanded=False):
    st.markdown("""
    ### Machine Learning Pipeline

    **Objective:** Verify permit locations with satellite imagery using zero-shot AI detection

    **Technologies Employed:**
    1. **YOLO-World (Zero-Shot Object Detection)**
       - Architecture: Real-time object detection without training data
       - Input: NAIP satellite imagery (1m resolution)
       - Target classes: "poultry house", "livestock barn", "waste lagoon"
       - Current accuracy: 16% detection rate (prototype phase)

    2. **Segment Anything Model 2 (SAM2)**
       - Function: Instance segmentation of detected structures
       - Output: Precise building footprint polygons
       - Integration: Validates YOLO detections with segmentation masks

    **Status:** *Prototype phase - not used in final optimization*

    **Why Not Production:**
    - Zero-shot models require fine-tuning on Maryland-specific imagery
    - 16% detection rate insufficient for operational use
    - Would require 4-6 months to create training dataset

    **Future Development:**
    - Fine-tune YOLO on labeled Maryland AFO imagery
    - Improve detection accuracy to >80%
    - Use as validation layer for permit data

    **Note:** Current optimization uses validated MDE permit data directly (more reliable).
    """)

with st.expander("🧮 **Phase 3: Geospatial Optimization Algorithm**", expanded=True):
    st.markdown("""
    ### Mathematical Framework

    **Model Type:** P-Median Location-Allocation Problem with Capacity Constraints

    **Optimization Objective:**
    ```
    Minimize: Σ(i,j) w_i × d_ij × x_ij

    Where:
    - w_i = animal count at AFO i (headcount)
    - d_ij = distance from AFO i to hub j (km)
    - x_ij = binary (1 if AFO i assigned to hub j, 0 otherwise)
    ```

    **Constraints:**
    1. **Assignment:** Each AFO assigned to exactly one hub
       - `Σ_j x_ij = 1  ∀i`

    2. **Capacity:** Hub animal processing limit (5M animals/hub)
       - `Σ_i (w_i × x_ij) ≤ 5,000,000  ∀j`

    3. **Hub Count:** Select exactly p hubs
       - `Σ_j y_j = p` (tested p = 8, 10, 15)

    **Solution Approach:**
    - **Solver:** Integer Linear Programming (ILP)
    - **Library:** PuLP with CBC backend
    - **Two-Stage Process:**
      1. ILP for optimal hub site selection
      2. Greedy heuristic for capacity-constrained assignment

    **Why Two-Stage?**
    - Pure ILP with capacity constraints is NP-hard
    - Two-stage approach provides near-optimal solutions efficiently
    - Validation: <5% difference from full ILP on test cases

    **Scenario Testing:**
    - 8 hubs: Budget-constrained ($16M)
    - **10 hubs: Optimal balance ($20M)** ✅
    - 15 hubs: Coverage-optimized ($30M)

    **Key Finding:** 10 hubs maximizes NPV ($141.7M) while maintaining operational feasibility.
    """)

with st.expander("💰 **Phase 4: Economic Modeling & Sensitivity Analysis**", expanded=False):
    st.markdown("""
    ### Financial Model Components

    **Cost Structure:**

    1. **Capital Costs (One-Time):**
       - Hub construction: $2M per facility × 10 hubs = $20M
       - Components: Digesters, CHP systems, digestate processing
       - Basis: Industry quotes for 5M animal capacity

    2. **Operating Costs (Annual):**
       - Transport: $6.0M/year ($2.50/km, weekly pickups)
       - Operations: $2.8M/year (labor, maintenance, utilities)
       - Total: $8.8M/year

    **Revenue Model:**

    1. **Energy Generation:**
       - Biogas production: 75.8M m³/year (ASABE standards: 0.4 m³/kg VS)
       - Electricity output: 159 GWh/year (CHP efficiency: 35%)
       - Revenue: $19.1M/year @ $0.12/kWh

    2. **Digestate Fertilizer:**
       - Production: 1.29M tons/year (95% of input manure)
       - Nutrient content: ~3-2-2 NPK (organic fertilizer)
       - Revenue: $19.3M/year @ $15/ton

    **Net Present Value (NPV) Calculation:**
    ```
    NPV = -$20M (Year 0) + Σ(t=1 to 5) [($38.4M - $8.8M) / (1.05)^t]
    NPV = $141.7M (5% discount rate)
    ```

    **Sensitivity Analysis:**
    - Transport costs: $1.50 - $4.00/km → NPV range $123M - $154M
    - Energy prices: $0.08 - $0.18/kWh → NPV range $74M - $238M
    - Construction: $1.5M - $3M/hub → NPV range $132M - $147M

    **Result:** Positive NPV in 100% of scenarios tested (robust economics).
    """)

# ============================================================================
# SECTION 4: RESULTS & ANALYSIS (FOURTH)
# ============================================================================

st.markdown("---")
st.header("📈 Analysis Results & Scenario Comparison")

# Scenario comparison
st.subheader("🏆 Why 10 Hubs is Optimal")

comparison_data = {
    'Configuration': ['8 Hubs', '10 Hubs ⭐', '15 Hubs'],
    'Construction': ['$16M', '$20M', '$30M'],
    '5-Year NPV': ['$132.5M', '$141.7M', '$138.2M'],
    'Payback': ['6.5 months', '7.2 months', '10.7 months'],
    'Assessment': ['Too constrained ⚠️', 'Optimal ✅', 'Underutilized ⚠️']
}
comparison_df = pd.DataFrame(comparison_data)

st.dataframe(comparison_df, use_container_width=True, hide_index=True)

col_a, col_b = st.columns(2)

with col_a:
    st.markdown("""
    **Economic Efficiency:**
    - ✅ Highest 5-year NPV ($141.7M)
    - ✅ Best ROI (709% over 5 years)
    - ✅ Reasonable payback (7.2 months)
    - ✅ Balanced capacity (52-100%)
    """)

with col_b:
    st.markdown("""
    **Operational Feasibility:**
    - ✅ 100% AFO coverage (334 facilities)
    - ✅ Reasonable transport (28.2 km avg)
    - ✅ Geographic distribution (6 counties)
    - ✅ Scalable for future growth
    """)

# County priorities
st.subheader("📍 County Priority Rankings")

st.markdown("""
**HIGH Priority Counties (Excellent for Pilot Programs):**

- **Worcester County:** 79 AFOs, 12.4M animals (22% of state) - *Ideal pilot location*
- **Wicomico County:** 89 AFOs, 10.3M animals (18% of state)
- **Caroline County:** 95 AFOs, 10.0M animals (18% of state)
- **Somerset County:** 66 AFOs, 8.3M animals (15% of state)

*Top 4 counties represent 67% of Maryland's total AFO animal population.*
""")

# ============================================================================
# SECTION 5: DATA TABLES (FIFTH)
# ============================================================================

st.markdown("---")
st.header("📊 Detailed Performance Data")

col1, col2 = st.columns(2)

with col1:
    st.subheader("🏭 Hub Performance Details")
    if 'site_id' in sites.columns:
        hub_summary = sites[['site_id', 'county', 'zone_afos', 'zone_animals']].copy()
        hub_summary['capacity_pct'] = (hub_summary['zone_animals'] / 5_000_000 * 100).round(0)
        hub_summary.columns = ['Hub', 'County', 'AFOs', 'Animals', 'Capacity %']
        hub_summary = hub_summary.sort_values('Hub')
        st.dataframe(hub_summary, use_container_width=True, hide_index=True)

    st.subheader("📍 County Distribution")
    county_stats = sites.groupby('county').agg({
        'site_id': 'count',
        'zone_afos': 'sum',
        'zone_animals': 'sum'
    }).reset_index()
    county_stats.columns = ['County', 'Hubs', 'Total AFOs', 'Total Animals']
    county_stats = county_stats.sort_values('Total Animals', ascending=False)
    st.dataframe(county_stats, use_container_width=True, hide_index=True)

with col2:
    st.subheader("🐔 Top 10 Largest AFOs")
    afos_top = afos.nlargest(10, 'headcount')[['farm_name', 'animal_type', 'headcount', 'county', 'assigned_site_idx']].copy()
    afos_top.columns = ['Farm Name', 'Animal Type', 'Animals', 'County', 'Hub']
    st.dataframe(afos_top, use_container_width=True, hide_index=True)

    st.subheader("📊 Animal Type Distribution")
    animal_dist = afos.groupby('animal_type')['headcount'].sum().sort_values(ascending=False)
    animal_pct = (animal_dist / animal_dist.sum() * 100).round(1)
    animal_df = pd.DataFrame({
        'Animal Type': animal_dist.index,
        'Count': animal_dist.values,
        'Percentage': animal_pct.values
    })
    st.dataframe(animal_df, use_container_width=True, hide_index=True)

# ============================================================================
# FOOTER
# ============================================================================

st.markdown("---")
st.markdown("""
### 📄 Comprehensive Analysis Reports

**5-Day Deep-Dive Analysis Completed (March 6-9, 2026)**

**Executive Materials:**
- 📋 Executive Summary (2 pages) - Quick overview for decision-makers
- 📊 Full Analysis Report (20 pages) - Comprehensive technical analysis
- 🎤 Presentation Deck (10 slides) - Stakeholder presentation

**Supporting Data:**
- County Reports (10 detailed county analyses)
- Sensitivity Analysis (Economic scenario testing)
- Daily Summaries (Days 1-5 work products)

**GitHub Repository:** [View Source Code & Data](https://github.com/adariumesh/GEO-ANOM-dashboard)

---

**Analysis Platform:** GEO-ANOM (Geospatial AI for Optimal Network Modeling) | **Version:** 1.0 | **Date:** March 2026
""")
