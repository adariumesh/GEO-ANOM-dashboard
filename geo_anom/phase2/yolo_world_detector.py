"""
YOLO-World Zero-Shot Detector for AFO Infrastructure.

Uses Ultralytics YOLO-World (open-vocabulary) to detect AFO structures
via text prompts — no fine-tuning required. Text prompts like "poultry house"
and "manure lagoon" are passed directly at inference time.

Reference: https://docs.ultralytics.com/models/yolo-world/
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import xy

from geo_anom.core.config import get_config, GeoAnomConfig
from geo_anom.core.logging import setup_logger
from geo_anom.phase2.yolo_detector import Detection  # reuse Detection dataclass

logger = setup_logger(__name__)


class YOLOWorldDetector:
    """
    Open-vocabulary (zero-shot) detector for AFO infrastructure via YOLO-World.

    YOLO-World uses a vision-language model to detect arbitrary object classes
    described in text. No domain-specific training data needed.

    This class is a **drop-in replacement** for ``YOLODetector`` with the same
    ``detect_tile()`` / ``detect_aoi()`` interface.

    Parameters
    ----------
    text_prompts : list[str], optional
        Text descriptions of classes to detect. Defaults to config values.
    model_name : str, optional
        YOLO-World checkpoint name (auto-downloaded on first run).
    conf_threshold : float, optional
        Minimum confidence score.
    device : str
        "cpu", "cuda", or "mps".
    """

    def __init__(
        self,
        text_prompts: list[str] | None = None,
        model_name: str | None = None,
        conf_threshold: float | None = None,
        device: str = "cpu",
        config: GeoAnomConfig | None = None,
    ) -> None:
        self.config = config or get_config()
        self.device = device

        # Resolve YOLO-World config section
        yw_cfg = getattr(self.config, "yolo_world", None)

        self.model_name = model_name or (
            yw_cfg.model if yw_cfg else "yolov8x-worldv2.pt"
        )
        self.conf = conf_threshold or (
            yw_cfg.confidence_threshold if yw_cfg else 0.15
        )
        self.iou = yw_cfg.iou_threshold if yw_cfg else 0.40
        self.image_size = yw_cfg.image_size if yw_cfg else 1024

        # Text prompts — the "classes" for open-vocabulary detection
        self.text_prompts = text_prompts or (
            list(yw_cfg.text_prompts) if yw_cfg else [
                "poultry house", "chicken barn", "manure lagoon",
                "feedlot", "grain silo", "agricultural pond",
            ]
        )

        self._model = None
        logger.info(
            "YOLOWorldDetector: model=%s, prompts=%s, device=%s",
            self.model_name, self.text_prompts, self.device,
        )

    # ------------------------------------------------------------------
    # Model loading (lazy)
    # ------------------------------------------------------------------

    def _load_model(self):
        """Lazy-load YOLO-World model with text prompts."""
        if self._model is None:
            from ultralytics import YOLOWorld

            logger.info(
                "Loading YOLO-World model: %s (first run will auto-download ~260MB)",
                self.model_name,
            )
            self._model = YOLOWorld(self.model_name)

            # Set text prompts — this is the zero-shot magic
            self._model.set_classes(self.text_prompts)
            logger.info("YOLO-World classes set: %s", self.text_prompts)

        return self._model

    # ------------------------------------------------------------------
    # Single tile detection
    # ------------------------------------------------------------------

    def detect_tile(self, tile_path: Path | str) -> list[Detection]:
        """
        Run YOLO-World inference on a single NAIP tile.

        Parameters
        ----------
        tile_path : Path
            Path to a GeoTIFF tile.

        Returns
        -------
        list[Detection]
            Detections with pixel and geographic bounding boxes.
        """
        tile_path = Path(tile_path)
        model = self._load_model()

        # Read raster transform for pixel→geo conversion
        try:
            with rasterio.open(tile_path) as src:
                transform = src.transform
        except Exception as e:
            logger.warning("Skipping invalid tile %s: %s", tile_path.name, e)
            return []

        # Run YOLO-World inference
        results = model.predict(
            source=str(tile_path),
            conf=self.conf,
            iou=self.iou,
            imgsz=self.image_size,
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

                cls_name = (
                    self.text_prompts[cls_id]
                    if cls_id < len(self.text_prompts)
                    else f"class_{cls_id}"
                )

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

        logger.info(
            "YOLO-World | tile=%s | %d detections (conf≥%.2f)",
            tile_path.name, len(detections), self.conf,
        )
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
        Run YOLO-World detection on all tiles in a directory.

        Parameters
        ----------
        tile_dir : Path
            Directory of NAIP GeoTIFF tiles.
        output_geojson : Path, optional
            Where to save combined GeoJSON detections.
        limit : int, optional
            Max tiles to process (for testing).

        Returns
        -------
        list[Detection]
        """
        tile_dir = Path(tile_dir)
        tiles = sorted(tile_dir.glob("*.tif"))
        if limit:
            tiles = tiles[:limit]

        logger.info(
            "YOLO-World AOI detection: %d tiles in %s", len(tiles), tile_dir
        )

        all_detections: list[Detection] = []
        for tile_path in tiles:
            dets = self.detect_tile(tile_path)
            all_detections.extend(dets)

        logger.info(
            "YOLO-World total: %d detections across %d tiles",
            len(all_detections), len(tiles),
        )

        if output_geojson:
            self._export_geojson(all_detections, Path(output_geojson))

        return all_detections

    # ------------------------------------------------------------------
    # GeoJSON export
    # ------------------------------------------------------------------

    def _export_geojson(
        self, detections: list[Detection], output_path: Path
    ) -> None:
        """Export detections as GeoJSON FeatureCollection."""
        output_path.parent.mkdir(parents=True, exist_ok=True)

        features = []
        for det in detections:
            if det.bbox_geo is None:
                continue

            w, s, e, n = det.bbox_geo
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[w, s], [e, s], [e, n], [w, n], [w, s]]],
                },
                "properties": {
                    "class_name": det.class_name,
                    "confidence": round(float(det.confidence), 4),
                    "detector": "yolo-world",
                    "tile": Path(det.tile_path).name,
                    "bbox_px": [int(x) for x in det.bbox_px],
                },
            })

        with open(output_path, "w") as f:
            json.dump({"type": "FeatureCollection", "features": features}, f, indent=2)

        logger.info("Exported %d detections → %s", len(features), output_path)

    # ------------------------------------------------------------------
    # Coordinate conversion (shared with base YOLODetector)
    # ------------------------------------------------------------------

    @staticmethod
    def _pixel_to_geo(
        x1: int, y1: int, x2: int, y2: int, transform
    ) -> tuple[float, float, float, float]:
        lon1, lat1 = xy(transform, y1, x1)
        lon2, lat2 = xy(transform, y2, x2)
        return (min(lon1, lon2), min(lat1, lat2), max(lon1, lon2), max(lat1, lat2))
