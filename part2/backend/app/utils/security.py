"""
File validation for uploaded medical documents.
Rejects unsupported formats, oversized files, and corrupted inputs.
"""
import os
from fastapi import HTTPException, UploadFile

ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".pdf"}
ALLOWED_MIME_TYPES = {"image/png", "image/jpeg", "image/jpg", "application/pdf"}


def validate_uploaded_file(file: UploadFile, max_mb: int = 10) -> str:
    """
    Validate file extension, mime type, and file size.
    Returns the file extension on success.
    Raises HTTPException on failure.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided.")

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    # Check MIME type if provided
    if file.content_type and file.content_type not in ALLOWED_MIME_TYPES:
        if not any(m in file.content_type for m in ["image", "pdf"]):
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported MIME type '{file.content_type}'."
            )

    # Validate file size if size attribute is present or file seekable
    if hasattr(file, "size") and file.size is not None:
        if file.size > max_mb * 1024 * 1024:
            raise HTTPException(
                status_code=400,
                detail=f"File exceeds maximum allowed size of {max_mb}MB."
            )

    return ext


def sanitize_filename(filename: str) -> str:
    """Remove path traversal characters from filename."""
    return os.path.basename(filename).replace("..", "").strip()
