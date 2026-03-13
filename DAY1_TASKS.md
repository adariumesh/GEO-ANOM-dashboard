# Day 1: Geocode Missing AFOs & Establish Baseline

**Time:** 4-6 hours
**Status:** IN PROGRESS

---

## 🎯 Goal

Get maximum AFO coverage by geocoding the 92 facilities missing coordinates, then establish baseline optimization results.

---

## ✅ Task Checklist

### Part 1: Analyze Current Data (30 min)

- [ ] **Task 1.1:** Check current data quality
```bash
python3 -c "
import geopandas as gpd
afos = gpd.read_file('data/processed/afo_permits.gpkg')
print(f'Total AFOs: {len(afos)}')
print(f'With coordinates: {(~afos.geometry.is_empty).sum()}')
print(f'Missing coordinates: {(afos.geometry.is_empty).sum()}')
print(f'With headcount: {(afos.headcount > 0).sum()}')
"
```

- [ ] **Task 1.2:** Export missing AFOs list
```bash
python3 -c "
import geopandas as gpd
afos = gpd.read_file('data/processed/afo_permits.gpkg')
missing = afos[afos.geometry.is_empty][['farm_name', 'city', 'county', 'zip_code']]
missing.to_csv('data/processed/missing_coords.csv', index=False)
print(f'Exported {len(missing)} AFOs with missing coordinates')
"
```

---

### Part 2: Geocode Missing AFOs (1-2 hours)

The geocoding code is already in the system. Let's use it:

- [ ] **Task 2.1:** Check if geocoding module works
```bash
python3 -c "
from geo_anom.phase1.afo_registry import AFORegistryClient
from geo_anom.core.config import get_config
print('✓ Geocoding module imported successfully')
"
```

- [ ] **Task 2.2:** Create geocoding script

I'll create this for you - see `scripts/geocode_missing.py` below

- [ ] **Task 2.3:** Run geocoding
```bash
python scripts/geocode_missing.py
```

**Expected result:** 50-70 additional AFOs get coordinates

---

### Part 3: Re-run Optimization with Full Data (1 hour)

- [ ] **Task 3.1:** Run realistic optimization with updated data
```bash
python scripts/realistic_optimization.py --region eastern-shore --n-sites 12
```

- [ ] **Task 3.2:** Compare before/after
```bash
python3 scripts/compare_results.py
```

---

### Part 4: Document Baseline (1 hour)

- [ ] **Task 4.1:** Create baseline report
```bash
python scripts/generate_baseline_report.py
```

- [ ] **Task 4.2:** Take screenshots
  - Dashboard map view
  - Analytics charts
  - Optimization summary

- [ ] **Task 4.3:** Save baseline metrics
  - Number of AFOs optimized
  - Total animals
  - Transport cost
  - Hub locations

---

## 📝 Scripts You Need

I'll create these scripts for you now:

1. `scripts/geocode_missing.py` - Geocode missing AFOs
2. `scripts/compare_results.py` - Compare before/after
3. `scripts/generate_baseline_report.py` - Create baseline document

---

## 📊 Expected Outcomes

**Before Geocoding:**
- AFOs with coordinates: 350 (79%)
- Missing: 92 (21%)

**After Geocoding:**
- AFOs with coordinates: 400-420 (90-95%)
- Missing: 22-42 (5-10%)

**Improvement:** +50-70 mappable facilities

---

## 🎯 Success Criteria

Day 1 is successful if you have:
- ✅ Geocoded as many missing AFOs as possible
- ✅ Updated afo_permits.gpkg file
- ✅ Baseline optimization results documented
- ✅ Before/after comparison showing improvement

---

## 🚀 Let's Start!

Run the first command now to see your current data quality.
