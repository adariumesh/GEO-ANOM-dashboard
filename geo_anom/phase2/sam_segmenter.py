"""
SAM2 Zero-Shot Segmenter for AFO Infrastructure.

Takes YOLO bounding-box detections as prompts and produces precise polygon
masks for lagoons, poultry houses, and other structures using the Segment
Anything Model 2 (SAM2).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import xy
from shapely.geometry import Polygon, mapping
from shapely import simplify

from geo_anom.core.config import get_config, GeoAnomConfig
from geo_anom.core.geo_utils import polygon_area_m2
from geo_anom.core.logging import setup_logger

logger = setup_logger(__name__)


@dataclass
class SegmentedObject:
    """Result of SAM2 segmentation on a single detection."""

    class_name: str
    confidence: float
    mask: np.ndarray | None          # Binary mask (H, W)
    polygon_px: list[tuple[int, int]]   # Pixel-space polygon vertices
    polygon_geo: Polygon | None      # Geographic polygon (WGS84)
    area_m2: float = 0.0
    tile_path: str = ""
    properties: dict = field(default_factory=dict)


class SAMSegmenter:
    """
    SAM2 zero-shot segmenter for AFO structures.

    Uses bounding-box prompts from YOLO detections to extract precise
    polygon masks from NAIP imagery.

    Parameters
    ----------
    model_type : str
        SAM2 model variant (e.g. "sam2_hiera_large").
    device : str
        Compute device ("cpu", "cuda", "mps").
    """

    def __init__(
        self,
        model_type: str | None = None,
        device: str = "cpu",
        config: GeoAnomConfig | None = None,
    ) -> None:
        self.config = config or get_config()
        self.model_type = model_type or self.config.sam.model_type
        self.device = device
        self._predictor = None

    def _load_model(self):
        """Lazy-load SAM2 model and predictor."""
        if self._predictor is None:
            try:
                from sam2.build_sam import build_sam2
                from sam2.sam2_image_predictor import SAM2ImagePredictor

                logger.info("Loading SAM2 model: %s (device=%s)", self.model_type, self.device)
                sam_model = build_sam2(self.model_type, device=self.device)
                self._predictor = SAM2ImagePredictor(sam_model)
            except ImportError:
                logger.warning(
                    "SAM2 not installed. Install with: pip install segment-anything-2. "
                    "Falling back to bbox-only polygons."
                )
                self._predictor = "FALLBACK"

        return self._predictor

    # ------------------------------------------------------------------
    # Single detection segmentation
    # ------------------------------------------------------------------

    def segment_detection(
        self,
        image: np.ndarray,
        bbox: tuple[int, int, int, int],
        transform=None,
    ) -> tuple[np.ndarray | None, list[tuple[int, int]]]:
        """
        Segment a single detection using its bounding box as a prompt.

        Parameters
        ----------
        image : np.ndarray
            Full tile image array (H, W, C).
        bbox : tuple
            (x1, y1, x2, y2) bounding box in pixel coordinates.
        transform : rasterio Affine, optional
            Geo-transform for coordinate conversion.

        Returns
        -------
        tuple[np.ndarray | None, list[tuple]]
            Binary mask and polygon vertices in pixel space.
        """
        predictor = self._load_model()

        if predictor == "FALLBACK":
            # Return bbox as a rectangular polygon
            x1, y1, x2, y2 = bbox
            polygon_px = [(x1, y1), (x2, y1), (x2, y2), (x1, y2), (x1, y1)]
            return None, polygon_px

        # Set the image for prediction
        predictor.set_image(image)

        # Use bbox as prompt
        input_box = np.array(bbox)  # [x1, y1, x2, y2]

        masks, scores, _ = predictor.predict(
            box=input_box[None, :],
            multimask_output=True,
        )

        # Select the mask with highest score
        best_idx = np.argmax(scores)
        best_mask = masks[best_idx]

        # Check minimum area
        if best_mask.sum() < self.config.sam.min_mask_area_px:
            logger.debug("Mask too small (%d px), skipping", best_mask.sum())
            return None, []

        # Extract polygon from mask contour
        polygon_px = self._mask_to_polygon(best_mask)

        return best_mask, polygon_px

    # ------------------------------------------------------------------
    # Tile-level segmentation
    # ------------------------------------------------------------------

    def segment_tile(
        self,
        tile_path: Path | str,
        detections: list,  # list[Detection] from yolo_detector
    ) -> list[SegmentedObject]:
        """
        Segment all detections on a single tile.

        Parameters
        ----------
        tile_path : Path
            Path to the NAIP GeoTIFF tile.
        detections : list[Detection]
            YOLO detection results for this tile.

        Returns
        -------
        list[SegmentedObject]
            Segmented objects with masks and geographic polygons.
        """
        tile_path = Path(tile_path)

        with rasterio.open(tile_path) as src:
            # Read as (C, H, W) then transpose to (H, W, C)
            bands = src.read()
            image = np.moveaxis(bands[:3], 0, -1)  # Use RGB only
            transform = src.transform

        segmented = []
        for det in detections:
            mask, polygon_px = self.segment_detection(image, det.bbox_px, transform)

            if not polygon_px or len(polygon_px) < 4:
                continue

            # Convert pixel polygon to geographic coordinates
            polygon_geo = self._pixel_polygon_to_geo(polygon_px, transform)

            # Simplify polygon
            tolerance = self.config.sam.simplify_tolerance_m / 111_000  # degrees approx
            polygon_geo = simplify(polygon_geo, tolerance, preserve_topology=True)

            # Calculate area
            area = polygon_area_m2(polygon_geo)

            seg_obj = SegmentedObject(
                class_name=det.class_name,
                confidence=det.confidence,
                mask=mask,
                polygon_px=polygon_px,
                polygon_geo=polygon_geo,
                area_m2=area,
                tile_path=str(tile_path),
                properties={
                    "class_id": det.class_id,
                    "yolo_confidence": det.confidence,
                },
            )
            segmented.append(seg_obj)

        logger.info(
            "Tile %s: segmented %d / %d detections",
            tile_path.name, len(segmented), len(detections),
        )
        return segmented

    # ------------------------------------------------------------------
    # GeoJSON export
    # ------------------------------------------------------------------

    def export_polygons(
        self,
        segmented_objects: list[SegmentedObject],
        output_path: Path | str,
    ) -> Path:
        """
        Export segmented polygons as a GeoJSON FeatureCollection.

        Parameters
        ----------
        segmented_objects : list[SegmentedObject]
            Segmented objects with geographic polygons.
        output_path : Path
            Output GeoJSON file path.

        Returns
        -------
        Path
            Path to the written GeoJSON.
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        features = []
        for obj in segmented_objects:
            if obj.polygon_geo is None or obj.polygon_geo.is_empty:
                continue

            feature = {
                "type": "Feature",
                "geometry": mapping(obj.polygon_geo),
                "properties": {
                    "class_name": obj.class_name,
                    "confidence": round(obj.confidence, 4),
                    "area_m2": round(obj.area_m2, 2),
                    "area_acres": round(obj.area_m2 / 4046.86, 4),
                    "tile": Path(obj.tile_path).name,
                    **obj.properties,
                },
            }
            features.append(feature)

        geojson = {
            "type": "FeatureCollection",
            "features": features,
        }

        with open(output_path, "w") as f:
            json.dump(geojson, f, indent=2)

        logger.info("Exported %d polygons → %s", len(features), output_path)
        return output_path

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _mask_to_polygon(mask: np.ndarray) -> list[tuple[int, int]]:
        """
        Extract the largest contour from a binary mask as a polygon.

        Uses a simple boundary-tracing approach without OpenCV dependency.
        """
        try:
            import cv2

            contours, _ = cv2.findContours(
                mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )
            if not contours:
                return []

            # Take the largest contour
            largest = max(contours, key=cv2.contourArea)
            polygon = [(int(pt[0][0]), int(pt[0][1])) for pt in largest]

            # Close the polygon
            if polygon and polygon[0] != polygon[-1]:
                polygon.append(polygon[0])

            return polygon

        except ImportError:
            # Fallback: use bounding box of the mask
            rows = np.any(mask, axis=1)
            cols = np.any(mask, axis=0)
            if not rows.any():
                return []
            y1, y2 = np.where(rows)[0][[0, -1]]
            x1, x2 = np.where(cols)[0][[0, -1]]
            return [(x1, y1), (x2, y1), (x2, y2), (x1, y2), (x1, y1)]

    @staticmethod
    def _pixel_polygon_to_geo(
        polygon_px: list[tuple[int, int]], transform
    ) -> Polygon:
        """Convert pixel-coordinate polygon to geographic Shapely Polygon."""
        geo_coords = []
        for px_x, px_y in polygon_px:
            lon, lat = xy(transform, px_y, px_x)
            geo_coords.append((lon, lat))
        return Polygon(geo_coords)
