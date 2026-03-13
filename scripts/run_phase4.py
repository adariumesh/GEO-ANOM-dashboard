#!/usr/bin/env python3
"""
GEO-ANOM Phase 4: Geospatial Optimization Modeling (GOM)

This script runs the location-allocation model to determine optimal sites
for anaerobic digesters based on nutrient supply (AFOs) and demand mapping.
"""

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import geopandas as gpd
from geo_anom.core.config import get_config
from geo_anom.core.logging import setup_logger
from geo_anom.phase4.optimizer import LocationAllocator

logger = setup_logger(__name__)

def main():
    parser = argparse.ArgumentParser(description="GEO-ANOM Phase 4: Optimization")
    parser.add_argument("--permits", type=str, help="Path to processed AFO permits GPKG")
    parser.add_argument("--n-sites", type=int, default=5, help="Number of digester sites to locate")
    parser.add_argument("--output-dir", type=str, help="Directory to save optimization results")
    parser.add_argument("--upload-to-gcs", action="store_true", help="Upload results to GCS")
    
    args = parser.parse_args()
    config = get_config()
    
    # Defaults
    permits_path = args.permits or str(config.processed_dir / "afo_permits.gpkg")
    output_dir = Path(args.output_dir or config.processed_dir / "optimization")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    if not Path(permits_path).exists():
        logger.error(f"Permits file not found: {permits_path}. Run Phase 1 first.")
        sys.exit(1)
        
    logger.info("============================================================")
    logger.info("GEO-ANOM Phase 4: Geospatial Optimization Modeling")
    logger.info("============================================================")
    logger.info(f"Input Permits: {permits_path}")
    logger.info(f"Target Sites: {args.n_sites}")
    
    # Load Supply Data
    supply_gdf = gpd.read_file(permits_path)
    if len(supply_gdf) == 0:
        logger.error("No AFO permits found in input file.")
        sys.exit(1)
        
    allocator = LocationAllocator(config=config)
    
    # Run Optimization
    result = allocator.optimize(
        supply_gdf=supply_gdf,
        n_facilities=args.n_sites
    )
    
    # Save Results
    sites_path = output_dir / "optimal_digester_sites.geojson"
    assignments_path = output_dir / "afo_assignments.geojson"
    
    result.optimal_sites.to_file(sites_path, driver="GeoJSON")
    result.assignments.to_file(assignments_path, driver="GeoJSON")
    
    logger.info(f"\nOptimization complete!")
    logger.info(f"Total Transport Effort: {result.total_transport_cost:.2f} animal-km")
    logger.info(f"Optimal sites saved to: {sites_path}")
    logger.info(f"AFO assignments saved to: {assignments_path}")
    
    if args.upload_to_gcs:
        from geo_anom.core.cloud_storage import get_storage
        storage = get_storage(config)
        
        for local_file in [sites_path, assignments_path]:
            gcs_uri = f"gs://{config.cloud.gcs_bucket}/{config.cloud.processed_prefix}optimization/{local_file.name}"
            logger.info(f"Uploading {local_file.name} to GCS...")
            storage.upload(local_file, gcs_uri)

if __name__ == "__main__":
    main()
