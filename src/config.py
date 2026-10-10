"""Configuration management for the document processing service."""

import os
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables with sensible defaults."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Google Cloud Project Configuration
    project_id: str = Field(
        default_factory=lambda: os.getenv("GOOGLE_CLOUD_PROJECT", os.getenv("GCP_PROJECT", "local-dev-project")),
        description="GCP Project ID"
    )
    gcs_bucket_name: str = Field(
        default="raw-documents",
        description="Source GCS bucket name for uploaded documents"
    )
    bigquery_dataset_id: str = Field(
        default="doc_analytics",
        description="Target BigQuery dataset name"
    )
    bigquery_table_id: str = Field(
        default="processed_documents",
        description="Target BigQuery table name"
    )

    # Processing & OCR Configuration
    ocr_engine: str = Field(
        default="simulated",
        description="OCR Engine to use: 'simulated' or 'vision_api'"
    )
    max_file_size_bytes: int = Field(
        default=50 * 1024 * 1024,  # 50 MB
        description="Maximum supported file size for in-memory processing"
    )
    allowed_extensions: List[str] = Field(
        default=[".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".tif", ".txt"],
        description="Supported file extensions for processing"
    )

    # Security & Pub/Sub Verification
    verify_oidc_token: bool = Field(
        default=False,
        description="Whether to enforce Google OIDC bearer token verification on push endpoints"
    )
    oidc_audience: str = Field(
        default="",
        description="Expected audience for Google OIDC token (Cloud Run service URL)"
    )

    # Logging and Server configuration
    log_level: str = Field(default="INFO", description="Application log level")
    port: int = Field(default=8080, description="Server port")

    # Offline / Test mode
    mock_gcp_clients: bool = Field(
        default_factory=lambda: (
            os.getenv("MOCK_GCP_CLIENTS", "false").lower() in ("true", "1")
            or (
                not os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
                and not os.getenv("K_SERVICE")  # Not running in Cloud Run container
                and os.getenv("GOOGLE_CLOUD_PROJECT", "") in ("", "local-dev-project")
            )
        ),
        description="Enable offline mock mode for GCS and BigQuery clients without GCP credentials"
    )


settings = Settings()
