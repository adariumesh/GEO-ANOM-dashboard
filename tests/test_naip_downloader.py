"""Tests for the NAIP Downloader."""

from __future__ import annotations

from unittest.mock import patch, MagicMock, PropertyMock

import pytest

from geo_anom.phase1.naip_downloader import NAIPDownloader
from geo_anom.core.geo_utils import BBox


@pytest.fixture
def downloader():
    return NAIPDownloader()


class TestNAIPDownloader:

    def test_export_tile_constructs_correct_url(self, downloader, tmp_path):
        """Verify the REST URL params are correctly constructed."""
        bbox = BBox(west=-76.1, south=38.5, east=-76.0, north=38.6)

        with patch.object(downloader, "_session") as mock_session:
            mock_resp = MagicMock()
            mock_resp.raise_for_status = MagicMock()
            mock_resp.headers = {"Content-Type": "image/tiff"}
            mock_resp.iter_content.return_value = [b"FAKE_TIFF_DATA"]
            mock_session.get.return_value = mock_resp

            output = tmp_path / "test_tile.tif"
            result = downloader.export_tile(bbox, output)

            # Verify the call was made
            call_args = mock_session.get.call_args
            params = call_args[1]["params"] if "params" in call_args[1] else call_args[0][1]

            assert result.exists()
            assert result.name == "test_tile.tif"

    def test_export_tile_detects_error_response(self, downloader, tmp_path):
        """Should raise if server returns JSON error instead of image."""
        bbox = BBox(west=-76.1, south=38.5, east=-76.0, north=38.6)

        with patch.object(downloader, "_session") as mock_session:
            mock_resp = MagicMock()
            mock_resp.raise_for_status = MagicMock()
            mock_resp.headers = {"Content-Type": "application/json"}
            mock_resp.text = '{"error": "Invalid bbox"}'
            mock_session.get.return_value = mock_resp

            with pytest.raises(RuntimeError, match="NAIP server error"):
                downloader.export_tile(bbox, tmp_path / "fail.tif")

    def test_bbox_to_esri_string(self):
        bbox = BBox(west=-76.1, south=38.5, east=-76.0, north=38.6)
        assert bbox.to_esri_string() == "-76.1,38.5,-76.0,38.6"

    def test_download_aoi_skips_existing(self, downloader, tmp_path):
        """Should skip tiles that already exist on disk."""
        bbox = BBox(west=-76.1, south=38.5, east=-76.0, north=38.6)

        # Pre-create the expected output file
        expected_name = "naip_000000_-76.1000_38.5000.tif"
        (tmp_path / expected_name).write_bytes(b"EXISTING")

        with patch.object(downloader, "export_tile") as mock_export:
            mock_export.return_value = tmp_path / expected_name
            result = downloader.download_aoi([bbox], output_dir=tmp_path, limit=1)

            assert len(result) == 1

    @patch("geo_anom.phase1.naip_downloader.requests.Session")
    def test_get_server_info(self, mock_session_cls, downloader):
        """Verify server info request returns JSON."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"currentVersion": 10.91}
        mock_resp.raise_for_status = MagicMock()

        with patch.object(downloader, "_session") as mock_session:
            mock_session.get.return_value = mock_resp
            info = downloader.get_server_info()
            assert "currentVersion" in info
