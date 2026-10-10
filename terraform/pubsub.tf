# Primary Pub/Sub Topic for document upload events
resource "google_pubsub_topic" "doc_upload_events" {
  name = "doc-upload-events"

  labels = {
    managed-by = "terraform"
    pipeline   = "document-processing"
  }
}

# Dead Letter Queue (DLQ) Topic for failed / poison-pill messages
resource "google_pubsub_topic" "doc_upload_dlq" {
  name = "doc-upload-dlq"

  labels = {
    managed-by = "terraform"
    pipeline   = "document-processing"
  }
}

# Pull Subscription on the DLQ topic for operator inspection / reprocessing
resource "google_pubsub_subscription" "dlq_sub" {
  name  = "doc-upload-dlq-sub"
  topic = google_pubsub_topic.doc_upload_dlq.name

  # Retain dead-lettered messages for up to 7 days
  message_retention_duration = "604800s"
  retain_acked_messages      = false

  labels = {
    managed-by = "terraform"
    pipeline   = "document-processing"
  }
}

# Pub/Sub Push Subscription triggering Cloud Run
resource "google_pubsub_subscription" "doc_upload_push_sub" {
  name  = "doc-upload-push-sub"
  topic = google_pubsub_topic.doc_upload_events.name

  # Allow 300 seconds for document OCR and BigQuery insertion before timeout
  ack_deadline_seconds = 300

  push_config {
    push_endpoint = "${google_cloud_run_v2_service.doc_processor.uri}/process-event"

    oidc_token {
      service_account_email = google_service_account.pubsub_invoker.email
      audience              = google_cloud_run_v2_service.doc_processor.uri
    }
  }

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.doc_upload_dlq.id
    max_delivery_attempts = 5
  }

  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }

  labels = {
    managed-by = "terraform"
    pipeline   = "document-processing"
  }

  depends_on = [
    google_pubsub_topic_iam_member.pubsub_agent_dlq_publisher,
    google_cloud_run_v2_service_iam_member.pubsub_invoker_run
  ]
}
