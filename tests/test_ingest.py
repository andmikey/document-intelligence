"""Unit tests for file ingestion and validation."""

import io
import os
from pathlib import Path

import fitz
import pytest
from PIL import Image

from pipeline.ingest import IngestionError, prepare_image, validate_file

# Test fixtures


class MockFile:
    """Mock file object for testing."""

    def __init__(self, name: str, content: bytes):
        self.name = name
        self.content = content
        self.position = 0

    def read(self, size: int = -1) -> bytes:
        if size == -1:
            result = self.content[self.position :]
            self.position = len(self.content)
        else:
            result = self.content[self.position : self.position + size]
            self.position += len(result)
        return result

    def seek(self, position: int, whence: int = 0) -> int:
        if whence == 0:  # Absolute
            self.position = position
        elif whence == 1:  # Relative
            self.position += position
        elif whence == 2:  # From end
            self.position = len(self.content) + position
        return self.position

    def tell(self) -> int:
        return self.position


def create_valid_png() -> bytes:
    """Create a valid PNG image in memory."""
    img = Image.new("RGB", (100, 100), color="red")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()


def create_valid_pdf() -> bytes:
    """Create a valid single-page PDF in memory."""
    doc = fitz.open()
    page = doc.new_page(width=200, height=200)
    page.insert_text((50, 50), "Test PDF")
    buffer = io.BytesIO()
    doc.save(buffer)
    doc.close()
    return buffer.getvalue()


# Tests


def test_rejects_unsupported_filetype():
    """Test that .docx files are rejected."""
    file = MockFile("document.docx", b"fake docx content")
    with pytest.raises(IngestionError) as exc_info:
        validate_file(file)
    assert "Unsupported file type" in str(exc_info.value)


def test_rejects_oversized_file(monkeypatch):
    """Test that files exceeding MAX_FILE_SIZE_MB are rejected."""
    # Set a small max size for testing
    monkeypatch.setenv("MAX_FILE_SIZE_MB", "0.001")  # 1KB

    # Create a file larger than 1KB
    large_content = b"x" * 2000  # 2KB
    file = MockFile("large.png", large_content)

    with pytest.raises(IngestionError) as exc_info:
        validate_file(file)
    assert "File too large" in str(exc_info.value)


def test_rejects_corrupt_image():
    """Test that corrupt PNG files are rejected."""
    # Create a file that claims to be PNG but has invalid content
    corrupt_png = b"\x89PNG\r\n\x1a\n" + b"corrupted data"
    file = MockFile("corrupt.png", corrupt_png)

    with pytest.raises(IngestionError) as exc_info:
        validate_file(file)
    assert "Corrupt or invalid image file" in str(exc_info.value)


def test_rejects_corrupt_pdf():
    """Test that corrupt PDF files are rejected."""
    # Create a file that claims to be PDF but has invalid content
    corrupt_pdf = b"%PDF-1.4\ncorrupted data"
    file = MockFile("corrupt.pdf", corrupt_pdf)

    with pytest.raises(IngestionError) as exc_info:
        validate_file(file)
    assert "Corrupt or invalid PDF file" in str(exc_info.value)


def test_valid_png_returns_base64():
    """Test that valid PNG files are converted to base64."""
    png_bytes = create_valid_png()
    file = MockFile("valid.png", png_bytes)

    # Should not raise
    validate_file(file)

    # Should return base64 string
    result = prepare_image(file)
    assert isinstance(result, str)
    assert len(result) > 0
    # Base64 strings are alphanumeric plus +, /, and =
    assert all(
        c in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/="
        for c in result
    )


def test_valid_pdf_returns_base64():
    """Test that valid PDF files are converted to base64."""
    pdf_bytes = create_valid_pdf()
    file = MockFile("valid.pdf", pdf_bytes)

    # Should not raise
    validate_file(file)

    # Should return base64 string
    result = prepare_image(file)
    assert isinstance(result, str)
    assert len(result) > 0
    # Base64 strings are alphanumeric plus +, /, and =
    assert all(
        c in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/="
        for c in result
    )
