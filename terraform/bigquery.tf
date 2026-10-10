# BigQuery Dataset
resource "google_bigquery_dataset" "doc_analytics" {
  dataset_id  = var.bigquery_dataset_id
  description = "Dataset storing metadata and extracted content from processed documents"
  location    = var.bigquery_location

  labels = {
    managed-by = "terraform"
    pipeline   = "document-processing"
  }
}

# Partitioned and Clustered BigQuery Table
resource "google_bigquery_table" "processed_documents" {
  dataset_id = google_bigquery_dataset.doc_analytics.dataset_id
  table_id   = var.bigquery_table_id

  deletion_protection = false

  time_partitioning {
    type  = "DAY"
    field = "processed_at"
  }

  clustering = ["status", "bucket"]

  schema = jsonencode([
    {
      name        = "document_id"
      type        = "STRING"
      mode        = "REQUIRED"
      description = "Unique idempotent record key: {bucket}/{name}#{generation}"
    },
    {
      name        = "filename"
      type        = "STRING"
      mode        = "REQUIRED"
      description = "Original object name/path in GCS bucket"
    },
    {
      name        = "bucket"
      type        = "STRING"
      mode        = "REQUIRED"
      description = "Source Cloud Storage bucket"
    },
    {
      name        = "content_type"
      type        = "STRING"
      mode        = "NULLABLE"
      description = "MIME content type"
    },
    {
      name        = "size_bytes"
      type        = "INTEGER"
      mode        = "REQUIRED"
      description = "File size in bytes"
    },
    {
      name        = "created_at"
      type        = "TIMESTAMP"
      mode        = "REQUIRED"
      description = "GCS object upload/creation timestamp"
    },
    {
      name        = "processed_at"
      type        = "TIMESTAMP"
      mode        = "REQUIRED"
      description = "Timestamp when OCR processing finished"
    },
    {
      name        = "word_count"
      type        = "INTEGER"
      mode        = "REQUIRED"
      description = "Extracted word count"
    },
    {
      name        = "tags"
      type        = "STRING"
      mode        = "REPEATED"
      description = "Extracted semantic classification tags"
    },
    {
      name        = "text_snippet"
      type        = "STRING"
      mode        = "NULLABLE"
      description = "Text preview snippet"
    },
    {
      name        = "ocr_engine"
      type        = "STRING"
      mode        = "REQUIRED"
      description = "Identifier of OCR engine used"
    },
    {
      name        = "processing_time_ms"
      type        = "INTEGER"
      mode        = "REQUIRED"
      description = "Total processing time in milliseconds"
    },
    {
      name        = "status"
      type        = "STRING"
      mode        = "REQUIRED"
      description = "Processing status: SUCCESS, FAILED, or SKIPPED"
    }
  ])

  labels = {
    managed-by = "terraform"
    pipeline   = "document-processing"
  }
}
