"""Unit tests for BigQuery ingestion service."""

from datetime import datetime, timezone
import pytest
from src.models import DocumentRecord, ProcessingStatus
from src.services.bq_service import BigQueryService


def test_bigquery_mock_insertion_and_deduplication():
    bq = BigQueryService()
    bq.ensure_table_exists()

    record_1 = DocumentRecord(
        document_id="bucket/doc1.pdf#1",
        filename="doc1.pdf",
        bucket="bucket",
        size_bytes=1000,
        created_at=datetime.now(timezone.utc),
        word_count=50,
        tags=["finance"],
        status=ProcessingStatus.SUCCESS,
    )

    success = bq.insert_record(record_1)
    assert success is True
    assert len(bq.in_memory_records) == 1
    assert bq.in_memory_records[0]["document_id"] == "bucket/doc1.pdf#1"

    # Re-inserting with same document_id (Pub/Sub duplicate delivery) should deduplicate
    record_1_retry = DocumentRecord(
        document_id="bucket/doc1.pdf#1",
        filename="doc1.pdf",
        bucket="bucket",
        size_bytes=1000,
        created_at=datetime.now(timezone.utc),
        word_count=50,
        tags=["finance"],
        status=ProcessingStatus.SUCCESS,
    )
    bq.insert_record(record_1_retry)
    assert len(bq.in_memory_records) == 1
