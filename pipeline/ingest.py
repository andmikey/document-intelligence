"""File validation and preprocessing for the document intelligence pipeline."""

import base64
import io
import os
from pathlib import Path

import fitz  # pymupdf
from PIL import Image


class IngestionError(Exception):
    """Raised when file validation or preprocessing fails."""

    pass


def validate_file(file) -> None:
    """Validate uploaded file type, size, and integrity.

    Args:
        file: Uploaded file object (Streamlit UploadedFile or file-like)

    Raises:
        IngestionError: If validation fails
    """
    # Get file extension
    if hasattr(file, "name"):
        filename = file.name
    else:
        raise IngestionError("Invalid file object")

    ext = Path(filename).suffix.lower()

    # Check extension
    allowed_extensions = {".pdf", ".png", ".jpg", ".jpeg"}
    if ext not in allowed_extensions:
        raise IngestionError(
            f"Unsupported file type: {ext}. Supported types: PDF, PNG, JPG, JPEG"
        )

    # Get MAX_FILE_SIZE_MB from environment, default to 10
    max_size_mb = float(os.getenv("MAX_FILE_SIZE_MB", "10"))
    max_size_bytes = max_size_mb * 1024 * 1024

    # Check file size
    file.seek(0, 2)  # Seek to end
    file_size = file.tell()
    file.seek(0)  # Reset to beginning

    if file_size > max_size_bytes:
        raise IngestionError(
            f"File too large: {file_size / 1024 / 1024:.1f}MB. "
            f"Maximum size: {max_size_mb}MB"
        )

    # Check file integrity based on type
    file_bytes = file.read()
    file.seek(0)  # Reset for subsequent reads

    if ext == ".pdf":
        try:
            # Attempt to open PDF
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            if len(doc) == 0:
                raise IngestionError("PDF file is empty")
            doc.close()
        except Exception as e:
            if isinstance(e, IngestionError):
                raise
            raise IngestionError(f"Corrupt or invalid PDF file: {str(e)}")
    else:
        # Image file (PNG, JPG, JPEG)
        try:
            img = Image.open(io.BytesIO(file_bytes))
            img.verify()  # Verify it's a valid image
        except Exception as e:
            raise IngestionError(f"Corrupt or invalid image file: {str(e)}")


def prepare_image(file) -> str:
    """Convert file to base64-encoded JPEG ready for LLM.

    Args:
        file: Validated file object

    Returns:
        Base64-encoded JPEG string
    """
    file.seek(0)
    file_bytes = file.read()
    file.seek(0)

    # Determine file type
    if hasattr(file, "name"):
        filename = file.name
    else:
        raise IngestionError("Invalid file object")

    ext = Path(filename).suffix.lower()

    # Convert to PIL Image
    if ext == ".pdf":
        # Render first page to image at 150dpi
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        page = doc[0]
        pix = page.get_pixmap(dpi=150)
        img_bytes = pix.tobytes("png")
        img = Image.open(io.BytesIO(img_bytes))
        doc.close()
    else:
        # Open image directly
        img = Image.open(io.BytesIO(file_bytes))

    # Resize to max 1568px on longest side (Gemini recommended max)
    max_dimension = 1568
    width, height = img.size
    if width > max_dimension or height > max_dimension:
        if width > height:
            new_width = max_dimension
            new_height = int(height * (max_dimension / width))
        else:
            new_height = max_dimension
            new_width = int(width * (max_dimension / height))
        img = img.resize((new_width, new_height), Image.LANCZOS)

    # Convert to RGB if necessary (for transparency in PNG)
    if img.mode in ("RGBA", "LA", "P"):
        background = Image.new("RGB", img.size, (255, 255, 255))
        if img.mode == "P":
            img = img.convert("RGBA")
        background.paste(
            img, mask=img.split()[-1] if img.mode in ("RGBA", "LA") else None
        )
        img = background
    elif img.mode != "RGB":
        img = img.convert("RGB")

    # Convert to JPEG with quality=85 and base64 encode
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=85)
    img_bytes = buffer.getvalue()

    return base64.b64encode(img_bytes).decode("utf-8")
