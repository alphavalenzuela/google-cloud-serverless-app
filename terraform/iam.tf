# -------------------------------------------------------------
# Service Accounts
# -------------------------------------------------------------

# Runtime Service Account for the Cloud Run container
resource "google_service_account" "doc_processor" {
  account_id   = "sa-doc-processor"
  display_name = "Cloud Run Document Processor Service Account"
  description  = "Identity for the doc-processor Cloud Run service to access GCS and BigQuery"
}

# Invoker Service Account used by Pub/Sub Push Subscription to call Cloud Run
resource "google_service_account" "pubsub_invoker" {
  account_id   = "sa-pubsub-invoker"
  display_name = "Pub/Sub Cloud Run Invoker Service Account"
  description  = "Identity used by Pub/Sub push subscription to sign OIDC tokens for Cloud Run"
}

# GCS System Service Account
data "google_storage_project_service_account" "gcs_account" {
  project = var.project_id
}

# -------------------------------------------------------------
# 1. GCS -> Pub/Sub Permissions
# -------------------------------------------------------------
resource "google_pubsub_topic_iam_member" "gcs_pubsub_publisher" {
  topic  = google_pubsub_topic.doc_upload_events.name
  role   = "roles/pubsub.publisher"
  member = "serviceAccount:${data.google_storage_project_service_account.gcs_account.email_address}"
}

# -------------------------------------------------------------
# 2. Pub/Sub -> Cloud Run Permissions
# -------------------------------------------------------------
resource "google_cloud_run_v2_service_iam_member" "pubsub_invoker_run" {
  name     = google_cloud_run_v2_service.doc_processor.name
  location = google_cloud_run_v2_service.doc_processor.location
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.pubsub_invoker.email}"
}

# -------------------------------------------------------------
# 3. Cloud Run -> GCS Permissions (Least Privilege: Object Viewer)
# -------------------------------------------------------------
resource "google_storage_bucket_iam_member" "cloud_run_gcs_reader" {
  bucket = google_storage_bucket.documents_bucket.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.doc_processor.email}"
}

# -------------------------------------------------------------
# 4. Cloud Run -> BigQuery Permissions (Data Editor + Job User)
# -------------------------------------------------------------
resource "google_bigquery_dataset_iam_member" "cloud_run_bq_editor" {
  dataset_id = google_bigquery_dataset.doc_analytics.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.doc_processor.email}"
}

resource "google_project_iam_member" "cloud_run_bq_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.doc_processor.email}"
}

resource "google_project_iam_member" "cloud_run_log_writer" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.doc_processor.email}"
}

# -------------------------------------------------------------
# 5. Pub/Sub Service Agent -> Dead Letter Queue Permissions
# -------------------------------------------------------------
resource "google_pubsub_topic_iam_member" "pubsub_agent_dlq_publisher" {
  topic  = google_pubsub_topic.doc_upload_dlq.name
  role   = "roles/pubsub.publisher"
  member = "serviceAccount:service-${data.google_project.current.number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}
