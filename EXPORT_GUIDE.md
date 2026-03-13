# Export & Sharing Guide
## How to Share GEO-ANOM Analysis Results

**Multiple methods to share your 5-day analysis with your professor**

---

## 📦 Method 1: PDF Report Package (RECOMMENDED)

**Best for:** Email attachment, professional presentation
**Time:** 5 minutes

### Option A: Convert Markdown to PDF (Pandoc)

```bash
cd "/Users/adariprasad/weapon/Helmets Kenya/GEO-AI/data/processed"

# Install pandoc if needed
brew install pandoc

# Convert reports to PDF
pandoc EXECUTIVE_SUMMARY.md -o EXECUTIVE_SUMMARY.pdf \
  --pdf-engine=wkhtmltopdf \
  -V geometry:margin=1in \
  --metadata title="Maryland Regional Digester Network - Executive Summary"

pandoc FULL_ANALYSIS_REPORT.md -o FULL_ANALYSIS_REPORT.pdf \
  --pdf-engine=wkhtmltopdf \
  -V geometry:margin=1in \
  --metadata title="Maryland AFO Analysis - Full Report"

pandoc PRESENTATION_DECK.md -o PRESENTATION_DECK.pdf \
  --pdf-engine=wkhtmltopdf \
  -V geometry:margin=1in \
  --metadata title="Regional Digester Network - Presentation"
```

### Option B: Markdown to PDF via VS Code

If you have VS Code:
1. Open `EXECUTIVE_SUMMARY.md`
2. Install "Markdown PDF" extension (yzane.markdown-pdf)
3. Right-click → "Markdown PDF: Export (pdf)"
4. Repeat for other files

### Option C: Use Online Converter

1. Go to https://www.markdowntopdf.com/
2. Upload each .md file
3. Download generated PDFs

---

## 📊 Method 2: Static HTML Dashboard Export

**Best for:** Interactive viewing without running code
**Time:** 2 minutes

### Create Standalone HTML

```bash
cd "/Users/adariprasad/weapon/Helmets Kenya/GEO-AI"

# Install required package
pip install streamlit-static

# Export dashboard to static HTML
streamlit run app.py --server.headless true &
sleep 10

# Or use alternative: Export map as HTML
python3 << 'EOF'
import geopandas as gpd
import folium
from pathlib import Path

# Load data
sites = gpd.read_file("data/processed/scenarios/scenario_10hubs/optimal_hubs_realistic.geojson")
afos = gpd.read_file("data/processed/scenarios/scenario_10hubs/afo_assignments_realistic.geojson")

# Create map
m = folium.Map(location=[39.0, -76.7], zoom_start=8)

# Colors for hubs
colors = ['red', 'blue', 'green', 'purple', 'orange', 'darkred', 'darkblue', 'darkgreen', 'cadetblue', 'pink']

# Add AFOs
for idx, row in afos.iterrows():
    if row.geometry is None or row.geometry.is_empty:
        continue
    site_idx = int(row.get("assigned_site_idx", 0))
    color = colors[site_idx % len(colors)]
    headcount = row.get('headcount', 0)

    radius = 2 if headcount == 0 else (3 if headcount < 10000 else (5 if headcount < 100000 else (8 if headcount < 1000000 else 12)))

    folium.CircleMarker(
        location=[row.geometry.centroid.y, row.geometry.centroid.x],
        radius=radius,
        color=color,
        fill=True,
        fill_opacity=0.7,
        tooltip=f"{row.get('farm_name', 'Unknown')}<br>Animals: {headcount:,}<br>Hub {site_idx}"
    ).add_to(m)

# Add hubs
for idx, row in sites.iterrows():
    site_id = row.get('site_id', idx)
    color = colors[int(site_id) % len(colors)]
    county = row.get('county', 'Unknown')
    zone_afos = row.get('zone_afos', 0)
    zone_animals = row.get('zone_animals', 0)
    capacity_pct = (zone_animals / 5_000_000 * 100) if zone_animals > 0 else 0

    tooltip = f"<b>Hub {site_id}</b><br>County: {county}<br>AFOs: {zone_afos}<br>Animals: {zone_animals:,.0f}<br>Capacity: {capacity_pct:.0f}%"

    folium.Marker(
        location=[row.geometry.centroid.y, row.geometry.centroid.x],
        icon=folium.Icon(color=color, icon='industry', prefix='fa'),
        tooltip=tooltip,
        popup=tooltip
    ).add_to(m)

# Add title
title_html = '''
<div style="position: fixed;
     top: 10px; left: 50px; width: 500px; height: 90px;
     background-color:white; border:2px solid grey; z-index:9999; font-size:14px;
     padding: 10px;">
     <h3 style="margin:0;">Maryland Regional Digester Network</h3>
     <p style="margin:5px 0;"><b>10-Hub Optimal Solution</b></p>
     <p style="margin:0; font-size:12px;">NPV: $141.7M | Payback: 7.2 months | 334 AFOs</p>
</div>
'''
m.get_root().html.add_child(folium.Element(title_html))

# Save
m.save("data/processed/INTERACTIVE_MAP.html")
print("✅ Interactive map saved to: data/processed/INTERACTIVE_MAP.html")
EOF
```

**Share the HTML file:**
- File: `data/processed/INTERACTIVE_MAP.html`
- Can be opened in any browser
- Fully interactive (zoom, click, explore)
- No code execution needed

---

## 📁 Method 3: Complete Analysis Archive

**Best for:** Full reproducibility, GitHub-style sharing
**Time:** 3 minutes

### Create Compressed Archive

```bash
cd "/Users/adariprasad/weapon/Helmets Kenya/GEO-AI"

# Create export directory
mkdir -p exports/maryland_afo_analysis

# Copy all key files
cp -r data/processed/EXECUTIVE_SUMMARY.md exports/maryland_afo_analysis/
cp -r data/processed/FULL_ANALYSIS_REPORT.md exports/maryland_afo_analysis/
cp -r data/processed/PRESENTATION_DECK.md exports/maryland_afo_analysis/
cp -r data/processed/day*.md exports/maryland_afo_analysis/
cp -r data/processed/scenario_comparison.csv exports/maryland_afo_analysis/
cp -r data/processed/county_reports exports/maryland_afo_analysis/
cp -r data/processed/sensitivity_analysis exports/maryland_afo_analysis/
cp -r data/processed/scenarios/scenario_10hubs exports/maryland_afo_analysis/optimal_solution
cp README.md exports/maryland_afo_analysis/
cp EXPORT_GUIDE.md exports/maryland_afo_analysis/

# Create a README for the export
cat > exports/maryland_afo_analysis/README_EXPORT.md << 'EOF'
# Maryland AFO Regional Digester Network - Analysis Package

**Date:** March 9, 2026
**Analyst:** GEO-ANOM Team
**Analysis Period:** 5 days (March 6-9, 2026)

## 📊 Contents

### Executive Materials
- `EXECUTIVE_SUMMARY.md` - 2-page overview
- `FULL_ANALYSIS_REPORT.md` - 20-page comprehensive analysis
- `PRESENTATION_DECK.md` - 10-slide presentation outline

### Daily Work Products
- `day1_summary.md` - Data foundation
- `day2_summary.md` - Scenario analysis
- `day3_summary.md` - County reports (not included)
- `day4_summary.md` - Economic sensitivity
- `day5_summary.md` - Final deliverables

### Data Files
- `scenario_comparison.csv` - Hub count comparison
- `county_reports/` - 10 county detailed reports
- `sensitivity_analysis/` - Economic sensitivity datasets
- `optimal_solution/` - 10-hub GeoJSON files

## 🎯 Key Finding

**Optimal Solution: 10 Regional Digester Hubs**
- Investment: $20M
- 5-Year NPV: $141.7M
- Payback: 7.2 months
- ROI: 709%

## 📖 How to Navigate

1. Start with `EXECUTIVE_SUMMARY.md` for overview
2. Read `FULL_ANALYSIS_REPORT.md` for detailed analysis
3. Review `PRESENTATION_DECK.md` for presentation structure
4. Explore data files for raw results

## 🗺️ Interactive Map

See `INTERACTIVE_MAP.html` (if included) for interactive visualization.

## 📧 Contact

For questions about this analysis, contact the GEO-ANOM team.
EOF

# Compress into ZIP
cd exports
zip -r maryland_afo_analysis_march2026.zip maryland_afo_analysis/

echo "✅ Archive created: exports/maryland_afo_analysis_march2026.zip"
echo "📦 Size: $(du -h maryland_afo_analysis_march2026.zip | cut -f1)"
```

**Result:** Single ZIP file containing everything
- File: `exports/maryland_afo_analysis_march2026.zip`
- Size: ~2-5 MB
- Easy to email or upload

---

## 🎤 Method 4: PowerPoint Presentation

**Best for:** In-person or video presentation
**Time:** 10-15 minutes

### Option A: Manual Creation (Recommended for polish)

1. **Open PowerPoint/Keynote/Google Slides**

2. **Use this structure from `PRESENTATION_DECK.md`:**
   - Slide 1: Title & Executive Summary
   - Slide 2: The Opportunity
   - Slide 3: Business Case
   - Slide 4: Why 10 Hubs
   - Slide 5: Geographic Strategy
   - Slide 6: Revenue Model
   - Slide 7: Economic Resilience
   - Slide 8: Environmental Impact
   - Slide 9: Implementation Roadmap
   - Slide 10: Call to Action

3. **Add visuals:**
   - Screenshot the dashboard map
   - Export tables from CSV files
   - Create charts from data
   - Use Maryland state outline graphics

4. **Save as:**
   - `Maryland_Regional_Digester_Analysis.pptx`
   - Or export to PDF: `Maryland_Regional_Digester_Analysis.pdf`

### Option B: Automated Conversion

```bash
# Convert markdown to PowerPoint using Pandoc
cd "/Users/adariprasad/weapon/Helmets Kenya/GEO-AI/data/processed"

pandoc PRESENTATION_DECK.md -o PRESENTATION.pptx \
  --reference-doc=template.pptx  # If you have a template

# Or simple conversion
pandoc PRESENTATION_DECK.md -o PRESENTATION.pptx
```

---

## 🌐 Method 5: Online Hosting (Interactive)

**Best for:** Easy access, no downloads
**Time:** 10-20 minutes

### Option A: GitHub Pages (Static)

```bash
cd "/Users/adariprasad/weapon/Helmets Kenya/GEO-AI"

# Initialize git if not already
git init
git add .
git commit -m "Maryland AFO Analysis - Complete"

# Create GitHub repo and push
# (Follow GitHub instructions to create repo)

# Enable GitHub Pages in repo settings
# Set source to main branch, /docs folder

# Copy key files to docs/
mkdir -p docs
cp data/processed/EXECUTIVE_SUMMARY.md docs/index.md
cp data/processed/INTERACTIVE_MAP.html docs/map.html
cp -r data/processed/county_reports docs/
```

**Share URL:** `https://yourusername.github.io/GEO-AI`

### Option B: Streamlit Cloud (Free Hosting)

1. Push code to GitHub
2. Go to https://streamlit.io/cloud
3. Sign in with GitHub
4. Deploy app from your repo
5. Share URL: `https://yourapp.streamlit.app`

**Pros:** Live interactive dashboard
**Cons:** Requires GitHub account, public repo

### Option C: Google Drive (Simple)

```bash
# Upload key files to Google Drive
# 1. Go to drive.google.com
# 2. Create folder "Maryland AFO Analysis"
# 3. Upload:
#    - EXECUTIVE_SUMMARY.md (or PDF)
#    - FULL_ANALYSIS_REPORT.md (or PDF)
#    - INTERACTIVE_MAP.html
#    - scenario_comparison.csv
#    - county_reports/ folder
# 4. Right-click folder → Share → Get link
# 5. Set to "Anyone with the link can view"
```

**Share:** Google Drive link

---

## 📧 Method 6: Email-Friendly Package

**Best for:** Direct professor email
**Time:** 5 minutes

### Create Email Package

```bash
cd "/Users/adariprasad/weapon/Helmets Kenya/GEO-AI"

mkdir -p exports/email_package

# Core documents (convert to PDF first if possible)
cp data/processed/EXECUTIVE_SUMMARY.md exports/email_package/
cp data/processed/FULL_ANALYSIS_REPORT.md exports/email_package/
cp data/processed/scenario_comparison.csv exports/email_package/
cp data/processed/INTERACTIVE_MAP.html exports/email_package/

# County summary
cp data/processed/county_reports/00_MASTER_SUMMARY.txt exports/email_package/
cp data/processed/county_reports/county_summary.csv exports/email_package/

# Key sensitivity data
cp data/processed/sensitivity_analysis/sensitivity_summary.txt exports/email_package/
cp data/processed/sensitivity_analysis/hub_count_npv_analysis.csv exports/email_package/

# Create cover letter
cat > exports/email_package/COVER_LETTER.txt << 'EOF'
Dear Professor [Name],

I'm pleased to share the results of my 5-day geospatial optimization analysis
for Maryland's Eastern Shore AFO waste management.

KEY FINDING: 10 regional anaerobic digester hubs is the optimal configuration
- Investment: $20 million
- 5-Year NPV: $141.7 million
- Payback: 7.2 months
- ROI: 709%

This analysis tested multiple scenarios (8, 10, 15 hubs), conducted economic
sensitivity testing, and identified Worcester County as the ideal pilot location.

PACKAGE CONTENTS:
1. EXECUTIVE_SUMMARY.md - 2-page overview
2. FULL_ANALYSIS_REPORT.md - 20-page comprehensive analysis
3. INTERACTIVE_MAP.html - Open in browser to explore
4. scenario_comparison.csv - Hub count comparison data
5. county_summary.csv - County-level statistics
6. sensitivity_summary.txt - Economic sensitivity results

The interactive map (INTERACTIVE_MAP.html) can be opened in any web browser
and shows all 10 hub locations with clickable markers.

I'm happy to discuss the methodology and findings at your convenience.

Best regards,
[Your Name]
EOF

# Compress
cd exports
zip -r email_package.zip email_package/

echo "✅ Email package ready: exports/email_package.zip"
echo "📧 Attach to email with COVER_LETTER.txt as email body"
```

**Email Size:** ~2-3 MB (should be within most email limits)

---

## 📊 Method 7: Data Visualization Export

**Best for:** Charts and graphs
**Time:** 10 minutes

### Create Visualization Images

```python
cd "/Users/adariprasad/weapon/Helmets Kenya/GEO-AI"

python3 << 'EOF'
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

# Set style
sns.set_style("whitegrid")
plt.rcParams['figure.figsize'] = (10, 6)

output_dir = Path("exports/visualizations")
output_dir.mkdir(parents=True, exist_ok=True)

# 1. Scenario Comparison Chart
scenarios = pd.DataFrame({
    'Hubs': [8, 10, 15],
    'Construction ($M)': [16, 20, 30],
    'NPV ($M)': [132.5, 141.7, 138.2],
    'Payback (months)': [6.5, 7.4, 10.7]
})

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

ax1.bar(scenarios['Hubs'], scenarios['NPV ($M)'], color=['gray', 'green', 'gray'])
ax1.set_xlabel('Number of Hubs')
ax1.set_ylabel('5-Year NPV ($M)')
ax1.set_title('NPV by Hub Count (10 Hubs Optimal)')
ax1.axhline(y=141.7, color='green', linestyle='--', alpha=0.5)

ax2.plot(scenarios['Hubs'], scenarios['Payback (months)'], marker='o', linewidth=2, markersize=10)
ax2.set_xlabel('Number of Hubs')
ax2.set_ylabel('Payback Period (months)')
ax2.set_title('Payback Period by Hub Count')
ax2.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig(output_dir / 'scenario_comparison.png', dpi=300, bbox_inches='tight')
print("✅ Saved: scenario_comparison.png")

# 2. Revenue Breakdown Pie Chart
plt.figure(figsize=(8, 8))
revenue = [19.1, 19.3]
labels = ['Energy Sales\n$19.1M/year', 'Digestate Sales\n$19.3M/year']
colors = ['#ff9999', '#66b3ff']
explode = (0.05, 0.05)

plt.pie(revenue, labels=labels, colors=colors, autopct='%1.1f%%',
        startangle=90, explode=explode, textprops={'fontsize': 12})
plt.title('Annual Revenue Breakdown ($38.4M Total)', fontsize=14, fontweight='bold')
plt.savefig(output_dir / 'revenue_breakdown.png', dpi=300, bbox_inches='tight')
print("✅ Saved: revenue_breakdown.png")

# 3. County Distribution
county_data = pd.DataFrame({
    'County': ['Worcester', 'Wicomico', 'Caroline', 'Somerset', "Queen Anne's", 'Dorchester'],
    'Hubs': [3, 2, 2, 2, 1, 1],
    'Animals (M)': [12.4, 10.3, 10.0, 8.3, 4.4, 3.6]
})

fig, ax = plt.subplots(figsize=(10, 6))
bars = ax.barh(county_data['County'], county_data['Animals (M)'], color='steelblue')
bars[0].set_color('darkgreen')  # Highlight Worcester
ax.set_xlabel('Animals (Millions)')
ax.set_title('Animal Distribution by County (Worcester = Pilot Location)', fontweight='bold')
ax.grid(axis='x', alpha=0.3)
plt.tight_layout()
plt.savefig(output_dir / 'county_distribution.png', dpi=300, bbox_inches='tight')
print("✅ Saved: county_distribution.png")

# 4. Economic Timeline
years = [0, 1, 2, 3, 4, 5]
cumulative_cashflow = [-20, 9.6, 39.2, 68.8, 98.4, 128.0]

plt.figure(figsize=(10, 6))
plt.plot(years, cumulative_cashflow, marker='o', linewidth=3, markersize=10, color='green')
plt.axhline(y=0, color='red', linestyle='--', alpha=0.5)
plt.fill_between(years, cumulative_cashflow, 0, where=[y >= 0 for y in cumulative_cashflow],
                 alpha=0.3, color='green', label='Profit')
plt.fill_between(years, cumulative_cashflow, 0, where=[y < 0 for y in cumulative_cashflow],
                 alpha=0.3, color='red', label='Investment')
plt.xlabel('Year')
plt.ylabel('Cumulative Cash Flow ($M)')
plt.title('5-Year Financial Projection (Payback at 7.2 months)', fontweight='bold')
plt.legend()
plt.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig(output_dir / 'financial_timeline.png', dpi=300, bbox_inches='tight')
print("✅ Saved: financial_timeline.png")

print(f"\n✅ All visualizations saved to: {output_dir}")
print("📊 Files created:")
print("  - scenario_comparison.png")
print("  - revenue_breakdown.png")
print("  - county_distribution.png")
print("  - financial_timeline.png")
EOF
```

**Use these images in:**
- PowerPoint slides
- Email attachments
- Report illustrations

---

## 🎯 RECOMMENDED WORKFLOW

### For Quick Share (5 minutes):
1. **Create interactive map HTML** (Method 2)
2. **Email to professor with:**
   - `INTERACTIVE_MAP.html` attached
   - Link to `EXECUTIVE_SUMMARY.md` (paste in email body or attach)
   - Brief cover note

### For Professional Package (15 minutes):
1. **Convert key docs to PDF** (Method 1)
2. **Create visualizations** (Method 7)
3. **Build email package** (Method 6)
4. **Send email with:**
   - PDFs attached (Executive Summary, Full Report)
   - Interactive map HTML
   - Key visualizations (PNG images)
   - Cover letter

### For Maximum Impact (30 minutes):
1. **Create PowerPoint** (Method 4)
2. **Generate all visualizations** (Method 7)
3. **Export interactive map** (Method 2)
4. **Create complete archive** (Method 3)
5. **Upload to cloud** (Google Drive, Method 5C)
6. **Email professor with:**
   - Link to cloud folder
   - PowerPoint attached
   - Brief summary

---

## 📋 Checklist Before Sharing

- [ ] Executive Summary reviewed (no typos)
- [ ] Interactive map opens and works in browser
- [ ] All CSV files open correctly in Excel
- [ ] Visualizations are high resolution (300 dpi)
- [ ] File names are professional (no spaces, descriptive)
- [ ] Total package size < 25 MB (for email)
- [ ] Cover letter/email drafted
- [ ] Your name and contact info included

---

## 🆘 Troubleshooting

**"File too large for email"**
→ Use Google Drive or Dropbox link instead
→ Or split into multiple emails

**"Professor can't open .md files"**
→ Convert to PDF first
→ Or paste content into Word document

**"Interactive map doesn't work"**
→ Make sure it's the HTML file, not screenshot
→ Professor needs to download and open in browser (Chrome/Firefox/Safari)
→ Can't open directly from email preview

**"Charts look blurry"**
→ Regenerate with dpi=300 or higher
→ Use PNG format, not JPG

---

## ✉️ Sample Email Template

```
Subject: Maryland AFO Analysis - Regional Digester Network Optimization

Dear Professor [Name],

I've completed a comprehensive 5-day geospatial optimization analysis for
Maryland's Eastern Shore animal feeding operations (AFO) waste management.

KEY FINDING:
A 10-hub regional anaerobic digester network is optimal, with:
• $20M investment → $141.7M NPV (5-year)
• 7.2-month payback period
• 709% ROI
• 334 facilities served, 41.2M animals

The analysis tested multiple configurations (8, 10, 15 hubs), conducted
economic sensitivity testing, and identified Worcester County as the ideal
pilot location.

ATTACHMENTS:
1. Executive_Summary.pdf - 2-page overview
2. Interactive_Map.html - Open in browser to explore the network
3. Scenario_Comparison.csv - Detailed hub analysis
4. Visualizations.zip - Charts and graphs

The interactive map shows all 10 hub locations. Click on markers to see
facility details, coverage areas, and capacity utilization.

I'm happy to present the findings or discuss methodology at your convenience.

Best regards,
[Your Name]
[Your Email]
[Course/Program]
```

---

**Questions? Check the main README or contact GEO-ANOM support.**
