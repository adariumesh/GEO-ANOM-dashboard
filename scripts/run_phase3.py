#!/usr/bin/env python3
"""
GEO-ANOM Phase 3: Nutrient Demand Mapping (NDM)

This script processes the USDA Cropland Data Layer (CDL) raster to calculate
the nutrient uptake requirement (demand) for nitrogen and phosphorus across 
the study area, applying environmental setbacks if available.
"""

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from geo_anom.core.config import get_config
from geo_anom.core.logging import setup_logger
from geo_anom.phase3.demand_map import DemandMapBuilder

logger = setup_logger(__name__)

def main():
    parser = argparse.ArgumentParser(description="GEO-ANOM Phase 3: Nutrient Demand Mapping")
    parser.add_argument("--cdl", type=str, help="Path to input CDL GeoTIFF")
    parser.add_argument("--setbacks", type=str, help="Path to waterway setbacks shapefile (optional)")
    parser.add_argument("--output-dir", type=str, help="Directory to save output demand maps")
    parser.add_argument("--upload-to-gcs", action="store_true", help="Upload outputs to GCS")
    
    args = parser.parse_args()
    config = get_config()
    
    # Defaults
    cdl_path = args.cdl or str(config.raw_dir / "cdl" / "cdl_24_2023.tif")
    output_dir = Path(args.output_dir or config.processed_dir / "demand_maps")
    
    if not Path(cdl_path).exists():
        logger.error(f"CDL raster not found: {cdl_path}. Run Phase 1 first.")
        sys.exit(1)
        
    logger.info("============================================================")
    logger.info("GEO-ANOM Phase 3: Nutrient Demand Mapping")
    logger.info("============================================================")
    logger.info(f"Input CDL: {cdl_path}")
    logger.info(f"Output Dir: {output_dir}")
    if args.setbacks:
        logger.info(f"Setbacks: {args.setbacks}")
    
    builder = DemandMapBuilder(config=config)
    
    # Run pipeline
    demand_rasters = builder.build(
        cdl_path=cdl_path,
        setback_path=args.setbacks,
        output_dir=output_dir
    )
    
    # Final Summary
    logger.info("\nPhase 3 complete!")
    logger.info(f"Results saved to: {output_dir}")
    
    if args.upload_to_gcs:
        from geo_anom.core.cloud_storage import get_storage
        storage = get_storage(config)
        
        for name in ["N_demand.tif", "P2O5_demand.tif"]:
            local_file = output_dir / name
            if local_file.exists():
                gcs_uri = f"gs://{config.cloud.gcs_bucket}/{config.cloud.processed_prefix}demand_maps/{name}"
                logger.info(f"Uploading {name} to GCS...")
                storage.upload(local_file, gcs_uri)

if __name__ == "__main__":
    main()
