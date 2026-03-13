# GEO-ANOM Dashboard Guide

**Complete Interactive Dashboard for AFO Optimization Analysis**

---

## 🚀 Quick Start

```bash
# Launch the dashboard
streamlit run app.py
```

The dashboard will open in your browser at `http://localhost:8501`

---

## 📱 Dashboard Pages

### 🗺️ Home (Main Map View)
**Interactive geospatial visualization of optimization results**

**Features:**
- Interactive Folium map with Maryland AFO locations
- 3 colored digester hub markers
- AFO circles sized by animal headcount
- Click tooltips showing:
  - Farm name
  - Animal count and type
  - Assigned hub zone
- Legend for hub zones
- Summary statistics panel
- Top 10 largest facilities table

**What You See:**
- Red/Blue/Green markers = Digester hub locations
- Colored circles = AFOs colored by assigned hub
- Circle size indicates facility size:
  - Tiny (2px): 0 animals
  - Small (3px): 1-10K animals
  - Medium (5px): 10K-100K animals
  - Large (8px): 100K-1M animals
  - Huge (12px): 1M+ animals

---

### 📊 Analytics
**Comprehensive charts and insights**

**Key Performance Indicators:**
- Total AFOs in database
- Total animal population
- AFOs with valid coordinates
- Number of digester hubs

**Visualizations:**

1. **Supply Distribution**
   - Top 10 counties by AFO count (bar chart)
   - Animal population by type (pie chart)

2. **Hub Zone Analysis**
   - AFOs per hub (bar chart)
   - Animal population per hub (bar chart)

3. **Facility Size Distribution**
   - Size category histogram
   - Top 15 largest facilities table

4. **Geographic Distribution**
   - Top 15 counties by animal population
   - Detailed statistics by hub zone

**Use Cases:**
- Understand supply concentration
- Identify high-density areas
- Compare hub zone balance
- Export statistics for reports

---

### 🗂️ Data Explorer
**Browse, filter, and export the complete dataset**

**Features:**

**Filters (Sidebar):**
- County selector (multi-select)
- Animal type filter
- Headcount range slider
- Status filter

**Data Table:**
- Sortable columns
- 500 facilities per view
- Real-time filtering

**Export Options:**
1. **CSV Download** - Full filtered dataset
2. **GeoJSON Download** - Spatial data with coordinates
3. **Summary Stats** - County-level aggregations

**Hub Assignment Explorer:**
- Tabbed view for each hub zone
- AFO lists by assigned hub
- Zone-specific metrics

**Use Cases:**
- Find specific facilities
- Filter by region/type
- Generate custom reports
- Export data for external analysis

---

### ⚙️ Configuration
**Pipeline control and system status**

**Pipeline Status Check:**
- ✅/❌ indicators for each data file
- File sizes and counts
- Quick health check

**Run Optimization:**
- Adjust number of hub sites (1-20)
- Enable demand-aware optimization (experimental)
- Custom input/output paths
- One-click re-optimization
- Real-time progress feedback

**Phase Controls:**
- **Phase 1**: Download AFO permits & imagery
- **Phase 2**: AI detection (optional)
- **Phase 3**: Generate demand maps
- **Phase 4**: Run optimization

**Advanced Settings:**
- Configuration file locations
- Model file inventory
- Data directory structure

**System Information:**
- Python version
- Operating system
- Project directory

**Use Cases:**
- Re-run optimization with different hub counts
- Check if all data is downloaded
- Manually trigger pipeline phases
- Troubleshoot missing files

---

## 🎯 Common Workflows

### Workflow 1: View Current Results
1. Launch dashboard: `streamlit run app.py`
2. Explore map on Home page
3. Review analytics on 📊 Analytics page
4. Export data from 🗂️ Data Explorer

### Workflow 2: Re-optimize with Different Hub Count
1. Go to ⚙️ Configuration page
2. Change "Number of Digester Hubs" (e.g., from 3 to 5)
3. Click "Run Optimization"
4. Wait for completion (~90 seconds)
5. Return to Home page to see updated map

### Workflow 3: Filter and Export County Data
1. Go to 🗂️ Data Explorer
2. Select counties in sidebar filter
3. Adjust headcount range if needed
4. Click "Download as CSV"
5. Open in Excel/R/Python for further analysis

### Workflow 4: Generate Custom Report
1. Go to 📊 Analytics
2. Screenshot charts you need
3. Go to 🗂️ Data Explorer
4. Download "Summary Stats" CSV
5. Combine in your report document

### Workflow 5: Run Full Pipeline from Scratch
1. Go to ⚙️ Configuration
2. Run Phase 1 (downloads data)
3. Run Phase 3 (generates demand maps)
4. Run Phase 4 (optimization)
5. Return to Home to view results

---

## 📊 Understanding the Optimization

### What the Model Does

The optimization uses **Integer Linear Programming (P-Median formulation)** to minimize:

```
Objective = Σ (headcount[i] × distance[i,j] × assignment[i,j])
```

**Translation:** Minimize total "animal-kilometers" of transport effort across the entire state.

### Constraints

1. **Exactly N facilities** must be selected (user-specified)
2. **Each AFO** must be assigned to exactly one hub
3. **AFOs can only** be assigned to selected hub sites

### What Makes a Good Solution

- **Balanced zones**: Similar total animals per hub
- **Geographic spread**: Hubs distributed across state
- **Minimized transport**: Average distance AFO→Hub is small
- **Practical locations**: Hubs near actual high-density areas

---

## 🔧 Customization

### Change Hub Count

Edit the default in Configuration page or run via CLI:

```bash
python scripts/run_phase4.py --n-sites 5
```

### Add Environmental Constraints

**Future enhancement** - integrate demand maps:

```python
# In optimizer.py
demand_weight = 0.5  # Penalize high-demand areas
```

### Custom Candidate Sites

Instead of using all AFOs as candidates, provide specific locations:

```python
# Create candidate grid or use strategic locations
candidates_gdf = gpd.read_file("custom_sites.geojson")
optimizer.optimize(supply_gdf, candidate_sites=candidates_gdf)
```

---

## 📈 Performance Tips

### Dashboard Loading
- First load caches data (~2 seconds)
- Subsequent page switches are instant
- Filters apply in real-time

### Optimization Runtime
- **3 hubs**: ~90 seconds
- **5 hubs**: ~120 seconds
- **10 hubs**: ~180 seconds
- Scales O(n²) with number of AFOs

### Large Datasets
- Dashboard handles 442 AFOs smoothly
- Map rendering is client-side (Folium)
- Use filters in Data Explorer for big exports

---

## 🐛 Troubleshooting

### "Could not load data"
**Solution:**
1. Check ⚙️ Configuration page status
2. Ensure Phase 4 has been run
3. Verify files exist in `data/processed/optimization/`

### Map not displaying
**Solution:**
- Check browser console for JavaScript errors
- Ensure AFOs have valid `geometry` column
- Try refreshing the page

### Charts showing wrong data
**Solution:**
- Clear Streamlit cache: Hamburger menu → "Clear cache"
- Restart dashboard: `Ctrl+C`, then `streamlit run app.py`

### Export downloads empty file
**Solution:**
- Apply filters first
- Check that filtered dataset has results
- Try different export format (CSV vs GeoJSON)

---

## 📚 Technical Details

### Data Files Used

| File | Purpose | Size |
|------|---------|------|
| `afo_permits.gpkg` | Source AFO database | ~180 KB |
| `optimal_digester_sites.geojson` | Hub locations | ~5 KB |
| `afo_assignments.geojson` | AFO→Hub mappings | ~150 KB |
| `N_demand.tif` | Nitrogen demand raster | 354 MB |
| `P2O5_demand.tif` | Phosphorus demand raster | 354 MB |

### Dashboard Stack

- **Framework**: Streamlit 1.54
- **Geospatial**: GeoPandas, Folium, Streamlit-Folium
- **Charts**: Plotly Express
- **Data**: Pandas, NumPy

### Map Specifications

- **CRS**: EPSG:4326 (WGS84)
- **Bounds**: Maryland state (37.88°N to 39.72°N, -79.48°W to -75.04°W)
- **Min Zoom**: 7 (state-wide view)
- **Max Bounds**: Locked to Maryland

---

## 🚀 Next Features (Roadmap)

- [ ] **Time-series view** of AFO growth over years
- [ ] **Scenario comparison** (compare 3-hub vs 5-hub solutions)
- [ ] **Cost modeling** (construction + transport costs)
- [ ] **Environmental impact** (nutrient runoff reduction estimates)
- [ ] **Route planning** (optimal truck routes AFO→Hub)
- [ ] **Capacity constraints** (max animals per hub)
- [ ] **Multi-objective** (cost + environmental + equity)

---

## 📞 Support

**Documentation:**
- `ANALYSIS.md` - Original pipeline issues
- `FIXES_APPLIED.md` - What was fixed
- `README.md` - Project overview

**Common Commands:**
```bash
# Launch dashboard
streamlit run app.py

# Re-run optimization
python scripts/run_phase4.py --n-sites 3

# Run full pipeline
python scripts/run_phase1.py
python scripts/run_phase3.py
python scripts/run_phase4.py
```

**Created:** 2026-03-07
**Version:** 1.0
**Status:** Production Ready ✅
