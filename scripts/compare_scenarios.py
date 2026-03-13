#!/usr/bin/env python3
"""
Compare all hub count scenarios to find optimal solution.

Creates comparison tables and recommendations.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import geopandas as gpd
from geo_anom.core.config import get_config
from geo_anom.core.logging import setup_logger

logger = setup_logger(__name__)

# Cost parameters
ANIMALS_PER_TRUCKLOAD = 25_000
COST_PER_KM = 2.50
TRIPS_PER_YEAR = 52
FIXED_HUB_COST = 2_000_000


def load_scenario(scenario_dir):
    """Load scenario results"""
    summary_path = scenario_dir / "optimization_summary.txt"
    assignments_path = scenario_dir / "afo_assignments_realistic.geojson"
    sites_path = scenario_dir / "optimal_hubs_realistic.geojson"

    if not all([p.exists() for p in [assignments_path, sites_path]]):
        return None

    sites = gpd.read_file(sites_path)
    assignments = gpd.read_file(assignments_path)

    # Parse summary for cost data
    costs = {}
    if summary_path.exists():
        with open(summary_path, 'r') as f:
            content = f.read()
            for line in content.split('\n'):
                if 'annual_transport_cost' in line.lower():
                    costs['annual_transport'] = float(line.split(':')[1].strip().replace(',', ''))
                elif 'total_construction_cost' in line.lower():
                    costs['construction'] = float(line.split(':')[1].strip().replace(',', ''))
                elif 'cost_per_animal_per_year' in line.lower():
                    costs['per_animal'] = float(line.split(':')[1].strip())
                elif 'avg_distance_km' in line.lower():
                    costs['avg_distance'] = float(line.split(':')[1].strip())

    return {
        'sites': sites,
        'assignments': assignments,
        'costs': costs
    }


def main():
    config = get_config()

    # Load all scenarios
    scenarios = {}
    for n_hubs in [8, 10, 12, 15]:
        scenario_dir = config.processed_dir / "scenarios" / f"scenario_{n_hubs}hubs"
        if not scenario_dir.exists():
            logger.warning(f"Scenario {n_hubs}-hubs not found at {scenario_dir}")
            continue

        result = load_scenario(scenario_dir)
        if result:
            scenarios[n_hubs] = result
            logger.info(f"✓ Loaded {n_hubs}-hub scenario")

    if not scenarios:
        logger.error("No scenarios found!")
        sys.exit(1)

    logger.info(f"\nComparing {len(scenarios)} scenarios...")

    # Build comparison table
    comparison = []
    for n_hubs, data in sorted(scenarios.items()):
        afos_served = len(data['assignments'])
        animals = data['assignments']['headcount'].sum()
        costs = data['costs']

        # Calculate 5-year total
        total_5yr = costs.get('annual_transport', 0) * 5 + costs.get('construction', 0)

        comparison.append({
            'Hubs': n_hubs,
            'AFOs Served': afos_served,
            'Animals (M)': animals / 1_000_000,
            'Construction ($M)': costs.get('construction', 0) / 1_000_000,
            'Annual Transport ($M)': costs.get('annual_transport', 0) / 1_000_000,
            '5-Year Total ($M)': total_5yr / 1_000_000,
            'Cost per Animal/Year ($)': costs.get('per_animal', 0),
            'Avg Distance (km)': costs.get('avg_distance', 0),
            'Max Hub Capacity (%)': (data['sites']['zone_animals'] / 5_000_000 * 100).max(),
            'Min Hub Capacity (%)': (data['sites']['zone_animals'] / 5_000_000 * 100).min(),
        })

    df = pd.DataFrame(comparison)

    # Print table
    print("\n" + "=" * 100)
    print("SCENARIO COMPARISON - Eastern Shore Digester Hubs")
    print("=" * 100)
    print("\n" + df.to_string(index=False))

    # Analysis
    print("\n" + "=" * 100)
    print("ANALYSIS")
    print("=" * 100)

    # Find optimal by different criteria
    min_5yr_cost_idx = df['5-Year Total ($M)'].idxmin()
    min_transport_idx = df['Annual Transport ($M)'].idxmin()
    min_distance_idx = df['Avg Distance (km)'].idxmin()

    print(f"\n✅ Lowest 5-Year Total Cost: {df.loc[min_5yr_cost_idx, 'Hubs']:.0f} hubs (${df.loc[min_5yr_cost_idx, '5-Year Total ($M)']:.1f}M)")
    print(f"✅ Lowest Annual Transport: {df.loc[min_transport_idx, 'Hubs']:.0f} hubs (${df.loc[min_transport_idx, 'Annual Transport ($M)']:.1f}M/yr)")
    print(f"✅ Shortest Average Distance: {df.loc[min_distance_idx, 'Hubs']:.0f} hubs ({df.loc[min_distance_idx, 'Avg Distance (km)']:.1f} km)")

    # Capacity analysis
    print(f"\n⚠️ Capacity Concerns:")
    for idx, row in df.iterrows():
        if row['Max Hub Capacity (%)'] >= 99:
            print(f"   {row['Hubs']:.0f} hubs: At least one hub at {row['Max Hub Capacity (%)']:.0f}% capacity (too high!)")

    # Recommendation
    print("\n" + "=" * 100)
    print("RECOMMENDATION")
    print("=" * 100)

    # Score each scenario (lower is better)
    df['Score'] = (
        df['5-Year Total ($M)'] / df['5-Year Total ($M)'].max() +  # Cost efficiency
        (100 - df['Max Hub Capacity (%)']).abs() / 100 +  # Capacity balance
        df['Avg Distance (km)'] / df['Avg Distance (km)'].max()  # Distance efficiency
    )

    best_idx = df['Score'].idxmin()
    best_hubs = df.loc[best_idx, 'Hubs']

    print(f"\n🏆 OPTIMAL SOLUTION: {best_hubs:.0f} hubs")
    print(f"\n   Why:")
    print(f"   • AFOs Served: {df.loc[best_idx, 'AFOs Served']:.0f} ({df.loc[best_idx, 'AFOs Served']/334*100:.0f}% of total)")
    print(f"   • 5-Year Cost: ${df.loc[best_idx, '5-Year Total ($M)']:.1f}M")
    print(f"   • Annual Transport: ${df.loc[best_idx, 'Annual Transport ($M)']:.1f}M/year")
    print(f"   • Avg Distance: {df.loc[best_idx, 'Avg Distance (km)']:.1f} km")
    print(f"   • Hub Capacity Range: {df.loc[best_idx, 'Min Hub Capacity (%)']:.0f}%-{df.loc[best_idx, 'Max Hub Capacity (%)']:.0f}% (balanced)")
    print(f"   • Cost per Animal: ${df.loc[best_idx, 'Cost per Animal/Year ($)']:.2f}/year")

    # Alternative scenarios
    print(f"\n💡 Alternative Scenarios:")
    print(f"   • Budget-constrained: 8 hubs (${df[df['Hubs']==8]['Construction ($M)'].values[0]:.0f}M construction)")
    print(f"   • Distance-optimized: 15 hubs ({df[df['Hubs']==15]['Avg Distance (km)'].values[0]:.1f} km avg)")

    # Save comparison
    output_path = config.processed_dir / "scenario_comparison.csv"
    df.to_csv(output_path, index=False)
    logger.info(f"\n✅ Comparison saved to: {output_path}")

    # Save recommendation
    rec_path = config.processed_dir / "recommendation.txt"
    with open(rec_path, 'w') as f:
        f.write("GEO-ANOM Scenario Analysis Recommendation\n")
        f.write("=" * 70 + "\n\n")
        f.write(f"OPTIMAL SOLUTION: {best_hubs:.0f} regional digester hubs\n\n")
        f.write(f"Key Metrics:\n")
        f.write(f"  • AFOs Served: {df.loc[best_idx, 'AFOs Served']:.0f}\n")
        f.write(f"  • Animals Processed: {df.loc[best_idx, 'Animals (M)']:.1f}M\n")
        f.write(f"  • Construction Cost: ${df.loc[best_idx, 'Construction ($M)']:.1f}M\n")
        f.write(f"  • Annual Transport: ${df.loc[best_idx, 'Annual Transport ($M)']:.1f}M\n")
        f.write(f"  • 5-Year Total: ${df.loc[best_idx, '5-Year Total ($M)']:.1f}M\n")
        f.write(f"  • Average Distance: {df.loc[best_idx, 'Avg Distance (km)']:.1f} km\n")
        f.write(f"  • Cost per Animal: ${df.loc[best_idx, 'Cost per Animal/Year ($)']:.2f}/year\n")

    logger.info(f"✅ Recommendation saved to: {rec_path}")
    print("\n" + "=" * 100)


if __name__ == "__main__":
    main()
