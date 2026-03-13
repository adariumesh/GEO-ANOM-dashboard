"""
Nutrient Supply Calculator.

Converts validated AFO polygons (from SAM2 + AlphaEarth) and MDE headcount
data into spatially-explicit nutrient supply volumes (N and P₂O₅).
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pandas as pd

from geo_anom.core.config import get_config, GeoAnomConfig, NutrientCoefficient
from geo_anom.core.geo_utils import meters_sq_to_acres
from geo_anom.core.logging import setup_logger

logger = setup_logger(__name__)


# Mapping from MDE animal type strings to config keys
_ANIMAL_TYPE_MAP: dict[str, str] = {
    "broiler": "broiler_chicken",
    "broiler chicken": "broiler_chicken",
    "broilers": "broiler_chicken",
    "chickens": "broiler_chicken",
    "chicken": "broiler_chicken",
    "layer": "layer_chicken",
    "layers": "layer_chicken",
    "layer chicken": "layer_chicken",
    "turkey": "turkey",
    "turkeys": "turkey",
    "dairy": "dairy_cattle",
    "dairy cattle": "dairy_cattle",
    "beef": "beef_cattle",
    "beef cattle": "beef_cattle",
    "cattle": "beef_cattle",
    "swine": "swine",
    "hog": "swine",
    "hogs": "swine",
    "pig": "swine",
    "pigs": "swine",
}


class SupplyCalculator:
    """
    Calculates nutrient supply from validated AFO polygons + MDE permits.

    Combines SAM-derived lagoon/structure areas with MDE headcount data
    to produce annual nitrogen (N) and phosphorus (P₂O₅) generation
    volumes per facility.

    Parameters
    ----------
    config : GeoAnomConfig, optional
        Pipeline configuration with nutrient coefficients.
    """

    def __init__(self, config: GeoAnomConfig | None = None) -> None:
        self.config = config or get_config()

    # ------------------------------------------------------------------
    # Main calculation
    # ------------------------------------------------------------------

    def calculate_supply(
        self,
        validated_polygons_gdf: gpd.GeoDataFrame,
        afo_permits_gdf: gpd.GeoDataFrame,
        max_join_distance_km: float = 2.0,
    ) -> gpd.GeoDataFrame:
        """
        Calculate nutrient supply by spatial-joining polygons with permits.

        Parameters
        ----------
        validated_polygons_gdf : GeoDataFrame
            Validated AFO polygons (from SAM2 + AlphaEarth filtering).
            Must have columns: geometry, class_name, area_m2, confidence.
        afo_permits_gdf : GeoDataFrame
            MDE permit data with columns: geometry, animal_type, headcount.
        max_join_distance_km : float
            Max distance (km) for nearest-neighbor spatial join.

        Returns
        -------
        GeoDataFrame
            Supply map with nutrient volumes per facility.
        """
        logger.info(
            "Calculating nutrient supply: %d polygons × %d permits",
            len(validated_polygons_gdf), len(afo_permits_gdf),
        )

        # Ensure both are in the same CRS
        polygons = validated_polygons_gdf.copy()
        permits = afo_permits_gdf.copy()

        if polygons.crs is None:
            polygons = polygons.set_crs("EPSG:4326")
        if permits.crs is None:
            permits = permits.set_crs("EPSG:4326")

        # Project to UTM 18N for distance-based join
        polygons_utm = polygons.to_crs("EPSG:32618")
        permits_utm = permits.to_crs("EPSG:32618")

        # Spatial join: nearest permit within max_join_distance
        max_dist_m = max_join_distance_km * 1000
        joined = gpd.sjoin_nearest(
            polygons_utm,
            permits_utm,
            how="left",
            max_distance=max_dist_m,
            distance_col="join_distance_m",
        )

        # Calculate nutrient supply for each matched row
        supply_records = []
        for idx, row in joined.iterrows():
            animal_type = self._normalize_animal_type(
                row.get("animal_type", "unknown")
            )
            hc_val = row.get("headcount", 0)
            if pd.isna(hc_val):
                hc_val = 0
            headcount = int(hc_val)
            
            area_m2 = float(row.get("area_m2", 0))

            # Look up nutrient coefficient
            coeff = self.config.nutrient_coefficients.get(animal_type)
            if coeff and headcount > 0:
                annual_n = headcount * coeff.N_lbs_per_head_per_year * coeff.flocks_per_year
                annual_p = headcount * coeff.P2O5_lbs_per_head_per_year * coeff.flocks_per_year
            else:
                annual_n = 0.0
                annual_p = 0.0
                if headcount > 0:
                    logger.warning(
                        "No nutrient coefficient for animal type '%s' (original: '%s')",
                        animal_type, row.get("animal_type", "unknown"),
                    )

            supply_records.append({
                "geometry": row.geometry,
                "class_name": row.get("class_name", "unknown"),
                "confidence": row.get("confidence", 0.0),
                "farm_name": row.get("farm_name", ""),
                "animal_type": animal_type,
                "headcount": headcount,
                "area_m2": area_m2,
                "area_acres": meters_sq_to_acres(area_m2),
                "annual_N_lbs": round(annual_n, 1),
                "annual_P2O5_lbs": round(annual_p, 1),
                "join_distance_m": row.get("join_distance_m", None),
            })

        result = gpd.GeoDataFrame(supply_records, crs="EPSG:32618")
        result = result.to_crs("EPSG:4326")

        # Summary stats
        total_n = result["annual_N_lbs"].sum()
        total_p = result["annual_P2O5_lbs"].sum()
        logger.info(
            "Supply calculated: %d facilities, total N=%.0f lbs/yr, P₂O₅=%.0f lbs/yr",
            len(result), total_n, total_p,
        )

        return result

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def export_supply_map(
        self,
        gdf: gpd.GeoDataFrame,
        output_path: Path | str,
        driver: str = "GPKG",
    ) -> Path:
        """
        Export the nutrient supply map to GeoPackage or GeoJSON.

        Parameters
        ----------
        gdf : GeoDataFrame
            Supply map from calculate_supply().
        output_path : Path
            Output file path.
        driver : str
            OGR driver ("GPKG" for GeoPackage, "GeoJSON" for JSON).

        Returns
        -------
        Path
            Path to the written file.
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        gdf.to_file(str(output_path), driver=driver)
        logger.info("Exported supply map → %s (%d features)", output_path, len(gdf))
        return output_path

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_animal_type(raw: str) -> str:
        """Map MDE animal type string to a standardised config key."""
        if not raw or pd.isna(raw):
            return "unknown"
        normalized = raw.strip().lower()
        return _ANIMAL_TYPE_MAP.get(normalized, normalized)
