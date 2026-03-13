"""
MDA Waterway Setback Masker.

Applies Maryland Department of Agriculture 10-ft and 35-ft waterway
exclusion buffers to nutrient demand rasters.
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np

from geo_anom.core.config import get_config, GeoAnomConfig
from geo_anom.core.logging import setup_logger

logger = setup_logger(__name__)


class SetbackMasker:
    """
    Masks nutrient demand rasters with MDA waterway setback buffers.

    Parameters
    ----------
    config : GeoAnomConfig, optional
        Pipeline configuration with setback distances.
    """

    def __init__(self, config: GeoAnomConfig | None = None) -> None:
        self.config = config or get_config()

    def load_waterway_buffers(
        self, shapefile_path: Path | str
    ) -> gpd.GeoDataFrame:
        """
        Load waterway buffer geometries from a shapefile.

        Parameters
        ----------
        shapefile_path : Path
            Path to MDA waterway setbacks shapefile or GeoJSON.

        Returns
        -------
        gpd.GeoDataFrame
            Waterway buffer polygons.
        """
        path = Path(shapefile_path)
        logger.info("Loading waterway setback buffers from %s", path)
        gdf = gpd.read_file(path)
        logger.info("Loaded %d waterway buffer features", len(gdf))
        return gdf

    def apply_setbacks(
        self,
        demand_raster: np.ndarray,
        buffers_gdf: gpd.GeoDataFrame,
        transform,
        buffer_type: str = "35ft",
    ) -> np.ndarray:
        """
        Zero out demand raster pixels within setback exclusion zones.

        Parameters
        ----------
        demand_raster : np.ndarray
            Nutrient demand raster (lbs/acre).
        buffers_gdf : GeoDataFrame
            Waterway buffer polygons.
        transform : rasterio Affine
            Geo-transform of the demand raster.
        buffer_type : str
            "10ft" or "35ft" setback distance.

        Returns
        -------
        np.ndarray
            Masked demand raster with exclusion zones set to 0.
        """
        try:
            from rasterio.features import geometry_mask

            mask = geometry_mask(
                buffers_gdf.geometry,
                out_shape=demand_raster.shape,
                transform=transform,
                invert=True,  # True inside geometries
            )

            masked = demand_raster.copy()
            masked[mask] = 0.0

            n_masked = mask.sum()
            logger.info(
                "Applied %s setback: masked %d pixels (%.1f%%)",
                buffer_type, n_masked, 100 * n_masked / demand_raster.size,
            )
            return masked

        except ImportError:
            logger.warning("rasterio.features not available; skipping setback masking")
            return demand_raster
