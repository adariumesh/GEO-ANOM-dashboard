# GEO-ANOM Quick Start Guide

**Get running in 60 seconds**

---

## Step 1: Install Dependencies

```bash
cd "Helmets Kenya/GEO-AI"
pip install -e ".[dev]"
```

**Note:** If you already have the data files, skip to Step 3.

---

## Step 2: Get Data (First Time Only)

### Option A: Use Existing Data ✅ Recommended
The repository already includes processed optimization results. Skip to Step 3.

### Option B: Download Fresh Data
```bash
# Download AFO permits (takes ~30 seconds)
python scripts/run_phase1.py

# Generate demand maps (takes ~5 minutes)
python scripts/run_phase3.py

# Run optimization (takes ~90 seconds)
python scripts/run_phase4.py --n-sites 3
```

---

## Step 3: Launch Dashboard

```bash
streamlit run app.py
```

Opens in browser at `http://localhost:8501`

---

## What You'll See

### 🗺️ Home Page
- Interactive map of Maryland
- 350 AFOs colored by hub zone
- 3 optimal digester locations
- Statistics overlay

### 📊 Analytics Page
- 10+ interactive charts
- County distributions
- Animal type breakdowns
- Hub zone analysis

### 🗂️ Data Explorer Page
- Filter 442 facilities
- Sort and search
- Export CSV/GeoJSON
- View hub assignments

### ⚙️ Configuration Page
- Re-run optimization
- Adjust hub count
- Check pipeline status
- System information

---

## Common Tasks

### Re-optimize with Different Hub Count
1. Go to ⚙️ Configuration page
2. Change "Number of Digester Hubs" to 5
3. Click "Run Optimization"
4. Wait ~2 minutes
5. Refresh Home page

### Export County Data
1. Go to 🗂️ Data Explorer
2. Select counties in sidebar
3. Click "Download as CSV"
4. Open in Excel/Python

### View Analytics
1. Go to 📊 Analytics
2. Scroll through charts
3. Screenshot for reports
4. Download summary stats

---

## Troubleshooting

### "Could not load data"
**Fix:** Run Phase 4 to generate optimization results
```bash
python scripts/run_phase4.py --n-sites 3
```

### "Module not found"
**Fix:** Install dependencies
```bash
pip install -e ".[dev]"
```

### Dashboard won't start
**Fix:** Check Python version (need 3.10+)
```bash
python3 --version
```

---

## Next Steps

- Read **[DASHBOARD_GUIDE.md](DASHBOARD_GUIDE.md)** for detailed features
- Read **[PRODUCT_SUMMARY.md](PRODUCT_SUMMARY.md)** for architecture
- Explore the multi-page dashboard
- Try different optimization parameters
- Export data for your analysis

---

**Ready to go!** 🚀

For help: See DASHBOARD_GUIDE.md or PRODUCT_SUMMARY.md
