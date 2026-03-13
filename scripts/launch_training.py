#!/usr/bin/env python3
"""
CLI to launch a Vertex AI YOLOv8 fine-tuning job.

Usage:
    python scripts/launch_training.py \\
        --dataset gs://geo-anom-maryland/training_data/meter_ml/ \\
        --output  gs://geo-anom-maryland/models/yolo_finetuned/ \\
        --epochs 100 --batch 16
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from geo_anom.core.config import load_config
from geo_anom.core.logging import setup_logger
from geo_anom.phase2.vertex_trainer import VertexAITrainer


def main():
    parser = argparse.ArgumentParser(
        description="Launch a YOLOv8 fine-tuning job on Vertex AI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--dataset", required=True,
                        help="GCS URI of training dataset (must contain data.yaml)")
    parser.add_argument("--output", required=True,
                        help="GCS URI for model output weights")
    parser.add_argument("--base-model", default="yolov8n.pt",
                        help="Starting checkpoint (default: yolov8n.pt)")
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--imgsz", type=int, default=1024)
    parser.add_argument("--batch", type=int, default=16)
    parser.add_argument("--job-name", default="geo-anom-yolo-finetune")
    parser.add_argument("--config", type=str, default=None)

    args = parser.parse_args()
    config = load_config(args.config)
    logger = setup_logger("geo_anom.training", level=config.env.log_level)

    logger.info("=" * 60)
    logger.info("GEO-ANOM: Vertex AI Fine-Tuning Job Launcher")
    logger.info("=" * 60)
    logger.info("Dataset : %s", args.dataset)
    logger.info("Output  : %s", args.output)
    logger.info("Model   : %s → fine-tuned", args.base_model)
    logger.info("Epochs  : %d", args.epochs)

    trainer = VertexAITrainer(config=config)

    job_name = trainer.launch_training_job(
        dataset_gcs_uri=args.dataset,
        output_gcs_uri=args.output,
        base_model=args.base_model,
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        job_display_name=args.job_name,
    )

    logger.info("\nJob submitted successfully!")
    logger.info("Resource name : %s", job_name)
    logger.info("Monitor at    : https://console.cloud.google.com/vertex-ai/training/custom-jobs")
    logger.info("\nCheck status with:")
    logger.info("  python scripts/launch_training.py --status %s", job_name)


if __name__ == "__main__":
    main()
