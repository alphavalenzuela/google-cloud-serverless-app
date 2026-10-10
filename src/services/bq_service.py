"""BigQuery ingestion service supporting partitioned tables, schema initialization, and idempotent streaming."""

from typing import Any, Dict, List, Optional
from google.cloud import bigquery
from google.cloud.exceptions import NotFound

from src.config import settings
from src.models import DocumentRecord
from src.utils.logger import get_logger

logger = get_logger("bq_service")


class BigQueryService:
    """Service for streaming document metadata into partitioned BigQuery tables."""

    SCHEMA = [
        bigquery.SchemaField("document_id", "STRING", mode="REQUIRED", description="Unique idempotent key"),
        bigquery.SchemaField("filename", "STRING", mode="REQUIRED", description="Object path in GCS"),
        bigquery.SchemaField("bucket", "STRING", mode="REQUIRED", description="Source bucket name"),
        bigquery.SchemaField("content_type", "STRING", mode="NULLABLE", description="MIME content type"),
        bigquery.SchemaField("size_bytes", "INT64", mode="REQUIRED", description="File size in bytes"),
        bigquery.SchemaField("created_at", "TIMESTAMP", mode="REQUIRED", description="Creation timestamp in GCS"),
        bigquery.SchemaField("processed_at", "TIMESTAMP", mode="REQUIRED", description="Pipeline processing timestamp"),
        bigquery.SchemaField("word_count", "INT64", mode="REQUIRED", description="Extracted word count"),
        bigquery.SchemaField("tags", "STRING", mode="REPEATED", description="Extracted semantic tags"),
        bigquery.SchemaField("text_snippet", "STRING", mode="NULLABLE", description="Preview snippet of extracted text"),
        bigquery.SchemaField("ocr_engine", "STRING", mode="REQUIRED", description="OCR engine identifier"),
        bigquery.SchemaField("processing_time_ms", "INT64", mode="REQUIRED", description="Processing latency in ms"),
        bigquery.SchemaField("status", "STRING", mode="REQUIRED", description="Pipeline status (SUCCESS/FAILED/SKIPPED)"),
    ]

    def __init__(self, client: Optional[bigquery.Client] = None):
        self._client = client
        self._attempted_init = False
        self.in_memory_records: List[Dict[str, Any]] = []

    @property
    def client(self) -> Optional[bigquery.Client]:
        if self._client is None and not self._attempted_init and not settings.mock_gcp_clients:
            self._attempted_init = True
            try:
                self._client = bigquery.Client(project=settings.project_id)
            except Exception as e:
                logger.warning(f"Could not initialize real BigQuery client, falling back to mock mode: {e}")
        return self._client

    @property
    def table_ref(self) -> str:
        return f"{settings.project_id}.{settings.bigquery_dataset_id}.{settings.bigquery_table_id}"

    def ensure_table_exists(self) -> None:
        """Verifies or creates the partitioned and clustered BigQuery dataset and table."""
        if self.client is None or settings.mock_gcp_clients:
            logger.info(f"[MOCK BQ] Verified existence of table {self.table_ref}")
            return

        dataset_ref = bigquery.DatasetReference(settings.project_id, settings.bigquery_dataset_id)
        try:
            self.client.get_dataset(dataset_ref)
        except NotFound:
            dataset = bigquery.Dataset(dataset_ref)
            dataset.location = "US"
            self.client.create_dataset(dataset, exists_ok=True)
            logger.info(f"Created BigQuery dataset: {settings.bigquery_dataset_id}")

        table = bigquery.Table(self.table_ref, schema=self.SCHEMA)
        table.time_partitioning = bigquery.TimePartitioning(
            type_=bigquery.TimePartitioningType.DAY,
            field="processed_at"
        )
        table.clustering_fields = ["status", "bucket"]

        try:
            self.client.create_table(table, exists_ok=True)
            logger.info(f"Verified/created BigQuery table: {self.table_ref}")
        except Exception as e:
            logger.error(f"Error creating BigQuery table {self.table_ref}: {e}")

    def insert_record(self, record: DocumentRecord) -> bool:
        """Streams a DocumentRecord into BigQuery idempotently using document_id deduplication."""
        row_dict = record.to_bigquery_row()

        # Handle mock/offline execution
        if self.client is None or settings.mock_gcp_clients:
            logger.info(
                f"[MOCK BQ] Inserted record {record.document_id} into {self.table_ref}"
            )
            # Maintain in-memory ledger with deduplication
            self.in_memory_records = [
                r for r in self.in_memory_records if r["document_id"] != record.document_id
            ]
            self.in_memory_records.append(row_dict)
            return True

        try:
            # Using insert_rows_json with row_ids provides at-least-once deduplication in BigQuery
            table = self.client.get_table(self.table_ref)
            errors = self.client.insert_rows_json(
                table,
                [row_dict],
                row_ids=[record.document_id]
            )

            if errors:
                logger.error(f"Failed to insert row into BigQuery {self.table_ref}: {errors}")
                return False

            logger.info(f"Successfully streamed row {record.document_id} to BigQuery {self.table_ref}")
            return True

        except Exception as e:
            logger.error(f"Exception during BigQuery row insertion: {e}")
            raise
