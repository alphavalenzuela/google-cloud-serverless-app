"""Data models and validation schemas for Pub/Sub events, GCS objects, and BigQuery records."""

import base64
import json
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class ProcessingStatus(str, Enum):
    """Execution status for a document processing attempt."""
    SUCCESS = "SUCCESS"
    SKIPPED = "SKIPPED"
    FAILED = "FAILED"


class PubSubMessage(BaseModel):
    """The Pub/Sub message envelope delivered in a push subscription."""
    data: str = Field(..., description="Base64-encoded payload data")
    attributes: Dict[str, str] = Field(default_factory=dict, description="Custom message attributes")
    messageId: str = Field(default="", description="Pub/Sub unique message ID")
    publishTime: str = Field(default="", description="Timestamp when message was published")


class PubSubPushPayload(BaseModel):
    """Top-level push payload delivered to the Cloud Run HTTP endpoint by Pub/Sub."""
    message: PubSubMessage
    subscription: str = Field(default="", description="The Pub/Sub subscription name")


class GCSObjectNotification(BaseModel):
    """Parsed GCS OBJECT_FINALIZE event payload contained in the Pub/Sub message data."""
    bucket: str = Field(..., description="GCS bucket name")
    name: str = Field(..., description="Object name / path inside the bucket")
    contentType: Optional[str] = Field(default="application/octet-stream", description="MIME content type")
    size: int = Field(default=0, description="File size in bytes")
    generation: Optional[str] = Field(default="0", description="GCS object generation number")
    metageneration: Optional[str] = Field(default="1", description="GCS object metageneration number")
    timeCreated: Optional[str] = Field(default=None, description="ISO timestamp of object creation")
    updated: Optional[str] = Field(default=None, description="ISO timestamp of object update")

    @classmethod
    def from_pubsub_data(cls, b64_data: str) -> "GCSObjectNotification":
        """Decodes and parses base64-encoded GCS notification data."""
        try:
            decoded_bytes = base64.b64decode(b64_data)
            payload_dict = json.loads(decoded_bytes.decode("utf-8"))
            return cls(**payload_dict)
        except Exception as e:
            raise ValueError(f"Failed to decode GCS notification data from base64: {e}") from e


class DocumentRecord(BaseModel):
    """Processed document metadata row targeted for BigQuery ingestion."""
    document_id: str = Field(..., description="Unique idempotent key: {bucket}/{name}#{generation}")
    filename: str = Field(..., description="Object name/path in bucket")
    bucket: str = Field(..., description="Source GCS bucket name")
    content_type: Optional[str] = Field(default="application/octet-stream")
    size_bytes: int = Field(default=0, ge=0)
    created_at: datetime = Field(..., description="GCS object creation timestamp")
    processed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Pipeline completion timestamp"
    )
    word_count: int = Field(default=0, ge=0)
    tags: List[str] = Field(default_factory=list)
    text_snippet: Optional[str] = Field(default=None, description="Excerpt of extracted text")
    ocr_engine: str = Field(default="simulated")
    processing_time_ms: int = Field(default=0, ge=0)
    status: ProcessingStatus = Field(default=ProcessingStatus.SUCCESS)
    error_message: Optional[str] = Field(default=None)

    def to_bigquery_row(self) -> Dict[str, Any]:
        """Converts model to dictionary formatted for BigQuery insertion."""
        return {
            "document_id": self.document_id,
            "filename": self.filename,
            "bucket": self.bucket,
            "content_type": self.content_type,
            "size_bytes": self.size_bytes,
            "created_at": self.created_at.isoformat(),
            "processed_at": self.processed_at.isoformat(),
            "word_count": self.word_count,
            "tags": self.tags,
            "text_snippet": self.text_snippet[:500] if self.text_snippet else None,
            "ocr_engine": self.ocr_engine,
            "processing_time_ms": self.processing_time_ms,
            "status": self.status.value,
        }
