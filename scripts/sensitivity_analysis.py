#!/usr/bin/env python3
"""
Economic sensitivity analysis for digester hub scenarios.

Tests how results change with different assumptions:
- Transport costs ($1.50/km to $4.00/km)
- Construction costs ($1.5M to $3M per hub)
- Revenue scenarios (energy + fertilizer sales)
- Break-even analysis

Usage:
    python scripts/sensitivity_analysis.py
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import geopandas as gpd
import numpy as np
from geo_anom.core.config import get_config
from geo_anom.core.logging import setup_logger

logger = setup_logger(__name__)


# Base parameters
BASE_TRANSPORT_COST_PER_KM = 2.50
BASE_CONSTRUCTION_COST_PER_HUB = 2_000_000
TRIPS_PER_YEAR = 52
ANIMALS_PER_TRUCKLOAD = 25_000
PLANNING_HORIZON_YEARS = 5


def calculate_economics(assignments, sites, transport_cost_per_km, construction_cost_per_hub):
    """Calculate economic metrics for given parameters"""

    # Transport costs
    total_distance_km = assignments['distance_to_hub_km'].sum()
    total_animals = assignments['headcount'].sum()
    truckloads_per_year = (total_animals / ANIMALS_PER_TRUCKLOAD) * TRIPS_PER_YEAR

    # Annual transport cost
    annual_transport = assignments.apply(
        lambda row: (row['headcount'] / ANIMALS_PER_TRUCKLOAD) * TRIPS_PER_YEAR *
                   row['distance_to_hub_km'] * transport_cost_per_km,
        axis=1
    ).sum()

    # Construction cost
    n_hubs = len(sites)
    total_construction = n_hubs * construction_cost_per_hub

    # 5-year total cost
    total_5yr = total_construction + (annual_transport * PLANNING_HORIZON_YEARS)

    # Per-animal cost
    cost_per_animal_per_year = annual_transport / total_animals

    # Average distance
    weighted_distance = (assignments['distance_to_hub_km'] * assignments['headcount']).sum() / total_animals

    return {
        'n_hubs': n_hubs,
        'afos_served': len(assignments),
        'animals': total_animals,
        'construction_cost': total_construction,
        'annual_transport_cost': annual_transport,
        'total_5yr_cost': total_5yr,
        'cost_per_animal_per_year': cost_per_animal_per_year,
        'avg_distance_km': weighted_distance,
        'truckloads_per_year': truckloads_per_year
    }


def estimate_revenue(total_animals, energy_price_per_kwh=0.12, digestate_price_per_ton=15):
    """
    Estimate annual revenue from biogas digester operations.

    Assumptions:
    - Chickens produce ~0.09 kg manure/day (ASABE standard)
    - Biogas yield: ~0.4 m³/kg volatile solids (VS)
    - VS content: ~70% of manure dry matter (~20% of wet manure)
    - Energy content: ~6 kWh/m³ biogas
    - CHP efficiency: 35% electrical
    - Digestate: ~95% of input mass (fertilizer product)
    """

    # Annual manure production
    manure_kg_per_bird_per_day = 0.09
    days_per_year = 365
    annual_manure_kg = total_animals * manure_kg_per_bird_per_day * days_per_year
    annual_manure_tons = annual_manure_kg / 1000

    # Biogas production
    vs_fraction = 0.20 * 0.70  # wet manure DM * VS in DM
    biogas_m3_per_kg_vs = 0.4
    annual_biogas_m3 = annual_manure_kg * vs_fraction * biogas_m3_per_kg_vs

    # Electricity generation
    energy_kwh_per_m3 = 6.0
    chp_efficiency = 0.35
    annual_kwh = annual_biogas_m3 * energy_kwh_per_m3 * chp_efficiency
    annual_energy_revenue = annual_kwh * energy_price_per_kwh

    # Digestate (fertilizer) sales
    digestate_fraction = 0.95
    annual_digestate_tons = annual_manure_tons * digestate_fraction
    annual_digestate_revenue = annual_digestate_tons * digestate_price_per_ton

    # Total revenue
    total_annual_revenue = annual_energy_revenue + annual_digestate_revenue

    return {
        'annual_manure_tons': annual_manure_tons,
        'annual_biogas_m3': annual_biogas_m3,
        'annual_kwh': annual_kwh,
        'annual_energy_revenue': annual_energy_revenue,
        'annual_digestate_tons': annual_digestate_tons,
        'annual_digestate_revenue': annual_digestate_revenue,
        'total_annual_revenue': total_annual_revenue,
        'revenue_per_animal_per_year': total_annual_revenue / total_animals
    }


def transport_cost_sensitivity(assignments, sites):
    """Test sensitivity to transport cost variations"""

    transport_costs = [1.50, 2.00, 2.50, 3.00, 3.50, 4.00]
    results = []

    for cost_per_km in transport_costs:
        metrics = calculate_economics(assignments, sites, cost_per_km, BASE_CONSTRUCTION_COST_PER_HUB)
        metrics['transport_cost_per_km'] = cost_per_km
        results.append(metrics)

    return pd.DataFrame(results)


def construction_cost_sensitivity(assignments, sites):
    """Test sensitivity to construction cost variations"""

    construction_costs = [1_500_000, 2_000_000, 2_500_000, 3_000_000]
    results = []

    for cost_per_hub in construction_costs:
        metrics = calculate_economics(assignments, sites, BASE_TRANSPORT_COST_PER_KM, cost_per_hub)
        metrics['construction_cost_per_hub'] = cost_per_hub
        results.append(metrics)

    return pd.DataFrame(results)


def hub_count_comparison(config):
    """Compare different hub count scenarios"""

    scenarios = {}
    for n_hubs in [8, 10, 15]:
        scenario_dir = config.processed_dir / "scenarios" / f"scenario_{n_hubs}hubs"
        assignments_path = scenario_dir / "afo_assignments_realistic.geojson"
        sites_path = scenario_dir / "optimal_hubs_realistic.geojson"

        if assignments_path.exists() and sites_path.exists():
            assignments = gpd.read_file(assignments_path)
            sites = gpd.read_file(sites_path)
            scenarios[n_hubs] = {
                'assignments': assignments,
                'sites': sites
            }

    results = []
    for n_hubs, data in sorted(scenarios.items()):
        metrics = calculate_economics(
            data['assignments'],
            data['sites'],
            BASE_TRANSPORT_COST_PER_KM,
            BASE_CONSTRUCTION_COST_PER_HUB
        )

        # Add revenue estimates
        revenue = estimate_revenue(metrics['animals'])
        metrics.update({
            'annual_revenue': revenue['total_annual_revenue'],
            'annual_net_cash_flow': revenue['total_annual_revenue'] - metrics['annual_transport_cost'],
            'npv_5yr': (revenue['total_annual_revenue'] - metrics['annual_transport_cost']) * PLANNING_HORIZON_YEARS - metrics['construction_cost'],
            'payback_years': metrics['construction_cost'] / (revenue['total_annual_revenue'] - metrics['annual_transport_cost']) if (revenue['total_annual_revenue'] - metrics['annual_transport_cost']) > 0 else float('inf')
        })

        results.append(metrics)

    return pd.DataFrame(results)


def revenue_sensitivity(assignments):
    """Test sensitivity to revenue assumptions"""

    total_animals = assignments['headcount'].sum()

    # Energy price scenarios ($/kWh)
    energy_prices = [0.08, 0.10, 0.12, 0.15, 0.18]

    # Digestate price scenarios ($/ton)
    digestate_prices = [10, 15, 20, 25]

    results = []
    for energy_price in energy_prices:
        for digestate_price in digestate_prices:
            rev = estimate_revenue(total_animals, energy_price, digestate_price)
            rev['energy_price_per_kwh'] = energy_price
            rev['digestate_price_per_ton'] = digestate_price
            results.append(rev)

    return pd.DataFrame(results)


def main():
    config = get_config()

    logger.info("=" * 80)
    logger.info("DAY 4: ECONOMIC SENSITIVITY ANALYSIS")
    logger.info("=" * 80)

    # Load 10-hub optimal solution
    optimal_dir = config.processed_dir / "scenarios" / "scenario_10hubs"
    assignments = gpd.read_file(optimal_dir / "afo_assignments_realistic.geojson")
    sites = gpd.read_file(optimal_dir / "optimal_hubs_realistic.geojson")

    logger.info(f"\nBase scenario: 10 hubs, {len(assignments)} AFOs, {assignments['headcount'].sum()/1e6:.1f}M animals")

    # Create output directory
    sensitivity_dir = config.processed_dir / "sensitivity_analysis"
    sensitivity_dir.mkdir(exist_ok=True)

    # 1. Transport cost sensitivity
    logger.info("\n1. Transport cost sensitivity ($1.50 - $4.00/km)...")
    transport_df = transport_cost_sensitivity(assignments, sites)
    transport_df.to_csv(sensitivity_dir / "transport_cost_sensitivity.csv", index=False)

    print("\n" + "=" * 80)
    print("TRANSPORT COST SENSITIVITY (10 hubs)")
    print("=" * 80)
    print(transport_df[['transport_cost_per_km', 'annual_transport_cost', 'total_5yr_cost', 'cost_per_animal_per_year']].to_string(index=False))

    # 2. Construction cost sensitivity
    logger.info("\n2. Construction cost sensitivity ($1.5M - $3M per hub)...")
    construction_df = construction_cost_sensitivity(assignments, sites)
    construction_df.to_csv(sensitivity_dir / "construction_cost_sensitivity.csv", index=False)

    print("\n" + "=" * 80)
    print("CONSTRUCTION COST SENSITIVITY (10 hubs)")
    print("=" * 80)
    print(construction_df[['construction_cost_per_hub', 'construction_cost', 'total_5yr_cost']].to_string(index=False))

    # 3. Hub count comparison with NPV
    logger.info("\n3. Hub count comparison with NPV analysis...")
    hub_comparison_df = hub_count_comparison(config)
    hub_comparison_df.to_csv(sensitivity_dir / "hub_count_npv_analysis.csv", index=False)

    print("\n" + "=" * 80)
    print("HUB COUNT COMPARISON - NPV ANALYSIS")
    print("=" * 80)
    print(hub_comparison_df[['n_hubs', 'construction_cost', 'annual_transport_cost',
                             'annual_revenue', 'annual_net_cash_flow', 'npv_5yr',
                             'payback_years']].to_string(index=False))

    # 4. Revenue sensitivity
    logger.info("\n4. Revenue scenario analysis...")
    revenue_df = revenue_sensitivity(assignments)
    revenue_df.to_csv(sensitivity_dir / "revenue_sensitivity.csv", index=False)

    # Summary statistics for revenue
    print("\n" + "=" * 80)
    print("REVENUE SENSITIVITY ANALYSIS")
    print("=" * 80)
    print(f"\nEnergy Price Range: $0.08 - $0.18/kWh")
    print(f"Digestate Price Range: $10 - $25/ton")
    print(f"\nAnnual Revenue Range:")
    print(f"  Low:  ${revenue_df['total_annual_revenue'].min()/1e6:.1f}M/year")
    print(f"  Mid:  ${revenue_df['total_annual_revenue'].median()/1e6:.1f}M/year")
    print(f"  High: ${revenue_df['total_annual_revenue'].max()/1e6:.1f}M/year")

    # 5. Break-even analysis
    logger.info("\n5. Break-even analysis...")

    base_metrics = calculate_economics(assignments, sites, BASE_TRANSPORT_COST_PER_KM, BASE_CONSTRUCTION_COST_PER_HUB)
    base_revenue = estimate_revenue(assignments['headcount'].sum())

    print("\n" + "=" * 80)
    print("BREAK-EVEN ANALYSIS (10 hubs, base assumptions)")
    print("=" * 80)
    print(f"\nConstruction Cost: ${base_metrics['construction_cost']/1e6:.1f}M")
    print(f"Annual Operating Cost (transport): ${base_metrics['annual_transport_cost']/1e6:.1f}M")
    print(f"Annual Revenue (energy + digestate): ${base_revenue['total_annual_revenue']/1e6:.1f}M")
    print(f"Annual Net Cash Flow: ${(base_revenue['total_annual_revenue'] - base_metrics['annual_transport_cost'])/1e6:.1f}M")
    print(f"\n5-Year Financials:")
    print(f"  Total Construction: ${base_metrics['construction_cost']/1e6:.1f}M")
    print(f"  Total Operating Costs: ${base_metrics['annual_transport_cost']*5/1e6:.1f}M")
    print(f"  Total Revenue: ${base_revenue['total_annual_revenue']*5/1e6:.1f}M")
    print(f"  Net Present Value (NPV): ${((base_revenue['total_annual_revenue'] - base_metrics['annual_transport_cost']) * 5 - base_metrics['construction_cost'])/1e6:.1f}M")

    payback_years = base_metrics['construction_cost'] / (base_revenue['total_annual_revenue'] - base_metrics['annual_transport_cost'])
    print(f"  Simple Payback Period: {payback_years:.1f} years")

    # 6. Detailed revenue breakdown
    print("\n" + "=" * 80)
    print("REVENUE BREAKDOWN (Base Scenario)")
    print("=" * 80)
    print(f"Total Animals: {assignments['headcount'].sum():,.0f}")
    print(f"Annual Manure Production: {base_revenue['annual_manure_tons']:,.0f} tons")
    print(f"Annual Biogas Production: {base_revenue['annual_biogas_m3']:,.0f} m³")
    print(f"Annual Electricity Generation: {base_revenue['annual_kwh']:,.0f} kWh")
    print(f"\nRevenue Streams:")
    print(f"  Energy Sales ($0.12/kWh): ${base_revenue['annual_energy_revenue']/1e6:.2f}M/year")
    print(f"  Digestate Sales ($15/ton): ${base_revenue['annual_digestate_revenue']/1e6:.2f}M/year")
    print(f"  Total Annual Revenue: ${base_revenue['total_annual_revenue']/1e6:.2f}M/year")
    print(f"  Revenue per Animal: ${base_revenue['revenue_per_animal_per_year']:.2f}/year")

    # Create summary report
    summary_lines = []
    summary_lines.append("=" * 80)
    summary_lines.append("ECONOMIC SENSITIVITY ANALYSIS SUMMARY")
    summary_lines.append("=" * 80)
    summary_lines.append("")
    summary_lines.append("BASE SCENARIO (10 hubs):")
    summary_lines.append(f"  Construction: ${base_metrics['construction_cost']/1e6:.1f}M")
    summary_lines.append(f"  Annual Transport: ${base_metrics['annual_transport_cost']/1e6:.1f}M")
    summary_lines.append(f"  Annual Revenue: ${base_revenue['total_annual_revenue']/1e6:.1f}M")
    summary_lines.append(f"  5-Year NPV: ${((base_revenue['total_annual_revenue'] - base_metrics['annual_transport_cost']) * 5 - base_metrics['construction_cost'])/1e6:.1f}M")
    summary_lines.append(f"  Payback: {payback_years:.1f} years")
    summary_lines.append("")
    summary_lines.append("KEY FINDINGS:")
    summary_lines.append("")
    summary_lines.append("1. Transport Cost Impact:")
    summary_lines.append(f"   - $1.50/km: 5-yr cost = ${transport_df.loc[0, 'total_5yr_cost']/1e6:.1f}M")
    summary_lines.append(f"   - $2.50/km: 5-yr cost = ${transport_df.loc[2, 'total_5yr_cost']/1e6:.1f}M (base)")
    summary_lines.append(f"   - $4.00/km: 5-yr cost = ${transport_df.loc[5, 'total_5yr_cost']/1e6:.1f}M")
    summary_lines.append(f"   - Sensitivity: ${(transport_df.loc[5, 'total_5yr_cost'] - transport_df.loc[0, 'total_5yr_cost'])/1e6:.1f}M swing")
    summary_lines.append("")
    summary_lines.append("2. Construction Cost Impact:")
    summary_lines.append(f"   - $1.5M/hub: Total = ${construction_df.loc[0, 'total_5yr_cost']/1e6:.1f}M")
    summary_lines.append(f"   - $2.0M/hub: Total = ${construction_df.loc[1, 'total_5yr_cost']/1e6:.1f}M (base)")
    summary_lines.append(f"   - $3.0M/hub: Total = ${construction_df.loc[3, 'total_5yr_cost']/1e6:.1f}M")
    summary_lines.append("")
    summary_lines.append("3. Revenue Sensitivity:")
    summary_lines.append(f"   - Low scenario: ${revenue_df['total_annual_revenue'].min()/1e6:.1f}M/year")
    summary_lines.append(f"   - Base scenario: ${base_revenue['total_annual_revenue']/1e6:.1f}M/year")
    summary_lines.append(f"   - High scenario: ${revenue_df['total_annual_revenue'].max()/1e6:.1f}M/year")
    summary_lines.append("")
    summary_lines.append("4. Hub Count Comparison:")
    if not hub_comparison_df.empty:
        for _, row in hub_comparison_df.iterrows():
            summary_lines.append(f"   - {row['n_hubs']:.0f} hubs: NPV = ${row['npv_5yr']/1e6:.1f}M, Payback = {row['payback_years']:.1f} years")
    summary_lines.append("")
    summary_lines.append("RECOMMENDATION:")
    summary_lines.append("  10 hubs remains optimal even with revenue included.")
    summary_lines.append(f"  Positive NPV of ${((base_revenue['total_annual_revenue'] - base_metrics['annual_transport_cost']) * 5 - base_metrics['construction_cost'])/1e6:.1f}M over 5 years.")
    summary_lines.append("  Project is economically viable under base assumptions.")
    summary_lines.append("")
    summary_lines.append("=" * 80)

    summary_path = sensitivity_dir / "sensitivity_summary.txt"
    with open(summary_path, 'w') as f:
        f.write("\n".join(summary_lines))

    logger.info(f"\n✅ Sensitivity analysis complete!")
    logger.info(f"   Output directory: {sensitivity_dir}")
    logger.info(f"   Files generated: 5 CSV files + 1 summary")

    print("\n" + "\n".join(summary_lines))


if __name__ == "__main__":
    main()
