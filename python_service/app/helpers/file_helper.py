"""Upload file validation helpers."""

from __future__ import annotations

from pathlib import Path

from app.exceptions.agent_exceptions import POFileInvalidError, POFileTooLargeError

ALLOWED_MIME_TYPES = {
    "application/pdf": {"pdf"},
    "image/png": {"png"},
    "image/jpeg": {"jpg", "jpeg"},
    "image/tiff": {"tif", "tiff"},
}


def validate_po_file(file_name: str | None, size: int, allowed_extensions: set[str], max_size_bytes: int) -> None:
    """Validate extension and size of an uploaded purchase order file."""
    if size > max_size_bytes:
        raise POFileTooLargeError(
            details={
                "max_size_bytes": max_size_bytes,
                "received_bytes": size,
            }
        )

    if not file_name:
        raise POFileInvalidError(details={"reason": "missing file name"})

    ext = Path(file_name).suffix.lstrip(".").lower() or ""
    if ext not in allowed_extensions:
        raise POFileInvalidError(
            details={
                "reason": "unsupported file extension",
                "extension": ext,
                "allowed": sorted(allowed_extensions),
            }
        )


def guess_mime_type(file_name: str) -> str:
    ext = Path(file_name).suffix.lstrip(".").lower()
    for mime, exts in ALLOWED_MIME_TYPES.items():
        if ext in exts:
            return mime
    return "application/octet-stream"
