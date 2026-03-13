"""
Vertex AI Fine-Tuning Job Launcher for YOLOv8.

Submits a custom container training job to Google Cloud Vertex AI
when you're ready to fine-tune YOLOv8 on METER-ML or custom Maryland
CAFO annotations — without needing local GPU infrastructure.
"""

from __future__ import annotations

from pathlib import Path

from geo_anom.core.config import get_config, GeoAnomConfig
from geo_anom.core.logging import setup_logger

logger = setup_logger(__name__)

# Container image: Ultralytics official GPU image (PyTorch + YOLOv8 pre-installed)
_TRAINING_IMAGE = "ultralytics/ultralytics:latest-gpu"

# YOLOv8 training command template
_TRAIN_CMD_TEMPLATE = [
    "yolo",
    "train",
    "model={base_model}",
    "data={data_yaml_gcs}",
    "epochs={epochs}",
    "imgsz={imgsz}",
    "batch={batch}",
    "project={output_dir}",
    "name=afo_detector",
    "save=True",
]


class VertexAITrainer:
    """
    Submits and monitors YOLOv8 fine-tuning jobs on Vertex AI.

    Usage
    -----
    Once you have labelled NAIP patches exported to GCS::

        trainer = VertexAITrainer()
        job = trainer.launch_training_job(
            dataset_gcs_uri="gs://geo-anom-maryland/training_data/",
            output_gcs_uri="gs://geo-anom-maryland/models/finetuned/",
        )
        print(trainer.get_job_status(job))

    Parameters
    ----------
    config : GeoAnomConfig, optional
        Pipeline configuration.
    """

    def __init__(self, config: GeoAnomConfig | None = None) -> None:
        self.config = config or get_config()
        cloud = getattr(self.config, "cloud", None)
        self.region = getattr(cloud, "vertex_ai_region", "us-east1") if cloud else "us-east1"
        self.staging_bucket = getattr(cloud, "vertex_ai_staging_bucket", "") if cloud else ""
        self.project_id = getattr(cloud, "gcs_project_id", "") if cloud else ""
        self.machine_type = getattr(cloud, "vertex_ai_machine_type", "n1-standard-8") if cloud else "n1-standard-8"
        self.accelerator = getattr(cloud, "vertex_ai_accelerator", "NVIDIA_TESLA_T4") if cloud else "NVIDIA_TESLA_T4"
        self.accelerator_count = getattr(cloud, "vertex_ai_accelerator_count", 1) if cloud else 1

    # ------------------------------------------------------------------
    # Launch training job
    # ------------------------------------------------------------------

    def launch_training_job(
        self,
        dataset_gcs_uri: str,
        output_gcs_uri: str,
        base_model: str = "yolov8n.pt",
        epochs: int = 100,
        imgsz: int = 1024,
        batch: int = 16,
        job_display_name: str = "geo-anom-yolo-finetune",
    ) -> str:
        """
        Submit a YOLOv8 fine-tuning job to Vertex AI.

        Parameters
        ----------
        dataset_gcs_uri : str
            GCS URI of the training dataset root
            (must contain ``data.yaml``, ``images/``, ``labels/``).
        output_gcs_uri : str
            GCS URI where model weights will be saved.
        base_model : str
            YOLOv8 checkpoint to start from (e.g. "yolov8n.pt", "yolov8x.pt").
        epochs : int
            Number of training epochs.
        imgsz : int
            Input image size.
        batch : int
            Batch size per GPU.
        job_display_name : str
            Human-readable job name in Vertex AI console.

        Returns
        -------
        str
            Vertex AI job resource name (for status polling).
        """
        try:
            from google.cloud import aiplatform

            aiplatform.init(
                project=self.project_id,
                location=self.region,
                staging_bucket=self.staging_bucket,
            )
        except ImportError:
            raise ImportError(
                "google-cloud-aiplatform not installed. "
                "Run: pip install google-cloud-aiplatform"
            )

        # Build training command
        data_yaml_gcs = f"{dataset_gcs_uri.rstrip('/')}/data.yaml"
        cmd = [
            arg.format(
                base_model=base_model,
                data_yaml_gcs=data_yaml_gcs,
                epochs=epochs,
                imgsz=imgsz,
                batch=batch,
                output_dir=output_gcs_uri,
            )
            for arg in _TRAIN_CMD_TEMPLATE
        ]

        logger.info(
            "Submitting Vertex AI training job: %s\n  Dataset: %s\n  Output: %s\n  Machine: %s + %s×%s",
            job_display_name, dataset_gcs_uri, output_gcs_uri,
            self.machine_type, self.accelerator_count, self.accelerator,
        )

        job = aiplatform.CustomContainerTrainingJob(
            display_name=job_display_name,
            container_uri=_TRAINING_IMAGE,
            command=cmd,
        )

        model = job.run(
            replica_count=1,
            machine_type=self.machine_type,
            accelerator_type=self.accelerator,
            accelerator_count=self.accelerator_count,
            sync=False,  # non-blocking — poll status separately
        )

        job_name = job.resource_name
        logger.info("Job submitted: %s", job_name)
        return job_name

    # ------------------------------------------------------------------
    # Status polling
    # ------------------------------------------------------------------

    def get_job_status(self, job_resource_name: str) -> str:
        """
        Get the current status of a Vertex AI training job.

        Parameters
        ----------
        job_resource_name : str
            Resource name returned by ``launch_training_job()``.

        Returns
        -------
        str
            Job state string (e.g. "JOB_STATE_RUNNING", "JOB_STATE_SUCCEEDED").
        """
        try:
            from google.cloud import aiplatform

            aiplatform.init(project=self.project_id, location=self.region)
            job = aiplatform.CustomTrainingJob.get(job_resource_name)
            state = str(job.state)
            logger.info("Job %s state: %s", job_resource_name, state)
            return state

        except Exception as e:
            logger.error("Failed to get job status: %s", e)
            return "UNKNOWN"

    # ------------------------------------------------------------------
    # Convenience: generate data.yaml for Vertex AI
    # ------------------------------------------------------------------

    def generate_data_yaml(
        self,
        dataset_local_dir: Path | str,
        output_path: Path | str,
    ) -> Path:
        """
        Generate a YOLOv8 ``data.yaml`` pointing to GCS paths.

        Parameters
        ----------
        dataset_local_dir : Path
            Local directory with ``images/`` and ``labels/`` subdirs.
        output_path : Path
            Where to save ``data.yaml``.

        Returns
        -------
        Path
        """
        import yaml

        yw_cfg = getattr(self.config, "yolo_world", None)
        classes = (
            list(yw_cfg.text_prompts) if yw_cfg
            else ["poultry house", "barn", "manure lagoon", "feedlot", "silo"]
        )

        data = {
            "path": str(dataset_local_dir),
            "train": "images/train",
            "val": "images/val",
            "nc": len(classes),
            "names": classes,
        }

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            yaml.dump(data, f, default_flow_style=False)

        logger.info("Generated data.yaml → %s", output_path)
        return output_path
