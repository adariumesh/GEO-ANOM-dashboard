"""
GEO-ANOM Configuration Loader.

Loads Maryland-specific constants from configs/maryland.yaml and environment
variables from .env, providing typed access through Pydantic models.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


# ---------------------------------------------------------------------------
# Resolve project root (two levels up from this file: geo_anom/core/config.py)
# ---------------------------------------------------------------------------
_THIS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = _THIS_DIR.parent.parent


def _load_yaml(path: Path) -> dict[str, Any]:
    """Load a YAML file and return its contents as a dict."""
    with open(path, "r") as fh:
        return yaml.safe_load(fh)


# ---------------------------------------------------------------------------
# Sub-models for structured config sections
# ---------------------------------------------------------------------------

class CountyInfo(BaseModel):
    name: str
    fips: str


class StateConfig(BaseModel):
    name: str = "Maryland"
    fips: str = "24"
    eastern_shore_counties: list[CountyInfo] = Field(default_factory=list)
    eastern_shore_bbox: list[float] = Field(
        default_factory=lambda: [-76.50, 37.91, -75.04, 39.72]
    )


class EndpointsConfig(BaseModel):
    naip_image_server: str = (
        "https://mdgeodata.md.gov/imagery/rest/services/NAIP/MD_NAIPImagery/ImageServer"
    )
    afo_registry_csv: str = (
        "https://opendata.maryland.gov/api/views/xwak-3f7s/rows.csv?accessType=DOWNLOAD"
    )
    afo_registry_json: str = (
        "https://opendata.maryland.gov/resource/xwak-3f7s.json"
    )
    cdl_wcs: str = "https://nassgeodata.gmu.edu/axis2/services/CDLService/GetCDLFile"
    cdl_stats: str = "https://nassgeodata.gmu.edu/axis2/services/CDLService/GetCDLStat"


class NAIPConfig(BaseModel):
    resolution_m: int = 1
    tile_size_px: int = 1024
    format: str = "tiff"
    bands: list[str] = Field(default_factory=lambda: ["R", "G", "B", "NIR"])
    max_workers: int = 4
    request_delay_s: float = 1.0


class YOLOConfig(BaseModel):
    classes: list[str] = Field(
        default_factory=lambda: [
            "poultry_house", "barn", "manure_lagoon", "feedlot", "silo"
        ]
    )
    confidence_threshold: float = 0.25
    iou_threshold: float = 0.45
    image_size: int = 1024
    weights_path: str = "data/models/yolov8_afo_best.pt"
    base_model: str = "yolov8n.pt"


class SAMConfig(BaseModel):
    model_type: str = "sam2_hiera_large"
    min_mask_area_px: int = 100
    simplify_tolerance_m: float = 2.0


class AlphaEarthConfig(BaseModel):
    collection_id: str = "GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL"
    embedding_dim: int = 64
    default_year: int = 2024
    similarity_threshold: float = 0.70
    sample_scale: int = 10


class NutrientCoefficient(BaseModel):
    N_lbs_per_head_per_year: float
    P2O5_lbs_per_head_per_year: float
    flocks_per_year: float = 1.0


class CropDemand(BaseModel):
    cdl_code: int
    N_lbs_per_acre: float
    P2O5_lbs_per_acre: float


class SetbacksConfig(BaseModel):
    buffer_10ft_m: float = 3.048
    buffer_35ft_m: float = 10.668


class AFOTargetingConfig(BaseModel):
    buffer_km: float = 2.0
    active_statuses: list[str] = Field(
        default_factory=lambda: ["Registered", "Pending", "Notice of Preliminary Approval"]
    )


class CloudConfig(BaseModel):
    """Google Cloud Storage and Vertex AI settings."""

    gcs_bucket: str = ""
    gcs_project_id: str = ""
    naip_tiles_prefix: str = "naip_tiles/"
    processed_prefix: str = "processed/"
    models_prefix: str = "models/"
    vertex_ai_region: str = "us-east1"
    vertex_ai_staging_bucket: str = ""
    vertex_ai_machine_type: str = "n1-standard-8"
    vertex_ai_accelerator: str = "NVIDIA_TESLA_T4"
    vertex_ai_accelerator_count: int = 1


class YOLOWorldConfig(BaseModel):
    """YOLO-World zero-shot detector configuration."""

    model: str = "yolov8x-worldv2.pt"
    text_prompts: list[str] = Field(
        default_factory=lambda: [
            "poultry house", "chicken barn", "manure lagoon",
            "feedlot", "grain silo", "agricultural pond",
        ]
    )
    confidence_threshold: float = 0.15
    iou_threshold: float = 0.40
    image_size: int = 1024
    weights_dir: str = "models/"


class GeocodingConfig(BaseModel):
    """US Census batch geocoding settings."""

    census_batch_url: str = (
        "https://geocoding.geo.census.gov/geocoder/locations/addressbatch"
    )
    census_benchmark: str = "Public_AR_Current"
    batch_size: int = 9999
    timeout_s: int = 120


# ---------------------------------------------------------------------------
# Environment-variable settings
# ---------------------------------------------------------------------------

class EnvSettings(BaseSettings):
    """Settings loaded from .env file or environment variables."""

    ee_service_account_email: str = ""
    ee_service_account_key_path: str = ""
    data_dir: str = "./data"
    log_level: str = "INFO"
    gcs_bucket: str = ""
    gcs_project_id: str = ""
    google_application_credentials: str = ""

    model_config = {"env_file": str(PROJECT_ROOT / ".env"), "env_file_encoding": "utf-8"}


# ---------------------------------------------------------------------------
# Master configuration
# ---------------------------------------------------------------------------

class GeoAnomConfig(BaseModel):
    """Top-level configuration combining YAML constants + env vars."""

    project_root: Path = PROJECT_ROOT
    state: StateConfig = Field(default_factory=StateConfig)
    endpoints: EndpointsConfig = Field(default_factory=EndpointsConfig)
    naip: NAIPConfig = Field(default_factory=NAIPConfig)
    yolo: YOLOConfig = Field(default_factory=YOLOConfig)
    sam: SAMConfig = Field(default_factory=SAMConfig)
    alphaearth: AlphaEarthConfig = Field(default_factory=AlphaEarthConfig)
    nutrient_coefficients: dict[str, NutrientCoefficient] = Field(default_factory=dict)
    crop_nutrient_demand: dict[str, CropDemand] = Field(default_factory=dict)
    setbacks: SetbacksConfig = Field(default_factory=SetbacksConfig)
    afo_targeting: AFOTargetingConfig = Field(default_factory=AFOTargetingConfig)
    cloud: CloudConfig = Field(default_factory=CloudConfig)
    yolo_world: YOLOWorldConfig = Field(default_factory=YOLOWorldConfig)
    geocoding: GeocodingConfig = Field(default_factory=GeocodingConfig)
    env: EnvSettings = Field(default_factory=EnvSettings)

    @property
    def data_dir(self) -> Path:
        return self.project_root / self.env.data_dir

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"

    @property
    def processed_dir(self) -> Path:
        return self.data_dir / "processed"

    @property
    def models_dir(self) -> Path:
        return self.data_dir / "models"


def load_config(
    yaml_path: Path | str | None = None,
) -> GeoAnomConfig:
    """
    Load the full GEO-ANOM configuration.

    Parameters
    ----------
    yaml_path : Path or str, optional
        Path to the YAML config file. Defaults to configs/maryland.yaml.

    Returns
    -------
    GeoAnomConfig
        Fully populated configuration object.
    """
    if yaml_path is None:
        yaml_path = PROJECT_ROOT / "configs" / "maryland.yaml"
    else:
        yaml_path = Path(yaml_path)

    raw = _load_yaml(yaml_path) if yaml_path.exists() else {}

    # Parse nutrient coefficients
    nc_raw = raw.get("nutrient_coefficients", {})
    nutrient_coefficients = {
        k: NutrientCoefficient(**v) for k, v in nc_raw.items()
    }

    # Parse crop demand
    cd_raw = raw.get("crop_nutrient_demand", {})
    crop_demand = {
        k: CropDemand(**v) for k, v in cd_raw.items()
    }

    return GeoAnomConfig(
        state=StateConfig(**raw.get("state", {})),
        endpoints=EndpointsConfig(**raw.get("endpoints", {})),
        naip=NAIPConfig(**raw.get("naip", {})),
        yolo=YOLOConfig(**raw.get("yolo", {})),
        sam=SAMConfig(**raw.get("sam", {})),
        alphaearth=AlphaEarthConfig(**raw.get("alphaearth", {})),
        nutrient_coefficients=nutrient_coefficients,
        crop_nutrient_demand=crop_demand,
        setbacks=SetbacksConfig(**raw.get("setbacks", {})),
        afo_targeting=AFOTargetingConfig(**raw.get("afo_targeting", {})),
        cloud=CloudConfig(**raw.get("cloud", {})),
        yolo_world=YOLOWorldConfig(**raw.get("yolo_world", {})),
        geocoding=GeocodingConfig(**raw.get("geocoding", {})),
    )


# Module-level singleton (lazy)
_config: GeoAnomConfig | None = None


def get_config() -> GeoAnomConfig:
    """Get or create the global config singleton."""
    global _config
    if _config is None:
        _config = load_config()
    return _config
