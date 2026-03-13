#!/usr/bin/env python3
"""
Generate Baseline Report

Creates a comprehensive baseline report documenting current optimization results.

Usage:
    python scripts/generate_baseline_report.py
"""

import sys
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import geopandas as gpd
import pandas as pd
from geo_anom.core.config import get_config
from geo_anom.core.logging import setup_logger

logger = setup_logger(__name__)


def generate_report():
    """Generate baseline report"""

    config = get_config()

    # Load data
    permits_path = config.processed_dir / "afo_permits.gpkg"
    results_dir = config.processed_dir / "optimization_realistic"

    if not permits_path.exists():
        logger.error(f"Permits not found: {permits_path}")
        sys.exit(1)

    permits = gpd.read_file(permits_path)

    # Check for optimization results
    sites_path = results_dir / "optimal_hubs_realistic.geojson"
    assignments_path = results_dir / "afo_assignments_realistic.geojson"

    has_results = sites_path.exists() and assignments_path.exists()

    if has_results:
        sites = gpd.read_file(sites_path)
        assignments = gpd.read_file(assignments_path)

    # Create report
    report = []
    report.append("=" * 70)
    report.append("GEO-ANOM BASELINE REPORT")
    report.append("=" * 70)
    report.append(f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append(f"\nData as of: Day 1 Analysis")

    # Data Quality
    report.append("\n\n" + "=" * 70)
    report.append("DATA QUALITY")
    report.append("=" * 70)
    report.append(f"\nTotal AFO Records: {len(permits):,}")
    report.append(f"With Valid Coordinates: {(~permits.geometry.is_empty).sum():,} ({(~permits.geometry.is_empty).sum()/len(permits)*100:.1f}%)")
    report.append(f"Missing Coordinates: {(permits.geometry.is_empty).sum():,}")
    report.append(f"With Headcount Data: {(permits.headcount > 0).sum():,}")
    report.append(f"Total Animals: {permits.headcount.sum():,.0f}")

    # Animal Types
    report.append("\n\nANIMAL TYPE DISTRIBUTION")
    report.append("-" * 70)
    animal_dist = permits.groupby('animal_type').agg({
        'farm_name': 'count',
        'headcount': 'sum'
    }).sort_values('headcount', ascending=False).head(5)
    for animal_type, row in animal_dist.iterrows():
        pct = row['headcount'] / permits.headcount.sum() * 100
        report.append(f"{animal_type:30s}: {row['farm_name']:4.0f} AFOs, {row['headcount']:>12,.0f} animals ({pct:5.1f}%)")

    # Geographic Distribution
    report.append("\n\nGEOGRAPHIC DISTRIBUTION (Top 10 Counties)")
    report.append("-" * 70)
    county_dist = permits.groupby('county').agg({
        'farm_name': 'count',
        'headcount': 'sum'
    }).sort_values('headcount', ascending=False).head(10)
    for county, row in county_dist.iterrows():
        pct = row['headcount'] / permits.headcount.sum() * 100
        report.append(f"{county:20s}: {row['farm_name']:4.0f} AFOs, {row['headcount']:>12,.0f} animals ({pct:5.1f}%)")

    # Facility Size
    report.append("\n\nFACILITY SIZE DISTRIBUTION")
    report.append("-" * 70)
    size_bins = [0, 1000, 10000, 100000, 1000000, float('inf')]
    size_labels = ['<1K', '1K-10K', '10K-100K', '100K-1M', '>1M']
    permits['size_cat'] = pd.cut(permits['headcount'], bins=size_bins, labels=size_labels)
    size_dist = permits['size_cat'].value_counts().sort_index()
    for size_cat, count in size_dist.items():
        pct = count / len(permits) * 100
        report.append(f"{size_cat:15s}: {count:4.0f} facilities ({pct:5.1f}%)")

    # Optimization Results
    if has_results:
        report.append("\n\n" + "=" * 70)
        report.append("OPTIMIZATION RESULTS")
        report.append("=" * 70)
        report.append(f"\nHub Configuration: {len(sites)} regional digesters")
        report.append(f"AFOs Assigned: {len(assignments):,}")
        report.append(f"Total Animals Processed: {assignments.headcount.sum():,.0f}")

        report.append("\n\nHUB DETAILS")
        report.append("-" * 70)
        for idx, hub in sites.iterrows():
            report.append(f"\nHub {hub['site_id']}:")
            report.append(f"  Location: {hub.get('county', 'Unknown')} County")
            report.append(f"  Coordinates: {hub.latitude:.4f}°N, {hub.longitude:.4f}°W")
            report.append(f"  AFOs Assigned: {hub['zone_afos']:,.0f}")
            report.append(f"  Total Animals: {hub['zone_animals']:,.0f}")
            if 'zone_animals' in hub:
                capacity_pct = hub['zone_animals'] / 5_000_000 * 100
                report.append(f"  Capacity Used: {capacity_pct:.1f}%")

    else:
        report.append("\n\n" + "=" * 70)
        report.append("OPTIMIZATION RESULTS")
        report.append("=" * 70)
        report.append("\n⚠️ No optimization results available yet")
        report.append("\nRun: python scripts/realistic_optimization.py --region eastern-shore --n-sites 12")

    # Key Findings
    report.append("\n\n" + "=" * 70)
    report.append("KEY FINDINGS")
    report.append("=" * 70)
    report.append(f"\n1. Maryland has {len(permits):,} registered AFOs managing {permits.headcount.sum():,.0f} animals")

    eastern_shore = permits[permits['county'].isin(['Worcester', 'Wicomico', 'Caroline', 'Somerset', 'Dorchester', "Queen Anne's", 'Kent', 'Talbot'])]
    es_pct = len(eastern_shore) / len(permits) * 100
    report.append(f"\n2. {es_pct:.1f}% of AFOs are concentrated on the Eastern Shore")

    chickens = permits[permits['animal_type'].str.contains('chicken', case=False, na=False)]
    chicken_pct = chickens.headcount.sum() / permits.headcount.sum() * 100
    report.append(f"\n3. {chicken_pct:.1f}% of total animals are chickens (poultry industry)")

    large_facilities = permits[permits.headcount > 100000]
    report.append(f"\n4. {len(large_facilities):,} facilities ({len(large_facilities)/len(permits)*100:.1f}%) have >100K animals (industrial scale)")

    if has_results:
        report.append(f"\n5. Optimization shows {len(sites)} regional hubs can serve {len(assignments):,} AFOs effectively")

    # Next Steps
    report.append("\n\n" + "=" * 70)
    report.append("NEXT STEPS")
    report.append("=" * 70)
    report.append("\nDay 2: Test different hub count scenarios (8, 10, 12, 15)")
    report.append("Day 3: Generate county-level detailed reports")
    report.append("Day 4: Economic sensitivity analysis")
    report.append("Day 5: Executive summary and recommendations")

    report.append("\n\n" + "=" * 70)
    report.append("END OF BASELINE REPORT")
    report.append("=" * 70)

    # Save report
    report_text = "\n".join(report)
    report_path = config.processed_dir / "baseline_report.txt"

    with open(report_path, 'w') as f:
        f.write(report_text)

    logger.info("=" * 70)
    logger.info("BASELINE REPORT GENERATED")
    logger.info("=" * 70)
    logger.info(f"\nSaved to: {report_path}")

    # Also print to console
    print("\n" + report_text)

    return report_path


if __name__ == "__main__":
    generate_report()
