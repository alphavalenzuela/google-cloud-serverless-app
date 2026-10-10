output "storage_bucket_name" {
  description = "The Cloud Storage bucket where documents are uploaded."
  value       = google_storage_bucket.documents_bucket.name
}

output "storage_bucket_url" {
  description = "The gs:// URL for the storage bucket."
  value       = google_storage_bucket.documents_bucket.url
}

output "pubsub_topic_id" {
  description = "The Pub/Sub topic ID receiving upload notifications."
  value       = google_pubsub_topic.doc_upload_events.id
}

output "pubsub_dlq_topic_id" {
  description = "The Dead Letter Queue Pub/Sub topic ID."
  value       = google_pubsub_topic.doc_upload_dlq.id
}

output "cloud_run_service_url" {
  description = "The HTTPS URL of the deployed Cloud Run processor."
  value       = google_cloud_run_v2_service.doc_processor.uri
}

output "bigquery_table_id" {
  description = "The fully-qualified BigQuery table ID storing processed metadata."
  value       = "${google_bigquery_dataset.doc_analytics.dataset_id}.${google_bigquery_table.processed_documents.table_id}"
}

output "pubsub_invoker_service_account" {
  description = "The service account email used for Pub/Sub push invocation."
  value       = google_service_account.pubsub_invoker.email
}

output "doc_processor_service_account" {
  description = "The service account email assumed by the Cloud Run container."
  value       = google_service_account.doc_processor.email
}
