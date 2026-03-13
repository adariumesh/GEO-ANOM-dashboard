"""
MD iMAP NAIP Tile Downloader.

Downloads high-resolution (1m) NAIP aerial imagery tiles from the
Maryland iMAP ArcGIS REST ImageServer for targeted AFO analysis areas.
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests
from tqdm import tqdm

from geo_anom.core.config import get_config, GeoAnomConfig
from geo_anom.core.geo_utils import BBox
from geo_anom.core.logging import setup_logger

logger = setup_logger(__name__)


class NAIPDownloader:
    """
    Downloads NAIP imagery tiles from the MD iMAP REST ImageServer.

    Uses the ArcGIS REST ``exportImage`` endpoint to extract GeoTIFF tiles
    for specified bounding boxes at 1-metre resolution.

    Attributes
    ----------
    config : GeoAnomConfig
        Pipeline configuration.
    """

    def __init__(self, config: GeoAnomConfig | None = None) -> None:
        self.config = config or get_config()
        self._session = requests.Session()

    # ------------------------------------------------------------------
    # Single tile export
    # ------------------------------------------------------------------

    def export_tile(
        self,
        bbox: BBox,
        output_path: Path | str,
        resolution: int | None = None,
        tile_size_px: int | None = None,
    ) -> Path:
        """
        Export a single NAIP tile as a GeoTIFF.

        Parameters
        ----------
        bbox : BBox
            Geographic bounding box (WGS84).
        output_path : Path
            Where to save the downloaded tile.
        resolution : int, optional
            Pixel resolution in metres (default 1m from config).
        tile_size_px : int, optional
            Output image size in pixels (default 1024 from config).

        Returns
        -------
        Path
            Path to the saved GeoTIFF.
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        tile_size = tile_size_px or self.config.naip.tile_size_px
        base_url = f"{self.config.endpoints.naip_image_server}/exportImage"

        params = {
            "bbox": bbox.to_esri_string(),
            "bboxSR": "4326",
            "imageSR": "4326",
            "format": self.config.naip.format,
            "size": f"{tile_size},{tile_size}",
            "f": "image",
            # Request all bands (RGBN)
            "bandIds": "",
            "noData": "",
            "interpolation": "RSP_BilinearInterpolation",
        }

        logger.debug("Requesting tile: %s", bbox.to_esri_string())

        try:
            resp = self._session.get(base_url, params=params, timeout=120, stream=True)
            resp.raise_for_status()

            # Verify we got an image, not an error JSON
            content_type = resp.headers.get("Content-Type", "")
            if "json" in content_type or "html" in content_type:
                error_msg = resp.text[:500]
                logger.error("Server returned error for bbox %s: %s", bbox.as_tuple, error_msg)
                raise RuntimeError(f"NAIP server error: {error_msg}")

            with open(output_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)

            logger.debug("Saved tile → %s (%.1f KB)", output_path, output_path.stat().st_size / 1024)
            return output_path

        except requests.exceptions.RequestException as e:
            logger.error("Failed to download tile for bbox %s: %s", bbox.as_tuple, e)
            raise

    # ------------------------------------------------------------------
    # Batch download
    # ------------------------------------------------------------------

    def download_aoi(
        self,
        bboxes: list[BBox],
        output_dir: Path | str | None = None,
        max_workers: int | None = None,
        limit: int | None = None,
    ) -> list[Path]:
        """
        Download NAIP tiles for a list of bounding boxes in parallel.

        Parameters
        ----------
        bboxes : list[BBox]
            List of target bounding boxes.
        output_dir : Path, optional
            Output directory. Defaults to ``data/raw/naip_tiles/``.
        max_workers : int, optional
            Number of parallel download threads (default from config).
        limit : int, optional
            Max tiles to download (for testing).

        Returns
        -------
        list[Path]
            Paths to all successfully downloaded tiles.
        """
        output_dir = Path(output_dir) if output_dir else self.config.raw_dir / "naip_tiles"
        output_dir.mkdir(parents=True, exist_ok=True)
        max_workers = max_workers or self.config.naip.max_workers

        if limit:
            bboxes = bboxes[:limit]

        logger.info(
            "Downloading %d NAIP tiles to %s (workers=%d)",
            len(bboxes), output_dir, max_workers,
        )

        downloaded: list[Path] = []
        delay = self.config.naip.request_delay_s

        def _download_one(idx_bbox: tuple[int, BBox]) -> Path | None:
            idx, bb = idx_bbox
            fname = f"naip_{idx:06d}_{bb.west:.4f}_{bb.south:.4f}.tif"
            out_path = output_dir / fname

            # Skip if already exists
            if out_path.exists():
                logger.debug("Tile already exists, skipping: %s", fname)
                return out_path

            try:
                result = self.export_tile(bb, out_path)
                time.sleep(delay)  # Polite rate limiting
                return result
            except Exception as e:
                logger.warning("Skipping tile %d due to error: %s", idx, e)
                return None

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(_download_one, (i, bb)): i
                for i, bb in enumerate(bboxes)
            }
            for future in tqdm(
                as_completed(futures),
                total=len(futures),
                desc="Downloading NAIP tiles",
            ):
                result = future.result()
                if result is not None:
                    downloaded.append(result)

        logger.info("Successfully downloaded %d / %d tiles", len(downloaded), len(bboxes))
        return downloaded

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def get_server_info(self) -> dict:
        """Fetch metadata about the NAIP ImageServer (extent, bands, etc.)."""
        url = self.config.endpoints.naip_image_server
        params = {"f": "json"}
        resp = self._session.get(url, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()
