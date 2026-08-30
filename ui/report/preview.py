"""Preview widgets and project-local image resolution for reports."""

import urllib.parse
from pathlib import Path
from typing import Dict, Optional

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QImage, QTextDocument
from PyQt6.QtWidgets import QTextEdit, QWidget

from core.logger import get_logger

logger = get_logger(__name__)

MAX_PREVIEW_IMAGE_FILE_SIZE = 15 * 1024 * 1024


class ReportPreviewEdit(QTextEdit):
    """Editable live preview that rejects direct image insertion."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setAcceptDrops(False)

    def insertFromMimeData(self, source):
        if source and (
            source.hasImage()
            or (
                source.hasUrls()
                and any(
                    url.toLocalFile().lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp"))
                    for url in source.urls()
                )
            )
        ):
            logger.warning("Blocked raw image paste/drop into editable preview document.")
            return
        super().insertFromMimeData(source)


class ReportDocument(QTextDocument):
    """Resolves report images only from the active project directory."""

    def __init__(self, project_dir: Optional[Path] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.project_dir = Path(project_dir) if project_dir else None
        self._image_cache: Dict[str, QImage] = {}

    def set_project_dir(self, project_dir: Optional[Path]) -> None:
        new_dir = Path(project_dir) if project_dir else None
        if self.project_dir == new_dir:
            return
        self.project_dir = new_dir
        self._image_cache.clear()
        if self.project_dir and self.project_dir.exists():
            try:
                self.setBaseUrl(QUrl.fromLocalFile(str(self.project_dir.resolve()) + "/"))
            except OSError:
                pass

    def loadResource(self, resource_type: int, name: QUrl):
        if resource_type != int(QTextDocument.ResourceType.ImageResource) and resource_type != 2:
            return super().loadResource(resource_type, name)

        url_str = name.toString() if hasattr(name, "toString") else str(name)
        if url_str in self._image_cache:
            return self._image_cache[url_str]
        if not self.project_dir:
            return super().loadResource(resource_type, name)

        try:
            project_root = self.project_dir.resolve()
        except (OSError, RuntimeError) as exc:
            logger.warning("Could not resolve project directory: %s", exc)
            return super().loadResource(resource_type, name)

        clean_path = urllib.parse.unquote(url_str).strip()
        if clean_path.startswith("file:///"):
            clean_path = clean_path[8:]
        elif clean_path.startswith("file://"):
            clean_path = clean_path[7:]

        path = Path(clean_path)
        candidates = [path] if path.is_absolute() else [self.project_dir / path, self.project_dir / "loot" / path.name]
        for candidate in candidates:
            try:
                resolved = candidate.resolve()
            except (OSError, RuntimeError):
                continue
            try:
                if not resolved.is_relative_to(project_root):
                    continue
            except (ValueError, AttributeError):
                continue
            if not resolved.exists() or not resolved.is_file():
                continue
            try:
                if resolved.stat().st_size > MAX_PREVIEW_IMAGE_FILE_SIZE or resolved.stat().st_size == 0:
                    continue
            except OSError:
                continue

            image = QImage(str(resolved))
            if image.isNull():
                continue
            if image.width() > 1400:
                image = image.scaledToWidth(1400, Qt.TransformationMode.SmoothTransformation)
            self._image_cache[url_str] = image
            return image

        return super().loadResource(resource_type, name)
