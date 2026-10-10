# Cloud Run v2 Service running the Document Processor container
resource "google_cloud_run_v2_service" "doc_processor" {
  name     = "doc-processor"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.doc_processor.email
    timeout         = "300s"

    scaling {
      min_instance_count = 0
      max_instance_count = var.max_instances
    }

    containers {
      image = var.container_image

      resources {
        limits = {
          cpu    = "1"
          memory = "1Gi"
        }
      }

      ports {
        container_port = 8080
      }

      env {
        name  = "PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "GCS_BUCKET_NAME"
        value = var.bucket_name
      }
      env {
        name  = "BIGQUERY_DATASET_ID"
        value = var.bigquery_dataset_id
      }
      env {
        name  = "BIGQUERY_TABLE_ID"
        value = var.bigquery_table_id
      }
      env {
        name  = "OCR_ENGINE"
        value = var.ocr_engine
      }
      env {
        name  = "VERIFY_OIDC_TOKEN"
        value = "true"
      }

      startup_probe {
        initial_delay_seconds = 2
        timeout_seconds       = 3
        period_seconds        = 5
        failure_threshold     = 3
        http_get {
          path = "/health"
          port = 8080
        }
      }

      liveness_probe {
        period_seconds    = 15
        timeout_seconds   = 3
        failure_threshold = 3
        http_get {
          path = "/health"
          port = 8080
        }
      }
    }
  }

  labels = {
    managed-by = "terraform"
    pipeline   = "document-processing"
  }
}
