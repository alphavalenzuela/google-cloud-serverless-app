"""Google Cloud Storage client service for downloading and inspecting blobs."""

from typing import Dict, Optional, Tuple
from google.cloud import storage
from google.cloud.exceptions import NotFound

from src.config import settings
from src.utils.logger import get_logger

logger = get_logger("gcs_service")


class GCSService:
    """Service for interacting with Google Cloud Storage."""

    def __init__(self, client: Optional[storage.Client] = None):
        """Initializes GCS client. If offline/mock mode is active, client is initialized lazily."""
        self._client = client
        self._attempted_init = False

    @property
    def client(self) -> Optional[storage.Client]:
        if self._client is None and not self._attempted_init and not settings.mock_gcp_clients:
            self._attempted_init = True
            try:
                self._client = storage.Client(project=settings.project_id)
            except Exception as e:
                logger.warning(f"Could not initialize real GCS client, falling back to mock mode: {e}")
        return self._client

    def download_blob_bytes(
        self, bucket_name: str, blob_name: str, max_bytes: Optional[int] = None
    ) -> Tuple[bytes, Dict[str, str]]:
        """Downloads the binary content of a GCS blob and returns (bytes, metadata).

        Raises:
            FileNotFoundError: If the blob does not exist.
            ValueError: If the file size exceeds max_bytes.
        """
        max_bytes = max_bytes or settings.max_file_size_bytes

        # If running in mock / local test mode without GCP credentials
        if self.client is None or settings.mock_gcp_clients:
            logger.info(f"[MOCK GCS] Simulated download of {bucket_name}/{blob_name}")
            mock_content = f"Simulated content for document {blob_name} uploaded to {bucket_name}.".encode("utf-8")
            return mock_content, {"content_type": "text/plain", "size": str(len(mock_content))}

        try:
            bucket = self.client.bucket(bucket_name)
            blob = bucket.get_blob(blob_name)

            if blob is None:
                raise FileNotFoundError(f"Blob {blob_name} was not found in bucket {bucket_name}.")

            if blob.size and blob.size > max_bytes:
                raise ValueError(
                    f"File size ({blob.size} bytes) exceeds configured limit ({max_bytes} bytes)."
                )

            data = blob.download_as_bytes()
            metadata = {
                "content_type": blob.content_type or "application/octet-stream",
                "size": str(blob.size or len(data)),
                "generation": str(blob.generation or "0"),
                "md5_hash": blob.md5_hash or "",
            }
            return data, metadata

        except NotFound as e:
            raise FileNotFoundError(f"Bucket or blob not found: {e}") from e
