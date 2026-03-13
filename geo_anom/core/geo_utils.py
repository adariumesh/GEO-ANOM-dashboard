"""
Shared geospatial utility functions for GEO-ANOM.

Provides CRS transformations, bounding-box helpers, and unit conversions
used across all pipeline phases.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterator

import geopandas as gpd
import numpy as np
from pyproj import Transformer
from shapely.geometry import Polygon, box


# ---------------------------------------------------------------------------
# BBox dataclass for clean bounding-box handling
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BBox:
    """Axis-aligned bounding box in WGS84 (EPSG:4326)."""

    west: float
    south: float
    east: float
    north: float

    @property
    def as_tuple(self) -> tuple[float, float, float, float]:
        return (self.west, self.south, self.east, self.north)

    @property
    def center(self) -> tuple[float, float]:
        return (
            (self.west + self.east) / 2,
            (self.south + self.north) / 2,
        )

    def to_polygon(self) -> Polygon:
        """Convert to a Shapely Polygon."""
        return box(self.west, self.south, self.east, self.north)

    def to_esri_string(self) -> str:
        """Format as 'xmin,ymin,xmax,ymax' for ArcGIS REST API."""
        return f"{self.west},{self.south},{self.east},{self.north}"

    def buffer(self, km: float) -> "BBox":
        """Expand the bbox by approximately `km` kilometres in each direction."""
        # Approximate conversion: 1 degree latitude ≈ 111 km
        lat_delta = km / 111.0
        lon_delta = km / (111.0 * math.cos(math.radians(self.center[1])))
        return BBox(
            west=self.west - lon_delta,
            south=self.south - lat_delta,
            east=self.east + lon_delta,
            north=self.north + lat_delta,
        )

    @classmethod
    def from_point(cls, lon: float, lat: float, buffer_km: float = 2.0) -> "BBox":
        """Create a bounding box centred on a point with the given buffer."""
        lat_delta = buffer_km / 111.0
        lon_delta = buffer_km / (111.0 * math.cos(math.radians(lat)))
        return cls(
            west=lon - lon_delta,
            south=lat - lat_delta,
            east=lon + lon_delta,
            north=lat + lat_delta,
        )


# ---------------------------------------------------------------------------
# CRS re-projection
# ---------------------------------------------------------------------------

def reproject_gdf(gdf: gpd.GeoDataFrame, target_crs: str = "EPSG:4326") -> gpd.GeoDataFrame:
    """Re-project a GeoDataFrame to the target CRS."""
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    return gdf.to_crs(target_crs)


def transform_coords(
    lon: float, lat: float, src_crs: str = "EPSG:4326", dst_crs: str = "EPSG:32618"
) -> tuple[float, float]:
    """
    Transform a single coordinate pair between CRS.

    Default: WGS84 → UTM Zone 18N (covers Maryland).
    """
    transformer = Transformer.from_crs(src_crs, dst_crs, always_xy=True)
    x, y = transformer.transform(lon, lat)
    return x, y


# ---------------------------------------------------------------------------
# Tiling
# ---------------------------------------------------------------------------

def tile_bbox(bbox: BBox, tile_size_m: float = 1024.0) -> Iterator[BBox]:
    """
    Split a large bounding box into smaller tiles of approximately
    `tile_size_m` metres on each side.

    Yields
    ------
    BBox
        Sub-tiles covering the original bbox.
    """
    # Convert tile size to approximate degrees
    center_lat = bbox.center[1]
    lat_step = tile_size_m / 111_000.0
    lon_step = tile_size_m / (111_000.0 * math.cos(math.radians(center_lat)))

    lon = bbox.west
    while lon < bbox.east:
        lat = bbox.south
        while lat < bbox.north:
            yield BBox(
                west=lon,
                south=lat,
                east=min(lon + lon_step, bbox.east),
                north=min(lat + lat_step, bbox.north),
            )
            lat += lat_step
        lon += lon_step


# ---------------------------------------------------------------------------
# Unit conversions
# ---------------------------------------------------------------------------

def meters_sq_to_acres(area_m2: float) -> float:
    """Convert square metres to acres."""
    return area_m2 / 4046.8564224


def acres_to_meters_sq(acres: float) -> float:
    """Convert acres to square metres."""
    return acres * 4046.8564224


# ---------------------------------------------------------------------------
# Polygon area in metres² (for WGS84 geometries)
# ---------------------------------------------------------------------------

def polygon_area_m2(polygon: Polygon, crs: str = "EPSG:4326") -> float:
    """
    Compute the geodesic area of a Shapely Polygon in square metres.

    For WGS84 geometries, projects to UTM Zone 18N for accurate area calculation.
    """
    if crs == "EPSG:4326":
        # Project to UTM 18N (Maryland)
        transformer = Transformer.from_crs("EPSG:4326", "EPSG:32618", always_xy=True)
        coords = [transformer.transform(x, y) for x, y in polygon.exterior.coords]
        projected = Polygon(coords)
        return projected.area
    else:
        return polygon.area
