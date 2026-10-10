"""FastAPI application receiving Pub/Sub push events for document OCR and BigQuery ingestion."""

import os
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import FastAPI, Header, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse

from src.config import settings
from src.models import (
    DocumentRecord,
    GCSObjectNotification,
    ProcessingStatus,
    PubSubPushPayload,
)
from src.services.bq_service import BigQueryService
from src.services.gcs_service import GCSService
from src.services.ocr_engine import get_ocr_engine
from src.utils.logger import get_logger

logger = get_logger("app")


# Global service instances
gcs_service = GCSService()
bq_service = BigQueryService()
ocr_engine = get_ocr_engine()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initializes external dependencies on startup."""
    logger.info("Initializing document processing service...")
    try:
        bq_service.ensure_table_exists()
    except Exception as e:
        logger.warning(f"Could not auto-create BigQuery table on startup: {e}")
    yield
    logger.info("Shutting down document processing service...")


app = FastAPI(
    title="Cloud Run Document Processing Pipeline",
    version="1.0.0",
    description="Serverless event-driven document OCR and metadata ingestion to BigQuery",
    lifespan=lifespan,
)


def verify_google_oidc_token(authorization: str | None) -> None:
    """Verifies Google OIDC Bearer token sent by Pub/Sub push subscription."""
    if not settings.verify_oidc_token:
        return

    if not authorization or not authorization.startswith("Bearer "):
        logger.error("Missing or malformed Authorization header in push event")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Bearer token",
        )

    token = authorization.split("Bearer ")[1].strip()
    try:
        from google.auth.transport import requests as auth_requests
        from google.oauth2 import id_token

        request_adapter = auth_requests.Request()
        claim = id_token.verify_oauth2_token(
            token,
            request_adapter,
            audience=settings.oidc_audience or None,
        )
        logger.debug(f"Verified OIDC token for email: {claim.get('email')}")
    except Exception as e:
        logger.error(f"Failed to verify Google OIDC token: {e}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Invalid OIDC token: {e}",
        )


@app.get("/health", status_code=status.HTTP_200_OK)
async def health_check() -> Dict[str, Any]:
    """Liveness and readiness probe for Cloud Run."""
    return {
        "status": "healthy",
        "service": "doc-processor",
        "project": settings.project_id,
        "ocr_engine": settings.ocr_engine,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/process-event", status_code=status.HTTP_200_OK)
async def handle_pubsub_event(
    payload: PubSubPushPayload,
    authorization: str | None = Header(None),
) -> Dict[str, Any]:
    """Receives and processes Pub/Sub push notification triggered by GCS object creation."""
    start_time = time.time()

    # 1. Authenticate request if OIDC enforcement is enabled
    verify_google_oidc_token(authorization)

    # 2. Extract and decode GCS notification data from Pub/Sub envelope
    try:
        notification = GCSObjectNotification.from_pubsub_data(payload.message.data)
        logger.info(
            f"Received event for object: {notification.bucket}/{notification.name} (generation {notification.generation})"
        )
    except Exception as e:
        logger.error(f"Malformed Pub/Sub message data: {e}")
        # Return 200 to acknowledge and discard permanently malformed messages without endless retries
        return {"status": "discarded", "reason": f"Malformed payload: {e}"}

    file_name = notification.name
    _, ext = os.path.splitext(file_name)
    ext = ext.lower()

    # Parse creation timestamp
    created_at = datetime.now(timezone.utc)
    if notification.timeCreated:
        try:
            created_at = datetime.fromisoformat(notification.timeCreated.replace("Z", "+00:00"))
        except Exception:
            pass

    doc_id = f"{notification.bucket}/{notification.name}#{notification.generation or '0'}"

    # 3. Check for unsupported file types (Graceful Skip)
    if ext not in settings.allowed_extensions:
        logger.warning(
            f"File {file_name} with extension '{ext}' is not in allowed extensions list. Skipping OCR."
        )
        skipped_record = DocumentRecord(
            document_id=doc_id,
            filename=file_name,
            bucket=notification.bucket,
            content_type=notification.contentType,
            size_bytes=notification.size,
            created_at=created_at,
            word_count=0,
            tags=["skipped", "unsupported-extension"],
            text_snippet=None,
            ocr_engine=settings.ocr_engine,
            processing_time_ms=int((time.time() - start_time) * 1000),
            status=ProcessingStatus.SKIPPED,
        )
        bq_service.insert_record(skipped_record)
        return {
            "status": "skipped",
            "document_id": doc_id,
            "reason": f"Unsupported extension {ext}",
        }

    # 4. Fetch blob content from Cloud Storage
    try:
        file_bytes, gcs_meta = gcs_service.download_blob_bytes(
            bucket_name=notification.bucket,
            blob_name=notification.name,
            max_bytes=settings.max_file_size_bytes,
        )
    except FileNotFoundError as e:
        logger.error(f"GCS object not found: {e}")
        # Acknowledge 200 so missing files do not loop infinitely
        return {"status": "error", "reason": "Blob not found in GCS"}
    except ValueError as e:
        logger.error(f"File size exceeded limit: {e}")
        # Record failure and acknowledge
        failed_record = DocumentRecord(
            document_id=doc_id,
            filename=file_name,
            bucket=notification.bucket,
            content_type=notification.contentType,
            size_bytes=notification.size,
            created_at=created_at,
            word_count=0,
            tags=["failed", "oversized"],
            ocr_engine=settings.ocr_engine,
            processing_time_ms=int((time.time() - start_time) * 1000),
            status=ProcessingStatus.FAILED,
            error_message=str(e),
        )
        bq_service.insert_record(failed_record)
        return {"status": "failed", "document_id": doc_id, "reason": str(e)}
    except Exception as e:
        logger.error(f"Transient error downloading blob: {e}")
        # Returning 500 signals Pub/Sub to retry with backoff, eventually routing to DLQ
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Transient GCS error: {e}",
        )

    # 5. Execute OCR Extraction
    try:
        ocr_result = ocr_engine.process(
            file_bytes=file_bytes,
            filename=file_name,
            content_type=notification.contentType,
        )
    except Exception as e:
        logger.error(f"OCR processing exception: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"OCR engine failure: {e}",
        )

    # 6. Stream metadata into BigQuery
    elapsed_ms = int((time.time() - start_time) * 1000)
    record = DocumentRecord(
        document_id=doc_id,
        filename=file_name,
        bucket=notification.bucket,
        content_type=notification.contentType,
        size_bytes=notification.size or len(file_bytes),
        created_at=created_at,
        word_count=ocr_result.word_count,
        tags=ocr_result.tags,
        text_snippet=ocr_result.text[:500],
        ocr_engine=ocr_result.ocr_engine,
        processing_time_ms=elapsed_ms,
        status=ProcessingStatus.SUCCESS,
    )

    try:
        bq_service.insert_record(record)
    except Exception as e:
        logger.error(f"BigQuery ingestion failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"BigQuery ingestion error: {e}",
        )

    logger.info(
        f"Pipeline successfully processed {doc_id} in {elapsed_ms}ms ({record.word_count} words)"
    )

    return {
        "status": "success",
        "document_id": record.document_id,
        "filename": record.filename,
        "word_count": record.word_count,
        "tags": record.tags,
        "processing_time_ms": elapsed_ms,
    }
