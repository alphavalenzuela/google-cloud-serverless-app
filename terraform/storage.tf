# Google Cloud Storage Bucket for Document Ingestion
resource "google_storage_bucket" "documents_bucket" {
  name                        = var.bucket_name
  location                    = var.region
  uniform_bucket_level_access = true
  force_destroy               = false

  versioning {
    enabled = true
  }

  lifecycle_rule {
    action {
      type = "Delete"
    }
    condition {
      num_newer_versions = 3
      with_state         = "ARCHIVED"
    }
  }

  labels = {
    managed-by = "terraform"
    pipeline   = "document-processing"
  }
}

# GCS Notification to Pub/Sub on object creation (OBJECT_FINALIZE)
resource "google_storage_notification" "upload_notification" {
  bucket         = google_storage_bucket.documents_bucket.name
  payload_format = "JSON_API_V1"
  topic          = google_pubsub_topic.doc_upload_events.id
  event_types    = ["OBJECT_FINALIZE"]

  depends_on = [
    google_pubsub_topic_iam_member.gcs_pubsub_publisher
  ]
}
