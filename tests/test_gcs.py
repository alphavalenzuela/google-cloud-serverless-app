"""Unit tests for Google Cloud Storage service."""

import pytest
from src.services.gcs_service import GCSService


def test_gcs_service_mock_download():
    gcs = GCSService()
    content, meta = gcs.download_blob_bytes("test-bucket", "invoices/inv-01.pdf")

    assert isinstance(content, bytes)
    assert len(content) > 0
    assert "inv-01.pdf" in content.decode("utf-8")
    assert meta["content_type"] == "text/plain"
