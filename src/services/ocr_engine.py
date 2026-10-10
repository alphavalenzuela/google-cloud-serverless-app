"""Extensible OCR Engine layer with Simulated and Cloud Vision adapters."""

import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional

from src.config import settings
from src.utils.logger import get_logger

logger = get_logger("ocr_engine")


@dataclass
class OCRResult:
    """Standardized output from OCR extraction."""
    text: str
    word_count: int
    tags: List[str] = field(default_factory=list)
    confidence: float = 1.0
    ocr_engine: str = "simulated"


class BaseOCREngine(ABC):
    """Abstract base class for OCR document processors."""

    @abstractmethod
    def process(self, file_bytes: bytes, filename: str, content_type: Optional[str] = None) -> OCRResult:
        """Processes document binary and returns extracted OCR text and metadata."""
        pass


class SimulatedOCREngine(BaseOCREngine):
    """Simulated OCR engine that generates realistic metadata and extracted text.

    Supports:
    - Real text decoding for text/markdown files.
    - Domain-aware synthetic text & tagging for PDFs and images based on filename patterns.
    - Word count calculation and automatic tag classification.
    """

    KEYWORD_TAG_MAP = {
        "invoice": ["finance", "billing", "invoice"],
        "receipt": ["finance", "expense", "receipt"],
        "tax": ["finance", "tax", "compliance"],
        "contract": ["legal", "contract", "agreement"],
        "nda": ["legal", "confidentiality", "nda"],
        "report": ["business", "analytics", "report"],
        "resume": ["hr", "recruitment", "resume"],
        "cv": ["hr", "recruitment", "cv"],
        "medical": ["healthcare", "medical", "clinical"],
        "passport": ["identity", "kyc", "government-id"],
    }

    def process(self, file_bytes: bytes, filename: str, content_type: Optional[str] = None) -> OCRResult:
        start_time = time.time()
        lower_name = filename.lower()

        # If it's a plain text file, extract actual text
        if lower_name.endswith(".txt") or (content_type and "text/plain" in content_type):
            try:
                extracted_text = file_bytes.decode("utf-8", errors="replace").strip()
            except Exception:
                extracted_text = f"Decoded binary file: {filename}"
        else:
            # Generate realistic synthetic OCR text based on document type
            extracted_text = self._generate_simulated_text(lower_name, len(file_bytes))

        # Calculate word count
        words = re.findall(r"\b\w+\b", extracted_text)
        word_count = len(words)

        # Extract classification tags
        tags = self._extract_tags(lower_name, extracted_text)

        elapsed_ms = int((time.time() - start_time) * 1000)
        logger.info(
            f"Simulated OCR completed for {filename}: {word_count} words, tags={tags} in {elapsed_ms}ms"
        )

        return OCRResult(
            text=extracted_text,
            word_count=word_count,
            tags=tags,
            confidence=0.98,
            ocr_engine="simulated",
        )

    def _generate_simulated_text(self, filename: str, byte_size: int) -> str:
        for keyword, tags in self.KEYWORD_TAG_MAP.items():
            if keyword in filename:
                return (
                    f"SIMULATED OCR DOCUMENT [{tags[0].upper()}]: File {filename}. "
                    f"Total bytes: {byte_size}. Contains authorized transaction, "
                    f"parties, terms, and date records."
                )

        return (
            f"SIMULATED OCR EXTRACT: Document {filename} processed successfully. "
            f"Extracted general content stream with size {byte_size} bytes."
        )

    def _extract_tags(self, filename: str, text: str) -> List[str]:
        tags = set()
        search_target = f"{filename} {text}".lower()

        for keyword, mapped_tags in self.KEYWORD_TAG_MAP.items():
            if keyword in search_target:
                tags.update(mapped_tags)

        # Default fallback tag
        if not tags:
            tags.add("general-document")

        return sorted(list(tags))


class VisionApiOCREngine(BaseOCREngine):
    """Google Cloud Vision API OCR adapter.

    Connects to google-cloud-vision when credentials and API are configured.
    """

    def process(self, file_bytes: bytes, filename: str, content_type: Optional[str] = None) -> OCRResult:
        try:
            from google.cloud import vision
            client = vision.ImageAnnotatorClient()
            image = vision.Image(content=file_bytes)
            response = client.document_text_detection(image=image)

            if response.error.message:
                raise RuntimeError(f"Vision API error: {response.error.message}")

            text = response.full_text_annotation.text if response.full_text_annotation else ""
            words = re.findall(r"\b\w+\b", text)

            return OCRResult(
                text=text,
                word_count=len(words),
                tags=["vision-api-ocr"],
                confidence=0.95,
                ocr_engine="vision_api",
            )
        except Exception as e:
            logger.error(f"Vision API processing failed: {e}. Falling back to simulated engine.")
            return SimulatedOCREngine().process(file_bytes, filename, content_type)


def get_ocr_engine(engine_name: Optional[str] = None) -> BaseOCREngine:
    """Factory helper to obtain the configured OCR engine instance."""
    name = (engine_name or settings.ocr_engine).lower()
    if name == "vision_api":
        return VisionApiOCREngine()
    return SimulatedOCREngine()
