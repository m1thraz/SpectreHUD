"""Image embedding budgets and media encoding for HTML reports."""

import base64
import mimetypes
from pathlib import Path
from typing import Optional

from core.logger import get_logger
from core.reporting.styles import (
    REPORT_BASE_CSS,
    REPORT_CSS,
    REPORT_LIGHT_CSS,
    REPORT_PRINT_CSS,
    get_report_css,
)

__all__ = [
    "ImageEmbeddingBudget",
    "MAX_EMBEDDED_IMAGES",
    "MAX_EMBED_IMAGE_FILE_SIZE",
    "MAX_TOTAL_IMAGE_BYTES",
    "REPORT_BASE_CSS",
    "REPORT_CSS",
    "REPORT_LIGHT_CSS",
    "REPORT_PRINT_CSS",
    "encode_image_base64",
    "get_report_css",
]

logger = get_logger(__name__)

MAX_EMBED_IMAGE_FILE_SIZE: int = 15 * 1024 * 1024  # 15 MB per image
MAX_EMBEDDED_IMAGES: int = 25
MAX_TOTAL_IMAGE_BYTES: int = 50 * 1024 * 1024  # 50 MB total session budget


class ImageEmbeddingBudget:
    """Tracks and enforces global image count and memory limits during HTML export."""

    def __init__(
        self, max_images: int = MAX_EMBEDDED_IMAGES, max_total_bytes: int = MAX_TOTAL_IMAGE_BYTES
    ):
        self.max_images = max_images
        self.max_total_bytes = max_total_bytes
        self.embedded_count: int = 0
        self.embedded_bytes: int = 0

    def can_embed(self, file_size: int) -> bool:
        if self.embedded_count >= self.max_images:
            return False
        if self.embedded_bytes + file_size > self.max_total_bytes:
            return False
        return True

    def record(self, file_size: int) -> None:
        self.embedded_count += 1
        self.embedded_bytes += file_size


def encode_image_base64(image_path: Path) -> Optional[str]:
    """Encodes an image file to a base64 data URI."""
    try:
        if not image_path.exists() or not image_path.is_file():
            return None
        if image_path.stat().st_size > MAX_EMBED_IMAGE_FILE_SIZE:
            logger.warning(
                f"Image too large to embed as base64 ({image_path.stat().st_size} bytes): {image_path}"
            )
            return None

        mime_type, _ = mimetypes.guess_type(str(image_path))
        if not mime_type or not mime_type.startswith("image/"):
            mime_type = "image/png"

        img_bytes = image_path.read_bytes()
        b64_str = base64.b64encode(img_bytes).decode("ascii")
        return f"data:{mime_type};base64,{b64_str}"
    except OSError as e:
        logger.warning(f"Failed to read image for base64 embedding {image_path}: {e}")
        return None
