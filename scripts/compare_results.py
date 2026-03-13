#!/usr/bin/env python3
"""
Compare Optimization Results

Compares baseline vs updated optimization results to show improvement.

Usage:
    python scripts/compare_results.py
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


def load_results(results_dir):
    """Load optimization results from directory"""
    sites_path = results_dir / "optimal_hubs_realistic.geojson"
    assignments_path = results_dir / "afo_assignments_realistic.geojson"
    summary_path = results_dir / "optimization_summary.txt"

    if not all([sites_path.exists(), assignments_path.exists()]):
        return None

    sites = gpd.read_file(sites_path)
    assignments = gpd.read_file(assignments_path)

    # Parse summary if exists
    summary = {}
    if summary_path.exists():
        with open(summary_path, 'r') as f:
            for line in f:
                if ':' in line:
                    key, value = line.split(':', 1)
                    summary[key.strip()] = value.strip()

    return {
        'sites': sites,
        'assignments': assignments,
        'summary': summary
    }


def compare(baseline, updated):
    """Compare two optimization results"""

    logger.info("=" * 70)
    logger.info("OPTIMIZATION COMPARISON")
    logger.info("=" * 70)

    # AFO coverage
    baseline_afos = len(baseline['assignments'])
    updated_afos = len(updated['assignments'])
    afo_improvement = updated_afos - baseline_afos

    logger.info(f"\n📍 AFO Coverage:")
    logger.info(f"  Baseline: {baseline_afos:,} AFOs")
    logger.info(f"  Updated:  {updated_afos:,} AFOs")
    logger.info(f"  Change:   +{afo_improvement:,} AFOs ({afo_improvement/baseline_afos*100:.1f}% increase)")

    # Animal count
    baseline_animals = baseline['assignments']['headcount'].sum()
    updated_animals = updated['assignments']['headcount'].sum()
    animal_improvement = updated_animals - baseline_animals

    logger.info(f"\n🐔 Animal Coverage:")
    logger.info(f"  Baseline: {baseline_animals:,.0f} animals")
    logger.info(f"  Updated:  {updated_animals:,.0f} animals")
    logger.info(f"  Change:   +{animal_improvement:,.0f} animals ({animal_improvement/baseline_animals*100:.1f}% increase)")

    # Hub count
    baseline_hubs = len(baseline['sites'])
    updated_hubs = len(updated['sites'])

    logger.info(f"\n🏭 Hub Configuration:")
    logger.info(f"  Baseline: {baseline_hubs} hubs")
    logger.info(f"  Updated:  {updated_hubs} hubs")

    # Hub balance
    logger.info(f"\n⚖️  Hub Balance:")
    logger.info(f"\n  Baseline:")
    for idx, hub in baseline['sites'].iterrows():
        pct = hub['zone_animals'] / baseline_animals * 100
        logger.info(f"    Hub {idx}: {hub['zone_afos']:3.0f} AFOs, {hub['zone_animals']:>12,.0f} animals ({pct:5.1f}%)")

    logger.info(f"\n  Updated:")
    for idx, hub in updated['sites'].iterrows():
        pct = hub['zone_animals'] / updated_animals * 100
        logger.info(f"    Hub {idx}: {hub['zone_afos']:3.0f} AFOs, {hub['zone_animals']:>12,.0f} animals ({pct:5.1f}%)")

    # Geographic spread
    baseline_counties = baseline['assignments']['county'].value_counts()
    updated_counties = updated['assignments']['county'].value_counts()

    logger.info(f"\n🗺️  Geographic Coverage:")
    logger.info(f"  Baseline counties: {len(baseline_counties)}")
    logger.info(f"  Updated counties:  {len(updated_counties)}")

    logger.info("\n" + "=" * 70)

    # Create comparison table
    comparison = pd.DataFrame({
        'Metric': [
            'AFOs',
            'Animals',
            'Hubs',
            'Counties',
            'Avg Animals/Hub',
            'Coverage %'
        ],
        'Baseline': [
            baseline_afos,
            baseline_animals,
            baseline_hubs,
            len(baseline_counties),
            baseline_animals / baseline_hubs,
            baseline_afos / 442 * 100  # Out of 442 total
        ],
        'Updated': [
            updated_afos,
            updated_animals,
            updated_hubs,
            len(updated_counties),
            updated_animals / updated_hubs,
            updated_afos / 442 * 100
        ]
    })

    comparison['Change'] = comparison['Updated'] - comparison['Baseline']
    comparison['Change %'] = (comparison['Change'] / comparison['Baseline'] * 100).round(1)

    return comparison


def main():
    config = get_config()

    # Look for results
    baseline_dir = config.processed_dir / "optimization_realistic_baseline"
    updated_dir = config.processed_dir / "optimization_realistic"

    logger.info("Looking for optimization results...")
    logger.info(f"  Baseline: {baseline_dir}")
    logger.info(f"  Updated:  {updated_dir}")

    baseline_results = load_results(baseline_dir)
    updated_results = load_results(updated_dir)

    if baseline_results is None and updated_results is None:
        logger.error("\n❌ No optimization results found!")
        logger.error("\nRun optimization first:")
        logger.error("  python scripts/realistic_optimization.py --region eastern-shore --n-sites 12")
        sys.exit(1)

    if baseline_results is None:
        logger.warning("\n⚠️ No baseline results found")
        logger.info("Current results will become the baseline")
        logger.info(f"\nCurrent optimization:")
        logger.info(f"  AFOs: {len(updated_results['assignments']):,}")
        logger.info(f"  Animals: {updated_results['assignments']['headcount'].sum():,.0f}")
        logger.info(f"  Hubs: {len(updated_results['sites'])}")

        # Save current as baseline
        import shutil
        shutil.copytree(updated_dir, baseline_dir, dirs_exist_ok=True)
        logger.info(f"\n✅ Baseline saved to: {baseline_dir}")
        return

    if updated_results is None:
        logger.error("\n❌ No updated results found")
        logger.error("Run optimization to generate new results")
        sys.exit(1)

    # Compare
    comparison_df = compare(baseline_results, updated_results)

    # Save comparison
    comparison_path = config.processed_dir / "optimization_comparison.csv"
    comparison_df.to_csv(comparison_path, index=False)
    logger.info(f"\n✅ Comparison saved to: {comparison_path}")

    print("\n" + comparison_df.to_string(index=False))


if __name__ == "__main__":
    main()
