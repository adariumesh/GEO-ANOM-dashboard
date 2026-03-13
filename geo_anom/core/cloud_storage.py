"""
Google Cloud Storage Adapter for GEO-ANOM.

Provides a transparent abstraction over GCS that falls back to local
filesystem when no GCS bucket is configured. All pipeline modules use
this adapter so switching between local and cloud requires only a config change.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterator

from geo_anom.core.logging import setup_logger

logger = setup_logger(__name__)


class GCSAdapter:
    """
    Transparent storage adapter for Google Cloud Storage.

    When ``gcs_bucket`` is empty or unset, all operations fall through
    to the local filesystem. Set ``gcs_bucket`` in ``configs/maryland.yaml``
    or the ``GCS_BUCKET`` environment variable to enable cloud storage.

    Parameters
    ----------
    bucket : str
        GCS bucket name (e.g. "geo-anom-maryland"). Empty string → local-only.
    project_id : str
        GCP project ID used for GCS authentication.
    local_root : Path
        Local data root directory for fallback / caching.
    """

    def __init__(
        self,
        bucket: str = "",
        project_id: str = "",
        local_root: Path | str = "./data",
    ) -> None:
        self.bucket = bucket or os.getenv("GCS_BUCKET", "")
        self.project_id = project_id or os.getenv("GCS_PROJECT_ID", "")
        self.local_root = Path(local_root)
        self._client = None
        self._gcs_bucket = None

        if self.bucket:
            logger.info("GCSAdapter: cloud mode (bucket=%s)", self.bucket)
        else:
            logger.info("GCSAdapter: local-only mode (set GCS_BUCKET to enable cloud)")

    # ------------------------------------------------------------------
    # GCS client (lazy)
    # ------------------------------------------------------------------

    def _get_client(self):
        """Lazily initialise the GCS client."""
        if self._client is None:
            try:
                from google.cloud import storage as gcs

                self._client = gcs.Client(project=self.project_id or None)
                self._gcs_bucket = self._client.bucket(self.bucket)
                logger.info("GCS client authenticated for project=%s", self.project_id)
            except ImportError:
                raise ImportError(
                    "google-cloud-storage is not installed. "
                    "Run: pip install google-cloud-storage"
                )
            except Exception as e:
                raise RuntimeError(f"GCS authentication failed: {e}") from e
        return self._client

    # ------------------------------------------------------------------
    # Upload
    # ------------------------------------------------------------------

    def upload(self, local_path: Path | str, gcs_key: str) -> str:
        """
        Upload a local file to GCS.

        Parameters
        ----------
        local_path : Path
            Local source file.
        gcs_key : str
            GCS object key (path within bucket), e.g. "naip_tiles/tile_001.tif".

        Returns
        -------
        str
            GCS URI (``gs://bucket/key``) or local path string in local mode.
        """
        local_path = Path(local_path)

        if not self.bucket:
            logger.debug("GCS disabled — skipping upload of %s", local_path)
            return str(local_path)

        self._get_client()
        blob = self._gcs_bucket.blob(gcs_key)
        blob.upload_from_filename(str(local_path))
        uri = f"gs://{self.bucket}/{gcs_key}"
        logger.info("Uploaded %s → %s", local_path.name, uri)
        return uri

    def upload_bytes(self, data: bytes, gcs_key: str, content_type: str = "application/octet-stream") -> str:
        """Upload raw bytes directly to GCS."""
        if not self.bucket:
            return gcs_key

        self._get_client()
        blob = self._gcs_bucket.blob(gcs_key)
        blob.upload_from_string(data, content_type=content_type)
        uri = f"gs://{self.bucket}/{gcs_key}"
        logger.debug("Uploaded bytes → %s", uri)
        return uri

    # ------------------------------------------------------------------
    # Download
    # ------------------------------------------------------------------

    def download(self, gcs_key: str, local_path: Path | str | None = None) -> Path:
        """
        Download a GCS object to a local path.

        Skips the download if the local cached file already exists.

        Parameters
        ----------
        gcs_key : str
            GCS object key (path within bucket).
        local_path : Path, optional
            Local destination. Defaults to ``<local_root>/<gcs_key>``.

        Returns
        -------
        Path
            Path to the local file.
        """
        if local_path is None:
            local_path = self.local_root / gcs_key

        local_path = Path(local_path)

        if not self.bucket:
            if local_path.exists():
                return local_path
            raise FileNotFoundError(
                f"GCS disabled and local file not found: {local_path}"
            )

        # Skip if cached
        if local_path.exists():
            logger.debug("Cache hit — skipping download of %s", gcs_key)
            return local_path

        local_path.parent.mkdir(parents=True, exist_ok=True)
        self._get_client()
        blob = self._gcs_bucket.blob(gcs_key)
        blob.download_to_filename(str(local_path))
        logger.info("Downloaded gs://%s/%s → %s", self.bucket, gcs_key, local_path)
        return local_path

    # ------------------------------------------------------------------
    # Existence check
    # ------------------------------------------------------------------

    def exists(self, gcs_key: str) -> bool:
        """Check whether a GCS object exists."""
        if not self.bucket:
            return (self.local_root / gcs_key).exists()

        self._get_client()
        blob = self._gcs_bucket.blob(gcs_key)
        return blob.exists()

    # ------------------------------------------------------------------
    # List
    # ------------------------------------------------------------------

    def list_blobs(self, prefix: str) -> list[str]:
        """
        List GCS object keys under a given prefix.

        Returns
        -------
        list[str]
            Object keys (without gs://bucket/ prefix).
        """
        if not self.bucket:
            # Fall back to listing local directory
            local_dir = self.local_root / prefix
            if not local_dir.exists():
                return []
            return [
                str(p.relative_to(self.local_root))
                for p in local_dir.rglob("*")
                if p.is_file()
            ]

        self._get_client()
        blobs = list(self._client.list_blobs(self.bucket, prefix=prefix))
        return [b.name for b in blobs]

    # ------------------------------------------------------------------
    # Convenience: local path from GCS key
    # ------------------------------------------------------------------

    def local_path(self, gcs_key: str) -> Path:
        """Return the expected local cache path for a GCS key."""
        return self.local_root / gcs_key

    def gcs_uri(self, gcs_key: str) -> str:
        """Return the full GCS URI for a key."""
        return f"gs://{self.bucket}/{gcs_key}"


def get_storage(config=None) -> GCSAdapter:
    """
    Build a GCSAdapter from pipeline configuration.

    Parameters
    ----------
    config : GeoAnomConfig, optional
        Pipeline config. Uses global config if not provided.
    """
    from geo_anom.core.config import get_config

    cfg = config or get_config()
    cloud = getattr(cfg, "cloud", None)

    bucket = ""
    project_id = ""
    if cloud:
        bucket = getattr(cloud, "gcs_bucket", "") or ""
        project_id = getattr(cloud, "gcs_project_id", "") or ""

    return GCSAdapter(
        bucket=bucket,
        project_id=project_id,
        local_root=cfg.data_dir,
    )
