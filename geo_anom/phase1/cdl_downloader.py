"""
USDA Cropland Data Layer (CDL) Downloader.

Fetches crop-specific land cover rasters for Maryland from the CropScape
Web Coverage Service (WCS). Used in Phase 3 for nutrient demand mapping.
"""

from __future__ import annotations

import re
import tempfile
from pathlib import Path
from zipfile import ZipFile

import requests

from geo_anom.core.config import get_config, GeoAnomConfig
from geo_anom.core.geo_utils import BBox
from geo_anom.core.logging import setup_logger

logger = setup_logger(__name__)


class CDLDownloader:
    """
    Client for the USDA CropScape CDL web service.

    Downloads the Cropland Data Layer raster for Maryland by state FIPS
    code or by bounding box for a given year.

    Attributes
    ----------
    config : GeoAnomConfig
        Pipeline configuration.
    """

    def __init__(self, config: GeoAnomConfig | None = None) -> None:
        self.config = config or get_config()
        self._session = requests.Session()

    # ------------------------------------------------------------------
    # State-level download
    # ------------------------------------------------------------------

    def download_state_cdl(
        self,
        year: int = 2023,
        state_fips: str | None = None,
        output_dir: Path | str | None = None,
    ) -> Path:
        """
        Download the CDL raster for an entire state.

        Parameters
        ----------
        year : int
            Crop year (e.g. 2023).
        state_fips : str, optional
            2-digit FIPS code. Defaults to Maryland's "24".
        output_dir : Path, optional
            Save directory. Defaults to ``data/raw/cdl/``.

        Returns
        -------
        Path
            Path to the downloaded GeoTIFF.
        """
        state_fips = state_fips or self.config.state.fips
        output_dir = Path(output_dir) if output_dir else self.config.raw_dir / "cdl"
        output_dir.mkdir(parents=True, exist_ok=True)

        url = self.config.endpoints.cdl_wcs
        params = {
            "year": str(year),
            "fips": state_fips,
        }

        logger.info("Requesting CDL for state FIPS=%s, year=%d", state_fips, year)

        resp = self._session.get(url, params=params, timeout=120)
        resp.raise_for_status()

        # CropScape returns XML with a URL to the actual TIF file
        tif_url = self._extract_tif_url(resp.text)
        if not tif_url:
            raise RuntimeError(
                f"Could not extract TIF URL from CropScape response:\n{resp.text[:500]}"
            )

        return self._download_tif(tif_url, output_dir, f"cdl_{state_fips}_{year}.tif")

    # ------------------------------------------------------------------
    # BBox-level download
    # ------------------------------------------------------------------

    def download_bbox_cdl(
        self,
        year: int,
        bbox: BBox,
        output_dir: Path | str | None = None,
    ) -> Path:
        """
        Download CDL clipped to a specific bounding box.

        Parameters
        ----------
        year : int
            Crop year.
        bbox : BBox
            Geographic extent in WGS84.
        output_dir : Path, optional
            Save directory.

        Returns
        -------
        Path
            Path to the clipped GeoTIFF.
        """
        output_dir = Path(output_dir) if output_dir else self.config.raw_dir / "cdl"
        output_dir.mkdir(parents=True, exist_ok=True)

        url = self.config.endpoints.cdl_wcs
        params = {
            "year": str(year),
            "bbox": f"{bbox.west},{bbox.south},{bbox.east},{bbox.north}",
        }

        logger.info("Requesting CDL for bbox=%s, year=%d", bbox.as_tuple, year)

        resp = self._session.get(url, params=params, timeout=120)
        resp.raise_for_status()

        tif_url = self._extract_tif_url(resp.text)
        if not tif_url:
            raise RuntimeError(
                f"Could not extract TIF URL from CropScape response:\n{resp.text[:500]}"
            )

        fname = f"cdl_bbox_{bbox.west:.2f}_{bbox.south:.2f}_{year}.tif"
        return self._download_tif(tif_url, output_dir, fname)

    # ------------------------------------------------------------------
    # CDL Statistics
    # ------------------------------------------------------------------

    def get_cdl_stats(
        self,
        year: int,
        bbox: BBox,
    ) -> dict:
        """
        Get crop acreage statistics for a bounding box without downloading the raster.

        Returns
        -------
        dict
            Raw XML/JSON response with crop acreage breakdown.
        """
        url = self.config.endpoints.cdl_stats
        params = {
            "year": str(year),
            "bbox": f"{bbox.west},{bbox.south},{bbox.east},{bbox.north}",
            "format": "json",
        }

        resp = self._session.get(url, params=params, timeout=60)
        resp.raise_for_status()

        try:
            return resp.json()
        except ValueError:
            return {"raw_response": resp.text}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_tif_url(response_text: str) -> str | None:
        """
        Extract the download URL for the TIF file from CropScape's XML response.

        CropScape returns XML like:
            <returnURL>https://nassgeodata.gmu.edu/...cdl_...tif</returnURL>
        """
        # Try XML pattern
        match = re.search(r"<returnURL>(.*?)</returnURL>", response_text)
        if match:
            return match.group(1).strip()

        # Try JSON pattern
        match = re.search(r'"returnURL"\s*:\s*"(.*?)"', response_text)
        if match:
            return match.group(1).strip()

        return None

    def _download_tif(self, tif_url: str, output_dir: Path, filename: str) -> Path:
        """Download a GeoTIFF from a URL (handles both .tif and .zip responses)."""
        logger.info("Downloading CDL raster from %s", tif_url)

        from tqdm import tqdm

        resp = self._session.get(tif_url, timeout=300, stream=True)
        resp.raise_for_status()

        output_path = output_dir / filename
        total_size = int(resp.headers.get("content-length", 0))

        # Check if response is a ZIP file
        content_type = resp.headers.get("Content-Type", "")
        if "zip" in content_type or tif_url.endswith(".zip"):
            with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
                with tqdm(total=total_size, unit="iB", unit_scale=True, desc=f"Downloading {filename}") as pbar:
                    for chunk in resp.iter_content(chunk_size=8192):
                        tmp.write(chunk)
                        pbar.update(len(chunk))
                tmp_path = tmp.name

            with ZipFile(tmp_path) as zf:
                tif_names = [n for n in zf.namelist() if n.endswith(".tif")]
                if tif_names:
                    zf.extract(tif_names[0], output_dir)
                    extracted = output_dir / tif_names[0]
                    extracted.rename(output_path)
                    logger.info("Extracted CDL → %s", output_path)
                else:
                    raise RuntimeError(f"No .tif files found in CDL zip: {zf.namelist()}")

            Path(tmp_path).unlink(missing_ok=True)
        else:
            with open(output_path, "wb") as f:
                with tqdm(total=total_size, unit="iB", unit_scale=True, desc=f"Downloading {filename}") as pbar:
                    for chunk in resp.iter_content(chunk_size=8192):
                        f.write(chunk)
                        pbar.update(len(chunk))
            logger.info("Saved CDL → %s (%.1f MB)", output_path, output_path.stat().st_size / 1e6)

        return output_path
