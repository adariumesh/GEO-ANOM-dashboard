# GEO-ANOM Pipeline Analysis & Issues

**Date:** 2026-03-07
**Status:** Critical Workflow Issues Identified

---

## Executive Summary

The GEO-ANOM pipeline has **fundamental architectural flaws** that prevent it from functioning as described. The dashboard claims to optimize 442 AFOs but actually processes only 71 AI-detected structures, many with zero headcount data. The workflow inverts the logical data flow by attempting to use uncertain AI detections as primary supply sources instead of validated permit data.

---

## Critical Issues Identified

### 1. **Inverted Data Flow Architecture** 🔴 CRITICAL

**Problem:**
The current pipeline tries to use AI detections (71 uncertain structures) as the primary optimization input instead of the known AFO permit database (442 validated facilities).

**Current Broken Flow:**
```
Phase 1: Download 442 AFO permits ✅
    ↓
Phase 2: Run YOLO on satellite tiles → Detect 71 structures
    ↓ (loses 371 AFOs!)
Phase 3: [Skipped/Incomplete]
    ↓
Phase 4: Optimize 71 AI detections (not 442 real AFOs) ❌
    ↓
Dashboard: Claims "442 AFOs optimized" (LIE) ❌
```

**Correct Flow Should Be:**
```
Phase 1: Download 442 AFO permits ✅
    ↓
Phase 2: [OPTIONAL] Use AI to verify/enhance permit locations
    ↓
Phase 3: Calculate demand maps from crop data
    ↓
Phase 4: Optimize ALL 442 known AFO permits ✅
    ↓
Dashboard: Show actual 442 AFO optimization results
```

---

### 2. **Missing/Invalid Data in Optimization** 🔴 CRITICAL

**Evidence from `afo_assignments.geojson`:**
```json
{
  "class_name": "grain silo",
  "confidence": 0.0365,
  "farm_name": null,          ← Missing!
  "animal_type": "unknown",   ← Missing!
  "headcount": 0,             ← Zero animals = zero nutrients!
  "annual_N_lbs": 0.0,
  "annual_P2O5_lbs": 0.0,
  "assigned_site_idx": 14
}
```

**Impact:**
- **Only 71 structures** detected vs 442 real AFOs (83% data loss)
- Many have **zero headcount** (cannot calculate nutrient supply)
- Many have **null farm_name** (cannot trace to permits)
- Optimization is based on **incomplete, low-confidence detections**

---

### 3. **Misleading Dashboard Claims** 🟠 HIGH

**File:** `app.py:16`

```python
st.markdown("""
1. **Phase 1 (Data Ingestion)**: Automatically targets and downloads permit
   data for all **442 active Animal Feeding Operations (AFOs)** in Maryland...
4. **Phase 4 (Geospatial Optimization)**: Runs a massive ILP (Integer Linear
   Programming) P-Median solver to minimize transport distances between the
   high-supply AFOs and the demand zones.
""")
```

**Reality:**
- Optimization input: **71 AI detections** (not 442 permits)
- Many detections have **zero nutrient data**
- No actual demand zone integration (Phase 3 incomplete)

---

### 4. **Phase 2 Should Be Optional, Not Required** 🟠 HIGH

**Current Problem:**
Phase 2 (AI detection) acts as a bottleneck that filters out most AFOs. It should be a validation/enhancement step, not a replacement for known permit data.

**Why AI Detection is Failing:**
- YOLO-World confidence threshold too low (0.0365 - essentially random)
- Detecting "grain silos" and "ponds" not actual livestock structures
- Limited NAIP tile coverage (not all 442 AFOs have imagery downloaded)
- Zero-shot models need fine-tuning for Maryland-specific structures

**Proper Use of Phase 2:**
- **Primary Source:** AFO permit database (442 known locations)
- **AI Enhancement:** Verify permit addresses, estimate building footprints
- **Flag Anomalies:** Identify permits without visible structures
- **Do NOT discard permits** just because AI didn't detect them

---

### 5. **Phase 3 Demand Mapping Not Integrated** 🟡 MEDIUM

**Status:** Code exists but not connected to Phase 4

Files present:
- `data/processed/demand_maps/N_demand.tif` ✅
- `data/processed/demand_maps/P2O5_demand.tif` ✅

**Problem:**
Phase 4 optimizer does NOT use demand maps. From `optimizer.py:56`:

```python
def optimize(
    self,
    supply_gdf: gpd.GeoDataFrame,
    demand_map: dict[str, np.ndarray] | None = None,  ← Always None!
```

The optimizer only minimizes transport distance weighted by headcount. It ignores:
- Where crops actually need nutrients
- Waterway setback regulations
- Nutrient balance (supply - demand)

---

### 6. **Dummy/Placeholder Logic Still Present** 🟡 MEDIUM

**Example from `run_phase2.py:109-156`:**

When YOLO produces no detections, the code generates "fallback boxes" by creating fake 100×100 pixel bounding boxes around permit coordinates. This is a testing shim that should not be in production.

---

## Data Inventory

### What Actually Exists

| File | Status | Records | Quality |
|------|--------|---------|---------|
| `afo_permits.gpkg` | ✅ Complete | 442 | High (real permit data) |
| `optimal_digester_sites.geojson` | ⚠️ Wrong Input | 3 | Based on 71 detections |
| `afo_assignments.geojson` | ⚠️ Wrong Input | 71 | Missing headcounts, sparse |
| `yolo_detections.geojson` | ⚠️ Low Quality | 71 | Low confidence (avg 0.02) |
| `N_demand.tif` / `P2O5_demand.tif` | ✅ Exists | State-wide | Unused! |

### What's Missing

1. **Correct Phase 4 input**: Should be 442 permits, not 71 detections
2. **Demand integration**: Demand maps exist but aren't used
3. **Supply calculation**: Most detections have `annual_N_lbs: 0.0`
4. **Proper spatial join**: AI detections → permits join is incomplete

---

## Proposed Fixes

### Immediate (Get Dashboard Working)

**Priority 1: Bypass Broken Phase 2**

Create a new Phase 4 runner that directly uses AFO permits:

```bash
python scripts/run_phase4.py --permits data/processed/afo_permits.gpkg --n-sites 3
```

This will:
- Use all 442 real AFOs (not AI detections)
- Use actual headcount data from permits
- Produce meaningful optimization results

**Priority 2: Update Dashboard**

Fix `app.py` to:
- Load correct AFO count
- Show real supply data
- Remove misleading "AI Detection" claims if not actually used

---

### Medium-Term (Fix Phase 2 Integration)

**Option A: Make Phase 2 Truly Optional**

```python
# In run_phase4.py
if Path("data/processed/supply_maps/nutrient_supply.gpkg").exists():
    # Use AI-enhanced supply data
    supply_gdf = gpd.read_file("data/processed/supply_maps/nutrient_supply.gpkg")
else:
    # Fallback to raw permits
    supply_gdf = gpd.read_file("data/processed/afo_permits.gpkg")
```

**Option B: Fix AI Detection Quality**

- Fine-tune YOLO on Maryland aerial imagery
- Increase confidence threshold (0.25+ minimum)
- Better spatial join logic (permits → detections matching)

---

### Long-Term (Proper Multi-Phase Integration)

**Phase 3 → Phase 4 Connection:**

```python
# In optimizer.py
def optimize(self, supply_gdf, demand_map, ...):
    # 1. Load demand rasters
    # 2. Sample demand at candidate sites
    # 3. Penalize sites in high-demand (deficit) areas
    # 4. Bonus points for surplus areas
```

**Environmental Constraints:**

- Apply waterway setbacks to candidate sites
- Ensure digesters are on low-value land (not prime cropland)
- Consider road network access for transport

---

## Recommendations

### For Working Demo

1. **Bypass Phase 2 entirely** for the dashboard
2. **Run Phase 4 directly on permits:**
   ```bash
   python scripts/run_phase4.py --permits data/processed/afo_permits.gpkg --n-sites 3
   ```
3. **Update dashboard** to show 442 real AFOs
4. **Remove AI detection** references from UI (not working)

### For Production System

1. **Redefine Phase 2** as optional enhancement (not filter)
2. **Integrate Phase 3** demand maps into Phase 4
3. **Add validation** layer comparing permits ↔ AI detections
4. **Build training dataset** for Maryland-specific YOLO fine-tuning
5. **Create confidence scoring:** permit + imagery + embeddings → confidence %

---

## Testing the Fix

After implementing Priority 1 fix, verify:

```bash
# Should produce 442 assignments (not 71)
python3 -c "
import geopandas as gpd
afos = gpd.read_file('data/processed/optimization/afo_assignments.geojson')
print(f'Total AFOs: {len(afos)}')
print(f'AFOs with headcount > 0: {(afos.headcount > 0).sum()}')
print(f'Total animals: {afos.headcount.sum():,.0f}')
"

# Dashboard should load without errors
streamlit run app.py
```

---

## Conclusion

**The current pipeline is a proof-of-concept with disconnected phases.** Phase 1 works perfectly, Phase 2 produces low-quality results that break the downstream flow, Phase 3 exists but isn't used, and Phase 4 operates on bad data.

**Quick Win:** Bypass Phase 2, run Phase 4 on raw permits, get a working 442-AFO optimization dashboard.

**Long-term:** Redesign Phase 2 as validation (not replacement), integrate demand maps, and create a proper end-to-end workflow.
