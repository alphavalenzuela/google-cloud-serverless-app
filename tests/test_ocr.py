"""Unit tests for the OCR engine layer."""

import pytest
from src.services.ocr_engine import SimulatedOCREngine, get_ocr_engine


def test_ocr_engine_factory():
    engine = get_ocr_engine("simulated")
    assert isinstance(engine, SimulatedOCREngine)


def test_simulated_ocr_plain_text():
    engine = SimulatedOCREngine()
    sample_text = "The quick brown fox jumps over the lazy dog."
    result = engine.process(
        file_bytes=sample_text.encode("utf-8"),
        filename="notes.txt",
        content_type="text/plain",
    )

    assert result.text == sample_text
    assert result.word_count == 9
    assert "general-document" in result.tags
    assert result.ocr_engine == "simulated"


def test_simulated_ocr_invoice_keywords():
    engine = SimulatedOCREngine()
    result = engine.process(
        file_bytes=b"dummy-binary-bytes",
        filename="vendor_invoice_2026.pdf",
        content_type="application/pdf",
    )

    assert result.word_count > 0
    assert "finance" in result.tags
    assert "invoice" in result.tags
    assert "SIMULATED OCR DOCUMENT" in result.text


def test_simulated_ocr_contract_keywords():
    engine = SimulatedOCREngine()
    result = engine.process(
        file_bytes=b"dummy-binary-bytes",
        filename="service_contract_final.pdf",
        content_type="application/pdf",
    )

    assert "legal" in result.tags
    assert "contract" in result.tags


def test_simulated_ocr_fallback():
    engine = SimulatedOCREngine()
    result = engine.process(
        file_bytes=b"sample",
        filename="unclassified_doc.png",
        content_type="image/png",
    )

    assert result.word_count > 0
    assert "general-document" in result.tags
