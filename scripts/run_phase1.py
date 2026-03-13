#!/usr/bin/env python3
"""
Phase 1 CLI: Data Ingestion & Targeting.

Downloads MDE AFO registry, NAIP imagery tiles, and USDA CDL data
for the Maryland study area.

Usage:
    python scripts/run_phase1.py
    python scripts/run_phase1.py --county Dorchester --limit 5
    python scripts/run_phase1.py --cdl-only --year 2023
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure project root is on the path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from geo_anom.core.config import load_config
from geo_anom.core.logging import setup_logger
from geo_anom.core.cloud_storage import get_storage
from geo_anom.phase1.afo_registry import AFORegistryClient
from geo_anom.phase1.naip_downloader import NAIPDownloader
from geo_anom.phase1.cdl_downloader import CDLDownloader


def main():
    parser = argparse.ArgumentParser(
        description="GEO-ANOM Phase 1: Data Ingestion & Targeting",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--county", type=str, default=None,
                        help="Filter AFOs to a specific county (e.g. 'Dorchester')")
    parser.add_argument("--limit", type=int, default=None,
                        help="Limit number of AFOs/tiles to process (for testing)")
    parser.add_argument("--year", type=int, default=2023,
                        help="CDL year to download (default: 2023)")
    parser.add_argument("--skip-afo", action="store_true",
                        help="Skip AFO registry download")
    parser.add_argument("--skip-naip", action="store_true",
                        help="Skip NAIP tile download")
    parser.add_argument("--cdl-only", action="store_true",
                        help="Only download CDL data")
    parser.add_argument("--upload-to-gcs", action="store_true",
                        help="Upload downloaded files to Google Cloud Storage")
    parser.add_argument("--config", type=str, default=None,
                        help="Path to YAML config file")

    args = parser.parse_args()
    config = load_config(args.config)
    logger = setup_logger("geo_anom.phase1", level=config.env.log_level)

    logger.info("=" * 60)
    logger.info("GEO-ANOM Phase 1: Data Ingestion & Targeting")
    logger.info("=" * 60)

    storage = get_storage(config) if args.upload_to_gcs else None

    # ---- Step 1: AFO Registry ----
    afo_bboxes = []
    if not args.skip_afo and not args.cdl_only:
        logger.info("\n--- Step 1: MDE AFO Registry ---")
        afo_client = AFORegistryClient(config)

        records = afo_client.download_json()
        afo_gdf = afo_client.parse_permits(records)
        afo_gdf = afo_client.filter_active_permits(afo_gdf)

        if args.county:
            afo_gdf = afo_client.filter_by_county(afo_gdf, args.county)

        if args.limit:
            afo_gdf = afo_gdf.head(args.limit)
            logger.info("Limited to %d AFOs for testing", args.limit)

        afo_bboxes = afo_client.get_target_bboxes(afo_gdf)

        # Save processed AFO data
        afo_output = config.processed_dir / "afo_permits.gpkg"
        afo_output.parent.mkdir(parents=True, exist_ok=True)
        afo_gdf.to_file(str(afo_output), driver="GPKG")
        logger.info("Saved processed AFO data → %s", afo_output)

        if storage:
            gcs_key = f"{config.cloud.processed_prefix}afo_permits.gpkg"
            storage.upload(afo_output, gcs_key)

    # ---- Step 2: NAIP Tiles ----
    if not args.skip_naip and not args.cdl_only and afo_bboxes:
        logger.info("\n--- Step 2: NAIP Imagery Tiles ---")
        naip = NAIPDownloader(config)

        tiles = naip.download_aoi(afo_bboxes, limit=args.limit)
        logger.info("Downloaded %d NAIP tiles", len(tiles))

        if storage:
            for tile_path in tiles:
                gcs_key = f"{config.cloud.naip_tiles_prefix}{tile_path.name}"
                storage.upload(tile_path, gcs_key)

    # ---- Step 3: USDA CDL ----
    if not args.skip_afo or args.cdl_only:
        logger.info("\n--- Step 3: USDA Cropland Data Layer ---")
        cdl = CDLDownloader(config)

        try:
            cdl_path = cdl.download_state_cdl(year=args.year)
            logger.info("CDL downloaded → %s", cdl_path)
            
            if storage:
                gcs_key = f"{config.cloud.processed_prefix}cdl_{args.year}.tif"
                storage.upload(cdl_path, gcs_key)
        except Exception as e:
            logger.error("CDL download failed: %s", e)

    logger.info("\n" + "=" * 60)
    logger.info("Phase 1 complete!")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
