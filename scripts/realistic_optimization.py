#!/usr/bin/env python3
"""
Realistic Optimization with Capacity Constraints

This script runs a more realistic optimization that:
1. Limits hub capacity (max 5M animals per site)
2. Focuses on Eastern Shore (where 74% of AFOs are)
3. Provides economic cost estimates
4. Generates actionable results

Usage:
    python scripts/realistic_optimization.py --n-sites 5
    python scripts/realistic_optimization.py --region eastern-shore --n-sites 3
    python scripts/realistic_optimization.py --full-state --n-sites 7
"""

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import geopandas as gpd
import pandas as pd
import numpy as np
from geo_anom.core.config import get_config
from geo_anom.core.logging import setup_logger

logger = setup_logger(__name__)

# Realistic constants
MAX_CAPACITY_ANIMALS = 5_000_000  # 5M animals per hub (realistic for large digester)
ANIMALS_PER_TRUCKLOAD = 25_000    # Chickens per truck
COST_PER_KM = 2.50                # USD per km (fuel + driver)
TRIPS_PER_YEAR = 52               # Weekly manure pickup
FIXED_HUB_COST = 2_000_000        # $2M construction cost per hub

EASTERN_SHORE_COUNTIES = ['Worcester', 'Wicomico', 'Caroline', 'Somerset',
                          'Dorchester', 'Queen Anne\'s', 'Kent', 'Talbot']


def filter_region(afos_gdf, region):
    """Filter AFOs by region"""
    if region == 'eastern-shore':
        logger.info(f"Filtering to Eastern Shore counties: {EASTERN_SHORE_COUNTIES}")
        filtered = afos_gdf[afos_gdf['county'].isin(EASTERN_SHORE_COUNTIES)]
    elif region == 'full-state':
        logger.info("Using full state (all AFOs)")
        filtered = afos_gdf
    else:
        logger.info(f"Filtering to county: {region}")
        filtered = afos_gdf[afos_gdf['county'] == region]

    return filtered


def optimize_with_capacity(afos_gdf, n_sites, max_capacity=MAX_CAPACITY_ANIMALS):
    """
    Run optimization with realistic capacity constraints

    This uses a greedy heuristic instead of ILP for speed with capacity constraints:
    1. Find n_sites largest AFOs as initial hubs
    2. Assign each AFO to nearest hub with capacity
    3. Refine hub locations by centroid of assigned AFOs
    4. Repeat until convergence
    """
    import pulp
    from scipy.spatial.distance import cdist

    logger.info(f"Running capacity-constrained optimization: {n_sites} hubs, max {max_capacity:,} animals each")

    # Filter to valid coordinates
    valid_afos = afos_gdf[~afos_gdf.geometry.is_empty].copy()
    logger.info(f"Using {len(valid_afos)} AFOs with valid coordinates")

    # Convert to projected coordinates
    afos_proj = valid_afos.to_crs("EPSG:2248")  # Maryland State Plane

    # Get coordinates
    coords = np.array([[geom.centroid.x, geom.centroid.y] for geom in afos_proj.geometry])
    headcounts = valid_afos['headcount'].values

    # Initial hub selection: pick n_sites largest facilities
    largest_indices = np.argsort(headcounts)[-n_sites:]
    hub_coords = coords[largest_indices]

    logger.info("Iteratively assigning AFOs to hubs with capacity constraints...")

    max_iterations = 20
    for iteration in range(max_iterations):
        # Calculate distances to all hubs
        distances = cdist(coords, hub_coords) / 1000.0  # km

        # Greedy assignment with capacity
        assignments = np.full(len(valid_afos), -1, dtype=int)
        hub_loads = np.zeros(n_sites)

        # Sort AFOs by size (assign largest first)
        sorted_indices = np.argsort(headcounts)[::-1]

        for idx in sorted_indices:
            afo_headcount = headcounts[idx]
            dists_to_hubs = distances[idx]

            # Find nearest hub with capacity
            sorted_hubs = np.argsort(dists_to_hubs)
            assigned = False

            for hub_idx in sorted_hubs:
                if hub_loads[hub_idx] + afo_headcount <= max_capacity:
                    assignments[idx] = hub_idx
                    hub_loads[hub_idx] += afo_headcount
                    assigned = True
                    break

            if not assigned:
                logger.warning(f"AFO {idx} ({afo_headcount:,} animals) could not be assigned (all hubs at capacity)")

        # Recalculate hub locations as centroids of assigned AFOs
        new_hub_coords = np.zeros_like(hub_coords)
        for hub_idx in range(n_sites):
            assigned_coords = coords[assignments == hub_idx]
            if len(assigned_coords) > 0:
                new_hub_coords[hub_idx] = assigned_coords.mean(axis=0)
            else:
                new_hub_coords[hub_idx] = hub_coords[hub_idx]  # Keep old location

        # Check convergence
        movement = np.linalg.norm(new_hub_coords - hub_coords)
        if movement < 100:  # <100m movement
            logger.info(f"Converged after {iteration + 1} iterations")
            break

        hub_coords = new_hub_coords

    # Calculate total transport effort
    total_transport_km = 0
    for idx, hub_idx in enumerate(assignments):
        if hub_idx >= 0:
            dist = distances[idx, hub_idx]
            total_transport_km += headcounts[idx] * dist

    # Add assignments to dataframe
    valid_afos['assigned_site_idx'] = assignments
    valid_afos['distance_to_hub_km'] = [
        distances[i, assignments[i]] if assignments[i] >= 0 else np.nan
        for i in range(len(valid_afos))
    ]

    # Create hub GeoDataFrame
    hubs = []
    for hub_idx in range(n_sites):
        # Find original AFO closest to hub centroid
        hub_coord = hub_coords[hub_idx]
        distances_to_centroid = np.linalg.norm(coords - hub_coord, axis=1)
        closest_afo_idx = np.argmin(distances_to_centroid)

        hub_info = valid_afos.iloc[closest_afo_idx].copy()
        hub_info['site_id'] = hub_idx
        hub_info['zone_afos'] = (assignments == hub_idx).sum()
        hub_info['zone_animals'] = hub_loads[hub_idx]
        hubs.append(hub_info)

    hubs_gdf = gpd.GeoDataFrame(hubs)

    return hubs_gdf, valid_afos, total_transport_km


def calculate_economics(hubs_gdf, afos_gdf, total_transport_km):
    """Calculate economic metrics"""

    # Transport cost
    total_truckloads = total_transport_km / ANIMALS_PER_TRUCKLOAD
    annual_transport_cost = total_truckloads * COST_PER_KM * TRIPS_PER_YEAR

    # Construction cost
    total_construction_cost = len(hubs_gdf) * FIXED_HUB_COST

    # Per-animal costs
    total_animals = afos_gdf['headcount'].sum()
    cost_per_animal_per_year = annual_transport_cost / total_animals

    return {
        'annual_transport_cost': annual_transport_cost,
        'total_construction_cost': total_construction_cost,
        'total_cost_5yr': annual_transport_cost * 5 + total_construction_cost,
        'cost_per_animal_per_year': cost_per_animal_per_year,
        'total_truckloads_per_year': total_truckloads * TRIPS_PER_YEAR,
        'avg_distance_km': total_transport_km / total_animals if total_animals > 0 else 0
    }


def print_results(hubs_gdf, afos_gdf, economics):
    """Print formatted results"""

    print("\n" + "=" * 70)
    print("REALISTIC OPTIMIZATION RESULTS")
    print("=" * 70)

    print(f"\n📍 Hub Locations ({len(hubs_gdf)} sites):\n")
    for idx, hub in hubs_gdf.iterrows():
        print(f"Hub {hub['site_id']}:")
        print(f"  Location: {hub.get('county', 'Unknown')} County")
        print(f"  Coordinates: {hub.latitude:.4f}°N, {hub.longitude:.4f}°W")
        print(f"  AFOs Assigned: {int(hub['zone_afos']):,}")
        print(f"  Total Animals: {int(hub['zone_animals']):,}")
        print(f"  Capacity Used: {hub['zone_animals'] / MAX_CAPACITY_ANIMALS * 100:.1f}%")
        print()

    print(f"💰 Economic Analysis:\n")
    print(f"Annual Transport Cost:   ${economics['annual_transport_cost']:>15,.0f}")
    print(f"Construction Cost:       ${economics['total_construction_cost']:>15,.0f}")
    print(f"5-Year Total Cost:       ${economics['total_cost_5yr']:>15,.0f}")
    print(f"Cost per Animal/Year:    ${economics['cost_per_animal_per_year']:>15,.2f}")
    print(f"Truck Trips per Year:    {economics['total_truckloads_per_year']:>15,.0f}")
    print(f"Average Distance:        {economics['avg_distance_km']:>15,.1f} km")

    print(f"\n📊 Zone Balance:\n")
    for idx, hub in hubs_gdf.iterrows():
        pct_animals = hub['zone_animals'] / afos_gdf['headcount'].sum() * 100
        pct_afos = hub['zone_afos'] / len(afos_gdf[afos_gdf['assigned_site_idx'] >= 0]) * 100
        print(f"Hub {hub['site_id']}: {pct_afos:5.1f}% of AFOs, {pct_animals:5.1f}% of animals")

    print("\n" + "=" * 70)


def main():
    parser = argparse.ArgumentParser(description="Realistic AFO Optimization with Capacity Constraints")
    parser.add_argument("--permits", type=str, default=None, help="Path to AFO permits")
    parser.add_argument("--region", type=str, default="eastern-shore",
                       help="Region: 'eastern-shore', 'full-state', or county name")
    parser.add_argument("--n-sites", type=int, default=3, help="Number of digester hubs")
    parser.add_argument("--max-capacity", type=int, default=MAX_CAPACITY_ANIMALS,
                       help="Max animals per hub")
    parser.add_argument("--output-dir", type=str, default=None, help="Output directory")

    args = parser.parse_args()
    config = get_config()

    # Load permits
    permits_path = args.permits or str(config.processed_dir / "afo_permits.gpkg")
    logger.info(f"Loading AFO permits from {permits_path}")

    if not Path(permits_path).exists():
        logger.error(f"Permits file not found: {permits_path}")
        logger.error("Run: python scripts/run_phase1.py")
        sys.exit(1)

    afos = gpd.read_file(permits_path)

    # Filter region
    afos_filtered = filter_region(afos, args.region)
    logger.info(f"Region: {args.region}")
    logger.info(f"AFOs: {len(afos_filtered)}")
    logger.info(f"Total animals: {afos_filtered['headcount'].sum():,.0f}")

    # Run optimization
    hubs_gdf, afos_assigned, total_transport_km = optimize_with_capacity(
        afos_filtered,
        args.n_sites,
        args.max_capacity
    )

    # Calculate economics
    economics = calculate_economics(hubs_gdf, afos_assigned, total_transport_km)

    # Print results
    print_results(hubs_gdf, afos_assigned, economics)

    # Save outputs
    output_dir = Path(args.output_dir or config.processed_dir / "optimization_realistic")
    output_dir.mkdir(parents=True, exist_ok=True)

    hubs_path = output_dir / "optimal_hubs_realistic.geojson"
    assignments_path = output_dir / "afo_assignments_realistic.geojson"

    hubs_gdf.to_file(hubs_path, driver="GeoJSON")
    afos_assigned.to_file(assignments_path, driver="GeoJSON")

    logger.info(f"\n✅ Results saved to {output_dir}")
    logger.info(f"   - {hubs_path.name}")
    logger.info(f"   - {assignments_path.name}")

    # Save summary report
    report_path = output_dir / "optimization_summary.txt"
    with open(report_path, 'w') as f:
        f.write(f"GEO-ANOM Realistic Optimization Summary\n")
        f.write(f"=" * 70 + "\n\n")
        f.write(f"Region: {args.region}\n")
        f.write(f"AFOs Analyzed: {len(afos_filtered)}\n")
        f.write(f"Hub Sites: {args.n_sites}\n")
        f.write(f"Max Capacity per Hub: {args.max_capacity:,} animals\n\n")
        f.write(f"Economic Results:\n")
        for key, value in economics.items():
            f.write(f"  {key}: {value:,.2f}\n")

    logger.info(f"   - {report_path.name}")


if __name__ == "__main__":
    main()
