#!/usr/bin/env python3
"""
Generate detailed county-level reports.

Creates comprehensive analysis for each county showing:
- AFO inventory
- Total animals
- Hub assignments
- Economic impact
- Priority ranking

Usage:
    python scripts/generate_county_reports.py
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import geopandas as gpd
import pandas as pd
from geo_anom.core.config import get_config
from geo_anom.core.logging import setup_logger

logger = setup_logger(__name__)


def generate_county_report(county_name, county_afos, all_afos, assignments=None):
    """Generate detailed report for a single county"""

    report = []
    report.append("=" * 80)
    report.append(f"{county_name.upper()} COUNTY - AFO ANALYSIS")
    report.append("=" * 80)

    # Summary stats
    total_afos = len(county_afos)
    total_animals = county_afos['headcount'].sum()
    pct_of_state = total_animals / all_afos['headcount'].sum() * 100

    report.append(f"\n📊 SUMMARY")
    report.append("-" * 80)
    report.append(f"Total AFOs: {total_afos:,}")
    report.append(f"Total Animals: {total_animals:,.0f}")
    report.append(f"Percentage of State Total: {pct_of_state:.1f}%")
    report.append(f"Average Animals per AFO: {total_animals/total_afos:,.0f}")

    # Animal types
    report.append(f"\n🐔 ANIMAL TYPE DISTRIBUTION")
    report.append("-" * 80)
    animal_types = county_afos.groupby('animal_type').agg({
        'farm_name': 'count',
        'headcount': 'sum'
    }).sort_values('headcount', ascending=False)

    for animal_type, row in animal_types.iterrows():
        pct = row['headcount'] / total_animals * 100
        report.append(f"{animal_type:30s}: {row['farm_name']:3.0f} AFOs, {row['headcount']:>12,.0f} animals ({pct:5.1f}%)")

    # Facility sizes
    report.append(f"\n📏 FACILITY SIZE DISTRIBUTION")
    report.append("-" * 80)
    size_bins = [0, 1000, 10000, 100000, 1000000, float('inf')]
    size_labels = ['<1K', '1K-10K', '10K-100K', '100K-1M', '>1M']
    county_afos_copy = county_afos.copy()
    county_afos_copy['size_cat'] = pd.cut(county_afos_copy['headcount'], bins=size_bins, labels=size_labels)
    size_dist = county_afos_copy['size_cat'].value_counts().sort_index()

    for size_cat, count in size_dist.items():
        pct = count / total_afos * 100
        report.append(f"{size_cat:15s}: {count:3.0f} facilities ({pct:5.1f}%)")

    # Top 10 facilities
    report.append(f"\n🏭 TOP 10 LARGEST FACILITIES")
    report.append("-" * 80)
    top10 = county_afos.nlargest(10, 'headcount')[['farm_name', 'animal_type', 'headcount']]
    for idx, row in top10.iterrows():
        report.append(f"{row['farm_name'][:50]:50s} {row['headcount']:>12,.0f} {row['animal_type']}")

    # Hub assignments (if provided)
    if assignments is not None:
        county_assigned = assignments[assignments['county'] == county_name]
        if len(county_assigned) > 0:
            report.append(f"\n🏗️ HUB ASSIGNMENTS (10-Hub Solution)")
            report.append("-" * 80)
            hub_dist = county_assigned.groupby('assigned_site_idx').agg({
                'farm_name': 'count',
                'headcount': 'sum'
            }).sort_values('headcount', ascending=False)

            for hub_idx, row in hub_dist.iterrows():
                pct = row['headcount'] / total_animals * 100
                report.append(f"Hub {hub_idx:2.0f}: {row['farm_name']:3.0f} AFOs, {row['headcount']:>12,.0f} animals ({pct:5.1f}%)")

    # Priority assessment
    report.append(f"\n⭐ PRIORITY ASSESSMENT")
    report.append("-" * 80)

    # Calculate priority score
    density_score = total_afos / 100  # Higher AFO count = higher score
    volume_score = total_animals / 10_000_000  # Higher animals = higher score
    industrial_pct = len(county_afos[county_afos['headcount'] > 100000]) / total_afos * 100

    priority_score = density_score + volume_score + (industrial_pct / 10)

    if priority_score > 5:
        priority = "HIGH"
        reason = "High AFO density and large animal population"
    elif priority_score > 2:
        priority = "MEDIUM"
        reason = "Significant AFO presence"
    else:
        priority = "LOW"
        reason = "Lower AFO concentration"

    report.append(f"Priority Level: {priority}")
    report.append(f"Reason: {reason}")
    report.append(f"AFO Density Score: {density_score:.1f}")
    report.append(f"Volume Score: {volume_score:.1f}")
    report.append(f"Industrial Facilities: {industrial_pct:.0f}%")

    # Recommendations
    report.append(f"\n💡 RECOMMENDATIONS")
    report.append("-" * 80)

    if priority == "HIGH":
        report.append(f"• Excellent candidate for pilot digester program")
        report.append(f"• Consider 2-3 hubs within county boundaries")
        report.append(f"• High potential for economies of scale")
        report.append(f"• Engage with top 10 facilities for partnership")
    elif priority == "MEDIUM":
        report.append(f"• Good candidate for regional hub serving multiple counties")
        report.append(f"• Consider shared infrastructure with neighboring counties")
        report.append(f"• Focus on largest facilities first")
    else:
        report.append(f"• Better suited for regional hub access")
        report.append(f"• May not justify standalone county hub")
        report.append(f"• Include in multi-county service area")

    report.append(f"\n" + "=" * 80)
    report.append(f"END OF {county_name.upper()} COUNTY REPORT")
    report.append(f"=" * 80)

    return "\n".join(report)


def main():
    config = get_config()

    logger.info("=" * 80)
    logger.info("DAY 3: COUNTY-LEVEL ANALYSIS")
    logger.info("=" * 80)

    # Load data
    permits_path = config.processed_dir / "afo_permits.gpkg"
    afos = gpd.read_file(permits_path)

    # Load 10-hub assignments (optimal solution)
    assignments_path = config.processed_dir / "scenarios" / "scenario_10hubs" / "afo_assignments_realistic.geojson"
    if assignments_path.exists():
        assignments = gpd.read_file(assignments_path)
    else:
        assignments = None
        logger.warning("10-hub scenario not found, proceeding without hub assignments")

    # Get top 10 counties by animal count
    county_stats = afos.groupby('county').agg({
        'farm_name': 'count',
        'headcount': 'sum'
    }).sort_values('headcount', ascending=False).head(10)

    logger.info(f"\nGenerating reports for top 10 counties...")

    # Create output directory
    reports_dir = config.processed_dir / "county_reports"
    reports_dir.mkdir(exist_ok=True)

    # Generate reports
    county_summaries = []

    for county_name, stats in county_stats.iterrows():
        logger.info(f"  • {county_name}...")

        county_afos = afos[afos['county'] == county_name]

        # Generate report
        report_text = generate_county_report(county_name, county_afos, afos, assignments)

        # Save individual report
        report_path = reports_dir / f"{county_name.replace(' ', '_')}_report.txt"
        with open(report_path, 'w') as f:
            f.write(report_text)

        # Save summary for combined report
        county_summaries.append({
            'County': county_name,
            'AFOs': len(county_afos),
            'Animals': county_afos['headcount'].sum(),
            'Pct_of_State': county_afos['headcount'].sum() / afos['headcount'].sum() * 100,
            'Avg_per_AFO': county_afos['headcount'].sum() / len(county_afos),
            'Industrial_Facilities': len(county_afos[county_afos['headcount'] > 100000])
        })

    # Create combined summary
    summary_df = pd.DataFrame(county_summaries)
    summary_path = reports_dir / "county_summary.csv"
    summary_df.to_csv(summary_path, index=False)

    # Create master report
    master_report = []
    master_report.append("=" * 80)
    master_report.append("MARYLAND AFO COUNTY ANALYSIS")
    master_report.append("Top 10 Counties by Animal Population")
    master_report.append("=" * 80)
    master_report.append(f"\n{summary_df.to_string(index=False)}")
    master_report.append(f"\n\nDetailed reports available in: {reports_dir}")
    master_report.append(f"\nIndividual county reports:")
    for county_name in county_stats.index:
        filename = f"{county_name.replace(' ', '_')}_report.txt"
        master_report.append(f"  • {filename}")

    master_path = reports_dir / "00_MASTER_SUMMARY.txt"
    with open(master_path, 'w') as f:
        f.write("\n".join(master_report))

    logger.info(f"\n✅ County reports generated!")
    logger.info(f"   Location: {reports_dir}")
    logger.info(f"   Counties: {len(county_summaries)}")
    logger.info(f"   Files: {len(list(reports_dir.glob('*.txt')))} reports + 1 CSV")

    print("\n" + "\n".join(master_report))


if __name__ == "__main__":
    main()
