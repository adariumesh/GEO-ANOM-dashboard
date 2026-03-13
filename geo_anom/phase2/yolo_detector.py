"""
YOLOv8 Object Detector for AFO Infrastructure.

Runs YOLOv8 inference on NAIP tiles to detect poultry houses, barns,
manure lagoons, feedlots, and silos. Outputs geo-referenced detections
as GeoJSON for downstream SAM2 segmentation.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import xy

from geo_anom.core.config import get_config, GeoAnomConfig
from geo_anom.core.logging import setup_logger

logger = setup_logger(__name__)


@dataclass
class Detection:
    """A single object detection result."""

    bbox_px: tuple[int, int, int, int]       # (x1, y1, x2, y2) in pixel coords
    bbox_geo: tuple[float, float, float, float] | None  # (west, south, east, north) WGS84
    confidence: float
    class_id: int
    class_name: str
    tile_path: str

    @property
    def center_px(self) -> tuple[int, int]:
        x1, y1, x2, y2 = self.bbox_px
        return ((x1 + x2) // 2, (y1 + y2) // 2)


class YOLODetector:
    """
    YOLOv8-based detector for AFO infrastructure in NAIP imagery.

    Wraps the Ultralytics YOLO API to run inference and convert pixel-space
    detections into geo-referenced bounding boxes using the tile's rasterio
    transform.

    Parameters
    ----------
    model_path : str or Path, optional
        Path to fine-tuned YOLOv8 weights. Falls back to base model.
    conf_threshold : float, optional
        Minimum confidence score to keep a detection.
    device : str
        "cpu", "cuda", or "mps" (Apple Silicon).
    """

    def __init__(
        self,
        model_path: str | Path | None = None,
        conf_threshold: float | None = None,
        device: str = "cpu",
        config: GeoAnomConfig | None = None,
    ) -> None:
        self.config = config or get_config()
        self.device = device
        self.conf = conf_threshold or self.config.yolo.confidence_threshold

        # Resolve model path
        if model_path:
            self._model_path = str(model_path)
        else:
            fine_tuned = self.config.project_root / self.config.yolo.weights_path
            if fine_tuned.exists():
                self._model_path = str(fine_tuned)
            else:
                self._model_path = self.config.yolo.base_model
                logger.warning(
                    "Fine-tuned weights not found at %s; using base model %s",
                    fine_tuned, self._model_path,
                )

        self._model = None

    def _load_model(self):
        """Lazy-load the YOLO model."""
        if self._model is None:
            from ultralytics import YOLO

            logger.info("Loading YOLOv8 model from %s (device=%s)", self._model_path, self.device)
            self._model = YOLO(self._model_path)
        return self._model

    # ------------------------------------------------------------------
    # Single tile inference
    # ------------------------------------------------------------------

    def detect_tile(self, tile_path: Path | str) -> list[Detection]:
        """
        Run YOLOv8 inference on a single NAIP tile.

        Parameters
        ----------
        tile_path : Path
            Path to a GeoTIFF tile.

        Returns
        -------
        list[Detection]
            Detections with both pixel and geographic bounding boxes.
        """
        tile_path = Path(tile_path)
        model = self._load_model()

        # Read the raster transform for pixel→geo conversion
        with rasterio.open(tile_path) as src:
            transform = src.transform
            crs = src.crs

        # Run YOLO inference
        results = model.predict(
            source=str(tile_path),
            conf=self.conf,
            iou=self.config.yolo.iou_threshold,
            imgsz=self.config.yolo.image_size,
            device=self.device,
            verbose=False,
        )

        detections = []
        for result in results:
            boxes = result.boxes
            if boxes is None or len(boxes) == 0:
                continue

            for i in range(len(boxes)):
                x1, y1, x2, y2 = boxes.xyxy[i].cpu().numpy().astype(int)
                conf = float(boxes.conf[i].cpu().numpy())
                cls_id = int(boxes.cls[i].cpu().numpy())

                # Map class ID to name
                cls_name = self.config.yolo.classes[cls_id] if cls_id < len(
                    self.config.yolo.classes
                ) else f"class_{cls_id}"

                # Convert pixel bbox to geographic coordinates
                geo_bbox = self._pixel_to_geo(x1, y1, x2, y2, transform)

                det = Detection(
                    bbox_px=(x1, y1, x2, y2),
                    bbox_geo=geo_bbox,
                    confidence=conf,
                    class_id=cls_id,
                    class_name=cls_name,
                    tile_path=str(tile_path),
                )
                detections.append(det)

        logger.info("Tile %s: %d detections", tile_path.name, len(detections))
        return detections

    # ------------------------------------------------------------------
    # Batch processing
    # ------------------------------------------------------------------

    def detect_aoi(
        self,
        tile_dir: Path | str,
        output_geojson: Path | str | None = None,
        limit: int | None = None,
    ) -> list[Detection]:
        """
        Run detection on all tiles in a directory.

        Parameters
        ----------
        tile_dir : Path
            Directory containing NAIP GeoTIFF tiles.
        output_geojson : Path, optional
            Path to save the combined detections GeoJSON.
        limit : int, optional
            Process at most this many tiles (for testing).

        Returns
        -------
        list[Detection]
            All detections across all tiles.
        """
        tile_dir = Path(tile_dir)
        tiles = sorted(tile_dir.glob("*.tif"))
        if limit:
            tiles = tiles[:limit]

        logger.info("Running YOLOv8 detection on %d tiles in %s", len(tiles), tile_dir)

        all_detections: list[Detection] = []
        for tile_path in tiles:
            dets = self.detect_tile(tile_path)
            all_detections.extend(dets)

        logger.info("Total detections across %d tiles: %d", len(tiles), len(all_detections))

        # Export as GeoJSON
        if output_geojson:
            output_geojson = Path(output_geojson)
            self._export_geojson(all_detections, output_geojson)

        return all_detections

    # ------------------------------------------------------------------
    # GeoJSON export
    # ------------------------------------------------------------------

    def _export_geojson(self, detections: list[Detection], output_path: Path) -> None:
        """Write detections as a GeoJSON FeatureCollection."""
        output_path.parent.mkdir(parents=True, exist_ok=True)

        features = []
        for det in detections:
            if det.bbox_geo is None:
                continue

            w, s, e, n = det.bbox_geo
            feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[
                        [w, s], [e, s], [e, n], [w, n], [w, s]
                    ]],
                },
                "properties": {
                    "class_name": det.class_name,
                    "class_id": det.class_id,
                    "confidence": round(det.confidence, 4),
                    "tile": Path(det.tile_path).name,
                    "bbox_px": list(det.bbox_px),
                },
            }
            features.append(feature)

        geojson = {
            "type": "FeatureCollection",
            "features": features,
        }

        with open(output_path, "w") as f:
            json.dump(geojson, f, indent=2)

        logger.info("Exported %d detections → %s", len(features), output_path)

    # ------------------------------------------------------------------
    # Coordinate conversion
    # ------------------------------------------------------------------

    @staticmethod
    def _pixel_to_geo(
        x1: int, y1: int, x2: int, y2: int, transform
    ) -> tuple[float, float, float, float]:
        """
        Convert pixel-space bbox to geographic coordinates using rasterio transform.

        Returns (west, south, east, north) in the raster's CRS.
        """
        # Top-left corner → geographic
        lon1, lat1 = xy(transform, y1, x1)
        # Bottom-right corner → geographic
        lon2, lat2 = xy(transform, y2, x2)

        west = min(lon1, lon2)
        east = max(lon1, lon2)
        south = min(lat1, lat2)
        north = max(lat1, lat2)

        return (west, south, east, north)
