import streamlit as st
import subprocess
from pathlib import Path
import geopandas as gpd

st.set_page_config(page_title="Configuration - GEO-ANOM", layout="wide", page_icon="⚙️")

st.title("⚙️ Pipeline Configuration & Control")
st.markdown("Run optimization with different parameters and view pipeline status")

# Pipeline Status Check
st.header("📊 Pipeline Status")

data_checks = {
    "AFO Permits": "data/processed/afo_permits.gpkg",
    "NAIP Imagery": "data/raw/naip_tiles",
    "CDL Raster": "data/raw/cdl/cdl_24_2023.tif",
    "N Demand Map": "data/processed/demand_maps/N_demand.tif",
    "P Demand Map": "data/processed/demand_maps/P2O5_demand.tif",
    "Optimization Results": "data/processed/optimization/optimal_digester_sites.geojson"
}

col1, col2 = st.columns(2)

for i, (name, path) in enumerate(data_checks.items()):
    with col1 if i % 2 == 0 else col2:
        exists = Path(path).exists()
        icon = "✅" if exists else "❌"

        if exists:
            if Path(path).is_file():
                size = Path(path).stat().st_size / (1024**2)  # MB
                st.success(f"{icon} {name} ({size:.1f} MB)")
            else:
                # Count files in directory
                count = len(list(Path(path).glob("*.tif")))
                st.success(f"{icon} {name} ({count} files)")
        else:
            st.error(f"{icon} {name} - Not Found")

# Optimization Controls
st.header("🎯 Run Optimization")

st.markdown("""
Adjust parameters and re-run the optimization to find different solutions.
The optimization minimizes transport effort while considering your constraints.
""")

col_opt1, col_opt2 = st.columns(2)

with col_opt1:
    n_sites = st.number_input(
        "Number of Digester Hubs",
        min_value=1,
        max_value=20,
        value=3,
        help="How many regional digester facilities to locate"
    )

    use_demand = st.checkbox(
        "Enable Demand-Aware Optimization",
        value=False,
        help="Consider nutrient demand maps (experimental)"
    )

with col_opt2:
    permits_path = st.text_input(
        "AFO Permits Path",
        value="data/processed/afo_permits.gpkg",
        help="Path to AFO permits GeoPackage"
    )

    output_dir = st.text_input(
        "Output Directory",
        value="data/processed/optimization",
        help="Where to save optimization results"
    )

if st.button("🚀 Run Optimization", type="primary"):
    with st.spinner(f"Running optimization for {n_sites} hub sites..."):
        cmd = [
            "python3", "scripts/run_phase4.py",
            "--permits", permits_path,
            "--n-sites", str(n_sites),
            "--output-dir", output_dir
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )

            if result.returncode == 0:
                st.success("✅ Optimization completed successfully!")
                st.code(result.stdout, language="text")

                # Show results
                sites_path = Path(output_dir) / "optimal_digester_sites.geojson"
                if sites_path.exists():
                    sites = gpd.read_file(sites_path)
                    st.metric("Optimal Sites Found", len(sites))
                    st.info("🔄 Refresh the main dashboard to see updated results")
            else:
                st.error("❌ Optimization failed")
                st.code(result.stderr, language="text")

        except subprocess.TimeoutExpired:
            st.error("⏱️ Optimization timed out (exceeded 5 minutes)")
        except Exception as e:
            st.error(f"Error: {e}")

# Phase Controls
st.header("🔄 Run Pipeline Phases")

tab1, tab2, tab3, tab4 = st.tabs(["Phase 1", "Phase 2", "Phase 3", "Phase 4"])

with tab1:
    st.subheader("Phase 1: Data Ingestion")
    st.markdown("""
    Downloads AFO permits, NAIP imagery, and CDL crop data.

    **What it does:**
    - Fetches AFO permit data from Maryland Open Data
    - Downloads high-resolution satellite imagery (NAIP)
    - Gets USDA Cropland Data Layer rasters
    """)

    col_p1_1, col_p1_2 = st.columns(2)
    with col_p1_1:
        p1_county = st.text_input("Filter County (optional)", value="", key="p1_county")
    with col_p1_2:
        p1_limit = st.number_input("Limit AFOs (for testing)", min_value=0, value=0, key="p1_limit")

    if st.button("Run Phase 1"):
        cmd = ["python3", "scripts/run_phase1.py"]
        if p1_county:
            cmd.extend(["--county", p1_county])
        if p1_limit > 0:
            cmd.extend(["--limit", str(p1_limit)])

        with st.spinner("Running Phase 1..."):
            st.code(" ".join(cmd))
            st.info("This will run in the background. Check logs for progress.")

with tab2:
    st.subheader("Phase 2: AI Detection (Optional)")
    st.markdown("""
    **Status:** In Development

    Uses YOLO-World and SAM2 to detect and segment AFO structures from satellite imagery.
    Currently optional - optimization works without this phase.
    """)
    st.warning("⚠️ Phase 2 is experimental. Fine-tuning needed for Maryland imagery.")

with tab3:
    st.subheader("Phase 3: Nutrient Demand Mapping")
    st.markdown("""
    Processes crop data to calculate where nutrients are needed across the state.

    **Outputs:**
    - N_demand.tif (Nitrogen demand map)
    - P2O5_demand.tif (Phosphorus demand map)
    """)

    if st.button("Run Phase 3"):
        cmd = ["python3", "scripts/run_phase3.py"]
        with st.spinner("Processing demand maps..."):
            st.code(" ".join(cmd))
            st.info("Check data/processed/demand_maps/ for outputs")

with tab4:
    st.subheader("Phase 4: Geospatial Optimization")
    st.markdown("Use the optimization controls above ⬆️")

# Advanced Settings
with st.expander("🔧 Advanced Settings"):
    st.markdown("""
    ### Configuration Files

    - `configs/maryland.yaml` - State-specific constants
    - `.env` - API keys and credentials
    - `pyproject.toml` - Package dependencies

    ### Model Files

    - `yolov8x-worldv2.pt` - YOLO-World weights (147 MB)
    - SAM2 models downloaded on first use

    ### Data Directories

    - `data/raw/` - Downloaded source data
    - `data/processed/` - Pipeline outputs
    - `data/models/` - AI model weights
    """)

# System Info
st.header("💻 System Information")
col_sys1, col_sys2, col_sys3 = st.columns(3)

with col_sys1:
    import sys
    st.metric("Python Version", f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")

with col_sys2:
    import platform
    st.metric("OS", platform.system())

with col_sys3:
    st.metric("Project Root", str(Path.cwd()))
