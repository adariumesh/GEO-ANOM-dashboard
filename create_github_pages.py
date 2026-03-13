#!/usr/bin/env python3
"""
Create GitHub Pages deployment with interactive map and documentation.
"""

import geopandas as gpd
import folium
import pandas as pd
from pathlib import Path
import shutil

print("🚀 Creating GitHub Pages deployment...")

# Create docs directory for GitHub Pages
docs_dir = Path("docs")
docs_dir.mkdir(exist_ok=True)

# Load data
print("📊 Loading optimization data...")
sites = gpd.read_file("data/processed/scenarios/scenario_10hubs/optimal_hubs_realistic.geojson")
afos = gpd.read_file("data/processed/scenarios/scenario_10hubs/afo_assignments_realistic.geojson")

# Create interactive map
print("🗺️ Creating interactive map...")
m = folium.Map(
    location=[39.0, -76.7],
    zoom_start=8,
    min_zoom=7,
    max_bounds=True,
    tiles='OpenStreetMap'
)

# Colors for 10 hubs
colors = ['red', 'blue', 'green', 'purple', 'orange', 'darkred', 'darkblue', 'darkgreen', 'cadetblue', 'pink']

# Add title and info box
title_html = '''
<div style="position: fixed;
     top: 20px; left: 50%; transform: translateX(-50%);
     width: 700px; height: auto;
     background-color:white; border:3px solid #2c3e50; z-index:9999;
     padding: 15px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
     <h2 style="margin:0; color:#2c3e50; text-align:center;">Maryland Regional Digester Network</h2>
     <p style="margin:5px 0; text-align:center; font-size:16px;"><b>10-Hub Optimal Solution</b></p>
     <div style="display:flex; justify-content:space-around; margin-top:10px; font-size:13px;">
         <div><b>💰 NPV:</b> $141.7M</div>
         <div><b>⚡ Payback:</b> 7.2 months</div>
         <div><b>🏭 AFOs:</b> 334</div>
         <div><b>🐔 Animals:</b> 41.2M</div>
     </div>
</div>
'''
m.get_root().html.add_child(folium.Element(title_html))

# Add legend
legend_html = '''
<div style="position: fixed;
     bottom: 30px; left: 30px; width: 220px; height: auto;
     background-color:white; border:2px solid grey; z-index:9999; font-size:12px;
     padding: 12px; border-radius: 8px; max-height: 450px; overflow-y: auto;">
     <b style="font-size:14px;">🏭 Hub Network</b><br>
     <hr style="margin: 8px 0;">
     <b>Hub Locations:</b><br>
     <div style="line-height: 1.8;">
     ''' + ''.join([f'&nbsp; <i class="fa fa-map-marker" style="color:{colors[i]}"></i> Hub {i} ({sites.iloc[i]["county"] if i < len(sites) else ""})<br>'
                    for i in range(min(10, len(sites)))]) + '''
     </div>
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
print("  Adding 334 AFO locations...")
for idx, row in afos.iterrows():
    if row.geometry is None or row.geometry.is_empty:
        continue

    site_idx = int(row.get("assigned_site_idx", 0))
    color = colors[site_idx % len(colors)]
    headcount = row.get('headcount', 0)

    # Size by headcount
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

    tooltip = f"""
    <b>{row.get('farm_name', 'Unknown AFO')}</b><br>
    Animals: {headcount:,}<br>
    Type: {row.get('animal_type', 'Unknown')}<br>
    County: {row.get('county', 'Unknown')}<br>
    Assigned to Hub {site_idx}
    """

    folium.CircleMarker(
        location=[row.geometry.centroid.y, row.geometry.centroid.x],
        radius=radius,
        color=color,
        fill=True,
        fill_opacity=0.6,
        weight=1,
        tooltip=tooltip
    ).add_to(m)

# Add Hubs
print("  Adding 10 hub locations...")
for idx, row in sites.iterrows():
    site_id = row.get('site_id', idx)
    color = colors[int(site_id) % len(colors)]
    county = row.get('county', 'Unknown')
    zone_afos = row.get('zone_afos', 0)
    zone_animals = row.get('zone_animals', 0)
    capacity_pct = (zone_animals / 5_000_000 * 100) if zone_animals > 0 else 0

    popup_html = f"""
    <div style="width:200px;">
        <h4 style="margin:0;">Hub {site_id}</h4>
        <hr style="margin:5px 0;">
        <b>County:</b> {county}<br>
        <b>AFOs Served:</b> {zone_afos}<br>
        <b>Animals:</b> {zone_animals:,.0f}<br>
        <b>Capacity:</b> {capacity_pct:.0f}%<br>
        <hr style="margin:5px 0;">
        <small>Click for details</small>
    </div>
    """

    folium.Marker(
        location=[row.geometry.centroid.y, row.geometry.centroid.x],
        icon=folium.Icon(color=color, icon='industry', prefix='fa'),
        tooltip=f"Hub {site_id} - {county} County",
        popup=folium.Popup(popup_html, max_width=250)
    ).add_to(m)

# Save map
map_path = docs_dir / "index.html"
m.save(str(map_path))
print(f"✅ Interactive map saved: {map_path}")

# Create data page
print("📄 Creating data summary page...")
data_html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Maryland Regional Digester Network - Analysis Data</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }}
        .header {{
            background: linear-gradient(135deg, #2c3e50 0%, #3498db 100%);
            color: white;
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 30px;
        }}
        .header h1 {{
            margin: 0 0 10px 0;
        }}
        .metric {{
            display: inline-block;
            margin: 10px 20px 10px 0;
            padding: 10px 15px;
            background: rgba(255,255,255,0.2);
            border-radius: 5px;
        }}
        .section {{
            background: white;
            padding: 25px;
            margin-bottom: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background: #3498db;
            color: white;
        }}
        tr:hover {{
            background: #f5f5f5;
        }}
        .button {{
            display: inline-block;
            padding: 12px 24px;
            background: #3498db;
            color: white;
            text-decoration: none;
            border-radius: 5px;
            margin: 10px 10px 10px 0;
        }}
        .button:hover {{
            background: #2980b9;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Maryland Regional Digester Network</h1>
        <p style="font-size: 18px; margin: 5px 0;">Comprehensive Analysis - March 2026</p>
        <div class="metric"><b>💰 5-Year NPV:</b> $141.7M</div>
        <div class="metric"><b>⚡ Payback:</b> 7.2 months</div>
        <div class="metric"><b>📈 ROI:</b> 709%</div>
        <div class="metric"><b>🏭 AFOs:</b> 334</div>
        <div class="metric"><b>🐔 Animals:</b> 41.2M</div>
    </div>

    <div class="section">
        <h2>🎯 Optimal Solution: 10 Regional Hubs</h2>
        <p>After testing multiple scenarios (8, 10, 15 hubs) and conducting comprehensive economic sensitivity analysis,
        <b>10 hubs emerged as the optimal configuration</b>.</p>

        <a href="index.html" class="button">📍 View Interactive Map</a>
        <a href="reports.html" class="button">📊 View Full Reports</a>
    </div>

    <div class="section">
        <h2>🏭 Hub Performance Details</h2>
        <table>
            <tr>
                <th>Hub ID</th>
                <th>County</th>
                <th>AFOs Served</th>
                <th>Animals</th>
                <th>Capacity</th>
            </tr>
"""

for idx, row in sites.iterrows():
    site_id = row.get('site_id', idx)
    county = row.get('county', 'Unknown')
    zone_afos = row.get('zone_afos', 0)
    zone_animals = row.get('zone_animals', 0)
    capacity_pct = (zone_animals / 5_000_000 * 100) if zone_animals > 0 else 0

    data_html += f"""
            <tr>
                <td>Hub {site_id}</td>
                <td>{county}</td>
                <td>{zone_afos}</td>
                <td>{zone_animals:,.0f}</td>
                <td>{capacity_pct:.0f}%</td>
            </tr>
"""

data_html += """
        </table>
    </div>

    <div class="section">
        <h2>📊 Scenario Comparison</h2>
        <table>
            <tr>
                <th>Configuration</th>
                <th>Construction</th>
                <th>5-Year NPV</th>
                <th>Payback</th>
                <th>Assessment</th>
            </tr>
            <tr>
                <td>8 Hubs</td>
                <td>$16M</td>
                <td>$132.5M</td>
                <td>6.5 months</td>
                <td>⚠️ Too constrained</td>
            </tr>
            <tr style="background: #e8f5e9;">
                <td><b>10 Hubs ⭐</b></td>
                <td><b>$20M</b></td>
                <td><b>$141.7M</b></td>
                <td><b>7.4 months</b></td>
                <td><b>✅ Optimal</b></td>
            </tr>
            <tr>
                <td>15 Hubs</td>
                <td>$30M</td>
                <td>$138.2M</td>
                <td>10.7 months</td>
                <td>⚠️ Underutilized</td>
            </tr>
        </table>
    </div>

    <div class="section">
        <h2>💰 Economic Performance</h2>
        <p><b>Annual Revenue:</b> $38.4M</p>
        <ul>
            <li>Energy sales: $19.1M/year (159 GWh @ $0.12/kWh)</li>
            <li>Digestate fertilizer: $19.3M/year (1.29M tons @ $15/ton)</li>
        </ul>

        <p><b>Annual Costs:</b> $8.8M</p>
        <ul>
            <li>Transport: $6.0M/year</li>
            <li>Operations: $2.8M/year</li>
        </ul>

        <p><b>Net Annual Cash Flow:</b> $29.6M/year</p>
    </div>

    <div class="section">
        <h2>📍 Implementation Roadmap</h2>
        <h3>Phase 1 (Year 1): Worcester County Pilot</h3>
        <ul>
            <li>Deploy: 2-3 hubs</li>
            <li>Investment: $4-6M</li>
            <li>Objective: Validate model</li>
        </ul>

        <h3>Phase 2 (Years 2-3): Regional Expansion</h3>
        <ul>
            <li>Add: 4 hubs (Caroline, Wicomico, Somerset)</li>
            <li>Investment: $8M</li>
            <li>Objective: Scale operations</li>
        </ul>

        <h3>Phase 3 (Years 4-5): Full Network</h3>
        <ul>
            <li>Complete: Final 3 hubs</li>
            <li>Investment: $6M</li>
            <li>Objective: Full coverage, maximum returns</li>
        </ul>
    </div>

    <div class="section">
        <h2>📧 Contact & More Information</h2>
        <p>For detailed analysis reports, methodology, and data files, visit the
        <a href="https://github.com/adariumesh/GEO-ANOM-dashboard">GitHub repository</a>.</p>

        <p><b>Analysis Date:</b> March 2026<br>
        <b>Platform:</b> GEO-ANOM (Geospatial AI for Optimal Network Modeling)</p>
    </div>
</body>
</html>
"""

# Save data page
data_page_path = docs_dir / "data.html"
with open(data_page_path, 'w') as f:
    f.write(data_html)
print(f"✅ Data summary page saved: {data_page_path}")

# Copy markdown reports
print("📋 Copying analysis reports...")
reports_to_copy = [
    "EXECUTIVE_SUMMARY.md",
    "FULL_ANALYSIS_REPORT.md",
    "day1_summary.md",
    "day2_summary.md",
    "day4_summary.md",
    "day5_summary.md"
]

for report in reports_to_copy:
    src = Path("data/processed") / report
    if src.exists():
        shutil.copy(src, docs_dir / report)
        print(f"  ✓ Copied {report}")

# Create README for GitHub
readme_content = """# Maryland Regional Digester Network - Analysis Dashboard

**Live Dashboard:** [View Interactive Map](https://adariumesh.github.io/GEO-ANOM-dashboard/)

## 🎯 Key Finding

**Optimal Solution: 10 Regional Digester Hubs**

- **Investment:** $20 million
- **5-Year NPV:** $141.7 million
- **Payback:** 7.2 months
- **ROI:** 709%
- **Coverage:** 334 AFOs, 41.2M animals

## 📊 What's Included

### Interactive Map
- 10 hub locations across Maryland's Eastern Shore
- 334 AFO facilities with assignments
- Click on markers for detailed information
- County-level distribution

### Analysis Reports
- Executive Summary (2 pages)
- Full Analysis Report (20 pages)
- Daily work summaries (5 days)
- Economic sensitivity analysis
- County-level reports

## 🗺️ View the Dashboard

**[Click here to view the interactive map →](https://adariumesh.github.io/GEO-ANOM-dashboard/)**

## 📄 Documentation

- [Executive Summary](docs/EXECUTIVE_SUMMARY.md)
- [Full Analysis Report](docs/FULL_ANALYSIS_REPORT.md)
- [Data Summary](https://adariumesh.github.io/GEO-ANOM-dashboard/data.html)

## 🚀 Analysis Methodology

- **Optimization:** P-Median location-allocation with capacity constraints
- **Solver:** Integer Linear Programming (PuLP + CBC)
- **Data:** 442 AFO permits, 350 with coordinates
- **Scenarios:** 8, 10, 15 hub configurations tested
- **Economics:** Revenue modeling, NPV analysis, sensitivity testing

## 📧 Contact

For questions about this analysis, please open an issue.

---

**Analysis Date:** March 2026
**Platform:** GEO-ANOM (Geospatial AI for Optimal Network Modeling)
"""

with open("README.md", 'w') as f:
    f.write(readme_content)
print("✅ README.md created")

print("\n" + "="*60)
print("✅ GitHub Pages deployment ready!")
print("="*60)
print("\n📁 Files created in docs/ directory:")
print("  - index.html (interactive map)")
print("  - data.html (data summary)")
print("  - *.md (analysis reports)")
print("\n🚀 Next steps:")
print("  1. Push to GitHub: git add . && git commit -m 'Add analysis' && git push")
print("  2. Enable GitHub Pages in repo settings")
print("  3. Set source to 'main' branch, '/docs' folder")
print("  4. Your site will be live at:")
print("     https://adariumesh.github.io/GEO-ANOM-dashboard/")
print("\n" + "="*60)
