"""Tests for the CDL Downloader."""

from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest

from geo_anom.phase1.cdl_downloader import CDLDownloader
from geo_anom.core.geo_utils import BBox


@pytest.fixture
def downloader():
    return CDLDownloader()


class TestCDLDownloader:

    def test_extract_tif_url_from_xml(self):
        """Should parse returnURL from CropScape XML response."""
        xml_response = """<?xml version="1.0"?>
        <GetCDLFileResult>
            <returnURL>https://nassgeodata.gmu.edu/webservice/nass_data_cache/CDL_2023_24.tif</returnURL>
        </GetCDLFileResult>"""

        url = CDLDownloader._extract_tif_url(xml_response)
        assert url == "https://nassgeodata.gmu.edu/webservice/nass_data_cache/CDL_2023_24.tif"

    def test_extract_tif_url_from_json(self):
        """Should parse returnURL from JSON response variant."""
        json_response = '{"returnURL": "https://nassgeodata.gmu.edu/cache/CDL_2023.tif"}'
        url = CDLDownloader._extract_tif_url(json_response)
        assert url == "https://nassgeodata.gmu.edu/cache/CDL_2023.tif"

    def test_extract_tif_url_returns_none_on_invalid(self):
        """Should return None if no returnURL found."""
        url = CDLDownloader._extract_tif_url("<html>Error</html>")
        assert url is None

    @patch("geo_anom.phase1.cdl_downloader.requests.Session")
    def test_download_state_cdl(self, mock_sess_cls, downloader, tmp_path):
        """Full state download flow with mocked HTTP."""
        xml_response = (
            '<GetCDLFileResult>'
            '<returnURL>https://nassgeodata.gmu.edu/cache/CDL_2023_24.tif</returnURL>'
            '</GetCDLFileResult>'
        )

        # Mock the initial WCS request
        mock_wcs_resp = MagicMock()
        mock_wcs_resp.text = xml_response
        mock_wcs_resp.raise_for_status = MagicMock()

        # Mock the TIF download
        mock_tif_resp = MagicMock()
        mock_tif_resp.headers = {"Content-Type": "image/tiff"}
        mock_tif_resp.iter_content.return_value = [b"FAKE_GEOTIFF_DATA"]
        mock_tif_resp.raise_for_status = MagicMock()

        with patch.object(downloader, "_session") as mock_session:
            mock_session.get.side_effect = [mock_wcs_resp, mock_tif_resp]

            result = downloader.download_state_cdl(year=2023, output_dir=tmp_path)
            assert result.exists()
            assert "cdl_24_2023" in result.name

    def test_download_bbox_cdl_raises_on_bad_response(self, downloader, tmp_path):
        """Should raise if CropScape returns invalid response."""
        bbox = BBox(west=-76.5, south=38.0, east=-75.5, north=39.0)

        with patch.object(downloader, "_session") as mock_session:
            mock_resp = MagicMock()
            mock_resp.text = "<html>Internal Server Error</html>"
            mock_resp.raise_for_status = MagicMock()
            mock_session.get.return_value = mock_resp

            with pytest.raises(RuntimeError, match="Could not extract TIF URL"):
                downloader.download_bbox_cdl(2023, bbox, output_dir=tmp_path)

    def test_maryland_fips_default(self, downloader):
        """Config should default to Maryland FIPS 24."""
        assert downloader.config.state.fips == "24"
