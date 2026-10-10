"""Tests for Pydantic models and data converters."""

import base64
import json
from datetime import datetime, timezone
import pytest
from src.models import (
    DocumentRecord,
    GCSObjectNotification,
    ProcessingStatus,
    PubSubMessage,
    PubSubPushPayload,
)


def test_gcs_notification_from_pubsub_data():
    raw_data = {
        "bucket": "my-bucket",
        "name": "contracts/nda.pdf",
        "size": 5000,
        "contentType": "application/pdf",
        "generation": "12345678",
    }
    b64_str = base64.b64encode(json.dumps(raw_data).encode("utf-8")).decode("utf-8")

    notification = GCSObjectNotification.from_pubsub_data(b64_str)
    assert notification.bucket == "my-bucket"
    assert notification.name == "contracts/nda.pdf"
    assert notification.size == 5000
    assert notification.contentType == "application/pdf"
    assert notification.generation == "12345678"


def test_gcs_notification_invalid_base64():
    with pytest.raises(ValueError, match="Failed to decode GCS notification"):
        GCSObjectNotification.from_pubsub_data("not-valid-base-64!!!")


def test_document_record_to_bigquery_row():
    now = datetime.now(timezone.utc)
    record = DocumentRecord(
        document_id="my-bucket/contracts/nda.pdf#123",
        filename="contracts/nda.pdf",
        bucket="my-bucket",
        content_type="application/pdf",
        size_bytes=5000,
        created_at=now,
        processed_at=now,
        word_count=120,
        tags=["legal", "contract"],
        text_snippet="A" * 600,  # exceeds 500 chars snippet
        ocr_engine="simulated",
        processing_time_ms=45,
        status=ProcessingStatus.SUCCESS,
    )

    row = record.to_bigquery_row()
    assert row["document_id"] == "my-bucket/contracts/nda.pdf#123"
    assert row["filename"] == "contracts/nda.pdf"
    assert row["bucket"] == "my-bucket"
    assert row["word_count"] == 120
    assert row["tags"] == ["legal", "contract"]
    assert len(row["text_snippet"]) == 500  # Truncated to 500
    assert row["status"] == "SUCCESS"
    assert row["processing_time_ms"] == 45
