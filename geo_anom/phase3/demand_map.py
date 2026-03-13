"""
Nutrient Balance Map Builder.

Combines crop-specific nutrient demand with environmental setback
exclusion zones to produce the constrained Nutrient Balance Map.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from geo_anom.core.config import get_config, GeoAnomConfig
from geo_anom.core.logging import setup_logger
from geo_anom.phase3.cdl_processor import CDLProcessor
from geo_anom.phase3.setback_masker import SetbackMasker

logger = setup_logger(__name__)


class DemandMapBuilder:
    """
    Builds the constrained Nutrient Demand Map.

    Orchestrates CDL processing → setback masking → final demand output.
    """

    def __init__(self, config: GeoAnomConfig | None = None) -> None:
        self.config = config or get_config()
        self.cdl_processor = CDLProcessor(config)
        self.setback_masker = SetbackMasker(config)

    def build(
        self,
        cdl_path: Path | str,
        setback_path: Path | str | None = None,
        output_dir: Path | str | None = None,
    ) -> dict[str, np.ndarray]:
        """
        Build the constrained nutrient demand map.

        Parameters
        ----------
        cdl_path : Path
            Path to CDL GeoTIFF raster.
        setback_path : Path, optional
            Path to MDA waterway setback shapefile.
        output_dir : Path, optional
            Directory to save output rasters.

        Returns
        -------
        dict[str, np.ndarray]
            Keys "N_demand" and "P2O5_demand" with masked rasters.
        """
        # Step 1: Load and map CDL
        cdl_array, transform = self.cdl_processor.load_cdl(cdl_path)
        n_demand, p_demand = self.cdl_processor.map_crop_demand(cdl_array)

        # Step 2: Apply setback masks if available
        if setback_path:
            buffers_gdf = self.setback_masker.load_waterway_buffers(setback_path)
            n_demand = self.setback_masker.apply_setbacks(
                n_demand, buffers_gdf, transform, "35ft"
            )
            p_demand = self.setback_masker.apply_setbacks(
                p_demand, buffers_gdf, transform, "35ft"
            )

        logger.info(
            "Demand map built: N range [%.0f, %.0f], P₂O₅ range [%.0f, %.0f] lbs/acre",
            n_demand.min(), n_demand.max(), p_demand.min(), p_demand.max(),
        )

        # Step 3: Save if output_dir provided
        if output_dir:
            self._save_rasters(n_demand, p_demand, transform, cdl_path, output_dir)

        return {"N_demand": n_demand, "P2O5_demand": p_demand}

    def _save_rasters(
        self, n_demand, p_demand, transform, cdl_path, output_dir
    ) -> None:
        """Save demand rasters as GeoTIFFs."""
        import rasterio

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        with rasterio.open(cdl_path) as src:
            meta = src.meta.copy()

        meta.update(dtype="float32", count=1, nodata=0)

        for name, data in [("N_demand", n_demand), ("P2O5_demand", p_demand)]:
            out_path = output_dir / f"{name}.tif"
            with rasterio.open(out_path, "w", **meta) as dst:
                dst.write(data.astype(np.float32), 1)
            logger.info("Saved %s → %s", name, out_path)
