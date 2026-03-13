"""
CDL Processor — Crop-type nutrient demand lookup.

Maps each CDL raster pixel's crop code to nitrogen and phosphorus
demand values (lbs/acre) using the crop nutrient demand table.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from geo_anom.core.config import get_config, GeoAnomConfig
from geo_anom.core.logging import setup_logger

logger = setup_logger(__name__)


class CDLProcessor:
    """
    Processes USDA Cropland Data Layer rasters into nutrient demand rasters.

    Parameters
    ----------
    config : GeoAnomConfig, optional
        Pipeline configuration with crop demand lookup table.
    """

    def __init__(self, config: GeoAnomConfig | None = None) -> None:
        self.config = config or get_config()
        self._demand_table = self._build_demand_table()

    def _build_demand_table(self) -> dict[int, dict[str, float]]:
        """Build CDL code → nutrient demand lookup from config."""
        table: dict[int, dict[str, float]] = {}
        for crop_name, demand in self.config.crop_nutrient_demand.items():
            table[demand.cdl_code] = {
                "crop_name": crop_name,
                "N_lbs_per_acre": demand.N_lbs_per_acre,
                "P2O5_lbs_per_acre": demand.P2O5_lbs_per_acre,
            }
        return table

    def load_cdl(self, tiff_path: Path | str) -> tuple[np.ndarray, Any]:
        """
        Load a CDL GeoTIFF raster.

        Returns
        -------
        tuple[np.ndarray, rasterio.transform.Affine]
            CDL integer array and geo-transform.
        """
        import rasterio

        tiff_path = Path(tiff_path)
        logger.info("Loading CDL raster: %s", tiff_path)

        with rasterio.open(tiff_path) as src:
            cdl_array = src.read(1)
            transform = src.transform
            meta = src.meta.copy()

        logger.info("CDL shape: %s, unique codes: %d", cdl_array.shape, len(np.unique(cdl_array)))
        return cdl_array, transform

    def map_crop_demand(
        self,
        cdl_array: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        """
        Map CDL crop codes to nutrient demand rasters.

        Parameters
        ----------
        cdl_array : np.ndarray
            Integer CDL raster (crop type codes).

        Returns
        -------
        tuple[np.ndarray, np.ndarray]
            N demand raster (lbs/acre) and P₂O₅ demand raster (lbs/acre).
        """
        n_demand = np.zeros_like(cdl_array, dtype=np.float32)
        p_demand = np.zeros_like(cdl_array, dtype=np.float32)

        for code, values in self._demand_table.items():
            mask = cdl_array == code
            n_demand[mask] = values["N_lbs_per_acre"]
            p_demand[mask] = values["P2O5_lbs_per_acre"]

        logger.info(
            "Mapped demand — pixels with N>0: %d, pixels with P>0: %d",
            (n_demand > 0).sum(), (p_demand > 0).sum(),
        )
        return n_demand, p_demand
