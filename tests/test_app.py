"""Integration tests for the FastAPI Cloud Run application endpoints."""

import base64
import json
import pytest
from fastapi.testclient import TestClient

from src.app import app
from src.config import settings

client = TestClient(app)


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "doc-processor"


def test_process_event_successful_pipeline(sample_pubsub_push_payload):
    response = client.post("/process-event", json=sample_pubsub_push_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["filename"] == "invoices/2026/test-invoice-101.pdf"
    assert data["word_count"] > 0
    assert "invoice" in data["tags"]
    assert "document_id" in data


def test_process_event_skipped_unsupported_file(sample_gcs_notification_dict):
    sample_gcs_notification_dict["name"] = "archive/backup_data.zip"
    b64_data = base64.b64encode(json.dumps(sample_gcs_notification_dict).encode("utf-8")).decode("utf-8")

    payload = {
        "message": {
            "data": b64_data,
            "messageId": "msg-zip-1",
        },
        "subscription": "test-sub",
    }

    response = client.post("/process-event", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "skipped"
    assert "Unsupported extension .zip" in data["reason"]


def test_process_event_malformed_base64():
    payload = {
        "message": {
            "data": "!!!INVALID_BASE64_PAYLOAD!!!",
            "messageId": "msg-bad-1",
        },
        "subscription": "test-sub",
    }

    response = client.post("/process-event", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "discarded"


def test_oidc_token_enforcement(sample_pubsub_push_payload, monkeypatch):
    monkeypatch.setattr(settings, "verify_oidc_token", True)

    # Request without Authorization header must fail with 401
    response = client.post("/process-event", json=sample_pubsub_push_payload)
    assert response.status_code == 401
    assert "Missing Bearer token" in response.json()["detail"]
