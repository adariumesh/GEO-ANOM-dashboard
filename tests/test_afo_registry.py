"""Tests for the MDE AFO Registry Client."""

from __future__ import annotations

import io
import textwrap
from pathlib import Path
from unittest.mock import patch, MagicMock

import pandas as pd
import pytest

from geo_anom.phase1.afo_registry import AFORegistryClient
from geo_anom.core.geo_utils import BBox


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_CSV = textwrap.dedent("""\
Farm Name,Farm Designation,Primary Animal Type,Number of Animals,Status,Farm City,Farm County,Farm Zip Code,Latitude,Longitude
Smith Poultry Farm,CAFO,Broiler Chicken,150000,Registered,Cambridge,Dorchester,21613,38.563,-76.078
Jones Dairy,MAFO,Dairy Cattle,500,Registered,Easton,Talbot,21601,38.774,-76.076
Old Farm LLC,CAFO,Turkey,25000,Closed,Salisbury,Wicomico,21801,38.360,-75.599
Eastern Layers,CAFO,Layer Chicken,200000,Pending,Denton,Caroline,21629,38.884,-75.827
""")


@pytest.fixture
def afo_client():
    return AFORegistryClient()


@pytest.fixture
def sample_csv_path(tmp_path):
    csv_path = tmp_path / "test_afo.csv"
    csv_path.write_text(SAMPLE_CSV)
    return csv_path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestAFORegistryClient:

    def test_parse_permits_creates_geodataframe(self, afo_client, sample_csv_path):
        gdf = afo_client.parse_permits(sample_csv_path)
        assert len(gdf) == 4
        assert "geometry" in gdf.columns
        assert gdf.crs.to_epsg() == 4326

    def test_parse_permits_extracts_headcount(self, afo_client, sample_csv_path):
        gdf = afo_client.parse_permits(sample_csv_path)
        assert gdf.iloc[0]["headcount"] == 150000

    def test_parse_permits_normalises_animal_type(self, afo_client, sample_csv_path):
        gdf = afo_client.parse_permits(sample_csv_path)
        # Should be lowercased
        assert gdf.iloc[0]["animal_type"] == "broiler chicken"

    def test_filter_active_permits(self, afo_client, sample_csv_path):
        gdf = afo_client.parse_permits(sample_csv_path)
        active = afo_client.filter_active_permits(gdf)
        # "Closed" should be excluded, "Registered" and "Pending" kept
        assert len(active) == 3
        assert "Closed" not in active["status"].values

    def test_filter_by_county(self, afo_client, sample_csv_path):
        gdf = afo_client.parse_permits(sample_csv_path)
        dorchester = afo_client.filter_by_county(gdf, "Dorchester")
        assert len(dorchester) == 1
        assert dorchester.iloc[0]["farm_name"] == "Smith Poultry Farm"

    def test_get_target_bboxes(self, afo_client, sample_csv_path):
        gdf = afo_client.parse_permits(sample_csv_path)
        bboxes = afo_client.get_target_bboxes(gdf, buffer_km=1.0)
        assert len(bboxes) == 4
        assert all(isinstance(b, BBox) for b in bboxes)

        # Each bbox should be centred near the AFO location
        first_bb = bboxes[0]
        assert abs(first_bb.center[1] - 38.563) < 0.1

    @patch("geo_anom.phase1.afo_registry.requests.get")
    def test_download_csv(self, mock_get, afo_client, tmp_path):
        mock_resp = MagicMock()
        mock_resp.content = SAMPLE_CSV.encode()
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        path = afo_client.download_csv(output_dir=tmp_path)
        assert path.exists()
        assert path.suffix == ".csv"

    @patch("geo_anom.phase1.afo_registry.requests.get")
    def test_download_json(self, mock_get, afo_client):
        mock_resp = MagicMock()
        mock_resp.json.return_value = [{"farm_name": "Test Farm"}]
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        records = afo_client.download_json(limit=10)
        assert len(records) == 1
