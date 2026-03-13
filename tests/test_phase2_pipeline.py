"""Tests for Phase 2 pipeline components."""

from __future__ import annotations

import numpy as np
import pytest

from geo_anom.core.config import load_config, NutrientCoefficient
from geo_anom.core.geo_utils import BBox, meters_sq_to_acres, polygon_area_m2
from geo_anom.phase2.yolo_detector import Detection
from geo_anom.phase2.supply_calculator import SupplyCalculator


class TestDetection:
    """Test the Detection dataclass."""

    def test_center_px(self):
        det = Detection(
            bbox_px=(100, 200, 300, 400),
            bbox_geo=(-76.1, 38.5, -76.0, 38.6),
            confidence=0.95,
            class_id=0,
            class_name="poultry_house",
            tile_path="test.tif",
        )
        assert det.center_px == (200, 300)


class TestSupplyCalculation:
    """Test nutrient supply math with known inputs."""

    def test_broiler_nitrogen_calculation(self):
        """
        150,000 broilers × 0.91 lb N/head/yr × 6.5 flocks/yr = 887,250 lb N/yr
        """
        coeff = NutrientCoefficient(
            N_lbs_per_head_per_year=0.91,
            P2O5_lbs_per_head_per_year=0.63,
            flocks_per_year=6.5,
        )
        headcount = 150_000
        annual_n = headcount * coeff.N_lbs_per_head_per_year * coeff.flocks_per_year
        assert abs(annual_n - 887_250.0) < 1.0

    def test_broiler_phosphorus_calculation(self):
        """
        150,000 broilers × 0.63 lb P₂O₅/head/yr × 6.5 flocks/yr = 614,250 lb P₂O₅/yr
        """
        coeff = NutrientCoefficient(
            N_lbs_per_head_per_year=0.91,
            P2O5_lbs_per_head_per_year=0.63,
            flocks_per_year=6.5,
        )
        headcount = 150_000
        annual_p = headcount * coeff.P2O5_lbs_per_head_per_year * coeff.flocks_per_year
        assert abs(annual_p - 614_250.0) < 1.0

    def test_dairy_cattle_nitrogen(self):
        """500 dairy cattle × 168 lb N/head/yr × 1 cycle = 84,000 lb N/yr"""
        coeff = NutrientCoefficient(
            N_lbs_per_head_per_year=168.0,
            P2O5_lbs_per_head_per_year=96.0,
            flocks_per_year=1.0,
        )
        headcount = 500
        annual_n = headcount * coeff.N_lbs_per_head_per_year * coeff.flocks_per_year
        assert annual_n == 84_000.0

    def test_normalize_animal_type(self):
        """Test that animal type normalization works."""
        calc = SupplyCalculator()
        assert calc._normalize_animal_type("Broiler Chicken") == "broiler_chicken"
        assert calc._normalize_animal_type("  TURKEY  ") == "turkey"
        assert calc._normalize_animal_type("dairy") == "dairy_cattle"
        assert calc._normalize_animal_type("hog") == "swine"
        assert calc._normalize_animal_type("") == "unknown"


class TestGeoUtils:
    """Test geospatial utilities."""

    def test_meters_sq_to_acres(self):
        # 1 acre = 4046.86 m²
        assert abs(meters_sq_to_acres(4046.86) - 1.0) < 0.001

    def test_bbox_from_point(self):
        bb = BBox.from_point(lon=-76.0, lat=38.5, buffer_km=1.0)
        assert bb.west < -76.0 < bb.east
        assert bb.south < 38.5 < bb.north

    def test_bbox_buffer(self):
        bb = BBox(west=-76.1, south=38.5, east=-76.0, north=38.6)
        buffered = bb.buffer(km=1.0)
        assert buffered.west < bb.west
        assert buffered.east > bb.east

    def test_bbox_to_esri_string(self):
        bb = BBox(west=-76.1, south=38.5, east=-76.0, north=38.6)
        assert bb.to_esri_string() == "-76.1,38.5,-76.0,38.6"

    def test_config_loads_nutrient_coefficients(self):
        config = load_config()
        assert "broiler_chicken" in config.nutrient_coefficients
        bc = config.nutrient_coefficients["broiler_chicken"]
        assert bc.N_lbs_per_head_per_year == 0.91
        assert bc.flocks_per_year == 6.5
