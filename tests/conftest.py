"""Shared pytest fixtures and test data."""

import base64
import json
import pytest
from src.config import settings


@pytest.fixture(autouse=True)
def setup_test_environment(monkeypatch):
    """Configures environment settings for isolated local testing."""
    monkeypatch.setattr(settings, "mock_gcp_clients", True)
    monkeypatch.setattr(settings, "verify_oidc_token", False)
    monkeypatch.setattr(settings, "project_id", "test-project-123")
    monkeypatch.setattr(settings, "gcs_bucket_name", "test-bucket")
    monkeypatch.setattr(settings, "bigquery_dataset_id", "test_dataset")
    monkeypatch.setattr(settings, "bigquery_table_id", "test_table")


@pytest.fixture
def sample_gcs_notification_dict():
    """Returns a dictionary representing a GCS OBJECT_FINALIZE notification."""
    return {
        "bucket": "test-bucket",
        "name": "invoices/2026/test-invoice-101.pdf",
        "contentType": "application/pdf",
        "size": 12450,
        "generation": "1728559000123456",
        "metageneration": "1",
        "timeCreated": "2026-10-10T08:00:00.000Z",
        "updated": "2026-10-10T08:00:00.000Z",
    }


@pytest.fixture
def sample_pubsub_push_payload(sample_gcs_notification_dict):
    """Returns a complete Pub/Sub push HTTP payload with base64 encoded GCS notification."""
    data_json = json.dumps(sample_gcs_notification_dict)
    b64_data = base64.b64encode(data_json.encode("utf-8")).decode("utf-8")

    return {
        "message": {
            "data": b64_data,
            "attributes": {
                "bucketId": sample_gcs_notification_dict["bucket"],
                "eventType": "OBJECT_FINALIZE",
                "objectId": sample_gcs_notification_dict["name"],
                "objectGeneration": sample_gcs_notification_dict["generation"],
            },
            "messageId": "msg-987654321",
            "publishTime": "2026-10-10T08:00:01.000Z",
        },
        "subscription": "projects/test-project-123/subscriptions/doc-upload-push-sub",
    }
