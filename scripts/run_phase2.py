#!/usr/bin/env python3
"""
Phase 2 CLI: Nutrient Supply Mapping (NSM) — Full GEOAI Pipeline.

Runs YOLO-World zero-shot detection → SAM segmentation → AlphaEarth filtering → Supply calculation.

Usage:
    python scripts/run_phase2.py
    python scripts/run_phase2.py --tile-dir data/raw/naip_tiles --limit 3
    python scripts/run_phase2.py --skip-alphaearth --device mps
    python scripts/run_phase2.py --use-custom-model data/models/yolo_afo.pt
"""

from __future__ import annotations

import argparse
import sys
import ssl
from pathlib import Path

# Temporary workaround: disable SSL verification globally for this script
# to allow `clip` weight downloads from local machines with strict SSL configs.
ssl._create_default_https_context = ssl._create_unverified_context

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from geo_anom.core.config import load_config
from geo_anom.core.logging import setup_logger
from geo_anom.phase2.yolo_world_detector import YOLOWorldDetector
from geo_anom.phase2.yolo_detector import YOLODetector
from geo_anom.phase2.sam_segmenter import SAMSegmenter
from geo_anom.phase2.alphaearth_filter import AlphaEarthFilter
from geo_anom.phase2.supply_calculator import SupplyCalculator


def main():
    parser = argparse.ArgumentParser(
        description="GEO-ANOM Phase 2: Nutrient Supply Mapping (YOLO → SAM → AlphaEarth)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--tile-dir", type=str, default=None,
                        help="Directory containing NAIP tiles (default: data/raw/naip_tiles)")
    parser.add_argument("--permits", type=str, default=None,
                        help="Path to processed AFO permits GeoPackage")
    parser.add_argument("--output-dir", type=str, default=None,
                        help="Output directory (default: data/processed)")
    parser.add_argument("--limit", type=int, default=None,
                        help="Process at most N tiles (for testing)")
    parser.add_argument("--device", type=str, default="cpu",
                        choices=["cpu", "cuda", "mps"],
                        help="Compute device for YOLO and SAM")
    parser.add_argument("--skip-alphaearth", action="store_true",
                        help="Skip AlphaEarth false-positive filtering")
    parser.add_argument("--use-custom-model", type=str, default=None,
                        help="Path to fine-tuned YOLOv8 weights (default: YOLO-World zero-shot)")
    parser.add_argument("--prompts", type=str, nargs="+", default=None,
                        help="Override YOLO-World text prompts (default: from config)")
    parser.add_argument("--config", type=str, default=None,
                        help="Path to YAML config file")

    args = parser.parse_args()
    config = load_config(args.config)
    logger = setup_logger("geo_anom.phase2", level=config.env.log_level)

    tile_dir = Path(args.tile_dir) if args.tile_dir else config.raw_dir / "naip_tiles"
    output_dir = Path(args.output_dir) if args.output_dir else config.processed_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 60)
    logger.info("GEO-ANOM Phase 2: Nutrient Supply Mapping")
    logger.info("=" * 60)
    logger.info("Tile dir  : %s", tile_dir)
    logger.info("Output dir: %s", output_dir)
    logger.info("Device    : %s", args.device)

    # ---- Step 1: YOLOv8 Detection ----
    logger.info("\n--- Step 1: AFO Detection (YOLO-World zero-shot) ---")

    if args.use_custom_model:
        # Fine-tuned weights path provided → use classic YOLODetector
        logger.info("Using fine-tuned model: %s", args.use_custom_model)
        detector = YOLODetector(
            model_path=args.use_custom_model,
            device=args.device,
            config=config,
        )
    else:
        # Default: YOLO-World open-vocabulary (zero-shot, no fine-tuning)
        logger.info(
            "Using YOLO-World (zero-shot). Prompts: %s",
            args.prompts or config.yolo_world.text_prompts,
        )
        detector = YOLOWorldDetector(
            text_prompts=args.prompts or None,
            device=args.device,
            config=config,
        )

    detections_geojson = output_dir / "detections" / "yolo_detections.geojson"
    detections = detector.detect_aoi(
        tile_dir,
        output_geojson=detections_geojson,
        limit=args.limit,
    )
    logger.info("Detector produced %d detections", len(detections))

    if not detections:
        logger.warning("No YOLO detections. Generating fallback boxes from AFO permits...")
        import geopandas as gpd
        import rasterio
        from shapely.geometry import box
        from geo_anom.phase2.yolo_detector import Detection
        
        afo_path = args.permits or str(config.processed_dir / "afo_permits.gpkg")
        if Path(afo_path).exists():
            afo_gdf = gpd.read_file(afo_path)
            if afo_gdf.crs != "EPSG:4326":
                afo_gdf = afo_gdf.to_crs("EPSG:4326")
                
            for t_path in sorted(tile_dir.glob("*.tif")):
                try:
                    with rasterio.open(t_path) as src:
                        transform = src.transform
                        w, s, e, n = src.bounds
                        tile_box = box(w, s, e, n)
                        
                        in_tile = afo_gdf[afo_gdf.geometry.intersects(tile_box)]
                        for _, row in in_tile.iterrows():
                            lon, lat = row.geometry.x, row.geometry.y
                            py, px = rasterio.transform.rowcol(transform, lon, lat)
                            
                            b_size = 100
                            x1 = int(max(0, px - b_size//2))
                            y1 = int(max(0, py - b_size//2))
                            x2 = int(min(src.width, px + b_size//2))
                            y2 = int(min(src.height, py + b_size//2))
                            
                            if x2 > x1 and y2 > y1:
                                det = Detection(
                                    bbox_px=(x1, y1, x2, y2),
                                    bbox_geo=(lon-0.001, lat-0.001, lon+0.001, lat+0.001), 
                                    confidence=1.0,
                                    class_id=0,
                                    class_name=row.get("animal_type", "afo_structure"),
                                    tile_path=str(t_path)
                                )
                                detections.append(det)
                except Exception:
                    pass
        
        logger.info("Generated %d fallback detections from permits.", len(detections))
        
        if not detections:
            logger.warning("Still no detections. Exiting Phase 2.")
            return

    # ---- Step 2: SAM2 Segmentation ----
    logger.info("\n--- Step 2: SAM2 Segmentation ---")
    segmenter = SAMSegmenter(device=args.device, config=config)

    # Group detections by tile
    tile_groups: dict[str, list] = {}
    for det in detections:
        tile_groups.setdefault(det.tile_path, []).append(det)

    all_segmented = []
    for tile_path, tile_dets in tile_groups.items():
        segmented = segmenter.segment_tile(tile_path, tile_dets)
        all_segmented.extend(segmented)

    # Export polygons
    polygons_geojson = output_dir / "masks" / "sam_polygons.geojson"
    segmenter.export_polygons(all_segmented, polygons_geojson)
    logger.info("SAM2 produced %d polygon masks", len(all_segmented))

    # ---- Step 3: AlphaEarth Filtering (optional) ----
    if not args.skip_alphaearth:
        logger.info("\n--- Step 3: AlphaEarth False-Positive Filtering ---")
        import geopandas as gpd

        # Load polygons as GeoDataFrame
        candidates_gdf = gpd.read_file(polygons_geojson)
        ae_filter = AlphaEarthFilter(config=config)

        # Load known AFOs for reference
        permits_path = args.permits or str(config.processed_dir / "afo_permits.gpkg")
        if Path(permits_path).exists():
            afo_gdf = gpd.read_file(permits_path)
            ae_filter.build_reference_db(afo_gdf)

        validated_gdf = ae_filter.classify(candidates_gdf)

        # Keep only validated AFOs
        validated_gdf = validated_gdf[validated_gdf["ae_is_afo"]].copy()
        validated_path = output_dir / "masks" / "validated_polygons.gpkg"
        validated_gdf.to_file(str(validated_path), driver="GPKG")
        logger.info("Validated %d polygons after AlphaEarth filtering", len(validated_gdf))
    else:
        logger.info("\n--- Step 3: AlphaEarth filtering SKIPPED ---")
        import geopandas as gpd

        validated_gdf = gpd.read_file(polygons_geojson)
        validated_gdf["area_m2"] = validated_gdf.geometry.to_crs("EPSG:32618").area

    # ---- Step 4: Nutrient Supply Calculation ----
    logger.info("\n--- Step 4: Nutrient Supply Calculation ---")
    calculator = SupplyCalculator(config=config)

    permits_path = args.permits or str(config.processed_dir / "afo_permits.gpkg")
    if Path(permits_path).exists():
        import geopandas as gpd

        afo_permits = gpd.read_file(permits_path)
        supply_gdf = calculator.calculate_supply(validated_gdf, afo_permits)
        supply_output = output_dir / "supply_maps" / "nutrient_supply.gpkg"
        calculator.export_supply_map(supply_gdf, supply_output)
    else:
        logger.warning(
            "AFO permits file not found at %s. "
            "Run Phase 1 first, or specify --permits path.",
            permits_path,
        )

    logger.info("\n" + "=" * 60)
    logger.info("Phase 2 complete!")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
