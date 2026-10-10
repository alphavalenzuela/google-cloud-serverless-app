variable "project_id" {
  type        = string
  description = "The Google Cloud Project ID where resources will be provisioned."
}

variable "region" {
  type        = string
  default     = "us-central1"
  description = "Google Cloud region for Cloud Run, Pub/Sub, and regional resources."
}

variable "bucket_name" {
  type        = string
  description = "Name of the Google Cloud Storage bucket for document uploads (must be globally unique)."
}

variable "bigquery_dataset_id" {
  type        = string
  default     = "doc_analytics"
  description = "ID of the BigQuery dataset."
}

variable "bigquery_table_id" {
  type        = string
  default     = "processed_documents"
  description = "ID of the BigQuery table storing processed document metadata."
}

variable "bigquery_location" {
  type        = string
  default     = "US"
  description = "Location for the BigQuery dataset (e.g. US, EU, us-central1)."
}

variable "container_image" {
  type        = string
  description = "Container image URL for the Cloud Run service (e.g., gcr.io/PROJECT_ID/doc-processor:latest or Artifact Registry URL)."
}

variable "ocr_engine" {
  type        = string
  default     = "simulated"
  description = "OCR extraction engine to activate: 'simulated' or 'vision_api'."
}

variable "max_instances" {
  type        = number
  default     = 10
  description = "Maximum number of container instances for Cloud Run autoscaling."
}
